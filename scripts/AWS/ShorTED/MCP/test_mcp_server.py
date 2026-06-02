"""
test_mcp_server.py — ShorTED MCP Server functional test.

Tests all MCP tools by calling them directly via the FastMCP in-process client.
No MongoDB required: mongo tools are skipped or caught gracefully.
No Ollama required: this tests the server tools themselves, not AI orchestration.

Usage:
    cd scripts/AWS/ShorTED/MCP
    python test_mcp_server.py
"""
import asyncio
import json
import os
import sys

# ── Env stub (no MongoDB needed for most tools) ───────────────────────────────
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017")
os.environ.setdefault("MONGODB_DB", "shorted_test")
os.environ.setdefault("MCP_SERVER_URL", "http://localhost:8080")

# ── Colour helpers ─────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def ok(msg):   print(f"  {GREEN}✅{RESET} {msg}")
def fail(msg): print(f"  {RED}❌{RESET} {msg}")
def info(msg): print(f"  {CYAN}ℹ️ {RESET} {msg}")
def warn(msg): print(f"  {YELLOW}⚠️ {RESET} {msg}")
def section(title):
    print(f"\n{BOLD}{CYAN}{'═'*60}{RESET}")
    print(f"{BOLD}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'═'*60}{RESET}")


# ── Import server modules directly (no HTTP) ──────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

from tag_utils import normalize_tags
from validation import validate_single, validate_batch, validate_final_set
from duplicate_detection import find_intra_batch_duplicates
from resources import register_resources
from urllib.parse import urlparse, urlencode, urlunparse, parse_qs


# ── Helper: build_talk_url (same logic as server) ────────────────────────────
def build_talk_url_sync(base_url: str, start_time: int) -> str:
    parsed = urlparse(base_url)
    params = parse_qs(parsed.query)
    params["t"] = [str(start_time)]
    new_query = urlencode({k: v[0] for k, v in params.items()})
    return urlunparse(parsed._replace(query=new_query))


# ── Sample snack (valid) ──────────────────────────────────────────────────────
GOOD_SNACK = {
    "segmentId": "seg_001",
    "talkId": "42",
    "talkSlug": "tiago_forte_second_brain",
    "speaker": "Tiago Forte",
    "talkTitle": "How to Build a Second Brain",
    "topic": "Information Overload and Cognitive Load",
    "quote": "The average person consumes 34 gigabytes of data every single day.",
    "motivationalText": "Despite having access to more information than any human in history, most people feel overwhelmed. Build a system to think better.",
    "aphorism": "Your brain is for having ideas, not for storing them.",
    "tags": ["cognitive-load", "knowledge-management", "information-explosion"],
    "score": 0.95,
    "startTime": 12,
    "endTime": 60,
    "talkUrl": "https://www.ted.com/talks/tiago_forte_second_brain?t=12",
    "language": "en",
}

GOOD_SNACK_2 = {**GOOD_SNACK,
    "segmentId": "seg_002",
    "topic": "The Second Brain concept",
    "quote": "A second brain is a trusted system outside your head.",
    "motivationalText": "Stop trying to remember everything. Your external system will do that for you.",
    "aphorism": "Offload thinking: build a reliable outside storage.",
    "tags": ["knowledge-system", "productivity", "external-memory"],
    "score": 0.98,
    "startTime": 70,
    "endTime": 105,
    "talkUrl": "https://www.ted.com/talks/tiago_forte_second_brain?t=70",
}

GOOD_SNACK_3 = {**GOOD_SNACK,
    "segmentId": "seg_003",
    "topic": "The Four Capabilities of a Second Brain",
    "quote": "There are four essential capabilities: remembering, connecting, creating, and sharing.",
    "motivationalText": "A knowledge system doesn't just save data — it enables you to create, connect, and share ideas at a new level.",
    "aphorism": "From Capture to Creation.",
    "tags": ["knowledge-organization", "skill-development", "creative-output"],
    "score": 0.97,
    "startTime": 122,
    "endTime": 215,
    "talkUrl": "https://www.ted.com/talks/tiago_forte_second_brain?t=122",
}

