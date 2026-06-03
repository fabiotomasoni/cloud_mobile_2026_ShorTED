"""
Fast local/free-provider AI client for ShorTED.

This is intentionally separate from the canonical Bedrock/OpenAI/Ollama
tool-use orchestration. It optimises for throughput on local/free models by:

  - avoiding MCP tool loops during generation
  - asking the model for only the fields that need semantic judgement
  - filling deterministic metadata in Python
  - relying on the existing final_validator and MongoDB idempotent persistence

It still runs inside the same handler, so SQS deletion, Mongo locks, skip checks
and retry behaviour remain exactly the same.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import requests

from config import (
    FREEROUTER_API_KEY,
    FREEROUTER_BASE_URL,
    FREEROUTER_MODEL,
    LOCAL_FAST_BACKENDS,
    LOCAL_FAST_MAX_REPAIR_ATTEMPTS,
    LOCAL_FAST_MAX_TOKENS,
    LOCAL_FAST_TEMPERATURE,
    LOCAL_FAST_TIMEOUT_SECONDS,
    LOCAL_FAST_TRANSCRIPT_MAX_CHARS,
    MAX_SNACKS,
    MIN_SNACKS,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
)
from errors import AIOutputInvalidError
from final_validator import validate_ai_result
from models import AIContext, AIResult, SnackDoc

logger = logging.getLogger(__name__)


def invoke_local_fast_orchestrator(
    ai_ctx: AIContext,
    _mcp_server_url: str,
    _pipeline_version: str,
) -> AIResult:
    """Generate snacks through the fast local/free-provider path."""
    errors: list[str] = []
    backends = LOCAL_FAST_BACKENDS or ["freerouter", "ollama"]

    for backend in backends:
        try:
            logger.info("local_fast backend=%s slug='%s'", backend, ai_ctx.slug)
            return _run_backend_with_repair(ai_ctx, backend)
        except AIOutputInvalidError as e:
            errors.append(f"{backend}: {e}")
            logger.warning("local_fast backend=%s failed for slug='%s': %s", backend, ai_ctx.slug, e)

    raise AIOutputInvalidError("All local_fast backends failed: " + " | ".join(errors))


def _run_backend_with_repair(ai_ctx: AIContext, backend: str) -> AIResult:
    messages = [
        {"role": "system", "content": _system_prompt(ai_ctx)},
        {"role": "user", "content": _user_prompt(ai_ctx)},
    ]

    last_text = ""
    last_error = ""
    for attempt in range(LOCAL_FAST_MAX_REPAIR_ATTEMPTS + 1):
        if attempt > 0:
            messages.append({"role": "assistant", "content": last_text[:4000]})
            messages.append({"role": "user", "content": _repair_prompt(last_error)})

        text = _call_backend(backend, messages)
        last_text = text
        try:
            result = _parse_fast_output(text, ai_ctx, backend)
            validate_ai_result(result, ai_ctx)
            return result
        except AIOutputInvalidError as e:
            last_error = str(e)
            logger.warning(
                "local_fast output invalid backend=%s attempt=%d/%d: %s",
                backend,
                attempt + 1,
                LOCAL_FAST_MAX_REPAIR_ATTEMPTS + 1,
                e,
            )

    raise AIOutputInvalidError(last_error or "local_fast output invalid")


def _call_backend(backend: str, messages: list[dict]) -> str:
    if backend == "freerouter":
        return _call_openai_compatible(
            base_url=FREEROUTER_BASE_URL,
            model=FREEROUTER_MODEL,
            api_key=FREEROUTER_API_KEY,
            messages=messages,
            backend_name="freerouter",
        )
    if backend == "ollama":
        return _call_ollama(messages)
    raise AIOutputInvalidError(f"Unsupported local_fast backend: {backend}")


def _call_openai_compatible(
    base_url: str,
    model: str,
    api_key: str,
    messages: list[dict],
    backend_name: str,
) -> str:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "temperature": LOCAL_FAST_TEMPERATURE,
        "max_tokens": LOCAL_FAST_MAX_TOKENS,
        "response_format": {"type": "json_object"},
    }
    try:
        response = requests.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers=headers,
            json=payload,
            timeout=LOCAL_FAST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        body = getattr(e.response, "text", "")[:1000] if getattr(e, "response", None) else ""
        raise AIOutputInvalidError(f"{backend_name} request failed: {e}. Body: {body}") from e

    data = response.json()
    try:
        return data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as e:
        raise AIOutputInvalidError(f"{backend_name} response missing message content: {data}") from e


def _call_ollama(messages: list[dict]) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": LOCAL_FAST_TEMPERATURE,
            "num_predict": LOCAL_FAST_MAX_TOKENS,
        },
    }
    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL.rstrip('/')}/api/chat",
            json=payload,
            timeout=LOCAL_FAST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        raise AIOutputInvalidError(f"ollama local_fast request failed: {e}") from e

    data = response.json()
    content = data.get("message", {}).get("content") or ""
    if not content:
        raise AIOutputInvalidError(f"ollama local_fast returned empty content: {data}")
    return content


def _parse_fast_output(text: str, ai_ctx: AIContext, backend: str) -> AIResult:
    raw = _extract_json_object(text)
    data = json.loads(raw)
    snacks_raw = data.get("final_snacks") or data.get("snacks")
    if not isinstance(snacks_raw, list):
        raise AIOutputInvalidError("local_fast output missing final_snacks list")

    snacks: list[SnackDoc] = []
    for index, item in enumerate(snacks_raw, start=1):
        if not isinstance(item, dict):
            raise AIOutputInvalidError(f"snack[{index}] is not an object")
        start = _safe_int(item.get("startTime", item.get("start_time")))
        end = _safe_int(item.get("endTime", item.get("end_time")))
        segment_id = str(item.get("segmentId") or item.get("segment_id") or f"seg_{index:03d}")
        if not segment_id.startswith("seg_"):
            segment_id = f"seg_{index:03d}"

        tags = _canonicalize_tags(item.get("tags") or ai_ctx.source_tags[:4])
        snacks.append(
            SnackDoc(
                segment_id=segment_id,
                talk_id=ai_ctx.talk_id,
                talk_slug=ai_ctx.slug,
                speaker=ai_ctx.speaker,
                talk_title=ai_ctx.title,
                topic=str(item.get("topic", "")).strip(),
                quote=str(item.get("quote", "")).strip(),
                motivationalText=str(item.get("motivationalText", item.get("motivational_text", ""))).strip(),
                aphorism=str(item.get("aphorism", "")).strip(),
                tags=tags,
                score=_safe_float(item.get("score"), 0.75),
                start_time=start,
                end_time=end,
                talk_url=_build_talk_url(ai_ctx.url, start),
                language=ai_ctx.language,
            )
        )

    talk = {
        "talkId": ai_ctx.talk_id,
        "slug": ai_ctx.slug,
        "title": ai_ctx.title,
        "speaker": ai_ctx.speaker,
        "speakers": ai_ctx.speakers,
        "url": ai_ctx.url,
        "duration": ai_ctx.duration,
        "imageUrl": ai_ctx.image_url,
        "sourceTags": ai_ctx.source_tags,
        "language": ai_ctx.language,
    }
    report = {
        "candidateSegments": data.get("candidateSegments", len(snacks)),
        "candidateSnacks": data.get("candidateSnacks", len(snacks)),
        "finalSnacks": len(snacks),
        "mcpToolsUsed": [],
        "warnings": [f"local_fast backend={backend}; deterministic post-processing applied"],
        "status": "completed",
    }
    return AIResult(talk=talk, final_snacks=snacks, processing_report=report)


def _system_prompt(ai_ctx: AIContext) -> str:
    return (
        "You generate ShorTED snack candidates from TED/TEDx transcripts. "
        "Return valid JSON only. Do not use markdown. Do not explain. "
        "Quotes must be exact or near-exact excerpts from the transcript. "
        f"Return {MIN_SNACKS} to {MAX_SNACKS} final_snacks. "
        "Each snack needs: segmentId, topic, quote, motivationalText, aphorism, "
        "tags, score, startTime, endTime. "
        "Use the transcript language. Make start/end times plausible and within the talk duration."
    )


def _user_prompt(ai_ctx: AIContext) -> str:
    transcript = _compact_transcript(ai_ctx)
    return f"""Talk:
