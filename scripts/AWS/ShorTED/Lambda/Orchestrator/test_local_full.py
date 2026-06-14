# type: ignore
"""
ShorTED AI Pipeline — Full Local Test (Zero External Services)
==============================================================

Runs the complete pipeline end-to-end with:
  - Mock S3       → in-memory, reads processed_data_example.json from disk
  - Mock MongoDB  → in-memory Python dicts (no Atlas needed)
  - Mock MCP Server → called directly as Python functions (no HTTP server needed)
  - Ollama AI     → gemma4:12b-mlx via local HTTP API (replaces Bedrock)
  - Real validation, persistence logic, source hash, lock mechanism

Usage:
  cd scripts/AWS/ShorTED/Lambda/Orchestrator
  python test_local_full.py

Requirements: only 'requests' (already installed), no AWS, no MongoDB, no MCP server running.
"""

import hashlib
import json
import logging
import os
import re
import sys
import time
from copy import deepcopy
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import Any, Optional
from urllib.parse import urlparse, urlencode, urlunparse, parse_qs

import requests

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("shorted.test")

# ── Paths ─────────────────────────────────────────────────────────────────────
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_THIS_DIR, "..", "..", "..", "..", ".."))

# Look for processed_data_example.json in several locations
_EXAMPLE_PATHS = [
    os.path.join(_THIS_DIR, "processed_data_example.json"),
    os.path.join(_REPO_ROOT, "data", "processed_data_example.json"),
    os.path.join(_REPO_ROOT, "docs", "ai_pipeline", "processed_data_example.json"),
    os.path.join(_THIS_DIR, "..", "..", "..", "data", "processed_data_example.json"),
]

# ── Config ────────────────────────────────────────────────────────────────────
OLLAMA_BASE_URL   = "http://localhost:11434"
OLLAMA_MODEL      = "gemma4:12b-mlx"
PIPELINE_VERSION  = "v1"
DEFAULT_LANGUAGE  = "en"
MIN_SNACKS        = 4
MAX_SNACKS        = 8
LOCK_TTL_SECONDS  = 900
MAX_TOOL_LOOPS    = 25
MIN_TAGS          = 3
MAX_TAGS          = 6
MAX_QUOTE_CHARS   = 180
MAX_MOTIVATIONAL_CHARS = 500
MAX_APHORISM_CHARS = 100
MIN_SEG_DURATION  = 20
MAX_SEG_DURATION  = 150
MIN_DISTANCE      = 45


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — MOCK DATA
# ══════════════════════════════════════════════════════════════════════════════

