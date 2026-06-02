"""
AI Context Builder (AI Input Adapter) for ShorTED.

Transforms the Glue-produced processed JSON into a lightweight AIContext
ready for the Bedrock Orchestrator. This is NOT a second ETL pass — it only:
  - selects the language to use
  - extracts sentences and converts timestamps to integers (ms)
  - assembles the flat metadata fields needed by the model
  - keeps the raw transcript for full-context prompting

Design constraint: does not rewrite, clean or semantically alter the data
produced by Glue. The processed JSON is treated as the source of truth.
"""
import logging
from models import AIContext
from errors import TranscriptUnavailableError

logger = logging.getLogger(__name__)


def build_ai_context(processed_json: dict, preferred_language: str) -> AIContext:
    """
    Build an AIContext from the Glue-processed talk JSON.

    Language selection order:
        1. preferred_language (from SQS message or DEFAULT_LANGUAGE)
        2. "en"  (most complete in TED dataset)
        3. first available language in transcriptions

    Args:
        processed_json:     Dict loaded from S3 processed JSON.
        preferred_language: Preferred language code (e.g. "en", "it").

    Returns:
        AIContext ready for the Bedrock Orchestrator.

    Raises:
        TranscriptUnavailableError: No usable transcript found in any language.
    """
    transcriptions: dict = processed_json["transcriptions"]

    language = _select_language(transcriptions, preferred_language, processed_json.get("slug", "?"))
    trans = transcriptions[language]

    sentences = _extract_sentences(trans)
    raw = trans.get("raw", "").strip()

    if not raw and not sentences:
        raise TranscriptUnavailableError(
            f"Empty transcript for slug='{processed_json.get('slug')}' language='{language}'"
        )

    # Build a single raw transcript from sentences if raw is missing
    if not raw and sentences:
        raw = " ".join(s["text"] for s in sentences)

    speakers: list[str] = processed_json.get("speakers") or []
    speaker: str = (
        processed_json.get("presenterDisplayName")
        or (speakers[0] if speakers else "Unknown")
    )

    return AIContext(
        talk_id=str(processed_json.get("id", "")),
        slug=processed_json["slug"],
        title=processed_json["title"],
        speaker=speaker,
        speakers=speakers,
        url=processed_json.get("url", ""),
        duration=_safe_int(processed_json.get("duration", 0)),
        image_url=processed_json.get("image", ""),
        source_tags=processed_json.get("tags") or [],
        language=language,
        sentences=sentences,
        raw_transcript=raw,
    )


# ── Internal helpers ─────────────────────────────────────────────────────────

def _select_language(
    transcriptions: dict,
    preferred: str,
    slug: str,
) -> str:
    """Select the best available language from the transcriptions map."""
    if preferred in transcriptions:
        logger.info("Language selected: '%s' (preferred) for slug='%s'", preferred, slug)
        return preferred

    if "en" in transcriptions:
        logger.info(
            "Language '%s' not available for slug='%s', falling back to 'en'",
            preferred, slug,
        )
        return "en"

    available = list(transcriptions.keys())
    if available:
        chosen = available[0]
        logger.warning(
            "Languages '%s' and 'en' not available for slug='%s', using first: '%s'",
            preferred, slug, chosen,
        )
        return chosen

    raise TranscriptUnavailableError(
        f"No languages available in transcriptions for slug='{slug}'"
    )


def _extract_sentences(trans: dict) -> list[dict]:
    """
    Extract sentences and normalise timestamps to integer milliseconds.

    Input format (from Glue):
        [{"timestamp": "7000", "text": "..."}, ...]

    Output format:
        [{"timestamp_ms": 7000, "text": "..."}, ...]
    """
    raw_sentences = trans.get("sentences") or []
    result = []
    for s in raw_sentences:
        text = s.get("text", "").strip()
        if not text:
            continue
        timestamp_ms = _safe_int(s.get("timestamp", 0))
        result.append({"timestamp_ms": timestamp_ms, "text": text})
    return result


def _safe_int(value, default: int = 0) -> int:
    """Convert value to int safely, returning default on failure."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
