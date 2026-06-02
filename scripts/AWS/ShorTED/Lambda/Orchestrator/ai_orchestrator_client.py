"""
Provider-neutral AI Orchestrator client for ShorTED.

Selects the model backend via AI_PROVIDER:
  - bedrock: existing AWS Bedrock Converse implementation
  - openai:  OpenAI Responses API with function calling
  - ollama:  Ollama /api/chat with native tool calls
"""
import json
import logging
import os
from typing import Any

import requests

from config import (
    AI_PROVIDER,
    MAX_REPAIR_ATTEMPTS,
    MAX_TOOL_LOOPS,
    MCP_TIMEOUT_SECONDS,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OLLAMA_TIMEOUT_SECONDS,
    OPENAI_BASE_URL,
    OPENAI_MAX_OUTPUT_TOKENS,
    OPENAI_MODEL,
    OPENAI_TIMEOUT_SECONDS,
)
from models import AIContext, AIResult
from mcp_http_client import MCPHttpClient
from prompts.orchestrator_system_prompt import build_system_prompt
from errors import AIOutputInvalidError, MCPServerError

from bedrock_orchestrator_client import (
    invoke_bedrock_orchestrator,
    _parse_ai_output,
)

logger = logging.getLogger(__name__)


def invoke_ai_orchestrator(
    ai_ctx: AIContext,
    mcp_server_url: str,
    pipeline_version: str,
) -> AIResult:
    """Invoke the configured AI provider."""
    provider = AI_PROVIDER.lower()
    if provider == "bedrock":
        return invoke_bedrock_orchestrator(ai_ctx, mcp_server_url, pipeline_version)
    if provider == "openai":
        return invoke_openai_orchestrator(ai_ctx, mcp_server_url, pipeline_version)
    if provider == "ollama":
        return invoke_ollama_orchestrator(ai_ctx, mcp_server_url, pipeline_version)
    raise AIOutputInvalidError(
        f"Unsupported AI_PROVIDER={AI_PROVIDER!r}. Use one of: bedrock, openai, ollama."
    )


