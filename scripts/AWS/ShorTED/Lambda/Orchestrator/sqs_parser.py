"""
SQS record parser for the ShorTED AI Orchestrator.

Parses the body of a single SQS record as produced by the Lambda Dispatcher.

Expected message body (JSON string):
    {"bucket": "shorted-processed", "file_key": "talks/example-transcript.json"}

Optional fields (future use):
    {"bucket": "...", "file_key": "...", "language": "it"}
"""
import json
from models import SQSMessage
from errors import PermanentInputError


def parse_sqs_record(record: dict) -> SQSMessage:
    """
    Parse one SQS event record into a typed SQSMessage.

    Args:
        record: A single element from event["Records"].

    Returns:
        SQSMessage with bucket, file_key, optional language, and messageId.

    Raises:
        PermanentInputError: If the record body is not valid JSON or is missing
                             required fields (bucket, file_key).
    """
    message_id = record.get("messageId", "")

    try:
        body = json.loads(record["body"])
    except (KeyError, json.JSONDecodeError) as e:
        raise PermanentInputError(
            f"[{message_id}] SQS record body is not valid JSON: {e}"
        ) from e

    bucket = body.get("bucket")
    file_key = body.get("file_key")

    if not bucket:
        raise PermanentInputError(
            f"[{message_id}] SQS message missing required field 'bucket'. Body: {body}"
        )
    if not file_key:
        raise PermanentInputError(
            f"[{message_id}] SQS message missing required field 'file_key'. Body: {body}"
        )

    return SQSMessage(
        bucket=bucket,
        file_key=file_key,
        language=body.get("language"),  # optional; None → use DEFAULT_LANGUAGE
        message_id=message_id,
    )