MOCK_PROCESSED_JSON = {
    "id": 42,
    "title": "How to Build a Second Brain",
    "slug": "tiago_forte_second_brain",
    "url": "https://www.ted.com/talks/tiago_forte_second_brain",
    "duration": 1080,
    "tags": ["productivity", "knowledge-management", "creativity", "learning", "technology"],
    "related_videos": [1, 3],
    "presenterDisplayName": "Tiago Forte",
    "speakers": ["Tiago Forte"],
    "image": "https://pi.tedcdn.com/r/talkstar-photos.s3.amazonaws.com/uploads/second_brain.jpg",
    "transcriptions": {
        "en": {
            "language": "English",
            "sentences": [
                {"timestamp": "0",    "text": "We are living through an explosion of information."},
                {"timestamp": "5000", "text": "The average person consumes 34 gigabytes of data every single day."},
                {"timestamp": "12000","text": "And yet, despite having access to more information than any human in history, most people feel overwhelmed, not empowered."},
                {"timestamp": "22000","text": "What if I told you the problem isn't the information itself, but how we're trying to manage it?"},
                {"timestamp": "32000","text": "For the last decade, I've been obsessed with one question: how do we think better?"},
                {"timestamp": "42000","text": "I've studied the notebooks of Leonardo da Vinci, the commonplace books of historical figures, and the personal knowledge systems of the world's most creative people."},
                {"timestamp": "58000","text": "And I discovered something surprising: the most prolific creators throughout history didn't rely solely on their biological brain."},
                {"timestamp": "70000","text": "They offloaded their thinking onto an external system — a second brain."},
                {"timestamp": "80000","text": "A second brain is a trusted system outside your head where you capture, organise, and retrieve your most valuable ideas and insights."},
                {"timestamp": "95000","text": "The key insight is that your brain is for having ideas, not for storing them."},
                {"timestamp": "108000","text": "Every time you try to remember something instead of writing it down, you're using up cognitive resources that could be spent on creativity."},
                {"timestamp": "122000","text": "There are four essential capabilities that a second brain gives you: remembering, connecting, creating, and sharing."},
                {"timestamp": "138000","text": "Remembering means capturing ideas before they disappear — a quote that moved you, an insight from a podcast, a solution you found to a recurring problem."},
                {"timestamp": "155000","text": "Connecting means linking ideas across different domains to generate new insights you couldn't have reached by staying in one silo."},
                {"timestamp": "172000","text": "The magic happens at the intersection of disciplines — when a concept from biology illuminates a problem in business, or when a design principle solves an engineering challenge."},
                {"timestamp": "190000","text": "Creating means using your accumulated knowledge as the raw material for new work — writing, presenting, building, teaching."},
                {"timestamp": "205000","text": "And sharing means turning your private knowledge into public value that helps others."},
                {"timestamp": "218000","text": "I call this system CODE: Capture, Organise, Distil, Express."},
                {"timestamp": "228000","text": "Capture: save only what resonates with you, what surprises you, what challenges your assumptions."},
                {"timestamp": "242000","text": "Organise: not by topic, but by project — by where you're going to use the information, not where it came from."},
                {"timestamp": "258000","text": "Distil: progressively summarise your notes so future you can quickly find the key insights without re-reading everything."},
                {"timestamp": "272000","text": "Express: turn your knowledge into creative output — don't just consume, produce."},
                {"timestamp": "285000","text": "The most important thing I've learned is that knowledge only becomes truly valuable when it's expressed and shared."},
                {"timestamp": "298000","text": "Building a second brain is not about technology — it's about developing a relationship with your own thinking."},
                {"timestamp": "312000","text": "Start small. Pick one idea that resonated with you today, capture it somewhere outside your head, and see what happens."},
                {"timestamp": "325000","text": "Because when you build a system to think better, you don't just become more productive — you become more creative, more intentional, and ultimately, more human."},
            ],
            "raw": (
                "We are living through an explosion of information. "
                "The average person consumes 34 gigabytes of data every single day. "
                "And yet, despite having access to more information than any human in history, most people feel overwhelmed, not empowered. "
                "What if I told you the problem isn't the information itself, but how we're trying to manage it? "
                "For the last decade, I've been obsessed with one question: how do we think better? "
                "I've studied the notebooks of Leonardo da Vinci, the commonplace books of historical figures, "
                "and the personal knowledge systems of the world's most creative people. "
                "And I discovered something surprising: the most prolific creators throughout history didn't rely solely on their biological brain. "
                "They offloaded their thinking onto an external system — a second brain. "
                "A second brain is a trusted system outside your head where you capture, organise, and retrieve your most valuable ideas and insights. "
                "The key insight is that your brain is for having ideas, not for storing them. "
                "Every time you try to remember something instead of writing it down, you're using up cognitive resources that could be spent on creativity. "
                "There are four essential capabilities that a second brain gives you: remembering, connecting, creating, and sharing. "
                "Remembering means capturing ideas before they disappear — a quote that moved you, an insight from a podcast, a solution you found to a recurring problem. "
                "Connecting means linking ideas across different domains to generate new insights you couldn't have reached by staying in one silo. "
                "The magic happens at the intersection of disciplines — when a concept from biology illuminates a problem in business, or when a design principle solves an engineering challenge. "
                "Creating means using your accumulated knowledge as the raw material for new work — writing, presenting, building, teaching. "
                "And sharing means turning your private knowledge into public value that helps others. "
                "I call this system CODE: Capture, Organise, Distil, Express. "
                "Capture: save only what resonates with you, what surprises you, what challenges your assumptions. "
                "Organise: not by topic, but by project — by where you're going to use the information, not where it came from. "
                "Distil: progressively summarise your notes so future you can quickly find the key insights without re-reading everything. "
                "Express: turn your knowledge into creative output — don't just consume, produce. "
                "The most important thing I've learned is that knowledge only becomes truly valuable when it's expressed and shared. "
                "Building a second brain is not about technology — it's about developing a relationship with your own thinking. "
                "Start small. Pick one idea that resonated with you today, capture it somewhere outside your head, and see what happens. "
                "Because when you build a system to think better, you don't just become more productive — you become more creative, more intentional, and ultimately, more human."
            ),
        }
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — IN-MEMORY MOCK MONGODB
# ══════════════════════════════════════════════════════════════════════════════

class _MockCollection:
    """Minimal in-memory MongoDB collection mock."""

    def __init__(self, name: str):
        self.name = name
        self._docs: dict[str, dict] = {}

    def find_one(self, query: dict, projection: dict | None = None) -> Optional[dict]:
        for doc in self._docs.values():
            if _matches(doc, query):
                return _project(deepcopy(doc), projection)
        return None

    def find(self, query: dict, projection: dict | None = None):
        results = [_project(deepcopy(d), projection) for d in self._docs.values() if _matches(d, query)]
        return _MockCursor(results)

    def find_one_and_update(self, query: dict, update: dict, upsert: bool = False, return_document: bool = True) -> Optional[dict]:
        for key, doc in self._docs.items():
            if _matches(doc, query):
                _apply_set(doc, update.get("$set", {}))
                return deepcopy(doc)
        if upsert:
            new_doc = {}
            _apply_set(new_doc, update.get("$set", {}))
            doc_id = new_doc.get("_id") or new_doc.get("slug", f"__new_{len(self._docs)}")
            new_doc["_id"] = doc_id
            self._docs[doc_id] = new_doc
            return deepcopy(new_doc)
        return None

    def update_one(self, query: dict, update: dict, upsert: bool = False) -> None:
        for doc in self._docs.values():
            if _matches(doc, query):
                _apply_set(doc, update.get("$set", {}))
                return
        if upsert:
            new_doc = {}
            _apply_set(new_doc, update.get("$set", {}))
            doc_id = new_doc.get("_id") or f"__upsert_{len(self._docs)}"
            new_doc.setdefault("_id", doc_id)
            self._docs[doc_id] = new_doc

    def delete_many(self, query: dict):
        to_delete = [k for k, d in self._docs.items() if _matches(d, query)]
        for k in to_delete:
            del self._docs[k]
        return type("R", (), {"deleted_count": len(to_delete)})()

    def insert_many(self, docs: list[dict], ordered: bool = True) -> None:
        for doc in docs:
            doc_id = doc.get("_id", f"__auto_{len(self._docs)}")
            if doc_id in self._docs:
                raise _DuplicateKeyError(f"Duplicate key: {doc_id}")
            doc["_id"] = doc_id
            self._docs[doc_id] = deepcopy(doc)

    def count_documents(self, query: dict) -> int:
        return sum(1 for d in self._docs.values() if _matches(d, query))

    def all_docs(self) -> list[dict]:
        return list(self._docs.values())


class _DuplicateKeyError(Exception):
    pass


class _MockCursor:
    def __init__(self, docs: list):
        self._docs = docs

    def limit(self, n: int):
        self._docs = self._docs[:n]
        return self

    def to_list(self, length: int | None = None):
        return self._docs[:length] if length else self._docs

    def __iter__(self):
        return iter(self._docs)


def _matches(doc: dict, query: dict) -> bool:
    """Simple query matcher supporting $or, $in, $lt, $ne, $nin."""
    for key, value in query.items():
        if key == "$or":
            if not any(_matches(doc, cond) for cond in value):
                return False
        elif isinstance(value, dict):
            doc_val = doc.get(key)
            for op, op_val in value.items():
                if op == "$in" and doc_val not in op_val:
                    return False
                elif op == "$nin" and doc_val in op_val:
                    return False
                elif op == "$lt" and (doc_val is None or doc_val >= op_val):
                    return False
                elif op == "$gt" and (doc_val is None or doc_val <= op_val):
                    return False
                elif op == "$ne" and doc_val == op_val:
                    return False
                elif op == "$gte" and (doc_val is None or doc_val < op_val):
                    return False
        else:
            if doc.get(key) != value:
                return False
    return True


def _apply_set(doc: dict, updates: dict) -> None:
    doc.update(updates)


def _project(doc: dict, projection: dict | None) -> dict:
    if not projection:
        return doc
    result = {}
    include = {k for k, v in projection.items() if v}
    exclude = {k for k, v in projection.items() if not v}
    if include:
        result = {k: v for k, v in doc.items() if k in include or k == "_id"}
    else:
        result = {k: v for k, v in doc.items() if k not in exclude}
    return result


# Create the in-memory database
_mock_db = {
    "talks": _MockCollection("talks"),
    "snacks": _MockCollection("snacks"),
}


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — MCP TOOLS (called directly as Python functions, no HTTP)
# ══════════════════════════════════════════════════════════════════════════════

TAG_ALIAS_MAP = {
    "artificial intelligence": "ai",
    "artificial-intelligence": "ai",
    "machine learning": "machine-learning",
    "machine-learning": "machine-learning",
    "self improvement": "self-improvement",
    "self-improvement": "self-improvement",
    "knowledge management": "knowledge-management",
    "knowledge-management": "knowledge-management",
    "ted": "", "tedx": "", "talk": "", "speaker": "",
}


def mcp_get_snack_schema() -> str:
    return json.dumps({
        "required": ["segmentId", "talkId", "talkSlug", "speaker", "talkTitle",
                     "topic", "quote", "motivationalText", "aphorism", "tags", "score", "startTime",
                     "endTime", "talkUrl", "language"],
        "constraints": {
            "quote": f"max {MAX_QUOTE_CHARS} chars, grounded in transcript",
            "motivationalText": {
                "type": "string",
                "description": f"max {MAX_MOTIVATIONAL_CHARS} chars, no invented facts, must be motivational text"
            },
            "aphorism": {
                "type": "string",
                "description": f"max {MAX_APHORISM_CHARS} chars, short punchy catchphrase"
            },
            "tags": f"{MIN_TAGS}-{MAX_TAGS} canonical lowercase hyphenated tags",
            "score": "float in [0.0, 1.0]",
            "segmentId": "unique, format: seg_001",
        }
    }, indent=2)


def mcp_get_mixer_rules() -> str:
    return json.dumps({
        "minSnacks": MIN_SNACKS, "maxSnacks": MAX_SNACKS,
        "minSegmentDurationSeconds": MIN_SEG_DURATION,
        "maxSegmentDurationSeconds": MAX_SEG_DURATION,
        "minDistanceBetweenSnacksSeconds": MIN_DISTANCE,
        "maxQuoteChars": MAX_QUOTE_CHARS, "maxMotivationalChars": MAX_MOTIVATIONAL_CHARS,
        "maxAphorismChars": MAX_APHORISM_CHARS,
        "minTags": MIN_TAGS, "maxTags": MAX_TAGS,
    }, indent=2)


def mcp_get_grounding_rules() -> str:
    return (
        "1. Quotes must be exact or near-exact excerpts from the transcript.\n"
        "2. Do not invent facts not present in the transcript.\n"
        "3. Summary must not introduce claims absent from the transcript.\n"
        "4. Topic must be specific, not generic like 'Main theme'.\n"
        "5. Prefer self-contained segments.\n"
        "6. Avoid generic motivational statements without substance.\n"
    )


def mcp_get_existing_snacks(talk_slug: str, language: str | None = None, limit: int = 20) -> list:
    query = {"talkSlug": talk_slug}
    if language:
        query["language"] = language
    return _mock_db["snacks"].find(query).limit(limit).to_list()


def mcp_validate_snack_candidate(snack: dict) -> dict:
    errors, warnings = [], []
    required = ["segmentId", "talkSlug", "speaker", "talkTitle",
                 "topic", "quote", "motivationalText", "aphorism", "tags", "score",
                 "startTime", "endTime", "talkUrl", "language"]
    for f in required:
        v = snack.get(f)
        if v is None:
            errors.append({"field": f, "message": "missing"})
        elif isinstance(v, str) and not v.strip():
            errors.append({"field": f, "message": "empty"})
    if errors:
        return {"valid": False, "errors": errors, "warnings": warnings}

    score = snack.get("score", 0)
    if not (0.0 <= float(score) <= 1.0):
        errors.append({"field": "score", "message": f"must be in [0,1], got {score}"})

    start, end = snack.get("startTime", 0), snack.get("endTime", 0)
    if start < 0:
        errors.append({"field": "startTime", "message": "must be >= 0"})
    if end <= start:
        errors.append({"field": "endTime", "message": f"must be > startTime ({start})"})

    quote = snack.get("quote", "")
    if len(quote) > MAX_QUOTE_CHARS:
        errors.append({"field": "quote", "message": f"exceeds {MAX_QUOTE_CHARS} chars"})

    tags = snack.get("tags", [])
    if not isinstance(tags, list) or not tags:
        errors.append({"field": "tags", "message": "must be non-empty list"})
    elif not (MIN_TAGS <= len(tags) <= MAX_TAGS):
        errors.append({"field": "tags", "message": f"count {len(tags)} not in [{MIN_TAGS},{MAX_TAGS}]"})

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}


def mcp_validate_snack_candidates(snacks_list: list) -> dict:
    return {"results": [mcp_validate_snack_candidate(s) for s in snacks_list]}


def mcp_validate_final_snack_set(snacks_list: list) -> dict:
    errors, warnings = [], []
    n = len(snacks_list)
    if not (MIN_SNACKS <= n <= MAX_SNACKS):
        errors.append({"field": "count", "message": f"count {n} not in [{MIN_SNACKS},{MAX_SNACKS}]"})
    seen_ids, seen_quotes = set(), set()
    for i, s in enumerate(snacks_list):
        r = mcp_validate_snack_candidate(s)
        errors.extend([{"field": f"[{i}].{e['field']}", "message": e["message"]} for e in r["errors"]])
        sid = s.get("segmentId", "")
        if sid in seen_ids:
            errors.append({"field": "segmentId", "message": f"duplicate: {sid}"})
        seen_ids.add(sid)
        q = s.get("quote", "").lower().strip()
        if q and q in seen_quotes:
            errors.append({"field": "quote", "message": f"duplicate quote: {q[:50]}…"})
        seen_quotes.add(q)
    scores = [float(s.get("score", 0)) for s in snacks_list if isinstance(s.get("score"), (int, float))]
    return {
        "valid": len(errors) == 0, "errors": errors, "warnings": warnings,
        "stats": {"count": n, "minScore": min(scores, default=None), "maxScore": max(scores, default=None)},
    }


def mcp_find_similar_snacks(talk_slug: str, candidate_snacks: list) -> dict:
    def sim(a, b):
        if a.get("topic", "").lower().strip() == b.get("topic", "").lower().strip():
            return True, "same_topic"
        r = SequenceMatcher(None, a.get("quote", "").lower(), b.get("quote", "").lower()).ratio()
        if r >= 0.85:
            return True, f"similar_quote ({r:.2f})"
        if abs(a.get("startTime", 0) - b.get("startTime", 0)) < MIN_DISTANCE:
            return True, "time_overlap"
        return False, ""
    intra = []
    for i in range(len(candidate_snacks)):
        for j in range(i + 1, len(candidate_snacks)):
            s, reason = sim(candidate_snacks[i], candidate_snacks[j])
            if s:
                intra.append({"indexA": i, "indexB": j,
                               "segmentIdA": candidate_snacks[i].get("segmentId"),
                               "segmentIdB": candidate_snacks[j].get("segmentId"),
                               "reason": reason})
    existing = mcp_get_existing_snacks(talk_slug)
    cross = []
    for i, c in enumerate(candidate_snacks):
        for e in existing:
            s, reason = sim(c, e)
            if s:
                cross.append({"candidateIndex": i, "existingSegmentId": e.get("segmentId"), "reason": reason})
                break
    return {"intraBatchDuplicates": intra, "crossDbDuplicates": cross, "hasDuplicates": bool(intra or cross)}


def mcp_canonicalize_tags(tags: list) -> list:
    result, seen = [], set()
    for tag in tags:
        n = tag.strip().lower()
        alias = TAG_ALIAS_MAP.get(n)
        if alias is not None:
            canonical = alias
        else:
            n = re.sub(r'\s+', '-', n)
            n = re.sub(r'[^a-z0-9-]', '', n)
            n = re.sub(r'-+', '-', n).strip('-')
            canonical = TAG_ALIAS_MAP.get(n, n)
        if canonical and canonical not in seen:
            seen.add(canonical)
            result.append(canonical)
    return sorted(result)


def mcp_build_talk_url(base_url: str, start_time: int) -> str:
    parsed = urlparse(base_url)
    params = parse_qs(parsed.query)
    params["t"] = [str(start_time)]
    new_query = urlencode({k: v[0] for k, v in params.items()})
    return urlunparse(parsed._replace(query=new_query))


# Tool dispatcher: maps tool_name → function
MCP_TOOLS = {
    "get_existing_snacks":         lambda args: mcp_get_existing_snacks(**args),
    "validate_snack_candidate":    lambda args: mcp_validate_snack_candidate(**args),
    "validate_snack_candidates":   lambda args: mcp_validate_snack_candidates(**args),
    "validate_final_snack_set":    lambda args: mcp_validate_final_snack_set(**args),
    "find_similar_snacks":         lambda args: mcp_find_similar_snacks(**args),
    "canonicalize_tags":           lambda args: mcp_canonicalize_tags(**args),
    "build_talk_url":              lambda args: mcp_build_talk_url(**args),
}


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — OLLAMA AI ORCHESTRATOR (replaces Bedrock Converse API)
# ══════════════════════════════════════════════════════════════════════════════

OLLAMA_TOOL_DEFINITIONS = [
    {"type": "function", "function": {"name": "get_existing_snacks",
      "description": "Return existing snack documents for a talk.",
      "parameters": {"type": "object",
        "properties": {"talk_slug": {"type": "string"}, "language": {"type": "string"}, "limit": {"type": "integer"}},
        "required": ["talk_slug"]}}},
    {"type": "function", "function": {"name": "validate_snack_candidate",
      "description": "Validate a single snack candidate. Returns {valid, errors, warnings}.",
      "parameters": {"type": "object",
        "properties": {"snack": {"type": "object", "description": "Snack candidate to validate"}},
        "required": ["snack"]}}},
    {"type": "function", "function": {"name": "validate_snack_candidates",
      "description": "Validate multiple snack candidates at once.",
      "parameters": {"type": "object",
        "properties": {"snacks_list": {"type": "array", "items": {"type": "object"}}},
        "required": ["snacks_list"]}}},
    {"type": "function", "function": {"name": "validate_final_snack_set",
      "description": "Validate the complete final snack set: count, spacing, duplicates, schema.",
      "parameters": {"type": "object",
        "properties": {"snacks_list": {"type": "array", "items": {"type": "object"}}},
        "required": ["snacks_list"]}}},
    {"type": "function", "function": {"name": "find_similar_snacks",
      "description": "Detect near-duplicate snacks using heuristics.",
      "parameters": {"type": "object",
        "properties": {
          "talk_slug": {"type": "string"},
          "candidate_snacks": {"type": "array", "items": {"type": "object"}}},
        "required": ["talk_slug", "candidate_snacks"]}}},
    {"type": "function", "function": {"name": "canonicalize_tags",
      "description": "Normalise tags: lowercase, hyphenate, alias map, deduplicate, sort.",
      "parameters": {"type": "object",
        "properties": {"tags": {"type": "array", "items": {"type": "string"}}},
        "required": ["tags"]}}},
    {"type": "function", "function": {"name": "build_talk_url",
      "description": "Build talk URL with timestamp: base_url?t=start_time",
      "parameters": {"type": "object",
        "properties": {"base_url": {"type": "string"}, "start_time": {"type": "integer"}},
        "required": ["base_url", "start_time"]}}},
]


def _ollama_chat(messages: list[dict], tools: list | None = None) -> dict:
    """Single Ollama /api/chat call."""
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
    }
    if tools:
        payload["tools"] = tools

    resp = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json=payload,
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json()


