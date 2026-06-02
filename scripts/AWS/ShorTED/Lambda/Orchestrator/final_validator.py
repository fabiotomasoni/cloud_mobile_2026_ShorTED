"""
Final deterministic validator for the ShorTED Lambda Orchestrator.

Runs AFTER the Bedrock Orchestrator returns and BEFORE MongoDB persistence.
This is the last safety gate — even if the model used MCP validation,
we validate again with pure Python to guarantee database integrity.

Validates:
  - final_snacks is a non-empty list in [MIN_SNACKS, MAX_SNACKS]
  - every snack has all required fields, non-empty
  - talkSlug matches the talk being processed
  - language matches the selected language
  - startTime >= 0, endTime > startTime
  - endTime <= duration (if duration > 0)
  - score in [0.0, 1.0]
  - quote non-empty
  - tags non-empty, count in [MIN_TAGS, MAX_TAGS]
  - segmentId unique across all snacks
  - talkUrl non-empty
"""
import logging

from models import AIResult, AIContext
from errors import AIOutputInvalidError
from config import MIN_SNACKS, MAX_SNACKS, MIN_TAGS, MAX_TAGS

logger = logging.getLogger(__name__)

# Required string fields for every snack.
_REQUIRED_STR_FIELDS = [
    "segment_id", "talk_id", "talk_slug", "speaker", "talk_title",
    "topic", "quote", "motivationalText", "aphorism", "talk_url", "language",
]


def validate_ai_result(ai_result: AIResult, ai_ctx: AIContext) -> None:
    """
    Deterministic validation of the AI result before persistence.

    Args:
        ai_result: Parsed AIResult from the Bedrock Orchestrator.
        ai_ctx:    AIContext for the talk being processed.

    Raises:
        AIOutputInvalidError: If any validation check fails.
                              Contains all error messages concatenated.
    """
    errors: list[str] = []
    snacks = ai_result.final_snacks

    # 1. final_snacks is a non-empty list
    if not snacks:
        raise AIOutputInvalidError("final_snacks is empty")

    # 2. count in [MIN_SNACKS, MAX_SNACKS]
    count = len(snacks)
    if not (MIN_SNACKS <= count <= MAX_SNACKS):
        errors.append(f"Snack count {count} not in [{MIN_SNACKS}, {MAX_SNACKS}]")

    segment_ids: set[str] = set()

    for i, s in enumerate(snacks):
        prefix = f"snacks[{i}] segmentId={s.segment_id!r}"

        # 3. Required string fields
        for field in _REQUIRED_STR_FIELDS:
            value = getattr(s, field, None)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{prefix}: field '{field}' is empty or missing")

        # 4. talkSlug must match the talk being processed
        if s.talk_slug and s.talk_slug != ai_ctx.slug:
            errors.append(
                f"{prefix}: talkSlug '{s.talk_slug}' != expected '{ai_ctx.slug}'"
            )

        # 5. language must match
        if s.language and s.language != ai_ctx.language:
            errors.append(
                f"{prefix}: language '{s.language}' != expected '{ai_ctx.language}'"
            )

        # 6. Timestamps
        if s.start_time < 0:
            errors.append(f"{prefix}: startTime {s.start_time} < 0")

        if s.end_time <= s.start_time:
            errors.append(
                f"{prefix}: endTime {s.end_time} <= startTime {s.start_time}"
            )

        if ai_ctx.duration > 0 and s.end_time > ai_ctx.duration:
            errors.append(
                f"{prefix}: endTime {s.end_time} > talk duration {ai_ctx.duration}"
            )

        # 7. Score
        if not isinstance(s.score, (int, float)) or not (0.0 <= float(s.score) <= 1.0):
            errors.append(f"{prefix}: score {s.score!r} not in [0.0, 1.0]")

        # 8. Tags
        if not s.tags:
            errors.append(f"{prefix}: tags list is empty")
        elif not (MIN_TAGS <= len(s.tags) <= MAX_TAGS):
            errors.append(
                f"{prefix}: tags count {len(s.tags)} not in [{MIN_TAGS}, {MAX_TAGS}]"
            )
        elif any(not isinstance(tag, str) or not tag.strip() for tag in s.tags):
            errors.append(f"{prefix}: tags must be non-empty strings")

        # 9. segmentId uniqueness
        sid = s.segment_id
        if sid in segment_ids:
            errors.append(f"{prefix}: duplicate segmentId '{sid}'")
        else:
            segment_ids.add(sid)

    if errors:
        error_summary = f"Final validation failed ({len(errors)} errors):\n" + "\n".join(
            f"  - {e}" for e in errors
        )
        logger.error(error_summary)
        raise AIOutputInvalidError(error_summary)

    logger.info(
        "Final validation passed: slug='%s' snackCount=%d",
        ai_ctx.slug,
        count,
    )
