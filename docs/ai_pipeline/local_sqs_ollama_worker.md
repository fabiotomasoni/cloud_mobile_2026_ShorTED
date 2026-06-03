# Local SQS + Ollama Worker

This runbook runs the ShorTED AI Orchestrator locally instead of Lambda, while
keeping the same processing path:

SQS -> `handler.py` -> S3 processed -> Ollama + local MCP -> MongoDB

The worker is conservative by default:

- one SQS message per batch unless explicitly changed
- no parallel AI calls
- SQS messages are deleted only after `handler.py` reports success
- failed messages remain in SQS for normal visibility-timeout retry/DLQ handling
- `should_skip_ai`, MongoDB locks and delete-before-insert persistence are reused
- completed talks are skipped by default and reprocessed only with an explicit flag

## Local Fast Mode

For local/free-model throughput, use the separate provider:

```dotenv
AI_PROVIDER=local_fast
LOCAL_FAST_BACKENDS=freerouter,ollama
FREEROUTER_BASE_URL=http://127.0.0.1:9000/v1
FREEROUTER_API_KEY=
FREEROUTER_MODEL=groq/llama-3.1-8b-instant
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gemma4:e4b-mlx
```

`local_fast` is separate from the canonical `bedrock`, `openai`, and `ollama`
tool-loop providers. It asks the model for only the semantic snack fields and
fills deterministic metadata in Python (`talkSlug`, `language`, `speaker`,
`talkTitle`, `talkId`, `talkUrl`, canonical-ish tags). The normal final
validator still runs before MongoDB persistence.

Anti-duplication rules:

- run only one local worker unless you explicitly want distributed local work
- keep `FORCE_REPROCESS_COMPLETED=false` for queue draining
- keep the same `PIPELINE_VERSION` unless you intentionally want regeneration
- let MongoDB locks decide ownership; do not manually delete SQS messages
- use `--max-messages 1` for one-at-a-time testing

## 1. Environment

Set the same environment used by the Lambda Orchestrator, plus the queue URL:

```bash
export AI_PROVIDER=ollama
export OLLAMA_BASE_URL=http://localhost:11434
export OLLAMA_MODEL=llama3.1
export MCP_SERVER_URL=http://localhost:8080
export MONGODB_URI='mongodb+srv://...'
export MONGODB_DB=shorted
export SQS_QUEUE_URL='https://sqs...'
export AWS_REGION='...'
```

Optional safety knobs:

```bash
export LOCAL_WORKER_BATCH_SIZE=1
export LOCAL_WORKER_VISIBILITY_TIMEOUT=1800
export LOCAL_WORKER_POLL_DELAY_SECONDS=2
```

### `.env` files

Both the Orchestrator and MCP server call `python-dotenv`'s `load_dotenv()`.
Use two local files, one per component, and never commit them:

`scripts/AWS/ShorTED/Lambda/Orchestrator/.env`

```dotenv
AI_PROVIDER=local_fast
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1
OLLAMA_TIMEOUT_SECONDS=180
LOCAL_FAST_BACKENDS=freerouter,ollama
LOCAL_FAST_TIMEOUT_SECONDS=240
LOCAL_FAST_MAX_REPAIR_ATTEMPTS=1
LOCAL_FAST_TRANSCRIPT_MAX_CHARS=12000
LOCAL_FAST_TEMPERATURE=0.2
LOCAL_FAST_MAX_TOKENS=5000
FREEROUTER_BASE_URL=http://127.0.0.1:9000/v1
FREEROUTER_API_KEY=
FREEROUTER_MODEL=groq/llama-3.1-8b-instant

MCP_SERVER_URL=http://localhost:8080
MCP_TIMEOUT_SECONDS=30

MONGODB_URI=mongodb+srv://USER:PASSWORD@HOST/?retryWrites=true&w=majority
MONGODB_DB=shorted

SQS_QUEUE_URL=https://sqs.REGION.amazonaws.com/ACCOUNT/QUEUE
AWS_REGION=REGION
PROCESSED_BUCKET=shorted-processed

PIPELINE_VERSION=v1
DEFAULT_LANGUAGE=en
MIN_SNACKS=4
MAX_SNACKS=8
MIN_TAGS=3
MAX_TAGS=6

LOCK_TTL_SECONDS=1800
MAX_TOOL_LOOPS=20
MAX_REPAIR_ATTEMPTS=1

LOCAL_WORKER_BATCH_SIZE=1
LOCAL_WORKER_VISIBILITY_TIMEOUT=1800
LOCAL_WORKER_POLL_DELAY_SECONDS=2
LOCAL_WORKER_STOP_AFTER_EMPTY_POLLS=3

# Keep false for normal idempotent runs.
FORCE_REPROCESS_COMPLETED=false
```