def build_orchestrator_prompt(ctx: dict) -> str:
    """Build the system + user prompt for snack generation."""
    sentences_text = "\n".join(
        f"  [{s['timestamp_ms'] // 1000}s] {s['text']}"
        for s in ctx["sentences"][:20]
    )
    if len(ctx["sentences"]) > 20:
        sentences_text += f"\n  … ({len(ctx['sentences']) - 20} more sentences)"

    # Inline schema/rules (instead of resource calls, to keep the prompt self-contained)
    schema = mcp_get_snack_schema()
    mixer  = mcp_get_mixer_rules()
    ground = mcp_get_grounding_rules()

    return f"""You are the ShorTED AI Orchestrator.

TASK: Transform this TED talk into {MIN_SNACKS}–{MAX_SNACKS} high-quality snack documents.

TALK METADATA:
- Title: {ctx['title']}
- Speaker: {ctx['speaker']}
- Talk ID: {ctx['talk_id']}
- Slug: {ctx['slug']}
- Language: {ctx['language']}
- Duration: {ctx['duration']} seconds
- URL: {ctx['url']}

TRANSCRIPT (key sentences with timestamps):
{sentences_text}

FULL TRANSCRIPT:
{ctx['raw_transcript']}

SNACK SCHEMA:
{schema}

MIXER RULES (MUST be respected):
{mixer}

GROUNDING RULES:
{ground}

MANDATORY TOOL SEQUENCE (call in this order):
1. Apply tag rules using canonicalize_tags.
2. For each candidate: generate segmentId, topic, quote, motivationalText, aphorism, tags, score, startTime, endTime, talkUrl
3. Validate batch using validate_snack_candidates.
4. find_similar_snacks to remove near-duplicates
5. validate_final_snack_set on your final selection

HARD CONSTRAINTS:
- segmentId must be unique, format: seg_001, seg_002, ...
- talkSlug in every snack MUST be exactly: {ctx['slug']}
- language in every snack MUST be: {ctx['language']}
- talkId in every snack MUST be: {ctx['talk_id']}
- speaker in every snack MUST be: {ctx['speaker']}
- Quotes MUST be from the transcript above (exact or near-exact)
- After all tool calls, return ONLY valid JSON, no markdown, no explanation

OUTPUT JSON SCHEMA:
{{
  "talk": {{"talkId":"...","slug":"...","title":"...","speaker":"...","speakers":["..."],"url":"...","duration":0,"imageUrl":"...","sourceTags":["..."],"language":"..."}},
  "final_snacks": [
    {{"segmentId":"seg_001","talkId":"...","talkSlug":"...","speaker":"...","talkTitle":"...","topic":"...","quote":"...","motivationalText":"...","aphorism":"...","tags":["..."],"score":0.9,"startTime":0,"endTime":60,"talkUrl":"...","language":"..."}}
  ],
  "processing_report": {{"candidateSegments":0,"candidateSnacks":0,"finalSnacks":0,"mcpToolsUsed":["..."],"warnings":[],"status":"completed"}}
}}"""


