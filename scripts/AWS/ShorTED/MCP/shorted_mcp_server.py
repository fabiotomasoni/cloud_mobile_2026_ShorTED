"""
ShorTED MCP Server — main entry point.

Exposes MCP tools, resources and prompts used by the Bedrock AI Orchestrator
during snack generation.

Running modes:
  1. Local development:
        python shorted_mcp_server.py
        → starts uvicorn on http://localhost:8080

  2. AWS Lambda Function URL (production):
        lambda_handler is the Lambda entry point.
        Deploy this directory as a Lambda zip.

Tools exposed to the AI model:
  - get_processing_context
  - get_existing_snacks
  - validate_snack_candidate
  - validate_snack_candidates
  - validate_final_snack_set
  - find_similar_snacks
  - canonicalize_tags
  - build_talk_url
"""
import json
import logging
import os
import asyncio
import base64
from urllib.parse import urlparse, urlencode, urlunparse, parse_qs

from mcp.server.fastmcp import FastMCP

from config import SERVER_PORT
from mongo_client import talks, snacks
from schemas import SNACK_SCHEMA
from config import (
    MIN_SNACKS,
    MAX_SNACKS,
    MIN_SEGMENT_DURATION,
    MAX_SEGMENT_DURATION,
    MIN_DISTANCE_SECONDS,
    MAX_QUOTE_CHARS,
    MAX_MOTIVATIONAL_CHARS,
    MAX_APHORISM_CHARS,
    MIN_TAGS,
    MAX_TAGS,
)
from validation import validate_single, validate_batch, validate_final_set
from duplicate_detection import find_intra_batch_duplicates, find_cross_db_duplicates
from tag_utils import normalize_tags
from resources import register_resources
from prompts import register_prompts

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── FastMCP server instance ───────────────────────────────────────────────────
mcp = FastMCP("shorted-mcp-server")


# ── TOOLS ─────────────────────────────────────────────────────────────────────

@mcp.tool()
async def get_snack_schema() -> dict:
    """Return the canonical ShorTED snack schema."""
    return SNACK_SCHEMA


@mcp.tool()
async def get_mixer_rules() -> dict:
    """Return numeric rules governing snack count, duration, spacing and lengths."""
    return {
        "minSnacks": MIN_SNACKS,
        "maxSnacks": MAX_SNACKS,
        "minSegmentDurationSeconds": MIN_SEGMENT_DURATION,
        "maxSegmentDurationSeconds": MAX_SEGMENT_DURATION,
        "minDistanceBetweenSnacksSeconds": MIN_DISTANCE_SECONDS,
        "maxQuoteChars": MAX_QUOTE_CHARS,
        "maxMotivationalChars": MAX_MOTIVATIONAL_CHARS,
        "maxAphorismChars": MAX_APHORISM_CHARS,
        "minTags": MIN_TAGS,
        "maxTags": MAX_TAGS,
    }


@mcp.tool()
async def get_grounding_rules() -> str:
    """Return quality and grounding rules for generated snacks."""
    return (
        "1. Quotes must be exact or near-exact excerpts from the transcript. "
        "Do not paraphrase or invent quotes.\n"
        "2. Do not introduce facts, names, dates, or claims not present in the transcript.\n"
        "3. Motivational text must be inspiring, directly grounded in the quote and topic, "
        "and must not be a summary or clickbait.\n"
        "4. Aphorisms must be short, punchy, standalone phrases.\n"
        "5. Topics must be specific and descriptive, not generic labels.\n"
        "6. Prefer self-contained segments that make sense without the rest of the talk.\n"
        "7. All generated fields must match the transcript language."
    )


