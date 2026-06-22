"""
Shared data models (dataclasses) for ShorTED Lambda AI Orchestrator.

These are pure data containers — no business logic here.
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SQSMessage:
    """Parsed content of one SQS record from the Dispatcher."""
    bucket: str
    file_key: str
    language: Optional[str] = None   # optional override; falls back to DEFAULT_LANGUAGE
    message_id: str = ""


@dataclass
class AIContext:
    """
    Lightweight representation of a processed talk, ready for AI consumption.
    Built by ai_context_builder from the Glue-produced JSON.
    No ETL here — only light transformations.
    """
    talk_id: str
    slug: str
    title: str
    speaker: str                     # presenterDisplayName or first speaker
    speakers: list[str]
    url: str
    duration: int                    # seconds
    image_url: str
    source_tags: list[str]
    language: str                    # selected language code (e.g. "en", "it")
    sentences: list[dict]            # [{"timestamp_ms": int, "text": str}, ...]
    raw_transcript: str              # full raw text for the selected language
    embed_url: str = ""
    thumbnail_url: str = ""
    thumbnail_url_hd: str = ""
    thumbnail_url_full_hd: str = ""
    hls_url: str = ""
    mp4_url: str = ""
    media_extracted_at: str = ""
    media_extraction_version: str = ""
    media_extraction_status: str = ""
    media_extraction_error: str = ""


@dataclass
class SnackDoc:
    """
    A single snack document as produced by the AI model.
    Maps 1:1 to a MongoDB snack document.
    """
    segment_id: str
    talk_id: str
    talk_slug: str
    speaker: str
    talk_title: str
    topic: str
    quote: str
    motivationalText: str
    aphorism: str
    tags: list[str]
    score: float
    start_time: int                  # seconds from beginning
    end_time: int                    # seconds from beginning
    talk_url: str                    # ted.com/talks/<slug>?t=<start_time>
    language: str


@dataclass
class AIResult:
    """
    Structured output returned by the Bedrock Orchestrator.
    Contains the talk metadata confirmed by AI + final snacks + a processing report.
    """
    talk: dict                       # talk metadata as returned by the model
    final_snacks: list[SnackDoc]
    processing_report: dict          # {candidateSegments, candidateSnacks, finalSnacks,
                                     #  mcpToolsUsed, warnings, status}


@dataclass
class SkipResult:
    """Result of the should_skip_ai check."""
    should_skip: bool
    reason: str                      # "already_completed" | "not_found" | "insufficient_snacks"
