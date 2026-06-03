"""
Local SQS worker for the ShorTED AI Orchestrator.

This script consumes the same SQS messages that normally trigger the Lambda
AI Orchestrator, but runs the existing Lambda handler locally. It is designed
for cautious local processing with Ollama + local MCP:

  - low default concurrency: one message at a time
  - deletes SQS messages only after the Lambda handler reports success
  - leaves failed messages in SQS for normal visibility-timeout retry/DLQ flow
  - skips already completed MongoDB talks unless explicitly forced
  - supports dry-run, max message count, max runtime and queue status checks

Required environment is the same as handler.py, plus SQS_QUEUE_URL:

  AI_PROVIDER=ollama
  OLLAMA_BASE_URL=http://localhost:11434
  MCP_SERVER_URL=http://localhost:8080
  MONGODB_URI=mongodb+srv://...
  SQS_QUEUE_URL=https://sqs...

Example:
  python3 local_sqs_worker.py status
  python3 local_sqs_worker.py run --max-messages 5 --batch-size 1
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
import time
from dataclasses import dataclass
from typing import Any


try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    env_path = os.path.join(os.getcwd(), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as env_file:
            for line in env_file:
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or "=" not in stripped:
                    continue
                key, value = stripped.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip("'\""))


logger = logging.getLogger("local_sqs_worker")
_STOP_REQUESTED = False


@dataclass
class WorkerStats:
    received: int = 0
    processed: int = 0
    deleted: int = 0
    failed: int = 0
    empty_polls: int = 0
    started_at: float = 0.0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(args.log_level)

    if args.command == "status":
        sqs = make_sqs_client(args)
        print_queue_status(sqs, args.queue_url)
        return 0

    install_signal_handlers()
    preflight(args)
    run_worker(args)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the ShorTED SQS AI Orchestrator locally."
    )
    parser.add_argument(
        "--queue-url",
        default=os.environ.get("SQS_QUEUE_URL"),
        required=not os.environ.get("SQS_QUEUE_URL"),
        help="SQS queue URL. Defaults to SQS_QUEUE_URL.",
    )
    parser.add_argument(
        "--region",
        default=os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION"),
        help="AWS region for SQS. Defaults to AWS_REGION/AWS_DEFAULT_REGION/profile.",
    )
    parser.add_argument(
        "--endpoint-url",
        default=os.environ.get("SQS_ENDPOINT_URL"),
        help="Optional SQS endpoint override, useful for localstack.",
    )
    parser.add_argument(
        "--log-level",
        default=os.environ.get("LOCAL_WORKER_LOG_LEVEL", "INFO"),
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="Print queue counters and exit.")

    run = subparsers.add_parser("run", help="Consume SQS and run handler.py locally.")
    run.add_argument(
        "--batch-size",
        type=int,
        default=int(os.environ.get("LOCAL_WORKER_BATCH_SIZE", "1")),
        help="Messages per local handler invocation. Keep 1 for safest Mongo/Ollama load.",
    )
    run.add_argument(
        "--wait-time-seconds",
        type=int,
        default=int(os.environ.get("LOCAL_WORKER_WAIT_TIME_SECONDS", "20")),
        help="SQS long-poll wait time, 0-20 seconds.",
    )
    run.add_argument(
        "--visibility-timeout",
        type=int,
        default=int(os.environ.get("LOCAL_WORKER_VISIBILITY_TIMEOUT", "1800")),
        help="Seconds a received message stays hidden while local AI runs.",
    )
    run.add_argument(
        "--poll-delay-seconds",
        type=float,
        default=float(os.environ.get("LOCAL_WORKER_POLL_DELAY_SECONDS", "2")),
        help="Sleep between polls to avoid hot loops and keep local load low.",
    )
    run.add_argument(
        "--max-messages",
        type=int,
        default=int(os.environ["LOCAL_WORKER_MAX_MESSAGES"])
        if os.environ.get("LOCAL_WORKER_MAX_MESSAGES")
        else None,
        help="Stop after receiving this many messages.",
    )
    run.add_argument(
        "--max-runtime-seconds",
        type=int,
        default=int(os.environ["LOCAL_WORKER_MAX_RUNTIME_SECONDS"])
        if os.environ.get("LOCAL_WORKER_MAX_RUNTIME_SECONDS")
        else None,
        help="Stop after this many seconds.",
    )
    run.add_argument(
        "--stop-after-empty-polls",
        type=int,
        default=int(os.environ.get("LOCAL_WORKER_STOP_AFTER_EMPTY_POLLS", "3")),
        help="Stop after this many empty long polls unless --forever is set.",
    )
    run.add_argument(
        "--forever",
        action="store_true",
        help="Keep polling until interrupted instead of stopping on empty polls.",
    )
    run.add_argument(
        "--dry-run",
        action="store_true",
        help="Receive and show messages, then immediately release them without AI or delete.",
    )
    run.add_argument(
        "--skip-health-checks",
        action="store_true",
        help="Skip Ollama/MCP health checks before running.",
    )
    run.add_argument(
        "--force-reprocess-completed",
        action="store_true",
        help="Regenerate even if MongoDB already has a completed talk with the same source hash.",
    )
    return parser


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def install_signal_handlers() -> None:
    def _request_stop(signum: int, _frame: Any) -> None:
        global _STOP_REQUESTED
        _STOP_REQUESTED = True
        logger.warning("Stop requested by signal %s; finishing current batch.", signum)

    signal.signal(signal.SIGINT, _request_stop)
    signal.signal(signal.SIGTERM, _request_stop)


def make_sqs_client(args: argparse.Namespace):
    try:
        import boto3
    except ImportError as e:
        raise SystemExit(
            "Missing dependency 'boto3'. Install the orchestrator requirements with: "
            "python3 -m pip install -r scripts/AWS/ShorTED/Lambda/Orchestrator/requirements.txt"
        ) from e

    kwargs: dict[str, Any] = {}
    if args.region:
        kwargs["region_name"] = args.region
    if args.endpoint_url:
        kwargs["endpoint_url"] = args.endpoint_url
    return boto3.client("sqs", **kwargs)


def preflight(args: argparse.Namespace) -> None:
    if args.batch_size < 1 or args.batch_size > 10:
        raise SystemExit("--batch-size must be between 1 and 10")
    if args.wait_time_seconds < 0 or args.wait_time_seconds > 20:
        raise SystemExit("--wait-time-seconds must be between 0 and 20")
    if args.visibility_timeout < 30:
        raise SystemExit("--visibility-timeout should be at least 30 seconds")

    required_env = ["MONGODB_URI", "MCP_SERVER_URL"]
    missing = [name for name in required_env if not os.environ.get(name)]
    if missing:
        raise SystemExit(f"Missing required environment variables: {', '.join(missing)}")

    ai_provider = os.environ.get("AI_PROVIDER", "bedrock").lower()
    if ai_provider not in ("ollama", "local_fast"):
        logger.warning(
            "AI_PROVIDER is %r. For this local safe path, use AI_PROVIDER=ollama or local_fast.",
            ai_provider,
        )

    if args.skip_health_checks or args.dry_run:
        return

    check_ollama()
    check_mcp()


def check_ollama() -> None:
    import requests

    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    model = os.environ.get("OLLAMA_MODEL", "llama3.1")
    try:
        response = requests.get(f"{base_url}/api/tags", timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        raise SystemExit(f"Ollama health check failed at {base_url}: {e}") from e

    models = [item.get("name", "") for item in response.json().get("models", [])]
    if models and not any(name == model or name.startswith(f"{model}:") for name in models):
        logger.warning("Ollama is reachable, but model %r was not listed: %s", model, models)
    else:
        logger.info("Ollama reachable at %s using model %s", base_url, model)

    if os.environ.get("AI_PROVIDER", "").lower() == "local_fast":
        backends = [item.strip().lower() for item in os.environ.get("LOCAL_FAST_BACKENDS", "").split(",")]
        if "freerouter" in backends:
            check_freerouter()


def check_freerouter() -> None:
    import requests

    base_url = os.environ.get("FREEROUTER_BASE_URL", "http://127.0.0.1:9000/v1").rstrip("/")
    health_url = base_url.removesuffix("/v1") + "/health"
    try:
        response = requests.get(health_url, timeout=5)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.warning("freeRouter not reachable at %s; local_fast will fall back if needed: %s", health_url, e)
        return
    logger.info("freeRouter reachable at %s", base_url)


def check_mcp() -> None:
    # Import here so status/dry-run do not require the full handler environment.
    from mcp_http_client import MCPHttpClient

    url = os.environ["MCP_SERVER_URL"]
    try:
        schema = MCPHttpClient(url, timeout=10).call_tool("get_snack_schema", {})
    except Exception as e:
        raise SystemExit(f"MCP health check failed at {url}: {e}") from e
    logger.info("MCP reachable at %s; schema type=%s", url, type(schema).__name__)


def run_worker(args: argparse.Namespace) -> None:
    sqs = make_sqs_client(args)
    stats = WorkerStats(started_at=time.time())

    if args.force_reprocess_completed:
        os.environ["FORCE_REPROCESS_COMPLETED"] = "true"
        logger.warning("FORCE_REPROCESS_COMPLETED=true: completed talks will be regenerated.")

    # Import after preflight so env vars are loaded and status mode stays cheap.
    from handler import handler

    logger.info(
        "Starting local SQS worker queue=%s batch_size=%d visibility=%ds dry_run=%s force_reprocess=%s",
        args.queue_url,
        args.batch_size,
        args.visibility_timeout,
        args.dry_run,
        args.force_reprocess_completed,
    )
    print_queue_status(sqs, args.queue_url)

    while not should_stop(args, stats):
        messages = receive_messages(sqs, args, remaining_message_budget(args, stats))
        if not messages:
            stats.empty_polls += 1
            logger.info("No messages received (empty_polls=%d).", stats.empty_polls)
            if should_stop_after_empty(args, stats):
                break
            sleep_if_needed(args.poll_delay_seconds)
            continue

        stats.empty_polls = 0
        stats.received += len(messages)
        records = [to_lambda_record(message) for message in messages]
        log_received(records)

        if args.dry_run:
            release_messages(sqs, args.queue_url, messages)
            sleep_if_needed(args.poll_delay_seconds)
            continue

        try:
            result = handler({"Records": records}, None)
        except Exception:
            stats.processed += len(messages)
            stats.failed += len(messages)
            logger.exception(
                "Handler crashed; no SQS messages from this batch were deleted. "
                "They will return after the visibility timeout."
            )
            sleep_if_needed(args.poll_delay_seconds)
            continue

        failed_ids = {
            item.get("itemIdentifier")
            for item in result.get("batchItemFailures", [])
        }
        successes = [
            message
            for message in messages
            if message.get("MessageId") not in failed_ids
        ]
        failures = len(messages) - len(successes)

        if successes:
            delete_messages(sqs, args.queue_url, successes)

        stats.processed += len(messages)
        stats.deleted += len(successes)
        stats.failed += failures
        logger.info(
            "Batch complete received=%d deleted=%d failed=%d totals=%s",
            len(messages),
            len(successes),
            failures,
            stats.__dict__,
        )
        sleep_if_needed(args.poll_delay_seconds)

    logger.info("Worker stopped. Final stats=%s", stats.__dict__)
    print_queue_status(sqs, args.queue_url)


def receive_messages(sqs, args: argparse.Namespace, max_to_receive: int | None) -> list[dict]:
    batch_size = args.batch_size if max_to_receive is None else min(args.batch_size, max_to_receive)
    if batch_size <= 0:
        return []
    response = sqs.receive_message(
        QueueUrl=args.queue_url,
        MaxNumberOfMessages=batch_size,
        WaitTimeSeconds=args.wait_time_seconds,
        VisibilityTimeout=5 if args.dry_run else args.visibility_timeout,
        AttributeNames=["All"],
        MessageAttributeNames=["All"],
    )
    return response.get("Messages", [])


def remaining_message_budget(args: argparse.Namespace, stats: WorkerStats) -> int | None:
    if args.max_messages is None:
        return None
    return max(0, args.max_messages - stats.received)


def should_stop(args: argparse.Namespace, stats: WorkerStats) -> bool:
    if _STOP_REQUESTED:
        return True
    if args.max_messages is not None and stats.received >= args.max_messages:
        return True
    if args.max_runtime_seconds is not None:
        if time.time() - stats.started_at >= args.max_runtime_seconds:
            return True
    return False


def should_stop_after_empty(args: argparse.Namespace, stats: WorkerStats) -> bool:
    return not args.forever and stats.empty_polls >= args.stop_after_empty_polls


def to_lambda_record(message: dict) -> dict:
    return {
        "messageId": message["MessageId"],
        "receiptHandle": message["ReceiptHandle"],
        "body": message.get("Body", ""),
        "attributes": message.get("Attributes", {}),
        "messageAttributes": message.get("MessageAttributes", {}),
        "md5OfBody": message.get("MD5OfBody"),
        "eventSource": "aws:sqs",
    }


def log_received(records: list[dict]) -> None:
    for record in records:
        try:
            body = json.loads(record["body"])
        except json.JSONDecodeError:
            body = {"rawBody": record["body"][:500]}
        logger.info(
            "Received message id=%s bucket=%s file_key=%s language=%s",
            record["messageId"],
            body.get("bucket"),
            body.get("file_key"),
            body.get("language"),
        )


def delete_messages(sqs, queue_url: str, messages: list[dict]) -> None:
    for chunk in chunks(messages, 10):
        entries = [
            {"Id": str(idx), "ReceiptHandle": message["ReceiptHandle"]}
            for idx, message in enumerate(chunk)
        ]
        response = sqs.delete_message_batch(QueueUrl=queue_url, Entries=entries)
        failed = response.get("Failed", [])
        if failed:
            raise RuntimeError(f"delete_message_batch failed for entries: {failed}")


def release_messages(sqs, queue_url: str, messages: list[dict]) -> None:
    for chunk in chunks(messages, 10):
        entries = [
            {
                "Id": str(idx),
                "ReceiptHandle": message["ReceiptHandle"],
                "VisibilityTimeout": 0,
            }
            for idx, message in enumerate(chunk)
        ]
        response = sqs.change_message_visibility_batch(QueueUrl=queue_url, Entries=entries)
        failed = response.get("Failed", [])
        if failed:
            raise RuntimeError(f"change_message_visibility_batch failed for entries: {failed}")
    logger.info("Dry-run released %d messages back to SQS.", len(messages))


def print_queue_status(sqs, queue_url: str) -> None:
    try:
        response = sqs.get_queue_attributes(
            QueueUrl=queue_url,
            AttributeNames=[
                "ApproximateNumberOfMessages",
                "ApproximateNumberOfMessagesNotVisible",
                "ApproximateNumberOfMessagesDelayed",
            ],
        )
    except Exception as e:
        raise SystemExit(f"Unable to read SQS queue attributes: {e}") from e

    attrs = response.get("Attributes", {})
    logger.info(
        "SQS status visible=%s in_flight=%s delayed=%s",
        attrs.get("ApproximateNumberOfMessages", "0"),
        attrs.get("ApproximateNumberOfMessagesNotVisible", "0"),
        attrs.get("ApproximateNumberOfMessagesDelayed", "0"),
    )


def chunks(items: list[dict], size: int):
    for index in range(0, len(items), size):
        yield items[index : index + size]


def sleep_if_needed(seconds: float) -> None:
    if seconds > 0 and not _STOP_REQUESTED:
        time.sleep(seconds)


if __name__ == "__main__":
    sys.exit(main())