@mcp.tool()
async def get_processing_context(
    talk_slug: str,
    language: str,
    pipeline_version: str,
) -> dict:
    """
    Return existing talk metadata and snack count for a given talk.
    Read-only. Useful to check if snacks already exist before generation.
    """
    talk = await talks.find_one(
        {"slug": talk_slug, "language": language, "aiPipelineVersion": pipeline_version},
        {"_id": 0},
    )
    snack_count = await snacks.count_documents(
        {"talkSlug": talk_slug, "language": language}
    )
    return {
        "talk": talk,
        "existingSnackCount": snack_count,
    }


@mcp.tool()
async def get_existing_snacks(
    talk_slug: str,
    language: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """
    Return existing snack documents for a talk.
    Useful for duplicate reference before generating new snacks.
    """
    query: dict = {"talkSlug": talk_slug}
    if language:
        query["language"] = language
    cursor = snacks.find(query, {"_id": 0}).limit(limit)
    return await cursor.to_list(length=limit)


@mcp.tool()
async def validate_snack_candidate(snack: dict) -> dict:
    """
    Validate a single snack candidate against the ShorTED schema and business rules.

    Returns:
        {
            "valid": bool,
            "errors": [{"field": str, "message": str}],
            "warnings": [{"field": str, "message": str}]
        }
    """
    return validate_single(snack)


@mcp.tool()
async def validate_snack_candidates(snacks_list: list[dict]) -> dict:
    """
    Validate multiple snack candidates at once.

    Returns:
        {"results": [validation result per snack]}
    """
    return validate_batch(snacks_list)


@mcp.tool()
async def validate_final_snack_set(snacks_list: list[dict]) -> dict:
    """
    Validate the complete final snack set:
      - Count in [MIN_SNACKS, MAX_SNACKS]
      - No duplicate segmentId or quote
      - Minimum spacing between snacks
      - Schema compliance for every snack

    Returns:
        {
            "valid": bool,
            "errors": [...],
            "warnings": [...],
            "stats": {"count": int, "minScore": float, "maxScore": float}
        }
    """
    return validate_final_set(snacks_list)


@mcp.tool()
async def find_similar_snacks(
    talk_slug: str,
    candidate_snacks: list[dict],
) -> dict:
    """
    Detect near-duplicate snacks using deterministic heuristics.

    Checks:
      - Intra-batch: pairs within the candidate list
      - Cross-DB: candidates vs existing snacks in MongoDB

    Heuristics:
      - Same topic (case-insensitive)
      - Quote similarity >= 0.85 (SequenceMatcher)
      - startTime distance < MIN_DISTANCE_SECONDS
      - Tag Jaccard overlap >= 80%

    Returns:
        {
            "intraBatchDuplicates": [...],
            "crossDbDuplicates": [...],
            "hasDuplicates": bool
        }
    """
    intra = find_intra_batch_duplicates(candidate_snacks)

    existing = await snacks.find(
        {"talkSlug": talk_slug},
        {"_id": 0, "segmentId": 1, "topic": 1, "quote": 1, "startTime": 1, "tags": 1},
    ).to_list(length=50)
    cross = find_cross_db_duplicates(candidate_snacks, existing)

    return {
        "intraBatchDuplicates": intra,
        "crossDbDuplicates": cross,
        "hasDuplicates": bool(intra or cross),
    }


@mcp.tool()
async def canonicalize_tags(tags: list[str]) -> list[str]:
    """
    Normalise tags to canonical form:
      - Lowercase
      - Spaces replaced with hyphens
      - Alias map applied (e.g. "Artificial Intelligence" → "ai")
      - Duplicates removed
      - Sorted alphabetically

    Use this before setting tags on any snack candidate.
    """
    return normalize_tags(tags)


@mcp.tool()
async def build_talk_url(base_url: str, start_time: int) -> str:
    """
    Build a TED talk URL with the segment start timestamp.

    Example:
        base_url = "https://www.ted.com/talks/example"
        start_time = 120
        → "https://www.ted.com/talks/example?t=120"

    Handles existing query parameters safely.
    """
    parsed = urlparse(base_url)
    params = parse_qs(parsed.query)
    params["t"] = [str(start_time)]
    new_query = urlencode({k: v[0] for k, v in params.items()})
    return urlunparse(parsed._replace(query=new_query))


HTTP_TOOL_DISPATCH = {
    "get_snack_schema": get_snack_schema,
    "get_mixer_rules": get_mixer_rules,
    "get_grounding_rules": get_grounding_rules,
    "get_processing_context": get_processing_context,
    "get_existing_snacks": get_existing_snacks,
    "validate_snack_candidate": validate_snack_candidate,
    "validate_snack_candidates": validate_snack_candidates,
    "validate_final_snack_set": validate_final_snack_set,
    "find_similar_snacks": find_similar_snacks,
    "canonicalize_tags": canonicalize_tags,
    "build_talk_url": build_talk_url,
}


# ── RESOURCES & PROMPTS ───────────────────────────────────────────────────────

register_resources(mcp)
register_prompts(mcp)


# ── ENTRY POINTS ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Local development mode
    import uvicorn
    uvicorn.run(
        mcp.streamable_http_app(),
        host="0.0.0.0",
        port=SERVER_PORT,
    )


def lambda_handler(event, context):
    """
    AWS Lambda Function URL entry point (production).

    Uses Mangum to wrap the FastMCP ASGI app for Lambda.
    Install mangum in requirements.txt.
    """
    direct_response = _handle_direct_jsonrpc_tool_call(event)
    if direct_response is not None:
        return direct_response

    try:
        from mangum import Mangum
    except ImportError:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "mangum not installed — add to requirements.txt"}),
        }

    handler = Mangum(mcp.streamable_http_app(), lifespan="auto")
    return handler(event, context)


