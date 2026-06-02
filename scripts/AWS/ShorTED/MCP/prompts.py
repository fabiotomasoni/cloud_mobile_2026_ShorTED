"""
MCP Prompts for the ShorTED MCP Server.

Exposes reusable prompt templates the AI model can request via MCP.
"""
from mcp.server.fastmcp import FastMCP
from config import (
    MIN_SNACKS,
    MAX_SNACKS,
    MIN_TAGS,
    MAX_TAGS,
)


def register_prompts(mcp: FastMCP) -> None:
    """Register all MCP prompts on the given FastMCP instance."""

    @mcp.prompt()
    def generate_snacks_prompt(talk_title: str, language: str) -> str:
        """
        Template prompt for snack generation.
        Use this as a starting structure when generating snacks for a new talk.
        """
        return (
            f"Generate {MIN_SNACKS}–{MAX_SNACKS} high-quality snack documents for the talk:\n"
            f"Title: {talk_title}\n"
            f"Language: {language}\n\n"
            f"Steps:\n"
            f"1. Read the snack schema from shorted://schemas/snack\n"
            f"2. Read the mixer rules from shorted://rules/mixer\n"
            f"3. Read the grounding rules from shorted://rules/grounding\n"
            f"4. Analyse the full transcript\n"
            f"5. Apply tag rules (min {MIN_TAGS}, max {MAX_TAGS}) using canonicalize_tags.\n"
            f"6. For each candidate: generate quote, motivationalText, aphorism, topic, tags, score, startTime, endTime\n"
            f"7. Validate batch using validate_snack_candidates.\n"
            f"8. Fix any validation errors\n"
            f"9. Call find_similar_snacks to remove near-duplicates\n"
            f"10. Select the best {MIN_SNACKS}–{MAX_SNACKS} candidates\n"
            f"11. Call validate_final_snack_set on your final selection\n"
            f"12. Return only the final JSON — no markdown, no explanation\n"
        )

    @mcp.prompt()
    def repair_invalid_snacks_prompt(validation_errors: str, original_snacks: str) -> str:
        """
        Repair prompt: given validation errors and the original snack list,
        fix the issues and return corrected snacks.
        """
        return (
            f"The following snacks failed validation. Fix all errors and return\n"
            f"corrected snacks in the same JSON format.\n\n"
            f"VALIDATION ERRORS:\n{validation_errors}\n\n"
            f"ORIGINAL SNACKS:\n{original_snacks}\n\n"
            f"Instructions:\n"
            f"- Fix each reported error\n"
            f"- Do not change snacks that passed validation\n"
            f"- Ensure all quotes remain grounded in the transcript\n"
            f"- Return only the corrected final JSON — no markdown\n"
        )
