# ShorTED Lambda environment variables

## ShorTED-MCP-Server

Required:

- `MONGODB_URI`: MongoDB Atlas connection string.

Optional:

- `MONGODB_DB`: database name. Current AWS value: `snacks`.
- `PORT`: local uvicorn port only, default `8080`.
- `MIN_SNACKS`: default `4`.
- `MAX_SNACKS`: default `8`.
- `MIN_SEGMENT_DURATION`: default `20`.
- `MAX_SEGMENT_DURATION`: default `150`.
- `MIN_DISTANCE_SECONDS`: default `45`.
- `MAX_QUOTE_CHARS`: default `180`.
- `MAX_MOTIVATIONAL_CHARS`: default `500`.
- `MAX_APHORISM_CHARS`: default `100`.
- `MIN_TAGS`: default `3`.
- `MAX_TAGS`: default `6`.

AWS runtime:

- Runtime: Python 3.12.
- Architecture: x86_64.
- Handler: `shorted_mcp_server.lambda_handler`.
- Function URL: enabled; this URL becomes `MCP_SERVER_URL` in the Orchestrator.

## ShorTED-AI-Orchestrator

Required for all providers:

- `MONGODB_URI`: MongoDB Atlas connection string.
- `MCP_SERVER_URL`: ShorTED MCP Lambda Function URL, without `/mcp` at the end.

Optional common settings:

- `MONGODB_DB`: database name. Current AWS value: `snacks`.
- `PROCESSED_BUCKET`: default `shorted-processed`.
- `PIPELINE_VERSION`: default `v1`.
- `DEFAULT_LANGUAGE`: default `en`.
- `MCP_TIMEOUT_SECONDS`: default `30`.
- `MIN_SNACKS`: default `4`.
- `MAX_SNACKS`: default `8`.
- `MIN_TAGS`: default `3`.
- `MAX_TAGS`: default `6`.
- `MAX_APHORISM_CHARS`: default `100`.
- `LOCK_TTL_SECONDS`: default `900`.
- `MAX_TOOL_LOOPS`: default `20`.
- `MAX_REPAIR_ATTEMPTS`: default `1`.

AI provider selection:

- `AI_PROVIDER`: one of `bedrock`, `openai`, `ollama`. Default: `bedrock`.

OpenAI provider:

- `AI_PROVIDER=openai`
- `OPENAI_API_KEY`: required.
- `OPENAI_MODEL`: default `gpt-5.4-mini`.
- `OPENAI_BASE_URL`: default `https://api.openai.com/v1`.
- `OPENAI_TIMEOUT_SECONDS`: default `120`.
- `OPENAI_MAX_OUTPUT_TOKENS`: default `8192`.

Ollama provider:

- `AI_PROVIDER=ollama`
- `OLLAMA_BASE_URL`: default `http://localhost:11434`.
- `OLLAMA_MODEL`: default `llama3.1`.
- `OLLAMA_TIMEOUT_SECONDS`: default `180`.

Important: if the Orchestrator runs in AWS Lambda, `localhost` means the Lambda
container, not your laptop. To use Ollama on your machine from Lambda, expose it
through a reachable URL such as a temporary tunnel, then set `OLLAMA_BASE_URL`
to that URL. If the Orchestrator runs locally, `http://localhost:11434` is fine.

Bedrock provider:

- `AI_PROVIDER=bedrock`
- `BEDROCK_REGION`: default `us-east-1`.
- `BEDROCK_MODEL_ID`: default `amazon.nova-lite-v1:0`.

In AWS Academy, current `LabRole` tests failed for Bedrock because
`bedrock:InvokeModel` is denied.

## SQS trigger

For `ShorTED-AI-Orchestrator`, enable `ReportBatchItemFailures` on the SQS event
source mapping. Otherwise Lambda ignores the handler's `batchItemFailures`
response and SQS deletes failed messages.