def _handle_direct_jsonrpc_tool_call(event: dict) -> dict | None:
    """
    Handle the Orchestrator's lightweight JSON-RPC tools/call POST directly.

    Full MCP clients can still use the FastMCP streamable_http app. The
    Orchestrator only needs deterministic tool calls, so this avoids MCP
    session-negotiation issues in Lambda Function URLs.
    """
    method = (
        event.get("requestContext", {})
        .get("http", {})
        .get("method")
        or event.get("httpMethod")
        or ""
    ).upper()
    path = (
        event.get("rawPath")
        or event.get("path")
        or event.get("requestContext", {}).get("http", {}).get("path")
        or ""
    ).rstrip("/")

    if method != "POST" or path != "/mcp":
        return None

    try:
        body = event.get("body") or "{}"
        if event.get("isBase64Encoded"):
            body = base64.b64decode(body).decode("utf-8")
        payload = json.loads(body)
        if payload.get("method") != "tools/call":
            return None

        params = payload.get("params") or {}
        tool_name = params.get("name")
        arguments = params.get("arguments") or {}

        if tool_name not in HTTP_TOOL_DISPATCH:
            return _jsonrpc_response(payload.get("id"), error={
                "code": -32601,
                "message": f"Unknown tool: {tool_name}",
            })

        result = asyncio.run(_call_dispatched_tool(tool_name, arguments))
        return _jsonrpc_response(payload.get("id"), result={
            "content": [{
                "type": "text",
                "text": json.dumps(result, ensure_ascii=False, default=str),
            }]
        })
    except Exception as e:
        logger.exception("Direct JSON-RPC MCP tool call failed")
        return _jsonrpc_response(None, error={
            "code": -32603,
            "message": str(e),
        })


async def _call_dispatched_tool(tool_name: str, arguments: dict):
    tool = HTTP_TOOL_DISPATCH[tool_name]
    return await tool(**arguments)


def _jsonrpc_response(request_id, result=None, error=None) -> dict:
    body = {"jsonrpc": "2.0", "id": request_id}
    status_code = 200
    if error is not None:
        body["error"] = error
        status_code = 400 if error.get("code") != -32603 else 500
    else:
        body["result"] = result
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, ensure_ascii=False, default=str),
    }
