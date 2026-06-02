"""
Lambda AI Orchestrator — Entry Point for ShorTED.

Triggered by SQS. Processes one batch of talk records:
  1. Parse SQS record
  2. Read processed JSON from S3
  3. Build AI context (select language, extract sentences)
  4. Compute source hash
  5. Pre-flight MongoDB check (skip if already completed)
  6. Acquire processing lock
  7. Invoke Bedrock AI Orchestrator (with MCP tool-use)
  8. Final deterministic validation
  9. Persist talk + snacks to MongoDB
  10. Mark talk as completed

Error handling:
  - PermanentInputError → mark failed + add to batchItemFailures (→ DLQ)
  - AIOutputInvalidError → mark failed + add to batchItemFailures
  - LockNotAcquiredError → silent skip (another Lambda is handling it)
  - Any other exception → mark failed + add to batchItemFailures (SQS retry)

Returns SQS partial batch response to avoid retrying successful records.
"""
import json
import logging

from config import (
    DEFAULT_LANGUAGE,
    LOCK_TTL_SECONDS,
    MIN_SNACKS,
    MAX_SNACKS,
    MCP_SERVER_URL,
    PIPELINE_VERSION,
)
from errors import (
    PermanentInputError,
    AIOutputInvalidError,
    LockNotAcquiredError,
    MongoRepositoryError,
    MCPServerError,
)
from models import AIContext
from sqs_parser import parse_sqs_record
from s3_processed_reader import read_processed_json
from ai_context_builder import build_ai_context
from source_hash import compute_source_hash
from mongo_repository import MongoRepository
from bedrock_orchestrator_client import invoke_bedrock_orchestrator
from final_validator import validate_ai_result
from persistence import save_talk_and_replace_snacks

# ── Logger setup ──────────────────────────────────────────────────────────────
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ── Warm-container singletons (reused across invocations) ─────────────────────
_repo = MongoRepository()


# ── Lambda handler ────────────────────────────────────────────────────────────

def handler(event, context):
    """
    Lambda entry point — processes a batch of SQS records.

    Returns:
        {"batchItemFailures": [...]} for SQS partial batch response.
        Only failed message IDs are included; successful ones are auto-deleted.
    """
    batch_failures: list[dict] = []
    records = event.get("Records", [])
    logger.info("Processing SQS batch of %d records", len(records))

    for record in records:
        slug = "unknown"
        language = DEFAULT_LANGUAGE
        message_id = record.get("messageId", "?")

        try:
            # ── Step 1: Parse SQS record ──────────────────────────────────
            msg = parse_sqs_record(record)
            message_id = msg.message_id

            # ── Step 2: Read processed JSON from S3 ───────────────────────
            processed_json = read_processed_json(msg.bucket, msg.file_key)

            # ── Step 3: Build AI context ──────────────────────────────────
            ai_ctx: AIContext = build_ai_context(
                processed_json,
                preferred_language=msg.language or DEFAULT_LANGUAGE,
            )
            slug = ai_ctx.slug
            language = ai_ctx.language

            # ── Step 4: Compute source hash ───────────────────────────────
            source_hash = compute_source_hash(ai_ctx)

            # ── Step 5: Pre-flight check — skip if already completed ───────
            skip = _repo.should_skip_ai(
                slug=slug,
                language=language,
                pipeline_version=PIPELINE_VERSION,
                source_hash=source_hash,
                min_snacks=MIN_SNACKS,
            )
            if skip.should_skip:
                _log_event("skip", slug, language, reason=skip.reason)
                continue  # message will be auto-deleted by SQS (no failure)

            # ── Step 6: Acquire processing lock ───────────────────────────
            acquired = _repo.acquire_processing_lock(
                slug=slug,
                language=language,
                pipeline_version=PIPELINE_VERSION,
                source_hash=source_hash,
                ttl_seconds=LOCK_TTL_SECONDS,
            )
            if not acquired:
                _log_event("lock_skip", slug, language, reason="active_lock")
                continue  # silent skip — another Lambda is processing this talk

            # ── Step 7: Invoke Bedrock + MCP ──────────────────────────────
            ai_result = invoke_bedrock_orchestrator(
                ai_ctx=ai_ctx,
                mcp_server_url=MCP_SERVER_URL,
                pipeline_version=PIPELINE_VERSION,
            )

            # ── Step 8: Final deterministic validation ────────────────────
            validate_ai_result(ai_result, ai_ctx)

            # ── Step 9: Persist to MongoDB ────────────────────────────────
            save_talk_and_replace_snacks(
                ai_ctx=ai_ctx,
                ai_result=ai_result,
                source_hash=source_hash,
                pipeline_version=PIPELINE_VERSION,
            )

            # ── Step 10: Mark completed ───────────────────────────────────
            _repo.mark_completed(
                slug=slug,
                language=language,
                pipeline_version=PIPELINE_VERSION,
                source_hash=source_hash,
                snack_count=len(ai_result.final_snacks),
            )

            _log_event(
                "completed", slug, language,
                final_snacks=len(ai_result.final_snacks),
                mcp_tools=ai_result.processing_report.get("mcpToolsUsed", []),
                warnings=ai_result.processing_report.get("warnings", []),
            )

        except PermanentInputError as e:
            # Non-retryable: bad S3 data, malformed JSON, missing transcript
            logger.error(
                json.dumps({"event": "permanent_error", "slug": slug, "msgId": message_id, "error": str(e)})
            )
            _repo.mark_failed_if_possible(slug, language, PIPELINE_VERSION, str(e))
            batch_failures.append({"itemIdentifier": message_id})

        except AIOutputInvalidError as e:
            # Model returned invalid output even after repair attempt
            logger.error(
                json.dumps({"event": "ai_output_invalid", "slug": slug, "msgId": message_id, "error": str(e)})
            )
            _repo.mark_failed_if_possible(slug, language, PIPELINE_VERSION, str(e))
            batch_failures.append({"itemIdentifier": message_id})

        except (MCPServerError, MongoRepositoryError) as e:
            # Transient errors — let SQS retry
            logger.error(
                json.dumps({"event": "transient_error", "slug": slug, "msgId": message_id, "error": str(e)})
            )
            _repo.mark_failed_if_possible(slug, language, PIPELINE_VERSION, str(e))
            batch_failures.append({"itemIdentifier": message_id})

        except Exception as e:
            # Unexpected error — also retryable
            logger.exception(
                json.dumps({"event": "unexpected_error", "slug": slug, "msgId": message_id, "error": str(e)})
            )
            _repo.mark_failed_if_possible(slug, language, PIPELINE_VERSION, str(e))
            batch_failures.append({"itemIdentifier": message_id})

    logger.info(
        "Batch complete: total=%d failures=%d", len(records), len(batch_failures)
    )
    return {"batchItemFailures": batch_failures}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _log_event(event: str, slug: str, language: str, **kwargs) -> None:
    """Emit a structured JSON log line for observability."""
    payload = {
        "event": event,
        "slug": slug,
        "language": language,
        "pipelineVersion": PIPELINE_VERSION,
        **kwargs,
    }
    logger.info(json.dumps(payload, default=str))
