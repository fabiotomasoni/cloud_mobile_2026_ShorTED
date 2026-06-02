"""
Configuration for ShorTED Lambda AI Orchestrator.

Reads from environment variables (set in Lambda console for AWS,
or from a local .env file during development).

Usage:
    from config import MIN_SNACKS, BEDROCK_MODEL_ID, ...
"""
import os

# Load .env file if present (development only — python-dotenv)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not available in Lambda runtime — that's fine


# ── MongoDB ──────────────────────────────────────────────────────────────────
# MongoDB connection URI — set as env var in Lambda console.
# Locally: set in .env (never commit .env)
MONGODB_URI: str = os.environ["MONGODB_URI"]
MONGODB_DB: str = os.environ.get("MONGODB_DB", "shorted")


# ── S3 ────────────────────────────────────────────────────────────────────────
# Processed data bucket — matches Dispatcher configuration
PROCESSED_BUCKET: str = os.environ.get("PROCESSED_BUCKET", "shorted-processed")


# ── Bedrock ───────────────────────────────────────────────────────────────────
BEDROCK_REGION: str = os.environ.get("BEDROCK_REGION", "us-east-1")
# Amazon Nova Lite — cost-effective, strong tool-use, Italian optimised
BEDROCK_MODEL_ID: str = os.environ.get("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0")


# ── MCP Server ────────────────────────────────────────────────────────────────
# URL of the ShorTED MCP server.
# Locally: http://localhost:8080
# AWS: Lambda Function URL (set after deploy)
MCP_SERVER_URL: str = os.environ["MCP_SERVER_URL"]
# Max seconds to wait for a single MCP tool call response
MCP_TIMEOUT_SECONDS: int = int(os.environ.get("MCP_TIMEOUT_SECONDS", "30"))


# ── Pipeline ──────────────────────────────────────────────────────────────────
PIPELINE_VERSION: str = os.environ.get("PIPELINE_VERSION", "v1")

# Default language when the SQS message does not specify one.
# Falls back to "en" to maximise transcript coverage across the dataset.
# Future: per-talk language override via SQS message attribute.
DEFAULT_LANGUAGE: str = os.environ.get("DEFAULT_LANGUAGE", "en")


# ── Snack rules ───────────────────────────────────────────────────────────────
MIN_SNACKS: int = int(os.environ.get("MIN_SNACKS", "4"))
MAX_SNACKS: int = int(os.environ.get("MAX_SNACKS", "8"))
MIN_TAGS: int = int(os.environ.get("MIN_TAGS", "3"))
MAX_TAGS: int = int(os.environ.get("MAX_TAGS", "6"))
MAX_APHORISM_CHARS: int = int(os.environ.get("MAX_APHORISM_CHARS", "100"))


# ── Processing lock ───────────────────────────────────────────────────────────
# Lock TTL must be >= Lambda timeout to prevent a crashed Lambda
# leaving a stuck lock. Lambda max timeout is 15 min = 900s.
LOCK_TTL_SECONDS: int = int(os.environ.get("LOCK_TTL_SECONDS", "900"))


# ── Bedrock tool-use loop limits ──────────────────────────────────────────────
# Safety cap on how many tool-use iterations Bedrock can make per talk.
MAX_TOOL_LOOPS: int = int(os.environ.get("MAX_TOOL_LOOPS", "20"))
# Max repair attempts if the model returns invalid JSON/schema
MAX_REPAIR_ATTEMPTS: int = int(os.environ.get("MAX_REPAIR_ATTEMPTS", "1"))
