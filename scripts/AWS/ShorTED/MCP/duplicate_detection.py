"""
Duplicate / similarity detection for ShorTED snack candidates.

Provides deterministic heuristic checks for:
  - intra-batch duplicates (within the current candidate list)
  - cross-DB duplicates (against existing snacks in MongoDB)

MVP heuristics (no embeddings):
  - same topic (lowercase, stripped)
  - near-identical quote (SequenceMatcher ratio >= 0.85)
  - overlapping startTime (distance < MIN_DISTANCE_SECONDS)
  - high tag overlap (>= 80% Jaccard)

Future evolution: replace or augment with Amazon Titan Embeddings for
semantic similarity — architecture already supports it (same interface,
just replace the heuristic functions).
"""
from difflib import SequenceMatcher
from config import MIN_DISTANCE_SECONDS


# ── Similarity helpers ────────────────────────────────────────────────────────

def _quote_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _topic_match(a: str, b: str) -> bool:
    return a.lower().strip() == b.lower().strip()


def _time_overlap(a_start: float, b_start: float) -> bool:
    return abs(a_start - b_start) < MIN_DISTANCE_SECONDS


def _tag_jaccard(a_tags: list, b_tags: list) -> float:
    if not a_tags or not b_tags:
        return 0.0
    set_a = set(t.lower() for t in a_tags)
    set_b = set(t.lower() for t in b_tags)
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def _is_similar(a: dict, b: dict) -> tuple[bool, str]:
    """
    Return (True, reason) if two snacks are considered similar/duplicate.
    """
    a_start = a.get("startTime", -999)
    b_start = b.get("startTime", -999)

    if _topic_match(a.get("topic", ""), b.get("topic", "")):
        return True, "same_topic"

    quote_sim = _quote_similarity(a.get("quote", ""), b.get("quote", ""))
    if quote_sim >= 0.85:
        return True, f"similar_quote (ratio={quote_sim:.2f})"

    if isinstance(a_start, (int, float)) and isinstance(b_start, (int, float)):
        if _time_overlap(a_start, b_start):
            return True, f"overlapping_startTime (|{a_start}-{b_start}|<{MIN_DISTANCE_SECONDS}s)"

    if _tag_jaccard(a.get("tags", []), b.get("tags", [])) >= 0.80:
        return True, "high_tag_overlap (>=80%)"

    return False, ""


# ── Public API ────────────────────────────────────────────────────────────────

def find_intra_batch_duplicates(candidate_snacks: list[dict]) -> list[dict]:
    """
    Find pairs of similar snacks within the candidate list.

    Returns:
        List of {indexA, indexB, reason, segmentIdA, segmentIdB}
    """
    duplicates = []
    n = len(candidate_snacks)
    for i in range(n):
        for j in range(i + 1, n):
            similar, reason = _is_similar(candidate_snacks[i], candidate_snacks[j])
            if similar:
                duplicates.append({
                    "indexA": i,
                    "indexB": j,
                    "segmentIdA": candidate_snacks[i].get("segmentId", f"[{i}]"),
                    "segmentIdB": candidate_snacks[j].get("segmentId", f"[{j}]"),
                    "reason": reason,
                })
    return duplicates


def find_cross_db_duplicates(candidate_snacks: list[dict], existing_snacks: list[dict]) -> list[dict]:
    """
    Find candidate snacks that are similar to existing DB snacks.

    Returns:
        List of {candidateIndex, existingSegmentId, reason}
    """
    duplicates = []
    for i, candidate in enumerate(candidate_snacks):
        for existing in existing_snacks:
            similar, reason = _is_similar(candidate, existing)
            if similar:
                duplicates.append({
                    "candidateIndex": i,
                    "candidateSegmentId": candidate.get("segmentId", f"[{i}]"),
                    "existingSegmentId": existing.get("segmentId", "?"),
                    "reason": reason,
                })
                break  # one match per candidate is enough
    return duplicates
