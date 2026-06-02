"""
MCP Resources for the ShorTED MCP Server.

Exposes read-only reference data via MCP resource URIs:
  shorted://schemas/snack    → canonical snack schema
  shorted://schemas/talk     → canonical talk schema
  shorted://rules/mixer      → numeric generation rules
  shorted://rules/grounding  → quality and grounding rules (text)
"""
import json
from mcp.server.fastmcp import FastMCP
from schemas import SNACK_SCHEMA, TALK_SCHEMA
from config import (
    MIN_SNACKS, MAX_SNACKS,
    MIN_SEGMENT_DURATION, MAX_SEGMENT_DURATION,
    MIN_DISTANCE_SECONDS,
    MAX_QUOTE_CHARS, MAX_MOTIVATIONAL_CHARS,
    MIN_TAGS, MAX_TAGS,
)


def register_resources(mcp: FastMCP) -> None:
    """Register all MCP resources on the given FastMCP instance."""

    @mcp.resource("shorted://schemas/snack")
    async def snack_schema() -> str:
        """Canonical JSON schema for a ShorTED snack document."""
        return json.dumps(SNACK_SCHEMA, indent=2, ensure_ascii=False)

    @mcp.resource("shorted://schemas/talk")
    async def talk_schema() -> str:
        """Canonical JSON schema for a ShorTED talk document."""
        return json.dumps(TALK_SCHEMA, indent=2, ensure_ascii=False)

    @mcp.resource("shorted://rules/mixer")
    async def mixer_rules() -> str:
        """Numeric rules governing snack generation (count, duration, spacing, length)."""
        rules = {
            "minSnacks": MIN_SNACKS,
            "maxSnacks": MAX_SNACKS,
            "minSegmentDurationSeconds": MIN_SEGMENT_DURATION,
            "maxSegmentDurationSeconds": MAX_SEGMENT_DURATION,
            "minDistanceBetweenSnacksSeconds": MIN_DISTANCE_SECONDS,
            "maxQuoteChars": MAX_QUOTE_CHARS,
            "maxMotivationalChars": MAX_MOTIVATIONAL_CHARS,
            "minTags": MIN_TAGS,
            "maxTags": MAX_TAGS,
        }
        return json.dumps(rules, indent=2)

    @mcp.resource("shorted://rules/grounding")
    async def grounding_rules() -> str:
        """Quality and grounding rules for AI-generated snack content."""
        return (
            "Grounding and Quality Rules for ShorTED Snacks\n"
            "================================================\n\n"
            "1. QUOTES must be exact or near-exact excerpts from the transcript.\n"
            "   - Do not paraphrase or invent quotes.\n"
            "   - Prefer complete sentences that stand alone without context.\n\n"
            "2. FACTS: Do not introduce facts, names, dates, or claims not\n"
            "   present in the transcript.\n\n"
            "3. MOTIVATIONAL TEXT (CRITICAL):\n"
            "   - Must NOT be a summary, recap, or table of contents.\n"
            "   - Must NOT be clickbait, advertising, or a generic title.\n"
            "   - MUST be a strong, inspiring 2-4 sentence statement directly\n"
            "     grounded in the quote and topic.\n"
            "   - Tone: first person plural or imperative. Speak to the reader.\n"
            "   - Goal: make the reader FEEL they must watch this talk segment.\n"
            "   - Max 500 characters.\n\n"
            "4. APHORISM (CRITICAL):\n"
            "   - A very short, punchy, standalone phrase. Max 100 characters.\n"
            "   - Must feel quotable: timeless, sharp, memorable.\n"
            "   - Can be a rephrased quote, a distillation of the idea, or\n"
            "     an original aphorism inspired by the speaker's words.\n"
            "   - Good: 'Your brain is for having ideas, not for storing them.'\n"
            "   - Bad: 'The speaker discusses knowledge management.' (too descriptive)\n\n"
            "5. TOPIC: Must be specific and descriptive.\n"
            "   Good: 'The role of failure in innovation'\n"
            "   Bad:  'Main theme' / 'Introduction' / 'Conclusion'\n\n"
            "6. SEGMENT SELECTION: Prefer self-contained segments that make\n"
            "   sense without the rest of the talk.\n\n"
            "7. LANGUAGE: All fields (quote, motivationalText, aphorism, topic, tags) must be in\n"
            "   the same language as the transcript used for generation.\n"
        )
