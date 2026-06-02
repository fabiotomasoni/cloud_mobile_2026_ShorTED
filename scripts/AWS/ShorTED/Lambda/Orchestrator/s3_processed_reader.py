"""
S3 processed JSON reader for the ShorTED AI Orchestrator.

Reads and validates the Glue-produced processed talk JSON from S3.
Does NOT re-normalise or re-transform the data — that is the job of
ai_context_builder. This module only ensures the file is readable and
has the minimum required structure.
"""
import json
import logging

import boto3
from botocore.exceptions import ClientError

from errors import PermanentInputError, S3ObjectNotFoundError

logger = logging.getLogger(__name__)

# Module-level S3 client — reused across warm Lambda invocations
_s3 = boto3.client("s3")

# Minimum fields that must be present in a processed JSON for it to be usable
_REQUIRED_FIELDS = {"slug", "title", "transcriptions"}


def read_processed_json(bucket: str, key: str) -> dict:
    """
    Download and parse the processed talk JSON from S3.

    Args:
        bucket: S3 bucket name (e.g. "shorted-processed").
        key:    S3 object key (e.g. "talks/example-transcript.json").

    Returns:
        Parsed dict from the processed JSON file.

    Raises:
        S3ObjectNotFoundError:  Object does not exist in the bucket.
        PermanentInputError:    File is not valid JSON, or missing required fields,
                                or transcriptions map is empty.
    """
    logger.info("Reading processed JSON from s3://%s/%s", bucket, key)

    try:
        response = _s3.get_object(Bucket=bucket, Key=key)
        raw = response["Body"].read().decode("utf-8")
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code in ("NoSuchKey", "404"):
            raise S3ObjectNotFoundError(
                f"S3 object not found: s3://{bucket}/{key}"
            ) from e
        # Other AWS errors (permissions, throttle, …) — let SQS retry
        raise

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise PermanentInputError(
            f"Processed JSON is not valid JSON at s3://{bucket}/{key}: {e}"
        ) from e

    if not isinstance(data, dict):
        raise PermanentInputError(
            f"Processed JSON root must be a dict, got {type(data).__name__} at s3://{bucket}/{key}"
        )

    # Validate required fields
    missing = _REQUIRED_FIELDS - set(data.keys())
    if missing:
        raise PermanentInputError(
            f"Processed JSON missing required fields {missing} at s3://{bucket}/{key}"
        )

    transcriptions = data.get("transcriptions")
    if not isinstance(transcriptions, dict) or not transcriptions:
        raise PermanentInputError(
            f"Processed JSON has empty or invalid 'transcriptions' at s3://{bucket}/{key}"
        )

    logger.info(
        "Loaded processed JSON for slug='%s', languages=%s",
        data.get("slug", "?"),
        list(transcriptions.keys()),
    )
    return data
