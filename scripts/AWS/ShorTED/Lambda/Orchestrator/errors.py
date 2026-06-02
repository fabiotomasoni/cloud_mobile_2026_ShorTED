"""
Custom exceptions for ShorTED Lambda AI Orchestrator.

Error hierarchy:
- PermanentInputError   → non-retryable, send to DLQ
- AIOutputInvalidError  → may retry Bedrock (repair call), then DLQ
- LockNotAcquiredError  → silent skip (another Lambda is processing)
- MCPServerError        → retryable via SQS
"""


class PermanentInputError(Exception):
    """
    Non-retryable input error.
    Examples: S3 object not found, JSON malformed, transcript empty.
    The SQS message should be sent to DLQ after this.
    """


class TranscriptUnavailableError(PermanentInputError):
    """No valid transcript found in the processed JSON for any language."""


class S3ObjectNotFoundError(PermanentInputError):
    """The S3 object referenced in the SQS message does not exist."""


class AIOutputInvalidError(Exception):
    """
    The AI model returned output that fails schema or business rule validation.
    A repair call may be attempted before giving up.
    """


class LockNotAcquiredError(Exception):
    """
    Another Lambda instance already holds the processing lock for this talk.
    Silent skip — do not add to batch_failures.
    """


class MCPServerError(Exception):
    """
    The MCP server is unreachable or returned a malformed response.
    This is a transient error — let SQS retry.
    """


class MongoRepositoryError(Exception):
    """
    Unexpected MongoDB error during read/write operations.
    This is a transient error — let SQS retry.
    """
