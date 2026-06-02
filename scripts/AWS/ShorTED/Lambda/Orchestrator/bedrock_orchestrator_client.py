"""
Bedrock AI Orchestrator Client for ShorTED.

Invokes Amazon Bedrock Converse API with tool-use (function calling) to
orchestrate the AI snack generation pipeline. The model uses MCP tools
during a multi-turn conversation loop before returning the final JSON.

Model: amazon.nova-lite-v1:0 (cost-effective, strong tool-use, Italian support)
API:   bedrock-runtime.converse (supports toolConfig natively)

Loop behaviour:
  1. Send system prompt + user message → Bedrock
  2. If stopReason == "tool_use":
       → Execute each requested MCP tool
       → Append toolResult to messages
       → Loop (up to MAX_TOOL_LOOPS)
  3. If stopReason == "end_turn":
       → Extract final JSON from text block
       → Parse and return AIResult
  4. If JSON is invalid: attempt one repair call
"""
import json
import logging
import re
from typing import Any

import boto3

from config import BEDROCK_REGION, BEDROCK_MODEL_ID, MAX_TOOL_LOOPS, MAX_REPAIR_ATTEMPTS
from models import AIContext, AIResult, SnackDoc
from mcp_http_client import MCPHttpClient
from prompts.orchestrator_system_prompt import build_system_prompt
from errors import AIOutputInvalidError, MCPServerError

logger = logging.getLogger(__name__)

# Module-level Bedrock client — warm Lambda reuse
_bedrock = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)


def invoke_bedrock_orchestrator(
    ai_ctx: AIContext,
    mcp_server_url: str,
    pipeline_version: str,
) -> AIResult:
    """
    Run the full AI orchestration loop for one talk.

    Args:
        ai_ctx:           AIContext with metadata and transcript.
        mcp_server_url:   URL of the ShorTED MCP server.
        pipeline_version: Current pipeline version string.

    Returns:
        Parsed and typed AIResult.

    Raises:
        AIOutputInvalidError: If the model fails to produce valid JSON
                              even after a repair attempt.
        MCPServerError:       If the MCP server is unreachable.
    """
    mcp = MCPHttpClient(mcp_server_url)
    system_prompt = build_system_prompt(ai_ctx)
    tool_definitions = mcp.get_tool_definitions()

    # Initial user message — brief, since transcript is in system prompt
    user_message = (
        f"Process the talk '{ai_ctx.title}' by {ai_ctx.speaker}. "
        f"Follow the mandatory tool-use sequence defined in your instructions "
        f"and return the final JSON."
    )

    messages = [{"role": "user", "content": [{"text": user_message}]}]
    tools_used: list[str] = []

    try:
        result_text = _run_tool_use_loop(
            system_prompt=system_prompt,
            messages=messages,
            tool_definitions=tool_definitions,
            mcp=mcp,
            tools_used=tools_used,
        )
    except AIOutputInvalidError:
        raise
    except Exception as e:
        raise

    # Parse final JSON
    try:
        ai_result = _parse_ai_output(result_text, ai_ctx, tools_used)
        return ai_result
    except AIOutputInvalidError as e:
        if MAX_REPAIR_ATTEMPTS < 1:
            raise

        logger.warning("Initial output invalid (%s) — attempting repair call", e)
        result_text = _repair_call(
            system_prompt=system_prompt,
            original_output=result_text,
            error_message=str(e),
            tool_definitions=tool_definitions,
            mcp=mcp,
            tools_used=tools_used,
        )
        ai_result = _parse_ai_output(result_text, ai_ctx, tools_used)
        return ai_result


# ── Internal helpers ──────────────────────────────────────────────────────────

def _run_tool_use_loop(
    system_prompt: str,
    messages: list[dict],
    tool_definitions: list[dict],
    mcp: MCPHttpClient,
    tools_used: list[str],
) -> str:
    """
    Run the Bedrock Converse tool-use loop until end_turn or max loops.

    Returns:
        Final text content from the model's last message.

    Raises:
        AIOutputInvalidError: If max loops exceeded or unexpected stopReason.
    """
    for loop_idx in range(MAX_TOOL_LOOPS):
        logger.info("Bedrock loop iteration %d/%d", loop_idx + 1, MAX_TOOL_LOOPS)

        response = _bedrock.converse(
            modelId=BEDROCK_MODEL_ID,
            system=[{"text": system_prompt}],
            messages=messages,
            toolConfig={"tools": tool_definitions},
        )

        stop_reason = response["stopReason"]
        assistant_message = response["output"]["message"]
        messages.append(assistant_message)

        if stop_reason == "end_turn":
            # Extract text from last message
            return _extract_text(assistant_message)

        if stop_reason == "tool_use":
            tool_results = _execute_tool_calls(assistant_message, mcp, tools_used)
            messages.append({"role": "user", "content": tool_results})
            continue

        if stop_reason == "max_tokens":
            raise AIOutputInvalidError(
                "Bedrock hit max_tokens before returning final JSON. "
                "Consider reducing transcript length or increasing max_tokens."
            )

        raise AIOutputInvalidError(f"Unexpected Bedrock stopReason: {stop_reason!r}")

    raise AIOutputInvalidError(
        f"Exceeded maximum tool-use loops ({MAX_TOOL_LOOPS}). "
        "Model did not return end_turn in time."
    )


