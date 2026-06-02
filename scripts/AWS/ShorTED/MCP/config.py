"""
Configuration for the ShorTED MCP Server.

Reads from environment variables (Lambda console) or local .env file.
"""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# ── MongoDB ───────────────────────────────────────────────────────────────────
MONGODB_URI: str = os.environ["MONGODB_URI"]
MONGODB_DB: str = os.environ.get("MONGODB_DB", "shorted")


# ── Snack generation rules ────────────────────────────────────────────────────
MIN_SNACKS: int = int(os.environ.get("MIN_SNACKS", "4"))
MAX_SNACKS: int = int(os.environ.get("MAX_SNACKS", "8"))
MIN_SEGMENT_DURATION: int = int(os.environ.get("MIN_SEGMENT_DURATION", "20"))   # seconds
MAX_SEGMENT_DURATION: int = int(os.environ.get("MAX_SEGMENT_DURATION", "150"))  # seconds
MIN_DISTANCE_SECONDS: int = int(os.environ.get("MIN_DISTANCE_SECONDS", "45"))
MAX_QUOTE_CHARS = int(os.getenv("MAX_QUOTE_CHARS", "180"))
MAX_MOTIVATIONAL_CHARS = int(os.getenv("MAX_MOTIVATIONAL_CHARS", "500"))
MAX_APHORISM_CHARS = int(os.getenv("MAX_APHORISM_CHARS", "100"))
MIN_TAGS: int = int(os.environ.get("MIN_TAGS", "3"))
MAX_TAGS: int = int(os.environ.get("MAX_TAGS", "6"))

# ── Server ────────────────────────────────────────────────────────────────────
SERVER_PORT: int = int(os.environ.get("PORT", "8080"))
