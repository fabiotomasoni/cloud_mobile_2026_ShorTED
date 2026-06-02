"""
Output schema for the Bedrock Orchestrator's required JSON response.

The model MUST return a JSON object matching this schema exactly.
Used in the system prompt to guide the model's final output format.
"""

OUTPUT_SCHEMA = """{
  "talk": {
    "talkId": "string — numeric ID of the talk",
    "slug": "string — URL-safe slug (MUST match the talk being processed)",
    "title": "string",
    "speaker": "string",
    "speakers": ["string"],
    "url": "string — original TED talk URL",
    "duration": "integer — duration in seconds",
    "imageUrl": "string",
    "sourceTags": ["string"],
    "language": "string — language code used (e.g. 'en', 'it')"
  },
  "final_snacks": [
    {
      "segmentId": "string — unique ID for this segment, format: seg_001",
      "talkId": "string — same as talk.talkId",
      "talkSlug": "string — same as talk.slug",
      "speaker": "string",
      "talkTitle": "string",
      "topic": "string — specific topic, not generic",
      "quote": "string — max 180 chars, exact or near-exact excerpt",
      "motivationalText": "string — motivational/inspiring phrase directly related to the quote, max 500 chars",
      "aphorism": "string — very short punchy catchphrase, max 100 chars",
      "tags": ["string — canonical lowercase hyphenated tags, 3-6 tags"],
      "score": "float — quality score in [0.0, 1.0]",
      "startTime": "integer — seconds from beginning",
      "endTime": "integer — seconds from beginning, must be > startTime",
      "talkUrl": "string — URL with timestamp: <base_url>?t=<startTime>",
      "language": "string — same as talk.language"
    }
  ],
  "processing_report": {
    "candidateSegments": "integer — number of segments you identified",
    "candidateSnacks": "integer — number of candidates you generated",
    "finalSnacks": "integer — number of snacks in final_snacks",
    "mcpToolsUsed": ["string — list of MCP tools you called"],
    "warnings": ["string — any warnings from validation or duplicate check"],
    "status": "string — 'completed' or 'partial'"
  }
}"""
