"""
Source hash computation for ShorTED AI pipeline idempotency.

The sourceHash is a stable SHA-256 fingerprint of the content fields that
determine whether a talk needs AI re-processing. It changes only when the
talk's content changes in a meaningful way (transcript, title, speakers, etc.)
and is invariant to processing timestamps or pipeline metadata.

Used to:
  - detect if the same talk was already processed (skip condition)
  - detect if the talk content has changed and needs re-processing
  - partition MongoDB documents for safe replace-by-hash operations
"""
import hashlib
import json

from models import AIContext


def compute_source_hash(ctx: AIContext) -> str:
    """
    Compute a stable SHA-256 hash of the content-determining fields.

    The payload is JSON-serialised with sorted keys and no extra whitespace
    to ensure identical output regardless of Python version or dict ordering.

    Fields included (content-determining):
        slug, title, speakers (sorted), language, raw_transcript,
        source_tags (sorted), duration

    Fields explicitly excluded (volatile / not content):
        processing timestamps, pipeline version, image URL, id

    Args:
        ctx: AIContext built from the processed JSON.

    Returns:
        Hex-encoded SHA-256 string (64 chars).
    """
    payload = {
        "slug": ctx.slug,
        "title": ctx.title,
        "speakers": sorted(ctx.speakers),
        "language": ctx.language,
        "raw": ctx.raw_transcript,
        "tags": sorted(ctx.source_tags),
        "duration": ctx.duration,
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
