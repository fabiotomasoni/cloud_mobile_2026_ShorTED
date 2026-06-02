# type: ignore
"""
Snack validation logic for the ShorTED MCP Server.

Provides deterministic validation of single snack candidates and full snack sets.
Called by MCP tools validate_snack_candidate, validate_snack_candidates,
and validate_final_snack_set.
"""
from config import (
    MIN_SNACKS, MAX_SNACKS,
    MIN_SEGMENT_DURATION, MAX_SEGMENT_DURATION,
    MIN_DISTANCE_SECONDS,
    MAX_QUOTE_CHARS, MAX_MOTIVATIONAL_CHARS, MAX_APHORISM_CHARS,
    MIN_TAGS, MAX_TAGS,
)

# Required fields for every snack
REQUIRED_FIELDS = [
    "segmentId", "talkId", "talkSlug", "speaker", "talkTitle",
    "topic", "quote", "motivationalText", "aphorism", "tags", "score",
    "startTime", "endTime", "talkUrl", "language",
]


def validate_single(snack: dict) -> dict:
    """
    Validate one snack candidate against schema and business rules.

    Returns:
        {
            "valid": bool,
            "errors": [{"field": str, "message": str}, ...],
            "warnings": [{"field": str, "message": str}, ...],
        }
    """
    errors = []
    warnings = []

    # 1. Required fields present and non-empty
    for field in REQUIRED_FIELDS:
        value = snack.get(field)
        if value is None:
            errors.append({"field": field, "message": "field is missing"})
        elif isinstance(value, str) and not value.strip():
            errors.append({"field": field, "message": "field is empty string"})

    # Stop early if required fields are missing — further checks would error
    if errors:
        return {"valid": False, "errors": errors, "warnings": warnings}

    # 2. score
    score = snack.get("score")
    if not isinstance(score, (int, float)) or not (0.0 <= float(score) <= 1.0):
        errors.append({"field": "score", "message": f"score must be in [0.0, 1.0], got {score!r}"})

    # 3. Timestamps
    start = snack.get("startTime")
    end = snack.get("endTime")
    if not isinstance(start, (int, float)) or start < 0:
        errors.append({"field": "startTime", "message": f"startTime must be >= 0, got {start!r}"})
    if not isinstance(end, (int, float)):
        errors.append({"field": "endTime", "message": f"endTime must be a number, got {end!r}"})
    elif isinstance(start, (int, float)) and end <= start:
        errors.append({"field": "endTime", "message": f"endTime ({end}) must be > startTime ({start})"})

    # 4. Segment duration
    if isinstance(start, (int, float)) and isinstance(end, (int, float)) and end > start:
        duration = end - start
        if duration < MIN_SEGMENT_DURATION:
            warnings.append({
                "field": "endTime",
                "message": f"Segment duration {duration}s < minimum {MIN_SEGMENT_DURATION}s",
            })
        if duration > MAX_SEGMENT_DURATION:
            warnings.append({
                "field": "endTime",
                "message": f"Segment duration {duration}s > maximum {MAX_SEGMENT_DURATION}s",
            })

    # 5. Quote length
    quote = snack.get("quote", "")
    if isinstance(quote, str) and len(quote) > MAX_QUOTE_CHARS:
        errors.append({
            "field": "quote",
            "message": f"quote length {len(quote)} exceeds max {MAX_QUOTE_CHARS} chars",
        })

    # 6. Motivational text length
    motivational = snack.get("motivationalText", "")
    if isinstance(motivational, str) and len(motivational) > MAX_MOTIVATIONAL_CHARS:
        errors.append({
            "field": "motivationalText",
            "message": f"motivationalText length {len(motivational)} exceeds max {MAX_MOTIVATIONAL_CHARS} chars"
        })

    # 6b. Aphorism length
    aphorism = snack.get("aphorism", "")
    if isinstance(aphorism, str) and len(aphorism) > MAX_APHORISM_CHARS:
        errors.append({
            "field": "aphorism",
            "message": f"aphorism length {len(aphorism)} exceeds max {MAX_APHORISM_CHARS} chars"
        })

    # 7. Tags count
    tags = snack.get("tags")
    if not isinstance(tags, list) or not tags:
        errors.append({"field": "tags", "message": "tags must be a non-empty list"})
    elif not (MIN_TAGS <= len(tags) <= MAX_TAGS):
        errors.append({
            "field": "tags",
            "message": f"tags count {len(tags)} not in [{MIN_TAGS}, {MAX_TAGS}]",
        })

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}