def invoke_openai_orchestrator(
    ai_ctx: AIContext,
    mcp_server_url: str,
    pipeline_version: str,
) -> AIResult:
    """Run ShorTED orchestration through the OpenAI Responses API."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise AIOutputInvalidError("OPENAI_API_KEY is required when AI_PROVIDER=openai")

    mcp = MCPHttpClient(mcp_server_url, timeout=MCP_TIMEOUT_SECONDS)
    system_prompt = build_system_prompt(ai_ctx)
    tools = mcp.get_openai_tool_definitions()
    tools_used: list[str] = []
    input_items: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": _initial_user_message(ai_ctx)},
    ]

    result_text = _run_openai_tool_loop(input_items, tools, mcp, tools_used, api_key)
    try:
        return _parse_ai_output(result_text, ai_ctx, tools_used)
    except AIOutputInvalidError as e:
        if MAX_REPAIR_ATTEMPTS < 1:
            raise
        logger.warning("OpenAI output invalid (%s) — attempting repair call", e)
        repair_input = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": _repair_prompt(result_text, str(e))},
        ]
        result_text = _run_openai_tool_loop(repair_input, tools, mcp, tools_used, api_key)
        return _parse_ai_output(result_text, ai_ctx, tools_used)


def invoke_ollama_orchestrator(
    ai_ctx: AIContext,
    mcp_server_url: str,
    pipeline_version: str,
) -> AIResult:
    """Run ShorTED orchestration through an Ollama /api/chat endpoint."""
    mcp = MCPHttpClient(mcp_server_url, timeout=MCP_TIMEOUT_SECONDS)
    system_prompt = build_system_prompt(ai_ctx)
    tools = mcp.get_ollama_tool_definitions()
    tools_used: list[str] = []
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": _initial_user_message(ai_ctx)},
    ]

    result_text = _run_ollama_tool_loop(messages, tools, mcp, tools_used)
    try:
        return _parse_ai_output(result_text, ai_ctx, tools_used)
    except AIOutputInvalidError as e:
        if MAX_REPAIR_ATTEMPTS < 1:
            raise
        logger.warning("Ollama output invalid (%s) — attempting repair call", e)
        messages.append({"role": "assistant", "content": result_text})
        messages.append({"role": "user", "content": _repair_prompt(result_text, str(e))})
        result_text = _run_ollama_tool_loop(messages, tools, mcp, tools_used)
        return _parse_ai_output(result_text, ai_ctx, tools_used)


def _run_openai_tool_loop(
    input_items: list[dict],
    tools: list[dict],
    mcp: MCPHttpClient,
    tools_used: list[str],
    api_key: str,
) -> str:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    url = f"{OPENAI_BASE_URL.rstrip('/')}/responses"

    for loop_idx in range(MAX_TOOL_LOOPS):
        logger.info("OpenAI loop iteration %d/%d", loop_idx + 1, MAX_TOOL_LOOPS)
        payload = {
            "model": OPENAI_MODEL,
            "input": input_items,
            "tools": tools,
            "tool_choice": "auto",
            "parallel_tool_calls": False,
            "max_output_tokens": OPENAI_MAX_OUTPUT_TOKENS,
        }
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=OPENAI_TIMEOUT_SECONDS,
        )
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise AIOutputInvalidError(
                f"OpenAI API returned HTTP {response.status_code}: {response.text[:1000]}"
            ) from e

        data = response.json()
        output = data.get("output", [])
        function_calls = [item for item in output if item.get("type") == "function_call"]
        if function_calls:
            input_items.extend(output)
            for call in function_calls:
                input_items.append(_execute_openai_tool_call(call, mcp, tools_used))
            continue

        text = _extract_openai_text(data)
        if text:
            return text

        raise AIOutputInvalidError(f"OpenAI response had no final text and no function calls: {data}")

    raise AIOutputInvalidError(f"Exceeded maximum OpenAI tool-use loops ({MAX_TOOL_LOOPS}).")


def _run_ollama_tool_loop(
    messages: list[dict],
    tools: list[dict],
    mcp: MCPHttpClient,
    tools_used: list[str],
) -> str:
    url = f"{OLLAMA_BASE_URL.rstrip('/')}/api/chat"

    for loop_idx in range(MAX_TOOL_LOOPS):
        logger.info("Ollama loop iteration %d/%d", loop_idx + 1, MAX_TOOL_LOOPS)
        payload = {
            "model": OLLAMA_MODEL,
            "messages": messages,
            "tools": tools,
            "stream": False,
            "format": "json",
        }
        try:
            response = requests.post(url, json=payload, timeout=OLLAMA_TIMEOUT_SECONDS)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise AIOutputInvalidError(f"Ollama request failed at {url}: {e}") from e

        data = response.json()
        message = data.get("message", {})
        tool_calls = message.get("tool_calls") or []
        if tool_calls:
            messages.append(message)
            for call in tool_calls:
                messages.append(_execute_ollama_tool_call(call, mcp, tools_used))
            continue

        content = message.get("content", "")
        if content:
            return content

        raise AIOutputInvalidError(f"Ollama response had no final content and no tool calls: {data}")

    raise AIOutputInvalidError(f"Exceeded maximum Ollama tool-use loops ({MAX_TOOL_LOOPS}).")


def _execute_openai_tool_call(
    call: dict,
    mcp: MCPHttpClient,
    tools_used: list[str],
) -> dict:
    tool_name = call["name"]
    tool_input = _loads_json_object(call.get("arguments", "{}"))
    if tool_name not in tools_used:
        tools_used.append(tool_name)
    logger.info("Executing MCP tool via OpenAI call: %s", tool_name)
    try:
        result = mcp.call_tool(tool_name, tool_input)
        output = json.dumps(result, ensure_ascii=False)
    except MCPServerError as e:
        output = json.dumps({"error": str(e)}, ensure_ascii=False)
    return {
        "type": "function_call_output",
        "call_id": call["call_id"],
        "output": output,
    }


def _execute_ollama_tool_call(
    call: dict,
    mcp: MCPHttpClient,
    tools_used: list[str],
) -> dict:
    function = call.get("function", {})
    tool_name = function.get("name")
    tool_input = function.get("arguments") or {}
    if isinstance(tool_input, str):
        tool_input = _loads_json_object(tool_input)
    if not tool_name:
        raise AIOutputInvalidError(f"Ollama tool call missing function.name: {call}")
    if tool_name not in tools_used:
        tools_used.append(tool_name)
    logger.info("Executing MCP tool via Ollama call: %s", tool_name)
    try:
        result = mcp.call_tool(tool_name, tool_input)
    except MCPServerError as e:
        result = {"error": str(e)}
    return {
        "role": "tool",
        "tool_name": tool_name,
        "content": json.dumps(result, ensure_ascii=False),
    }


def _extract_openai_text(data: dict) -> str:
    if data.get("output_text"):
        return data["output_text"]
    parts: list[str] = []
    for item in data.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") in ("output_text", "text"):
                parts.append(content.get("text", ""))
    return "\n".join(part for part in parts if part)


def _loads_json_object(value: str) -> dict:
    try:
        parsed = json.loads(value or "{}")
    except json.JSONDecodeError as e:
        raise AIOutputInvalidError(f"Tool arguments are not valid JSON: {value}") from e
    if not isinstance(parsed, dict):
        raise AIOutputInvalidError(f"Tool arguments must be a JSON object, got {type(parsed).__name__}")
    return parsed


def _initial_user_message(ai_ctx: AIContext) -> str:
    return (
        f"Process the talk '{ai_ctx.title}' by {ai_ctx.speaker}. "
        "Follow the mandatory tool-use sequence defined in your instructions "
        "and return the final JSON."
    )


def _repair_prompt(original_output: str, error_message: str) -> str:
    return (
        "Your previous output was invalid:\n\n"
        f"ERROR: {error_message}\n\n"
        f"ORIGINAL OUTPUT:\n{original_output[:3000]}\n\n"
        "Please fix all errors and return ONLY the corrected valid JSON. "
        "No markdown. No explanation."
    )