def run_ollama_orchestrator(ctx: dict) -> dict:
    """
    Run the Ollama tool-use loop to generate snacks.
    Returns the parsed AI result dict.
    """
    system_prompt = build_orchestrator_prompt(ctx)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": (
            f"Generate {MIN_SNACKS}–{MAX_SNACKS} snacks for the talk '{ctx['title']}'. "
            "Use the mandatory tool sequence, then return the final JSON."
        )},
    ]
    tools_used = []
    in_tokens = 0
    out_tokens = 0

    logger.info("Starting Ollama tool-use loop (model: %s)", OLLAMA_MODEL)

    for loop_idx in range(MAX_TOOL_LOOPS):
        logger.info("  Loop iteration %d/%d …", loop_idx + 1, MAX_TOOL_LOOPS)
        response = _ollama_chat(messages, tools=OLLAMA_TOOL_DEFINITIONS)
        
        in_tokens += response.get("prompt_eval_count", 0)
        out_tokens += response.get("eval_count", 0)

        msg = response.get("message", {})
        role = msg.get("role", "assistant")
        content = msg.get("content") or ""
        tool_calls = msg.get("tool_calls", [])

        messages.append({"role": role, "content": content, "tool_calls": tool_calls})

        if tool_calls:
            # Execute each tool call
            for tc in tool_calls:
                fn = tc.get("function", {})
                tool_name = fn.get("name", "")
                tool_args = fn.get("arguments", {})

                logger.info("    🔧 MCP tool: %s(%s)", tool_name,
                            str(tool_args)[:80].replace('\n', ' '))

                if tool_name not in tools_used:
                    tools_used.append(tool_name)

                dispatcher = MCP_TOOLS.get(tool_name)
                if dispatcher:
                    try:
                        result = dispatcher(tool_args)
                    except Exception as e:
                        result = {"error": str(e)}
                else:
                    result = {"error": f"Unknown tool: {tool_name}"}

                # Feed result back
                messages.append({
                    "role": "tool",
                    "content": json.dumps(result, ensure_ascii=False),
                })
            continue

        # No tool calls — model might be returning final JSON or just talking
        if content:
            if "final_snacks" in content:
                logger.info("  Model returned final response (loop %d)", loop_idx + 1)
                logger.info("  📊 Token usage (Ollama estimation): %d input, %d output", in_tokens, out_tokens)
                parsed_data = _parse_model_output(content, ctx, tools_used)
                parsed_data["processing_report"]["tokenUsage"] = {
                    "inputTokens": in_tokens,
                    "outputTokens": out_tokens,
                    "totalTokens": in_tokens + out_tokens
                }
                return parsed_data
            else:
                logger.warning("  Model returned text but no tool calls and no final_snacks. Prompting it to continue.")
                messages.append({"role": "user", "content": "You didn't call any tool and didn't output the final JSON with 'final_snacks'. Please either call a tool or provide the final JSON output."})
                continue

        # Empty response — ask again
        messages.append({"role": "user", "content": "Please return the final JSON now."})

    raise ValueError(f"Exceeded max tool loops ({MAX_TOOL_LOOPS}) without final JSON")