def _execute_tool_calls(
    assistant_message: dict,
    mcp: MCPHttpClient,
    tools_used: list[str],
) -> list[dict]:
    """
    Execute all tool_use requests from one Bedrock response.

    Returns:
        List of toolResult content blocks for the next message.
    """
    tool_results = []
    for block in assistant_message.get("content", []):
        if "toolUse" not in block:
            continue

        tool_use = block["toolUse"]
        tool_name = tool_use["name"]
        tool_input = tool_use.get("input", {})
        tool_use_id = tool_use["toolUseId"]

        logger.info("Executing MCP tool: %s", tool_name)
        if tool_name not in tools_used:
            tools_used.append(tool_name)

        try:
            result = mcp.call_tool(tool_name, tool_input)
            result_text = json.dumps(result, ensure_ascii=False)
            tool_results.append({
                "toolResult": {
                    "toolUseId": tool_use_id,
                    "content": [{"text": result_text}],
                    "status": "success",
                }
            })
        except MCPServerError as e:
            logger.error("MCP tool '%s' failed: %s", tool_name, e)
            tool_results.append({
                "toolResult": {
                    "toolUseId": tool_use_id,
                    "content": [{"text": f"Tool error: {e}"}],
                    "status": "error",
                }
            })

    return tool_results


def _repair_call(
    system_prompt: str,
    original_output: str,
    error_message: str,
    tool_definitions: list[dict],
    mcp: MCPHttpClient,
    tools_used: list[str],
) -> str:
    """
    Send a repair message to the model asking it to fix the invalid output.
    """
    repair_message = (
        f"Your previous output was invalid:\n\n"
        f"ERROR: {error_message}\n\n"
        f"ORIGINAL OUTPUT:\n{original_output[:3000]}\n\n"
        f"Please fix all errors and return ONLY the corrected valid JSON. "
        f"No markdown. No explanation."
    )
    messages = [
        {"role": "user", "content": [{"text": "Process the talk and return final JSON."}]},
        {"role": "assistant", "content": [{"text": original_output}]},
        {"role": "user", "content": [{"text": repair_message}]},
    ]
    return _run_tool_use_loop(system_prompt, messages, tool_definitions, mcp, tools_used)


def _extract_text(message: dict) -> str:
    """Extract concatenated text from all text blocks in a message."""
    parts = []
    for block in message.get("content", []):
        if "text" in block:
            parts.append(block["text"])
    return "\n".join(parts)


def _parse_ai_output(text: str, ai_ctx: AIContext, tools_used: list[str]) -> AIResult:
    """
    Parse the model's text output into a typed AIResult.

    Handles cases where the model wraps JSON in markdown code blocks.

    Raises:
        AIOutputInvalidError: If JSON cannot be parsed or structure is invalid.
    """
    # Try to extract JSON from markdown code fences if present
    fence_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    json_text = fence_match.group(1) if fence_match else text

    # Fallback: find first { ... } span
    if not fence_match:
        brace_match = re.search(r'\{.*\}', json_text, re.DOTALL)
        if brace_match:
            json_text = brace_match.group(0)

    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as e:
        raise AIOutputInvalidError(f"Cannot parse JSON from model output: {e}\nText: {text[:500]}")

    if not isinstance(data, dict):
        raise AIOutputInvalidError(f"Model output root must be a JSON object, got {type(data)}")

    if "final_snacks" not in data:
        raise AIOutputInvalidError("Model output missing 'final_snacks' key")

    if not isinstance(data["final_snacks"], list):
        raise AIOutputInvalidError("'final_snacks' must be a list")

    # Parse snacks
    snack_docs: list[SnackDoc] = []
    for i, s in enumerate(data["final_snacks"]):
        if not isinstance(s, dict):
            raise AIOutputInvalidError(f"final_snacks[{i}] is not a dict")
        try:
            snack_docs.append(SnackDoc(
                segment_id=s.get("segmentId", ""),
                talk_id=s.get("talkId", ai_ctx.talk_id),
                talk_slug=s.get("talkSlug", ai_ctx.slug),
                speaker=s.get("speaker", ai_ctx.speaker),
                talk_title=s.get("talkTitle", ai_ctx.title),
                topic=s.get("topic", ""),
                quote=s.get("quote", ""),
                motivationalText=s.get("motivationalText", ""),
                aphorism=s.get("aphorism", ""),
                tags=s.get("tags", []),
                score=float(s.get("score", 0.0)),
                start_time=int(s.get("startTime", 0)),
                end_time=int(s.get("endTime", 0)),
                talk_url=s.get("talkUrl", ""),
                language=s.get("language", ai_ctx.language),
            ))
        except (TypeError, ValueError) as e:
            raise AIOutputInvalidError(f"Cannot parse final_snacks[{i}]: {e}")

    # Build processing report with tools_used merged in
    report = data.get("processing_report", {})
    if isinstance(report, dict):
        # Ensure mcpToolsUsed reflects actual calls, not just what model reported
        report["mcpToolsUsed"] = list(set(tools_used + report.get("mcpToolsUsed", [])))

    return AIResult(
        talk=data.get("talk", {}),
        final_snacks=snack_docs,
        processing_report=report,
    )
