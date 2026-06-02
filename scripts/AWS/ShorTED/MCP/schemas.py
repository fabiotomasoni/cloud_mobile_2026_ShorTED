"""
Canonical schemas for ShorTED snack and talk documents.

These are used by MCP resources (shorted://schemas/snack and shorted://schemas/talk)
and as the reference for validation logic.
"""

SNACK_SCHEMA = {
    "description": "A single ShorTED snack — a meaningful, self-contained segment of a TED/TEDx talk.",
    "type": "object",
    "required": [
        "segmentId", "talkId", "talkSlug", "speaker", "talkTitle",
        "topic", "quote", "motivationalText", "aphorism", "tags", "score",
        "startTime", "endTime", "talkUrl", "language",
    ],
    "properties": {
        "segmentId": {
            "type": "string",
            "description": "Unique identifier for this segment within the talk. Format: seg_001, seg_002, …",
            "example": "seg_001",
        },
        "talkId": {
            "type": "string",
            "description": "Numeric ID of the talk (as string).",
        },
        "talkSlug": {
            "type": "string",
            "description": "URL-safe slug of the talk. Must match the talk being processed.",
        },
        "speaker": {
            "type": "string",
            "description": "Name of the speaker (presenterDisplayName).",
        },
        "talkTitle": {
            "type": "string",
            "description": "Full title of the talk.",
        },
        "topic": {
            "type": "string",
            "description": "Short, specific topic label for this snack (not generic like 'Main theme').",
        },
        "quote": {
            "type": "string",
            "description": "A short, impactful excerpt from the transcript. Must be grounded in the transcript text. Max 180 chars.",
            "maxLength": 180,
        },
        "motivationalText": {
            "type": "string",
            "description": "A strong, impactful, and inspiring statement that directly relates to the quote and the topic of the segment. Must NOT be a summary. Max 500 chars.",
            "maxLength": 500,
        },
        "aphorism": {
            "type": "string",
            "description": "A very short, punchy catchphrase or aphorism that captures the essence of the segment. Max 100 chars.",
            "maxLength": 100,
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 3,
            "maxItems": 6,
            "description": "Canonical, lowercase, hyphenated tags. Use canonicalize_tags tool.",
        },
        "score": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
            "description": "Quality/relevance score assigned by the AI. Higher is better.",
        },
        "startTime": {
            "type": "integer",
            "minimum": 0,
            "description": "Start of the segment in seconds from the beginning of the video.",
        },
        "endTime": {
            "type": "integer",
            "description": "End of the segment in seconds. Must be greater than startTime.",
        },
        "talkUrl": {
            "type": "string",
            "description": "Direct URL to the talk at the segment start. Format: https://www.ted.com/talks/<slug>?t=<startTime>",
        },
        "language": {
            "type": "string",
            "description": "Language code of this snack (e.g. 'en', 'it'). Matches the transcript language used.",
        },
    },
}

TALK_SCHEMA = {
    "description": "A processed TED/TEDx talk stored in MongoDB.",
    "type": "object",
    "required": ["talkId", "slug", "title", "speaker", "url", "language"],
    "properties": {
        "talkId":     {"type": "string"},
        "slug":       {"type": "string"},
        "title":      {"type": "string"},
        "speaker":    {"type": "string"},
        "speakers":   {"type": "array", "items": {"type": "string"}},
        "url":        {"type": "string"},
        "duration":   {"type": "integer", "description": "Talk duration in seconds."},
        "imageUrl":   {"type": "string"},
        "sourceTags": {"type": "array", "items": {"type": "string"}},
        "language":   {"type": "string"},
        "aiPipelineVersion": {"type": "string"},
        "sourceHash": {"type": "string"},
        "processingStatus": {
            "type": "string",
            "enum": ["processing", "completed", "failed"],
        },
        "snackCount": {"type": "integer"},
        "processedAt": {"type": "string", "format": "date-time"},
    },
}
