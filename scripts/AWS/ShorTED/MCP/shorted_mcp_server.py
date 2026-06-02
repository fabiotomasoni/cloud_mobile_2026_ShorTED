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
from urllib.parse import urlparse, urlencode, urlunparse, parse_qs

from mcp.server.fastmcp import FastMCP

from config import SERVER_PORT
from mongo_client import talks, snacks
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
    try:
                from mangum import Mangum
    except ImportError:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "mangum not installed — add to requirements.txt"}),
        }

    handler = Mangum(mcp.streamable_http_app(), lifespan="off")
    return handler(event, context)