def validate_batch(snacks: list[dict]) -> dict:
    """
    Validate a list of snack candidates individually.

    Returns:
        {"results": [validate_single(s) for s in snacks]}
    """
    return {"results": [validate_single(s) for s in snacks]}


def validate_final_set(snacks: list[dict]) -> dict:
    """
    Validate the complete final snack set for the talk.

    Checks beyond individual validation:
        - Count in [MIN_SNACKS, MAX_SNACKS]
        - No duplicate segmentId
        - No exact-duplicate quote
        - Minimum distance between consecutive snacks (by startTime)

    Returns:
        {
            "valid": bool,
            "errors": [...],
            "warnings": [...],
            "stats": {"count": int, "minScore": float, "maxScore": float},
        }
    """
    errors = []
    warnings = []

    # 1. Count
    count = len(snacks)
    if not (MIN_SNACKS <= count <= MAX_SNACKS):
        errors.append({
            "field": "count",
            "message": f"Snack count {count} not in [{MIN_SNACKS}, {MAX_SNACKS}]",
        })

    # 2. Per-snack validation
    for i, snack in enumerate(snacks):
        result = validate_single(snack)
        for err in result["errors"]:
            errors.append({"field": f"snacks[{i}].{err['field']}", "message": err["message"]})
        for w in result["warnings"]:
            warnings.append({"field": f"snacks[{i}].{w['field']}", "message": w["message"]})

    # 3. Duplicate segmentId
    segment_ids = [s.get("segmentId", "") for s in snacks]
    seen_ids: set[str] = set()
    for sid in segment_ids:
        if sid in seen_ids:
            errors.append({"field": "segmentId", "message": f"Duplicate segmentId: {sid!r}"})
        seen_ids.add(sid)

    # 4. Duplicate quotes (exact match, case-insensitive)
    quotes = [s.get("quote", "").strip().lower() for s in snacks]
    seen_quotes: set[str] = set()
    for q in quotes:
        if q and q in seen_quotes:
            errors.append({"field": "quote", "message": f"Duplicate quote detected: {q[:60]!r}…"})
        seen_quotes.add(q)

    # 5. Minimum distance between snacks (sort by startTime first)
    try:
        sorted_snacks = sorted(
            snacks,
            key=lambda s: s.get("startTime") if isinstance(s.get("startTime"), (int, float)) else 0,
        )
        for i in range(len(sorted_snacks) - 1):
            a_start = sorted_snacks[i].get("startTime", 0)
            b_start = sorted_snacks[i + 1].get("startTime", 0)
            if isinstance(a_start, (int, float)) and isinstance(b_start, (int, float)):
                distance = b_start - a_start
                if distance < MIN_DISTANCE_SECONDS:
                    warnings.append({
                        "field": "startTime",
                        "message": (
                            f"Snacks at {a_start}s and {b_start}s are only {distance}s apart "
                            f"(minimum: {MIN_DISTANCE_SECONDS}s)"
                        ),
                    })
    except Exception:
        pass  # non-blocking

    # Stats
    scores = [
        float(s.get("score", 0))
        for s in snacks
        if isinstance(s.get("score"), (int, float))
    ]
    stats = {
        "count": count,
        "minScore": min(scores) if scores else None,
        "maxScore": max(scores) if scores else None,
    }

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "stats": stats,
    }