`scripts/AWS/ShorTED/MCP/.env`

```dotenv
MONGODB_URI=mongodb+srv://USER:PASSWORD@HOST/?retryWrites=true&w=majority
MONGODB_DB=shorted
PORT=8080

MIN_SNACKS=4
MAX_SNACKS=8
MIN_SEGMENT_DURATION=20
MAX_SEGMENT_DURATION=150
MIN_DISTANCE_SECONDS=45
MAX_QUOTE_CHARS=180
MAX_MOTIVATIONAL_CHARS=500
MAX_APHORISM_CHARS=100
MIN_TAGS=3
MAX_TAGS=6
```

Run each component from its own directory so the intended `.env` is loaded:

```bash
cd scripts/AWS/ShorTED/MCP
python3 shorted_mcp_server.py

cd ../Lambda/Orchestrator
python3 local_sqs_worker.py status
```

## 2. Start local services

Start Ollama and make sure the selected model is available:

```bash
ollama pull "$OLLAMA_MODEL"
```

Start the local MCP server in another terminal:

```bash
cd scripts/AWS/ShorTED/MCP
python3 shorted_mcp_server.py
```

## 3. Check SQS status

```bash
cd scripts/AWS/ShorTED/Lambda/Orchestrator
python3 local_sqs_worker.py status
```

## 4. Dry-run one message

This receives one message, prints its S3 key and immediately releases it back
to SQS. It does not call AI, MongoDB or delete the message.

```bash
python3 local_sqs_worker.py run --dry-run --max-messages 1
```

## 5. Process a small safe batch

Start with a very small run:

```bash
python3 local_sqs_worker.py run --batch-size 1 --max-messages 3
```

Then inspect MongoDB and the queue status. If everything is healthy, continue:

```bash
python3 local_sqs_worker.py run --batch-size 1 --max-runtime-seconds 3600
```

Use `Ctrl+C` to request a graceful stop. The worker finishes the current batch,
deletes only successful messages and exits.

To deliberately regenerate already completed talks, use the explicit flag:

```bash
python3 local_sqs_worker.py run --batch-size 1 --max-messages 3 --force-reprocess-completed
```

Do not use that flag for the normal full queue drain.

## 6. Operational notes

- Keep `--batch-size 1` while using a local Ollama model unless the machine is
  clearly underused.
- Set `VisibilityTimeout` longer than the slowest expected AI run. If the local
  model is slow, use `--visibility-timeout 3600`.
- If a message fails, the worker does not delete it. SQS will make it visible
  again after the visibility timeout and eventually route it to the DLQ if the
  queue redrive policy is configured.
- If the local handler crashes before returning a partial-batch response, the
  worker deletes nothing from that batch; messages return after visibility
  timeout.
- If the same talk is already complete with the same `sourceHash` and pipeline
  version, the existing MongoDB skip check prevents another AI call and the SQS
  message is deleted as successful. Set `--force-reprocess-completed` only when
  you intentionally want to bypass this skip.
- The script reuses MongoDB locks from the Lambda implementation, so accidental
  duplicate local workers should not process the same talk simultaneously.
- Idempotent persistence is delete-before-insert scoped to
  `(slug, language, pipelineVersion, sourceHash)`, with deterministic snack IDs.