title: {ai_ctx.title}
speaker: {ai_ctx.speaker}
slug: {ai_ctx.slug}
language: {ai_ctx.language}
duration_seconds: {ai_ctx.duration}
source_tags: {", ".join(ai_ctx.source_tags[:12])}

Transcript:
{transcript}

Return this JSON shape exactly:
{{
  "final_snacks": [
    {{
      "segmentId": "seg_001",
      "topic": "specific topic",
      "quote": "exact or near-exact quote, max 180 chars",
      "motivationalText": "grounded motivational text, max 500 chars",
      "aphorism": "short punchy phrase, max 100 chars",
      "tags": ["lowercase-tag", "another-tag", "third-tag"],
      "score": 0.0,
      "startTime": 0,
      "endTime": 30
    }}
  ]
}}"""


def _compact_transcript(ai_ctx: AIContext) -> str:
    if ai_ctx.sentences:
        lines = [
            f"[{s['timestamp_ms'] // 1000}s] {s['text']}"
            for s in ai_ctx.sentences
            if s.get("text")
        ]
        text = "\n".join(lines)
    else:
        text = ai_ctx.raw_transcript
    if len(text) <= LOCAL_FAST_TRANSCRIPT_MAX_CHARS:
        return text
    return text[:LOCAL_FAST_TRANSCRIPT_MAX_CHARS] + "\n[TRUNCATED]"


def _repair_prompt(error_message: str) -> str:
    return (
        "Your previous JSON failed validation:\n"
        f"{error_message[:2000]}\n\n"
        "Return ONLY corrected valid JSON with final_snacks. No markdown. "
        "Keep talk metadata out; the backend fills it deterministically."
    )


def _extract_json_object(text: str) -> str:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        return fence.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1]
    raise AIOutputInvalidError(f"No JSON object found in local_fast output: {text[:500]}")


def _canonicalize_tags(tags: Any) -> list[str]:
    if not isinstance(tags, list):
        tags = []
    result: list[str] = []
    for tag in tags:
        slug = re.sub(r"[^a-z0-9]+", "-", str(tag).strip().lower()).strip("-")
        if slug and slug not in result:
            result.append(slug)
    while len(result) < 3:
        fallback = f"tedx-{len(result) + 1}"
        if fallback not in result:
            result.append(fallback)
    return result[:6]


def _build_talk_url(base_url: str, start_time: int) -> str:
    if not base_url:
        return f"?t={start_time}"
    parsed = urlparse(base_url)
    query = parse_qs(parsed.query)
    query["t"] = [str(max(0, start_time))]
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, parsed))
