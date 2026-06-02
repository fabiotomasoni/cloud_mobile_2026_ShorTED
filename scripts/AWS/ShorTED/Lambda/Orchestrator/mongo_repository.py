"""
MongoDB repository for ShorTED Lambda AI Orchestrator.

Handles all MongoDB interactions:
  - should_skip_ai   → pre-flight check before calling Bedrock
  - acquire_processing_lock → atomic lock to prevent concurrent processing
  - mark_completed   → update talk status after successful persistence
  - mark_failed_if_possible → best-effort failure marking

Connection is initialised at module level to benefit from Lambda warm
container reuse (avoids reconnect overhead on every invocation).

NOTE: MongoDB URI is read from the MONGODB_URI environment variable,
set directly in the Lambda console (not via Secrets Manager).
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from pymongo import MongoClient
from pymongo.errors import PyMongoError

from config import MONGODB_URI, MONGODB_DB
from models import SkipResult
from errors import MongoRepositoryError

logger = logging.getLogger(__name__)

# ── Module-level connection (warm Lambda reuse) ───────────────────────────────
_client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
_db = _client[MONGODB_DB]
_talks = _db["talks"]
_snacks = _db["snacks"]


class MongoRepository:
    """
    Thin repository layer over the talks and snacks collections.
    All methods are synchronous (pymongo) — suitable for Lambda.
    """

    # ── Pre-flight check ──────────────────────────────────────────────────────

    def should_skip_ai(
        self,
        slug: str,
        language: str,
        pipeline_version: str,
        source_hash: str,
        min_snacks: int,
    ) -> SkipResult:
        """
        Determine whether AI processing can be safely skipped.

        Skip condition (ALL must be true):
          - talk exists with processingStatus=completed
          - same aiPipelineVersion
          - same sourceHash (content unchanged)
          - at least min_snacks snack documents exist in MongoDB

        Args:
            slug:             Talk slug (unique identifier).
            language:         Language code used for processing.
            pipeline_version: Current pipeline version string (e.g. "v1").
            source_hash:      SHA-256 of content-determining fields.
            min_snacks:       Minimum snack count to consider processing complete.

        Returns:
            SkipResult with should_skip=True and reason if skipping,
            or should_skip=False with reason explaining why not.
        """
        try:
            talk = _talks.find_one({
                "slug": slug,
                "language": language,
                "aiPipelineVersion": pipeline_version,
                "sourceHash": source_hash,
                "processingStatus": "completed",
            })
        except PyMongoError as e:
            raise MongoRepositoryError(f"should_skip_ai MongoDB error for slug='{slug}': {e}") from e

        if not talk:
            return SkipResult(False, "not_found")

        try:
            count = _snacks.count_documents({
                "talkSlug": slug,
                "language": language,
                "aiPipelineVersion": pipeline_version,
                "sourceHash": source_hash,
            })
        except PyMongoError as e:
            raise MongoRepositoryError(f"snack count MongoDB error for slug='{slug}': {e}") from e

        if count >= min_snacks:
            logger.info("skip=True slug='%s' snackCount=%d", slug, count)
            return SkipResult(True, "already_completed")

        logger.info(
            "skip=False slug='%s' reason=insufficient_snacks snackCount=%d required=%d",
            slug, count, min_snacks,
        )
        return SkipResult(False, "insufficient_snacks")

    # ── Processing lock ───────────────────────────────────────────────────────

    def acquire_processing_lock(
        self,
        slug: str,
        language: str,
        pipeline_version: str,
        source_hash: str,
        ttl_seconds: int,
    ) -> bool:
        """
        Atomically acquire a processing lock for this (slug, language) pair.

        Lock is granted when the document:
          - does not exist yet, OR
          - has processingStatus in (None, "failed"), OR
          - has processingStatus="processing" AND lockExpiresAt is in the past, OR
          - has a different aiPipelineVersion (stale version — regenerate), OR
          - has a different sourceHash (content changed — regenerate)

        Uses find_one_and_update with upsert=True for atomicity.

        Args:
            slug:             Talk slug.
            language:         Language code.
            pipeline_version: Current pipeline version.
            source_hash:      SHA-256 of the current content.
            ttl_seconds:      Lock TTL — should be >= Lambda timeout (900s).

        Returns:
            True if the lock was acquired, False if another process holds it.
        """
        now = datetime.utcnow()
        lock_expires = now + timedelta(seconds=ttl_seconds)

        try:
            result = _talks.find_one_and_update(
                {
                    "slug": slug,
                    "language": language,
                    "$or": [
                        {"processingStatus": {"$in": [None, "failed"]}},
                        # Expired lock — safe to take over
                        {"processingStatus": "processing", "lockExpiresAt": {"$lt": now}},
                        # Version or content changed — regenerate
                        {"aiPipelineVersion": {"$ne": pipeline_version}},
                        {"sourceHash": {"$ne": source_hash}},
                    ],
                },
                {
                    "$set": {
                        "processingStatus": "processing",
                        "lockExpiresAt": lock_expires,
                        "processingStartedAt": now,
                        "aiPipelineVersion": pipeline_version,
                        "sourceHash": source_hash,
                        "language": language,
                        "slug": slug,
                    }
                },
                upsert=True,
                return_document=True,
            )
        except PyMongoError as e:
            raise MongoRepositoryError(
                f"acquire_processing_lock MongoDB error for slug='{slug}': {e}"
            ) from e

        acquired = result is not None
        if acquired:
            logger.info("lock_acquired slug='%s' language='%s'", slug, language)
        else:
            logger.info("lock_not_acquired slug='%s' (active lock held by another process)", slug)
        return acquired

    # ── Status updates ────────────────────────────────────────────────────────

    def mark_completed(
        self,
        slug: str,
        language: str,
        pipeline_version: str,
        source_hash: str,
        snack_count: int,
    ) -> None:
        """
        Mark a talk as fully processed and release the lock.
        Called AFTER persistence.save_talk_and_replace_snacks succeeds.
        """
        try:
            _talks.update_one(
                {
                    "slug": slug,
                    "language": language,
                    "aiPipelineVersion": pipeline_version,
                },
                {
                    "$set": {
                        "processingStatus": "completed",
                        "snackCount": snack_count,
                        "processedAt": datetime.utcnow(),
                        "lockExpiresAt": None,
                        "lastError": None,
                        "sourceHash": source_hash,
                    }
                },
            )
        except PyMongoError as e:
            raise MongoRepositoryError(
                f"mark_completed MongoDB error for slug='{slug}': {e}"
            ) from e

    def mark_failed_if_possible(
        self,
        slug: str,
        language: str,
        pipeline_version: str,
        error_message: str,
    ) -> None:
        """
        Best-effort: mark the talk as failed and release the lock.
        Swallows exceptions — called from error handlers where we cannot raise.
        """
        try:
            _talks.update_one(
                {
                    "slug": slug,
                    "language": language,
                    "aiPipelineVersion": pipeline_version,
                },
                {
                    "$set": {
                        "processingStatus": "failed",
                        "lockExpiresAt": None,
                        "lastError": error_message[:1000],  # cap length
                        "failedAt": datetime.utcnow(),
                    }
                },
                upsert=False,  # do not create if it does not exist
            )
        except Exception:
            logger.exception("mark_failed_if_possible failed (best-effort) for slug='%s'", slug)