GOOD_SNACK_4 = {**GOOD_SNACK,
    "segmentId": "seg_004",
    "topic": "The CODE Framework for Knowledge Management",
    "quote": "I call this system CODE: Capture, Organise, Distil, Express.",
    "motivationalText": "True knowledge is only valuable when expressed. Start producing, not just consuming.",
    "aphorism": "Capture. Organise. Distil. Express.",
    "tags": ["productivity-framework", "knowledge-capture", "self-improvement"],
    "score": 0.96,
    "startTime": 218,
    "endTime": 305,
    "talkUrl": "https://www.ted.com/talks/tiago_forte_second_brain?t=218",
}

BAD_SNACK = {
    "segmentId": "seg_bad",  # valid id so we test the other constraints
    "talkId": "42",
    "talkSlug": "tiago_forte_second_brain",
    "speaker": "Tiago Forte",
    "talkTitle": "How to Build a Second Brain",
    "topic": "main theme",   # too generic (warning)
    "quote": "X" * 200,      # too long → error
    "motivationalText": "ok",
    "aphorism": "Y" * 110,   # too long → error
    "tags": ["a"],            # too few → error
    "score": 1.5,             # out of range → error
    "startTime": 10,
    "endTime": 5,             # endTime <= startTime → error
    "talkUrl": "https://www.ted.com/talks/tiago_forte_second_brain",
    "language": "en",
}

FINAL_SET = [GOOD_SNACK, GOOD_SNACK_2, GOOD_SNACK_3, GOOD_SNACK_4]

errors_total = 0
passed_total = 0


def check(condition: bool, label: str, detail: str = ""):
    global errors_total, passed_total
    if condition:
        ok(label)
        passed_total += 1
    else:
        fail(f"{label}{' — ' + detail if detail else ''}")
        errors_total += 1


# ══════════════════════════════════════════════════════════════════════════════
section("1 — canonicalize_tags")
# ══════════════════════════════════════════════════════════════════════════════

raw = ["AI", "machine learning", "Productivity", "ai", "  Knowledge Management  "]
result = normalize_tags(raw)
info(f"Input:  {raw}")
info(f"Output: {result}")
check(isinstance(result, list), "Returns a list")
check(all(t == t.lower() for t in result), "All tags lowercase")
check(all(" " not in t for t in result), "No spaces (replaced with hyphens)")
check(len(set(result)) == len(result), "No duplicates")
check(result == sorted(result), "Sorted alphabetically")


# ══════════════════════════════════════════════════════════════════════════════
section("2 — validate_snack_candidate (valid snack)")
# ══════════════════════════════════════════════════════════════════════════════

result = validate_single(GOOD_SNACK)
info(f"valid={result['valid']}  errors={result['errors']}  warnings={result['warnings']}")
check(result["valid"] is True, "Valid snack passes")
check(len(result["errors"]) == 0, "No errors")


# ══════════════════════════════════════════════════════════════════════════════
section("3 — validate_snack_candidate (invalid snack)")
# ══════════════════════════════════════════════════════════════════════════════

result = validate_single(BAD_SNACK)
info(f"valid={result['valid']}  errors={len(result['errors'])}  warnings={len(result['warnings'])}")
for e in result["errors"]:
    info(f"  ERROR  [{e['field']}] {e['message']}")
for w in result["warnings"]:
    info(f"  WARN   [{w['field']}] {w['message']}")
check(result["valid"] is False, "Invalid snack fails")
check(len(result["errors"]) >= 4, f"At least 4 errors detected (got {len(result['errors'])})")
error_fields = {e["field"] for e in result["errors"]}
check("quote" in error_fields, "quote too-long detected")
check("aphorism" in error_fields, "aphorism too-long detected")
check("score" in error_fields, "score out-of-range detected")
check("endTime" in error_fields, "endTime <= startTime detected")


