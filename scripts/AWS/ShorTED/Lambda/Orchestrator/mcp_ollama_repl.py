#!/usr/bin/env python3
"""
Interactive Ollama + MCP tester for the local ShorTED pipeline.

This script is intentionally separate from SQS/Mongo persistence. It lets you
exercise the same MCP tools exposed to Ollama without consuming queue messages.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import requests

from errors import MCPServerError
from mcp_http_client import MCPHttpClient


DEFAULT_SYSTEM_PROMPT = (
    "You are testing the ShorTED MCP tools through Ollama. "
    "Use tools when useful, keep answers concise, and explain any MCP error plainly."
)


def _load_dotenv() -> None:
    env_path = Path(__file__).with_name(".env")
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _compact_json(value: Any, max_chars: int = 4000) -> str:
    text = _json_dumps(value)
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}\n... [truncated {len(text) - max_chars} chars]"


def _parse_json_object(raw: str) -> dict:
    try:
        value = json.loads(raw or "{}")
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON non valido: {e}") from e
    if not isinstance(value, dict):
        raise ValueError("L'input del tool deve essere un oggetto JSON.")
    return value


def _ollama_chat(
    base_url: str,
    model: str,
    messages: list[dict],
    tools: list[dict] | None,
    timeout: int,
) -> dict:
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
    }
    if tools:
        payload["tools"] = tools
    response = requests.post(
        f"{base_url.rstrip('/')}/api/chat",
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def _tool_call_to_message(call: dict, mcp: MCPHttpClient, show_raw: bool) -> dict:
    function = call.get("function", {})
    tool_name = function.get("name")
    tool_input = function.get("arguments") or {}
    if isinstance(tool_input, str):
        tool_input = _parse_json_object(tool_input)
    if not tool_name:
        result = {"error": f"Ollama tool call senza function.name: {call}"}
        return {"role": "tool", "tool_name": "unknown", "content": _json_dumps(result)}

    print(f"\n[MCP] {tool_name}")
    if show_raw:
        print(f"input:\n{_compact_json(tool_input)}")

    try:
        result = mcp.call_tool(tool_name, tool_input)
    except MCPServerError as e:
        result = {"error": str(e)}

    print(f"output:\n{_compact_json(result)}")
    return {
        "role": "tool",
        "tool_name": tool_name,
        "content": json.dumps(result, ensure_ascii=False),
    }


def _print_help() -> None:
    print(
        "\nComandi:\n"
        "  /help                         mostra questa guida\n"
        "  /tools                        lista i tool MCP esposti a Ollama\n"
        "  /call <tool> <json>           chiama direttamente un tool MCP\n"
        "  /reset                        azzera la conversazione Ollama\n"
        "  /exit                         esci\n"
        "\nEsempi:\n"
        "  /call get_snack_schema {}\n"
        "  /call canonicalize_tags {\"tags\":[\"AI Ethics\",\"Personal growth\"]}\n"
    )


def _print_tools(tools: list[dict]) -> None:
    print("")
    for tool in tools:
        function = tool["function"]
        required = function.get("parameters", {}).get("required", [])
        suffix = f" required={required}" if required else ""
        print(f"- {function['name']}: {function.get('description', '')}{suffix}")


def _direct_tool_call(raw: str, mcp: MCPHttpClient) -> None:
    parts = raw.split(maxsplit=2)
    if len(parts) < 2:
        print("Uso: /call <tool> <json>")
        return
    tool_name = parts[1]
    raw_json = parts[2] if len(parts) == 3 else "{}"
    try:
        tool_input = _parse_json_object(raw_json)
        result = mcp.call_tool(tool_name, tool_input)
    except (ValueError, MCPServerError) as e:
        print(f"Errore: {e}")
        return
    print(_compact_json(result))


def run_repl(args: argparse.Namespace) -> int:
    _load_dotenv()
    ollama_base_url = args.ollama_base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model = args.model or os.environ.get("OLLAMA_MODEL", "llama3.1")
    mcp_server_url = args.mcp_server_url or os.environ.get("MCP_SERVER_URL", "http://localhost:8080")

    mcp = MCPHttpClient(mcp_server_url, timeout=args.mcp_timeout)
    tools = [] if args.no_tools else mcp.get_ollama_tool_definitions()
    messages = [{"role": "system", "content": args.system_prompt or DEFAULT_SYSTEM_PROMPT}]

    print(f"Ollama: {ollama_base_url} model={ollama_model}")
    print(f"MCP:    {mcp_server_url}")
    print("Scrivi /help per i comandi. Questo REPL non consuma SQS e non salva su Mongo.")

    while True:
        try:
            user_input = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("")
            return 0

        if not user_input:
            continue
        if user_input in {"/exit", "/quit"}:
            return 0
        if user_input == "/help":
            _print_help()
            continue
        if user_input == "/tools":
            _print_tools(tools)
            continue
        if user_input == "/reset":
            messages = [{"role": "system", "content": args.system_prompt or DEFAULT_SYSTEM_PROMPT}]
            print("Conversazione azzerata.")
            continue
        if user_input.startswith("/call"):
            _direct_tool_call(user_input, mcp)
            continue

        messages.append({"role": "user", "content": user_input})
        for loop_idx in range(args.max_tool_loops):
            try:
                data = _ollama_chat(
                    base_url=ollama_base_url,
                    model=ollama_model,
                    messages=messages,
                    tools=tools,
                    timeout=args.ollama_timeout,
                )
            except requests.exceptions.RequestException as e:
                err_msg = str(e)
                if hasattr(e, "response") and e.response is not None:
                    try:
                        body = e.response.json()
                        if "error" in body:
                            err_msg = f"HTTP {e.response.status_code} - {body['error']}"
                    except Exception:
                        pass
                print(f"Errore Ollama: {err_msg}")
                break

            message = data.get("message", {})
            if args.show_raw:
                print(f"\n[Ollama raw]\n{_compact_json(data)}")

            tool_calls = message.get("tool_calls") or []
            if tool_calls:
                messages.append(message)
                for call in tool_calls:
                    messages.append(_tool_call_to_message(call, mcp, args.show_raw))
                continue

            content = message.get("content") or ""
            messages.append({"role": "assistant", "content": content})
            print(f"\n{content}" if content else "\n[Ollama ha risposto senza testo e senza tool call]")
            break
        else:
            print(f"Interrotto: superato max tool loop ({args.max_tool_loops}).")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="REPL locale per testare Ollama con il server MCP ShorTED.")
    parser.add_argument("--model", help="Modello Ollama. Default: OLLAMA_MODEL o llama3.1")
    parser.add_argument("--ollama-base-url", help="Default: OLLAMA_BASE_URL o http://localhost:11434")
    parser.add_argument("--mcp-server-url", help="Default: MCP_SERVER_URL o http://localhost:8080")
    parser.add_argument("--ollama-timeout", type=int, default=180)
    parser.add_argument("--mcp-timeout", type=int, default=30)
    parser.add_argument("--max-tool-loops", type=int, default=10)
    parser.add_argument("--system-prompt", help="System prompt alternativo per la sessione.")
    parser.add_argument("--no-tools", action="store_true", help="Chat Ollama senza passare tool definitions.")
    parser.add_argument("--show-raw", action="store_true", help="Mostra payload grezzi Ollama e input tool.")
    return parser.parse_args()


if __name__ == "__main__":
    sys.exit(run_repl(parse_args()))