def _parse_model_output(text: str, ctx: dict, tools_used: list) -> dict:
    """Extract and parse JSON from model output."""
    # Try markdown code fence first
    fence = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    json_text = fence.group(1) if fence else text

    # Fallback: find outermost { ... } that looks like our final schema
    if not fence:
        # We know the final JSON starts with "talk" or "final_snacks"
        # but simple regex `{.*}` might capture across multiple independent dicts.
        # We can try to find the start of the actual root object.
        match = re.search(r'\{\s*"(?:talk|final_snacks)"\s*:.*\}', json_text, re.DOTALL)
        if match:
            json_text = match.group(0)
        else:
            # Last resort
            brace = re.search(r'\{.*\}', json_text, re.DOTALL)
            if brace:
                json_text = brace.group(0)

    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Cannot parse JSON from model output: {e}\nText: {text[:500]}")

    if "final_snacks" not in data:
        raise ValueError(f"Model output missing 'final_snacks'. Keys: {list(data.keys())}")

    # Merge actual tools_used into report
    report = data.get("processing_report", {})
    if isinstance(report, dict):
        report["mcpToolsUsed"] = list(set(tools_used + report.get("mcpToolsUsed", [])))

    data["processing_report"] = report
    return data


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — PIPELINE STAGES (using mocked services)
# ══════════════════════════════════════════════════════════════════════════════