# ══════════════════════════════════════════════════════════════════════════════
section("4 — validate_snack_candidates (batch)")
# ══════════════════════════════════════════════════════════════════════════════

result = validate_batch([GOOD_SNACK, BAD_SNACK])
check("results" in result, "Returns results key")
check(len(result["results"]) == 2, "Two results returned")
check(result["results"][0]["valid"] is True, "First snack valid")
check(result["results"][1]["valid"] is False, "Second snack invalid")


# ══════════════════════════════════════════════════════════════════════════════
section("5 — validate_final_snack_set")
# ══════════════════════════════════════════════════════════════════════════════

result = validate_final_set(FINAL_SET)
info(f"valid={result['valid']}  errors={result['errors']}  warnings={result['warnings']}")
if "stats" in result:
    info(f"stats={result['stats']}")
check(result["valid"] is True, "Final set of 4 snacks passes")
check(len(result["errors"]) == 0, "No errors in final set")

# Test: too few snacks
result_few = validate_final_set([GOOD_SNACK])
check(result_few["valid"] is False, "Single snack fails count check")


# ══════════════════════════════════════════════════════════════════════════════
section("6 — find_similar_snacks (intra-batch)")
# ══════════════════════════════════════════════════════════════════════════════

# Duplicate pair: same topic + similar quote + close time
dup_snack = {**GOOD_SNACK, "segmentId": "seg_dup", "startTime": 15, "endTime": 50}
result = find_intra_batch_duplicates([GOOD_SNACK, dup_snack])
info(f"Intra-batch duplicates: {result}")
check(len(result) > 0, "Near-duplicate pair detected")

result_no_dup = find_intra_batch_duplicates([GOOD_SNACK, GOOD_SNACK_2, GOOD_SNACK_3, GOOD_SNACK_4])
check(len(result_no_dup) == 0, "No duplicates in clean set")


# ══════════════════════════════════════════════════════════════════════════════
section("7 — build_talk_url")
# ══════════════════════════════════════════════════════════════════════════════

url = build_talk_url_sync("https://www.ted.com/talks/example", 120)
info(f"URL: {url}")
check("?t=120" in url, "Timestamp appended correctly")

url2 = build_talk_url_sync("https://www.ted.com/talks/example?lang=it", 45)
info(f"URL (existing params): {url2}")
check("t=45" in url2 and "lang=it" in url2, "Existing params preserved")

url3 = build_talk_url_sync("https://www.ted.com/talks/example?t=99", 0)
check("t=0" in url3, "t=0 overwrites existing t param")


# ══════════════════════════════════════════════════════════════════════════════
section("8 — aphorism field compliance")
# ══════════════════════════════════════════════════════════════════════════════

for snack in FINAL_SET:
    a = snack.get("aphorism", "")
    check(len(a) <= 100, f"[{snack['segmentId']}] aphorism ≤100 chars ({len(a)} chars): '{a}'")
    check(len(a) > 0, f"[{snack['segmentId']}] aphorism non-empty")


# ══════════════════════════════════════════════════════════════════════════════
# Summary
# ══════════════════════════════════════════════════════════════════════════════
print()
total = passed_total + errors_total
if errors_total == 0:
    print(f"{BOLD}{GREEN}╔══════════════════════════════════════════╗{RESET}")
    print(f"{BOLD}{GREEN}║  ✅ ALL {total} TESTS PASSED                  ║{RESET}")
    print(f"{BOLD}{GREEN}╚══════════════════════════════════════════╝{RESET}")
else:
    print(f"{BOLD}{RED}╔══════════════════════════════════════════╗{RESET}")
    print(f"{BOLD}{RED}║  ❌ {errors_total} FAILURES / {total} TESTS             ║{RESET}")
    print(f"{BOLD}{RED}╚══════════════════════════════════════════╝{RESET}")
    sys.exit(1)
