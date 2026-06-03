"""
Configuration for ShorTED Lambda AI Orchestrator.

Reads from environment variables (set in Lambda console for AWS,
or from a local .env file during development).

Usage:
    from config import MIN_SNACKS, AI_PROVIDER, OPENAI_MODEL, ...
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


# ── AI Provider ───────────────────────────────────────────────────────────────
# Supported values:
#   bedrock → AWS Bedrock Converse API
#   openai  → OpenAI Responses API
#   ollama  → Ollama /api/chat endpoint
AI_PROVIDER: str = os.environ.get("AI_PROVIDER", "bedrock").lower()


# ── Bedrock ───────────────────────────────────────────────────────────────────
BEDROCK_REGION: str = os.environ.get("BEDROCK_REGION", "us-east-1")
# Amazon Nova Lite — cost-effective, strong tool-use, Italian optimised
BEDROCK_MODEL_ID: str = os.environ.get("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0")


# ── OpenAI ────────────────────────────────────────────────────────────────────
# OPENAI_API_KEY is intentionally read lazily by the OpenAI client so local
# Bedrock/Ollama tests do not require it to exist.
OPENAI_BASE_URL: str = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL: str = os.environ.get("OPENAI_MODEL", "gpt-5.4-mini")
OPENAI_TIMEOUT_SECONDS: int = int(os.environ.get("OPENAI_TIMEOUT_SECONDS", "120"))
OPENAI_MAX_OUTPUT_TOKENS: int = int(os.environ.get("OPENAI_MAX_OUTPUT_TOKENS", "8192"))


# ── Ollama ────────────────────────────────────────────────────────────────────
# For Lambda, this must be a network-reachable HTTPS/HTTP endpoint; localhost
# means "inside the Lambda container", not the developer machine.
OLLAMA_BASE_URL: str = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL: str = os.environ.get("OLLAMA_MODEL", "llama3.1")
OLLAMA_TIMEOUT_SECONDS: int = int(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "180"))
OLLAMA_EMPTY_CONTENT_REPROMPTS: int = int(os.environ.get("OLLAMA_EMPTY_CONTENT_REPROMPTS", "2"))


# ── Local fast provider ───────────────────────────────────────────────────────
# Separate high-throughput local/free-provider path. It intentionally does not
# change the canonical bedrock/openai/ollama tool-loop providers.
LOCAL_FAST_BACKENDS: list[str] = [
    item.strip().lower()
    for item in os.environ.get("LOCAL_FAST_BACKENDS", "freerouter,ollama").split(",")
    if item.strip()
]
LOCAL_FAST_TIMEOUT_SECONDS: int = int(os.environ.get("LOCAL_FAST_TIMEOUT_SECONDS", "240"))
LOCAL_FAST_MAX_REPAIR_ATTEMPTS: int = int(os.environ.get("LOCAL_FAST_MAX_REPAIR_ATTEMPTS", "1"))
LOCAL_FAST_TRANSCRIPT_MAX_CHARS: int = int(os.environ.get("LOCAL_FAST_TRANSCRIPT_MAX_CHARS", "12000"))
LOCAL_FAST_TEMPERATURE: float = float(os.environ.get("LOCAL_FAST_TEMPERATURE", "0.2"))
LOCAL_FAST_MAX_TOKENS: int = int(os.environ.get("LOCAL_FAST_MAX_TOKENS", "5000"))

# freeRouter exposes an OpenAI-compatible /v1/chat/completions endpoint.
FREEROUTER_BASE_URL: str = os.environ.get("FREEROUTER_BASE_URL", "http://127.0.0.1:9000/v1")
FREEROUTER_API_KEY: str = os.environ.get("FREEROUTER_API_KEY", "")
FREEROUTER_MODEL: str = os.environ.get("FREEROUTER_MODEL", "groq/llama-3.1-8b-instant")


# ── MCP Server ────────────────────────────────────────────────────────────────
# URL of the ShorTED MCP server.
# Locally: http://localhost:8080
# AWS: Lambda Function URL (set after deploy)
MCP_SERVER_URL: str = os.environ["MCP_SERVER_URL"]
# Max seconds to wait for a single MCP tool call response
MCP_TIMEOUT_SECONDS: int = int(os.environ.get("MCP_TIMEOUT_SECONDS", "30"))


# ── Pipeline ──────────────────────────────────────────────────────────────────
PIPELINE_VERSION: str = os.environ.get("PIPELINE_VERSION", "v1")

# Default is idempotent skip: completed talks with same sourceHash and enough
# snacks are not regenerated. Set true only for deliberate reprocessing runs.
FORCE_REPROCESS_COMPLETED: bool = (
    os.environ.get("FORCE_REPROCESS_COMPLETED", "false").lower()
    in ("1", "true", "yes", "y")
)

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


# ── AI tool-use loop limits ───────────────────────────────────────────────────
# Safety cap on how many tool-use iterations the model can make per talk.
MAX_TOOL_LOOPS: int = int(os.environ.get("MAX_TOOL_LOOPS", "20"))
# Max repair attempts if the model returns invalid JSON/schema
MAX_REPAIR_ATTEMPTS: int = int(os.environ.get("MAX_REPAIR_ATTEMPTS", "1"))
