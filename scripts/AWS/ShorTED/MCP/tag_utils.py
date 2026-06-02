"""
Tag normalisation utilities for the ShorTED MCP Server.

Provides canonicalize_tags: a deterministic function that normalises
a list of raw tags into consistent, hyphenated, lowercased canonical forms.

Future evolution: the alias map could be stored in MongoDB so it can be
updated without redeploying the MCP server.
"""
import re

# Alias map: normalised form → canonical form.
# Keys must already be lowercase with hyphens (applied after initial normalisation).
TAG_ALIAS_MAP: dict[str, str] = {
    "artificial-intelligence": "ai",
    "artificial intelligence": "ai",
    "machine-learning": "machine-learning",
    "machine learning": "machine-learning",
    "deep-learning": "deep-learning",
    "deep learning": "deep-learning",
    "natural-language-processing": "nlp",
    "natural language processing": "nlp",
    "self-improvement": "self-improvement",
    "self improvement": "self-improvement",
    "self improvement ": "self-improvement",
    "climate-change": "climate-change",
    "climate change": "climate-change",
    "mental-health": "mental-health",
    "mental health": "mental-health",
    "social-media": "social-media",
    "social media": "social-media",
    "human-rights": "human-rights",
    "human rights": "human-rights",
    "public-health": "public-health",
    "public health": "public-health",
    "ted": "",          # remove generic meta-tags
    "tedx": "",
    "talk": "",
    "speaker": "",
}


def normalize_tags(tags: list[str]) -> list[str]:
    """
    Normalise a list of raw tags to canonical form.

    Steps:
        1. Strip whitespace
        2. Lowercase
        3. Replace internal spaces with hyphens
        4. Remove non-alphanumeric characters (except hyphens)
        5. Apply alias map
        6. Remove empty strings
        7. Deduplicate (preserve insertion order)
        8. Sort for consistency

    Args:
        tags: List of raw tag strings (e.g. ["Artificial Intelligence", "TED", "Self Improvement"])

    Returns:
        Sorted list of canonical tag strings (e.g. ["ai", "self-improvement"])
    """
    result: list[str] = []
    seen: set[str] = set()

    for tag in tags:
        if not isinstance(tag, str):
            continue

        # 1-2. Strip and lowercase
        normalized = tag.strip().lower()

        # Try alias lookup before further normalisation
        alias = TAG_ALIAS_MAP.get(normalized)
        if alias is not None:
            # explicit alias (including empty string = remove)
            canonical = alias
        else:
            # 3. Spaces → hyphens
            normalized = re.sub(r'\s+', '-', normalized)
            # 4. Remove chars that are not alphanumeric or hyphen
            normalized = re.sub(r'[^a-z0-9-]', '', normalized)
            # Collapse multiple hyphens
            normalized = re.sub(r'-+', '-', normalized).strip('-')
            # Try alias again on fully normalised form
            canonical = TAG_ALIAS_MAP.get(normalized, normalized)

        if not canonical:
            continue  # skip empty / removed tags

        if canonical not in seen:
            seen.add(canonical)
            result.append(canonical)

    return sorted(result)