def load_processed_json() -> dict:
    """Load processed JSON — from disk if available, otherwise use built-in mock."""
    for path in _EXAMPLE_PATHS:
        if os.path.exists(path):
            logger.info("Loading processed JSON from disk: %s", path)
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    logger.info("No processed_data_example.json found — using built-in mock data")
    return MOCK_PROCESSED_JSON


def build_ai_context(processed_json: dict, preferred_language: str = "en") -> dict:
    """Build AI context from processed JSON."""
    transcriptions = processed_json["transcriptions"]

    # Language selection
    if preferred_language in transcriptions:
        language = preferred_language
    elif "en" in transcriptions:
        language = "en"
        logger.warning("Language '%s' not found, falling back to 'en'", preferred_language)
    else:
        language = list(transcriptions.keys())[0]
        logger.warning("Using first available language: '%s'", language)

    trans = transcriptions[language]
    sentences = [
        {"timestamp_ms": int(s.get("timestamp", 0)), "text": s["text"].strip()}
        for s in trans.get("sentences", [])
        if s.get("text", "").strip()
    ]
    raw = trans.get("raw", "").strip() or " ".join(s["text"] for s in sentences)

    speakers = processed_json.get("speakers") or []
    speaker = processed_json.get("presenterDisplayName") or (speakers[0] if speakers else "Unknown")

    return {
        "talk_id": str(processed_json.get("id", "")),
        "slug": processed_json["slug"],
        "title": processed_json["title"],
        "speaker": speaker,
        "speakers": speakers,
        "url": processed_json.get("url", ""),
        "duration": int(processed_json.get("duration", 0)),
        "image_url": processed_json.get("image", ""),
        "source_tags": processed_json.get("tags") or [],
        "language": language,
        "sentences": sentences,
        "raw_transcript": raw,
    }


