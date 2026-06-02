"""
Idempotent MongoDB persistence for ShorTED snacks and talk documents.

Persistence strategy (safe for SQS retries):
  1. Delete existing snacks for (slug, language, pipelineVersion, sourceHash)
  2. Insert new snacks (bulk)
  3. Upsert talk document with processingStatus=completed
     (done by mongo_repository.mark_completed after this function returns)

The ordering is intentional:
  - snacks are replaced BEFORE the talk is marked completed
  - if step 3 fails, the talk stays "processing" and will be retried
  - on retry, step 1 removes any partial snack set → clean state

Does NOT mark the talk as completed — that is done by MongoRepository.mark_completed
after this function returns successfully.
"""
import logging
from datetime import datetime

from pymongo.errors import PyMongoError, BulkWriteError

from config import MONGODB_URI, MONGODB_DB
from models import AIContext, AIResult
from errors import MongoRepositoryError

# Reuse the same connection initialised in mongo_repository
from mongo_repository import _db

logger = logging.getLogger(__name__)

_talks = _db["talks"]
_snacks = _db["snacks"]


def save_talk_and_replace_snacks(
    ai_ctx: AIContext,
    ai_result: AIResult,
    source_hash: str,
    pipeline_version: str,
) -> None:
    """
    Atomically replace snacks and upsert the talk document.

    Args:
        ai_ctx:           AIContext with talk metadata and selected language.
        ai_result:        Validated AIResult from the Bedrock Orchestrator.
        source_hash:      SHA-256 of content-determining fields.
        pipeline_version: Current pipeline version string.

    Raises:
        MongoRepositoryError: On any MongoDB error during persistence.
    """
    now = datetime.utcnow()
    slug = ai_ctx.slug
    language = ai_ctx.language

    # ── Step 1: Remove old snacks for this (slug, lang, version, hash) ───────
    try:
        delete_result = _snacks.delete_many({
            "talkSlug": slug,
            "language": language,
            "aiPipelineVersion": pipeline_version,
            "sourceHash": source_hash,
        })
        if delete_result.deleted_count > 0:
            logger.info(
                "Deleted %d old snacks for slug='%s'", delete_result.deleted_count, slug
            )
    except PyMongoError as e:
        raise MongoRepositoryError(f"delete_many snacks failed for slug='{slug}': {e}") from e

    # ── Step 2: Insert new snacks ─────────────────────────────────────────────
    snack_docs = [
        {
            "_id": f"{slug}:{language}:{pipeline_version}:{s.segment_id}",
            "segmentId": s.segment_id,
            "talkId": ai_ctx.talk_id,
            "talkSlug": slug,
            "speaker": s.speaker,
            "talkTitle": s.talk_title,
            "topic": s.topic,
            "quote": s.quote,
            "motivationalText": s.motivationalText,
            "aphorism": s.aphorism,
            "tags": s.tags,
            "score": s.score,
            "startTime": s.start_time,
            "endTime": s.end_time,
            "talkUrl": s.talk_url,
            "language": language,
            "aiPipelineVersion": pipeline_version,
            "sourceHash": source_hash,
            "createdAt": now,
        }
        for s in ai_result.final_snacks
    ]

    if not snack_docs:
        raise MongoRepositoryError(f"No snack documents to insert for slug='{slug}'")

    try:
        _snacks.insert_many(snack_docs, ordered=False)
        logger.info("Inserted %d snacks for slug='%s'", len(snack_docs), slug)
    except BulkWriteError as e:
        # On retry, some docs may already exist (same _id) — that is acceptable
        # if all errors are duplicate key errors (code 11000)
        non_dup = [
            err for err in e.details.get("writeErrors", [])
            if err.get("code") != 11000
        ]
        if non_dup:
            raise MongoRepositoryError(
                f"insert_many snacks non-duplicate errors for slug='{slug}': {non_dup}"
            ) from e
        logger.warning(
            "Duplicate key on snack insert for slug='%s' (retry?) — continuing", slug
        )
    except PyMongoError as e:
        raise MongoRepositoryError(f"insert_many snacks failed for slug='{slug}': {e}") from e

    # ── Step 3: Upsert talk document (metadata, NOT status — that comes later) ─
    talk_doc = {
        "talkId": ai_ctx.talk_id,
        "slug": slug,
        "title": ai_ctx.title,
        "speaker": ai_ctx.speaker,
        "speakers": ai_ctx.speakers,
        "url": ai_ctx.url,
        "duration": ai_ctx.duration,
        "imageUrl": ai_ctx.image_url,
        "sourceTags": ai_ctx.source_tags,
        "language": language,
        "aiPipelineVersion": pipeline_version,
        "sourceHash": source_hash,
        "updatedAt": now,
    }

    try:
        _talks.update_one(
            {"slug": slug, "language": language},
            {"$set": talk_doc},
            upsert=True,
        )
        logger.info("Upserted talk document for slug='%s'", slug)
    except PyMongoError as e:
        raise MongoRepositoryError(f"upsert talk failed for slug='{slug}': {e}") from e
