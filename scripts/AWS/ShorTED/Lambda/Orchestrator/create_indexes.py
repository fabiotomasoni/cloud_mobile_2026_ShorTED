"""
One-shot script to create MongoDB indexes for ShorTED collections.

Run once against the ShorTED Atlas cluster (not mytedx).
Safe to run multiple times — createIndex is idempotent.

Usage (local):
    MONGODB_URI=mongodb+srv://... MONGODB_DB=shorted python create_indexes.py
"""
import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


from pymongo import MongoClient, ASCENDING, DESCENDING
MONGODB_URI = os.environ["MONGODB_URI"]
MONGODB_DB = os.environ.get("MONGODB_DB", "shorted")

client = MongoClient(MONGODB_URI)
db = client[MONGODB_DB]


def create_talks_indexes():
    talks = db["talks"]

    # Unique compound index: one document per (slug, language, version)
    # sourceHash is a field, not part of _id, so multiple hashes can exist
    # during migration but only one completed per version.
    talks.create_index(
        [("slug", ASCENDING), ("language", ASCENDING), ("aiPipelineVersion", ASCENDING)],
        unique=True,
        name="talks_unique_slug_lang_version",
    )

    # For skip check and lock expiry scans
    talks.create_index([("processingStatus", ASCENDING)], name="talks_processingStatus")
    talks.create_index([("lockExpiresAt", ASCENDING)], name="talks_lockExpiresAt")
    talks.create_index([("sourceHash", ASCENDING)], name="talks_sourceHash")

    print("✅ talks indexes created")


def create_snacks_indexes():
    snacks = db["snacks"]

    # Unique per (slug, language, version, segmentId) — matches _id format
    snacks.create_index(
        [
            ("talkSlug", ASCENDING),
            ("language", ASCENDING),
            ("aiPipelineVersion", ASCENDING),
            ("sourceHash", ASCENDING),
            ("segmentId", ASCENDING),
        ],
        unique=True,
        name="snacks_unique_segment",
    )

    # Query indexes for API layer
    snacks.create_index([("talkSlug", ASCENDING)], name="snacks_talkSlug")
    snacks.create_index([("language", ASCENDING)], name="snacks_language")
    snacks.create_index([("score", DESCENDING)], name="snacks_score")
    snacks.create_index([("tags", ASCENDING)], name="snacks_tags")

    # Compound: feed query (talkSlug + lang + version + hash — for skip check)
    snacks.create_index(
        [
            ("talkSlug", ASCENDING),
            ("language", ASCENDING),
            ("aiPipelineVersion", ASCENDING),
            ("sourceHash", ASCENDING),
        ],
        name="snacks_compound_pipeline",
    )

    # Compound: personalised feed (tags + score)
    snacks.create_index(
        [("tags", ASCENDING), ("score", DESCENDING)],
        name="snacks_tags_score",
    )

    print("✅ snacks indexes created")


if __name__ == "__main__":
    print(f"Connecting to MongoDB: {MONGODB_DB} …")
    create_talks_indexes()
    create_snacks_indexes()
    print("All indexes created successfully.")
    client.close()