def compute_source_hash(ctx: dict) -> str:
    payload = {
        "slug": ctx["slug"], "title": ctx["title"],
        "speakers": sorted(ctx["speakers"]),
        "language": ctx["language"], "raw": ctx["raw_transcript"],
        "tags": sorted(ctx["source_tags"]), "duration": ctx["duration"],
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def should_skip(ctx: dict, source_hash: str) -> tuple[bool, str]:
    """Check if AI processing can be skipped."""
    talk = _mock_db["talks"].find_one({
        "slug": ctx["slug"], "language": ctx["language"],
        "aiPipelineVersion": PIPELINE_VERSION, "sourceHash": source_hash,
        "processingStatus": "completed",
    })
    if not talk:
        return False, "not_found"
    count = _mock_db["snacks"].count_documents({
        "talkSlug": ctx["slug"], "language": ctx["language"],
        "aiPipelineVersion": PIPELINE_VERSION, "sourceHash": source_hash,
    })
    if count >= MIN_SNACKS:
        return True, "already_completed"
    return False, "insufficient_snacks"


def acquire_lock(ctx: dict, source_hash: str) -> bool:
    """Try to acquire processing lock."""
    now = datetime.utcnow()
    lock_expires = now + timedelta(seconds=LOCK_TTL_SECONDS)
    result = _mock_db["talks"].find_one_and_update(
        {
            "slug": ctx["slug"], "language": ctx["language"],
            "$or": [
                {"processingStatus": {"$in": [None, "failed"]}},
                {"processingStatus": "processing", "lockExpiresAt": {"$lt": now}},
                {"aiPipelineVersion": {"$ne": PIPELINE_VERSION}},
                {"sourceHash": {"$ne": source_hash}},
            ],
        },
        {"$set": {
            "processingStatus": "processing",
            "lockExpiresAt": lock_expires,
            "processingStartedAt": now,
            "aiPipelineVersion": PIPELINE_VERSION,
            "sourceHash": source_hash,
            "language": ctx["language"], "slug": ctx["slug"],
        }},
        upsert=True,
    )
    return result is not None


def validate_final_output(ai_result: dict, ctx: dict) -> list[str]:
    """Deterministic final validation. Returns list of errors (empty = OK)."""
    errors = []
    snacks = ai_result.get("final_snacks", [])
    if not snacks:
        return ["final_snacks is empty"]
    n = len(snacks)
    if not (MIN_SNACKS <= n <= MAX_SNACKS):
        errors.append(f"Snack count {n} not in [{MIN_SNACKS},{MAX_SNACKS}]")
    seen_ids = set()
    def validate_snack(s, p):
        for f in ["segmentId", "quote", "motivationalText", "aphorism", "topic", "talkUrl", "language"]:
            if not str(s.get(f, "")).strip():
                errors.append(f"{p}.{f} is empty")
        if s.get("talkSlug") != ctx["slug"]:
            errors.append(f"{p}.talkSlug mismatch: {s.get('talkSlug')} != {ctx['slug']}")
        if s.get("language") != ctx["language"]:
            errors.append(f"{p}.language mismatch: {s.get('language')} != {ctx['language']}")
        start, end = s.get("startTime", 0), s.get("endTime", 0)
        if start < 0: errors.append(f"{p}.startTime < 0")
        if end <= start: errors.append(f"{p}.endTime <= startTime")
        score = s.get("score", -1)
        if not (0.0 <= float(score) <= 1.0): errors.append(f"{p}.score {score} not in [0,1]")
        sid = s.get("segmentId", "")
        if sid in seen_ids: errors.append(f"{p}.segmentId duplicate: {sid}")
        seen_ids.add(sid)

    for i, s in enumerate(snacks):
        validate_snack(s, f"snacks[{i}]")

    return errors


def persist(ctx: dict, ai_result: dict, source_hash: str) -> None:
    """Save snacks and talk to mock MongoDB."""
    now = datetime.utcnow()
    slug, language = ctx["slug"], ctx["language"]

    # Delete old snacks
    deleted = _mock_db["snacks"].delete_many({
        "talkSlug": slug, "language": language,
        "aiPipelineVersion": PIPELINE_VERSION, "sourceHash": source_hash,
    })
    if deleted.deleted_count > 0:
        logger.info("Deleted %d old snacks", deleted.deleted_count)

    # Insert new snacks
    snack_docs = [
        {
            "_id": f"{slug}:{language}:{PIPELINE_VERSION}:{s['segmentId']}",
            **s,
            "aiPipelineVersion": PIPELINE_VERSION,
            "sourceHash": source_hash,
            "createdAt": now.isoformat(),
        }
        for s in ai_result["final_snacks"]
    ]
    _mock_db["snacks"].insert_many(snack_docs)
    logger.info("Inserted %d snacks", len(snack_docs))

    # Upsert talk
    _mock_db["talks"].update_one(
        {"slug": slug, "language": language},
        {"$set": {
            "talkId": ctx["talk_id"], "slug": slug, "title": ctx["title"],
            "speaker": ctx["speaker"], "speakers": ctx["speakers"],
            "url": ctx["url"], "duration": ctx["duration"],
            "imageUrl": ctx["image_url"], "sourceTags": ctx["source_tags"],
            "language": language, "aiPipelineVersion": PIPELINE_VERSION,
            "sourceHash": source_hash, "processingStatus": "completed",
            "snackCount": len(ai_result["final_snacks"]),
            "processedAt": now.isoformat(), "lockExpiresAt": None, "lastError": None,
        }},
        upsert=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — TEST RUNNER
# ══════════════════════════════════════════════════════════════════════════════

def print_section(title: str) -> None:
    print(f"\n{'═' * 60}")
    print(f"  {title}")
    print('═' * 60)


def print_result(label: str, value, ok: bool | None = None) -> None:
    icon = {True: "✅", False: "❌", None: "ℹ️ "}[ok]
    print(f"  {icon} {label}: {value}")


def run_pipeline(processed_json: dict, run_label: str) -> bool:
    """Run the full pipeline for one processed talk. Returns True on success."""
    print_section(f"{run_label}")
    logger.info("=== %s ===", run_label)

    # Step 1: Build context
    ctx = build_ai_context(processed_json)
    source_hash = compute_source_hash(ctx)
    print_result("Talk", f"'{ctx['title']}' by {ctx['speaker']}", None)
    print_result("Language", ctx["language"], None)
    print_result("Source hash", source_hash[:16] + "…", None)
    print_result("Sentences", f"{len(ctx['sentences'])} loaded", None)

    # Step 2: Skip check
    skip, reason = should_skip(ctx, source_hash)
    print_result("Skip check", f"{skip} (reason: {reason})", skip is False or None)
    if skip:
        logger.info("Skipping — already completed")
        return True

    # Step 3: Acquire lock
    locked = acquire_lock(ctx, source_hash)
    print_result("Lock acquired", locked, locked)
    if not locked:
        logger.warning("Could not acquire lock")
        return False

    # Step 4: AI Orchestrator (Ollama)
    print(f"\n  🤖 Calling Ollama ({OLLAMA_MODEL}) …")
    t0 = time.time()
    try:
        ai_result = run_ollama_orchestrator(ctx)
    except Exception as e:
        print_result("AI Orchestrator", f"FAILED: {e}", False)
        logger.exception("Ollama orchestrator failed")
        return False
    elapsed = time.time() - t0
    print_result("AI Orchestrator", f"completed in {elapsed:.1f}s", True)
    print_result("Snacks returned", len(ai_result.get("final_snacks", [])), None)
    print_result("MCP tools used", ai_result.get("processing_report", {}).get("mcpToolsUsed", []), None)

    # Step 5: Final validation
    errors = validate_final_output(ai_result, ctx)
    if errors:
        print_result("Final validation", f"FAILED ({len(errors)} errors)", False)
        for e in errors[:5]:
            print(f"    • {e}")
        return False
    print_result("Final validation", "passed", True)

    # Step 6: Persist
    persist(ctx, ai_result, source_hash)
    print_result("MongoDB persist", "done", True)

    return True


def run_idempotency_check(processed_json: dict) -> bool:
    """Run the pipeline a second time and verify it skips."""
    print_section("RUN 2 — Idempotency check (should SKIP)")
    ctx = build_ai_context(processed_json)
    source_hash = compute_source_hash(ctx)
    skip, reason = should_skip(ctx, source_hash)
    print_result("Skip triggered", f"{skip} (reason: {reason})", skip)
    return skip


def print_db_summary(run_path: str | None = None, report_path: str | None = None) -> None:
    """Print what's in the mock MongoDB and show saved file paths."""
    print_section("Mock MongoDB contents")
    talks = _mock_db["talks"].all_docs()
    snacks = _mock_db["snacks"].all_docs()
    print(f"\n  📄 talks collection: {len(talks)} document(s)")
    for t in talks:
        print(f"    • slug={t.get('slug')} | status={t.get('processingStatus')} | snackCount={t.get('snackCount')}")

    print(f"\n  🍿 snacks collection: {len(snacks)} document(s)")
    for s in sorted(snacks, key=lambda s: s.get("startTime", 0)):
        score = f"{s.get('score', 0):.2f}"
        print(f"    • [{s.get('segmentId')}] score={score} | {s.get('startTime')}s–{s.get('endTime')}s | \"{s.get('topic', '')[:50]}\"")

    if run_path:
        print(f"\n  💾 Output salvato in:")
        print(f"    • {run_path}")
        print(f"    • {report_path}")
    print()


def save_test_output(processed_json: dict, ai_result: dict, source_hash: str, elapsed: float) -> str:
    """
    Save the full test output to test_output/ in the production-compatible format.

    Files saved:
      test_output/<slug>_<timestamp>_run.json    ← full structured output (talk + snacks)
      test_output/<slug>_<timestamp>_report.json ← processing report + test metadata

    Returns the output directory path.
    """
    out_dir = os.path.join(_THIS_DIR, "test_output")
    os.makedirs(out_dir, exist_ok=True)

    ctx = build_ai_context(processed_json)
    slug = ctx["slug"]
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    snacks = _mock_db["snacks"].all_docs()
    talk_doc = _mock_db["talks"].find_one({"slug": slug})

    # ── Full output (production-compatible format) ────────────────────────────
    run_output = {
        "_meta": {
            "generatedAt": datetime.now(tz=timezone.utc).isoformat(),
            "model": OLLAMA_MODEL,
            "pipelineVersion": PIPELINE_VERSION,
            "sourceHash": source_hash,
            "testMode": "local_mock",
        },
        "talk": {
            k: v for k, v in (talk_doc or {}).items()
            if k not in ("_id", "lockExpiresAt", "lastError")
        },
        "snacks": [
            {k: v for k, v in s.items() if k not in ("_id", "createdAt")}
            for s in sorted(snacks, key=lambda s: s.get("startTime", 0))
        ],
    }

    run_path = os.path.join(out_dir, f"{slug}_{ts}_run.json")
    with open(run_path, "w", encoding="utf-8") as f:
        json.dump(run_output, f, indent=2, ensure_ascii=False, default=str)

    # ── Processing report (test metadata + AI report) ─────────────────────────
    report_output = {
        "_meta": {
            "generatedAt": datetime.now(tz=timezone.utc).isoformat(),
            "model": OLLAMA_MODEL,
            "pipelineVersion": PIPELINE_VERSION,
            "elapsedSeconds": round(elapsed, 1),
            "testMode": "local_mock",
        },
        "processingReport": ai_result.get("processing_report", {}),
        "snackCount": len(snacks),
        "snackSummary": [
            {
                "segmentId": s.get("segmentId"),
                "topic": s.get("topic"),
                "score": s.get("score"),
                "startTime": s.get("startTime"),
                "endTime": s.get("endTime"),
                "tags": s.get("tags", []),
            }
            for s in sorted(snacks, key=lambda s: s.get("startTime", 0))
        ],
    }

    report_path = os.path.join(out_dir, f"{slug}_{ts}_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_output, f, indent=2, ensure_ascii=False, default=str)

    return out_dir, run_path, report_path



def main():
    print("\n" + "\u2554" + "\u2550" * 58 + "\u2557")
    print("\u2551  ShorTED AI Pipeline \u2014 Full Local Test (No External Svcs) \u2551")
    print("\u255a" + "\u2550" * 58 + "\u255d")
    print(f"\n  Model:    {OLLAMA_MODEL}")
    print(f"  Pipeline: {PIPELINE_VERSION}")
    print(f"  Snacks:   {MIN_SNACKS}\u2013{MAX_SNACKS}")

    # Load data
    processed_json = load_processed_json()

    # Run 1: full pipeline
    ai_result_store: dict = {}
    elapsed_store: dict = {}

    def run_pipeline_with_capture(label: str) -> bool:
        """Wrapper to capture ai_result and elapsed for output saving."""
        print_section(label)
        ctx = build_ai_context(processed_json)
        source_hash = compute_source_hash(ctx)
        print_result("Talk", f"'{ctx['title']}' by {ctx['speaker']}", None)
        print_result("Language", ctx["language"], None)
        print_result("Source hash", source_hash[:16] + "\u2026", None)
        print_result("Sentences", f"{len(ctx['sentences'])} loaded", None)

        skip, reason = should_skip(ctx, source_hash)
        print_result("Skip check", f"{skip} (reason: {reason})", skip is False or None)
        if skip:
            return True

        locked = acquire_lock(ctx, source_hash)
        print_result("Lock acquired", locked, locked)
        if not locked:
            return False

        print(f"\n  \U0001f916 Calling Ollama ({OLLAMA_MODEL}) \u2026")
        t0 = time.time()
        try:
            ai_result = run_ollama_orchestrator(ctx)
        except Exception as e:
            print_result("AI Orchestrator", f"FAILED: {e}", False)
            logger.exception("Ollama orchestrator failed")
            return False
        elapsed = time.time() - t0
        ai_result_store["result"] = ai_result
        elapsed_store["elapsed"] = elapsed
        source_hash_store["hash"] = source_hash

        print_result("AI Orchestrator", f"completed in {elapsed:.1f}s", True)
        print_result("Snacks returned", len(ai_result.get("final_snacks", [])), None)
        print_result("MCP tools used", ai_result.get("processing_report", {}).get("mcpToolsUsed", []), None)

        errors = validate_final_output(ai_result, ctx)
        if errors:
            print_result("Final validation", f"FAILED ({len(errors)} errors)", False)
            for e in errors[:5]:
                print(f"    \u2022 {e}")
            return False
        print_result("Final validation", "passed", True)

        persist(ctx, ai_result, source_hash)
        print_result("MongoDB persist", "done", True)
        return True

    source_hash_store: dict = {}
    success = run_pipeline_with_capture("RUN 1 \u2014 First processing")
    if not success:
        print("\n\u274c Run 1 failed. Check logs above.")
        sys.exit(1)

    # Run 2: idempotency
    ok = run_idempotency_check(processed_json)
    if not ok:
        print("\n\u26a0\ufe0f  Idempotency check failed \u2014 pipeline ran again instead of skipping.")
    else:
        print("\n  \u2705 Idempotency verified \u2014 second run correctly skipped AI.")

    # Save output
    run_path = report_path = None
    if ai_result_store.get("result"):
        from datetime import timezone
        _, run_path, report_path = save_test_output(
            processed_json,
            ai_result_store["result"],
            source_hash_store.get("hash", ""),
            elapsed_store.get("elapsed", 0.0),
        )

    # DB summary
    print_db_summary(run_path, report_path)

    # Final verdict
    print("\u2554" + "\u2550" * 58 + "\u2557")
    if success and ok:
        print("\u2551  \u2705 ALL TESTS PASSED                                      \u2551")
    else:
        print("\u2551  \u26a0\ufe0f  SOME TESTS FAILED \u2014 see output above                 \u2551")
    print("\u255a" + "\u2550" * 58 + "\u255d\n")


if __name__ == "__main__":
    from datetime import timezone
    main()
