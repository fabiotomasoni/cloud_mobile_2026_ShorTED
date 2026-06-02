"""
MCP HTTP Client — thin HTTP client for the ShorTED MCP Server.

The Lambda Orchestrator uses this to call MCP tools during the
Bedrock tool-use loop. Implements only what the orchestrator needs:
  - call a tool by name with a JSON payload
  - get the static tool definitions for Bedrock toolConfig

No full MCP protocol SDK required — the MCP server exposes tools via
HTTP endpoints compatible with this thin client.

Note on protocol: FastMCP's streamable_http transport uses JSON-RPC 2.0
over HTTP. This client wraps that protocol.
"""
import json
import logging
from typing import Any

import requests

from errors import MCPServerError

logger = logging.getLogger(__name__)

# Static tool definitions matching the MCP server tools.
# Bedrock toolConfig expects ToolSpec with name, description, inputSchema.
# These must match the actual tools in shorted_mcp_server.py.
BEDROCK_TOOL_DEFINITIONS: list[dict] = [
    {
        "toolSpec": {
            "name": "get_snack_schema",
            "description": "Return the canonical ShorTED snack schema.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "get_mixer_rules",
            "description": "Return numeric rules governing snack count, duration, spacing and field lengths.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "get_grounding_rules",
            "description": "Return quality and grounding rules for generated snacks.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "get_processing_context",
            "description": "Return existing talk/snack metadata for a given talk. Read-only. Use to check if snacks already exist before generation.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "talk_slug": {"type": "string", "description": "Talk slug identifier"},
                        "language": {"type": "string", "description": "Language code (e.g. 'en', 'it')"},
                        "pipeline_version": {"type": "string", "description": "Pipeline version (e.g. 'v1')"},
                    },
                    "required": ["talk_slug", "language", "pipeline_version"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "get_existing_snacks",
            "description": "Return existing snack documents for a talk. Useful for duplicate reference.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "talk_slug": {"type": "string"},
                        "language": {"type": "string"},
                        "limit": {"type": "integer", "default": 20},
                    },
                    "required": ["talk_slug"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "validate_snack_candidate",
            "description": "Validate a single snack candidate against ShorTED schema and business rules. Returns {valid, errors, warnings}.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "snack": {
                            "type": "object",
                            "description": "A snack candidate document to validate",
                        }
                    },
                    "required": ["snack"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "validate_snack_candidates",
            "description": "Validate multiple snack candidates at once. Returns {results: [...]}, one result per snack.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "snacks_list": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "List of snack candidates to validate",
                        }
                    },
                    "required": ["snacks_list"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "validate_final_snack_set",
            "description": "Validate the complete final snack set: count, spacing, no duplicates, schema. Returns {valid, errors, warnings, stats}.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "snacks_list": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "The final selected snack set to validate",
                        }
                    },
                    "required": ["snacks_list"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "find_similar_snacks",
            "description": "Detect near-duplicate snacks using heuristics (topic, quote similarity, time overlap, tag overlap). Returns {intraBatchDuplicates, crossDbDuplicates, hasDuplicates}.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "talk_slug": {"type": "string"},
                        "candidate_snacks": {
                            "type": "array",
                            "items": {"type": "object"},
                        },
                    },
                    "required": ["talk_slug", "candidate_snacks"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "canonicalize_tags",
            "description": "Normalise tags: lowercase, hyphenate, apply alias map, deduplicate, sort. Always use this before setting tags on snacks.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Raw tag strings to normalise",
                        }
                    },
                    "required": ["tags"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "build_talk_url",
            "description": "Build a TED talk URL with a timestamp query parameter. Format: <base_url>?t=<start_time>",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "base_url": {"type": "string", "description": "Base talk URL"},
                        "start_time": {"type": "integer", "description": "Start time in seconds"},
                    },
                    "required": ["base_url", "start_time"],
                }
            },
        }
    },
]


class MCPHttpClient:
    """
    Thin HTTP client for the ShorTED MCP Server.

    Calls MCP tools via HTTP POST using the FastMCP JSON-RPC 2.0 protocol.
    """

    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
        })
        self._call_id = 0

    def call_tool(self, tool_name: str, tool_input: dict) -> Any:
        """
        Call an MCP tool by name with the given input dict.

        Uses JSON-RPC 2.0 protocol (FastMCP streamable_http transport).

        Args:
            tool_name:  Name of the MCP tool (e.g. "validate_snack_candidate")
            tool_input: Tool input parameters as a dict

        Returns:
            Tool result (parsed JSON)

        Raises:
            MCPServerError: On network error or non-2xx response
        """
        self._call_id += 1
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": tool_input,
            },
            "id": self._call_id,
        }

        logger.debug("MCP call: %s %s", tool_name, tool_input)

        try:
            response = self._session.post(
                f"{self.base_url}/mcp",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.exceptions.Timeout:
            raise MCPServerError(f"MCP tool '{tool_name}' timed out after {self.timeout}s")
        except requests.exceptions.ConnectionError as e:
            raise MCPServerError(f"Cannot connect to MCP server at {self.base_url}: {e}")
        except requests.exceptions.HTTPError as e:
            raise MCPServerError(
                f"MCP server returned HTTP {response.status_code} for tool '{tool_name}': {e}"
            )

        try:
            data = response.json()
        except ValueError as e:
            raise MCPServerError(f"MCP server returned non-JSON response for '{tool_name}': {e}")

        if "error" in data:
            raise MCPServerError(f"MCP tool '{tool_name}' error: {data['error']}")

        # Extract result content from JSON-RPC response
        result = data.get("result", {})
        content = result.get("content", [])
        if content and isinstance(content, list) and content[0].get("type") == "text":
            text = content[0]["text"]
            try:
                return json.loads(text)
            except (json.JSONDecodeError, ValueError):
                return text  # return as-is if not JSON

        return result

    @staticmethod
    def get_tool_definitions() -> list[dict]:
        """Return the static Bedrock toolConfig tool definitions."""
        return BEDROCK_TOOL_DEFINITIONS

    @staticmethod
    def get_openai_tool_definitions() -> list[dict]:
        """Return OpenAI Responses API function tool definitions."""
        tools = []
        for item in BEDROCK_TOOL_DEFINITIONS:
            spec = item["toolSpec"]
            tools.append({
                "type": "function",
                "name": spec["name"],
                "description": spec["description"],
                "parameters": spec["inputSchema"]["json"],
                "strict": False,
            })
        return tools

    @staticmethod
    def get_ollama_tool_definitions() -> list[dict]:
        """Return Ollama /api/chat function tool definitions."""
        tools = []
        for item in BEDROCK_TOOL_DEFINITIONS:
            spec = item["toolSpec"]
            tools.append({
                "type": "function",
                "function": {
                    "name": spec["name"],
                    "description": spec["description"],
                    "parameters": spec["inputSchema"]["json"],
                },
            })
        return tools
