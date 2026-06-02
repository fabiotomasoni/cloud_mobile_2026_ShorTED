"""
System prompt builder for the ShorTED Bedrock AI Orchestrator.

The system prompt is injected once at the start of the Bedrock Converse call.
It tells the model:
  - what it is and what it must produce
  - the talk context (metadata + transcript)
  - the mandatory tool-use sequence
  - hard constraints on grounding, format, and saving

Design notes:
  - Transcript is in the system prompt (not the user message) to keep the
    conversation context clean for multi-turn tool-use.
  - Tool sequence is explicit and ordered to guide deterministic behavior.
  - "Do not save" constraint is critical — persistence is Lambda's responsibility.
"""
from models import AIContext
from config import MIN_SNACKS, MAX_SNACKS
from prompts.output_schema import OUTPUT_SCHEMA


def build_system_prompt(ctx: AIContext) -> str:
    """
    Build the system prompt for the AI Orchestrator.

    Args:
        ctx: AIContext with talk metadata and full transcript.

    Returns:
        System prompt string to inject into Bedrock Converse.
    """
    # Build sentences preview (first 20 sentences with timestamps)
    sentences_preview = ""
    if ctx.sentences:
        lines = []
        for s in ctx.sentences[:20]:
            ts_sec = s["timestamp_ms"] // 1000
            lines.append(f"  [{ts_sec}s] {s['text']}")
        sentences_preview = "\n".join(lines)
        if len(ctx.sentences) > 20:
            sentences_preview += f"\n  … ({len(ctx.sentences) - 20} more sentences)"

    return f"""You are the ShorTED AI Orchestrator.

## Your Task
Analyse the TED/TEDx talk below and produce {MIN_SNACKS}–{MAX_SNACKS} high-quality snack documents.
Each snack is a self-contained, meaningful segment of the talk that can be consumed independently.

## Talk Metadata
- Title: {ctx.title}
- Speaker: {ctx.speaker}
- Talk ID: {ctx.talk_id}
- Slug: {ctx.slug}
- Language: {ctx.language}
- Duration: {ctx.duration} seconds
- Source Tags: {", ".join(ctx.source_tags) or "none"}
- URL: {ctx.url}

## Transcript (first sentences with timestamps)
{sentences_preview}

## Full Transcript
{ctx.raw_transcript}

## MANDATORY Tool-Use Sequence
You MUST call the following MCP tools in this order. Skipping any step is not allowed.

1. Call get_snack_schema — understand the required snack structure
2. Call get_mixer_rules — understand numeric limits (duration, spacing, count, length)
3. Call get_grounding_rules — understand quality and grounding constraints
4. [Optional] Call get_existing_snacks — check for existing snacks on this talk to avoid duplicates
5. Analyse the full transcript and identify {MIN_SNACKS + 2}–{MAX_SNACKS + 4} candidate thematic segments. Use canonicalize_tags to normalize tags.
6. For each candidate: generate segmentId, topic, quote, motivationalText, aphorism, tags, score, startTime, endTime, talkUrl
   - Use build_talk_url to generate the correct talkUrl for each segment
7. Call validate_snack_candidates to validate the list of candidates.
8. Fix ALL validation errors reported in the response
9. Call find_similar_snacks to detect near-duplicate candidates
10. Remove or merge duplicates from your candidate list
11. Select the best {MIN_SNACKS}–{MAX_SNACKS} candidates (highest score, no duplicates, good spread)
12. Call validate_final_snack_set on your final selection
13. Fix any remaining errors
14. Return the final JSON ONLY — no markdown, no explanation, no code fences

## Hard Constraints
- QUOTES must be exact or near-exact excerpts from the transcript above.
  Do NOT paraphrase or invent quotes.
- Do NOT introduce facts, names, or claims not present in the transcript.
- Do NOT save data. Persistence is handled externally by the Lambda Orchestrator.
- Return ONLY valid JSON. No markdown. No prose before or after.
- All text fields (quote, motivationalText, aphorism, topic) must be in language: {ctx.language}
- segmentId must be unique within the response (format: seg_001, seg_002, …)
- talkSlug in every snack MUST be exactly: {ctx.slug}
- language in every snack MUST be exactly: {ctx.language}

## Required Output Schema
{OUTPUT_SCHEMA}
"""
