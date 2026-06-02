# ShorTED - Istruzioni complete per implementare AI Orchestrator, MCP e generazione Snack

## 0. Scopo del documento

Questo documento e' un handoff operativo per un agente AI o uno sviluppatore incaricato di implementare il prossimo passo dell'architettura ShorTED: la Lambda AI Orchestrator, la pipeline AI multi-model con AWS Bedrock, l'uso attivo di un server MCP da parte dei modelli e il salvataggio finale sicuro su MongoDB.

Il documento contiene contesto, decisioni gia' prese, vincoli, struttura consigliata, flussi, schema dati, responsabilita' dei componenti, tool MCP, prompt strategy, criteri di validazione, gestione retry/idempotenza e piano di implementazione.

La regola principale e': non modificare cio' che e' gia' implementato fino a SQS. Il lavoro parte dal messaggio SQS e finisce con `talks` e `snacks` salvati in MongoDB.

---

## 1. Contesto generale del progetto

ShorTED e' un'app cloud/mobile che trasforma talk TED/TEDx lunghi in contenuti brevi e personalizzati, chiamati `snacks`. Ogni snack rappresenta un segmento interessante del talk, con topic, quote, summary, tag, score e link al video con timestamp.

L'architettura e' divisa in layer:

1. Data ingestion e processing.
2. AI snack generation.
3. Storage MongoDB.
4. Backend API.
5. App Flutter.

La parte gia' implementata arriva fino a SQS:

```text
CSV dataset / transcript source
  -> Transcript Fetcher
  -> S3 Raw
  -> Glue ETL
  -> S3 Processed
  -> Lambda Dispatcher
  -> SQS Queue
```

La parte da implementare ora e':

```text
SQS Queue
  -> Lambda AI Orchestrator
  -> Bedrock AI Orchestrator con uso attivo di MCP tools
  -> Lambda final validation + deterministic persistence
  -> MongoDB talks/snacks
```

---

## 2. File e componenti di riferimento

### 2.1 File architetturali importanti

Usare come riferimento:

- `architecture_graph.png`: grafo complessivo dell'architettura.
- `component_05.2_sqs_queue.md`: SQS come coda di distribuzione e retry.
- `component_06.1_lambda_ai.md`: ruolo della Lambda AI Orchestrator.
- `component_06.2_ai_pipeline.md`: pipeline AI multi-step.
- `component_07_mongodb.md`: collezioni `talks`, `snacks`, `users`.
- `processed_data_example.json`: esempio reale del formato dati dopo Glue.
- `tedx_server.py`: esempio di server MCP basato su FastMCP, da usare come riferimento strutturale ma non come implementazione finale.

### 2.2 Stato di `tedx_server.py`

Il file `tedx_server.py` attuale e' una demo MCP per interrogare una collection MongoDB `unibg_tedx_2026.tedx_data` tramite tool come:

- `search_by_tag`
- `search_by_speaker`
- `search_by_keyword`
- `get_talk`
- `top_tags`

Va considerato solo come esempio di struttura:

- usa `FastMCP`;
- definisce tool con `@mcp.tool()`;
- definisce resource con `@mcp.resource()`;
- definisce prompt con `@mcp.prompt()`;
- avvia un server HTTP streamable tramite uvicorn.

Non va mantenuto cosi' com'e'. Deve essere rifattorizzato o sostituito con un server specifico per ShorTED.

Problemi del server demo:

- credenziali Mongo hardcoded;
- database e collection non coerenti con ShorTED;
- tool orientati alla ricerca, non alla pipeline AI;
- nessun supporto per validazione snack;
- nessun supporto per deduplica;
- nessun supporto per schema `talks`/`snacks`;
- nessun supporto per regole del mixer;
- nessun uso pensato per AI tool-use nella generazione.

---

## 3. Formato dati processato da Glue

Il formato dopo Glue e' considerato valido. Non bisogna rifare ETL nella Lambda AI.

Esempio di struttura attesa:

```json
{
  "id": 1,
  "title": "Example Transcript",
  "slug": "example-transcript",
  "url": "https://example.com/transcripts/example-transcript",
  "duration": 3600,
  "tags": ["example", "transcript"],
  "related_videos": [2, 3],
  "presenterDisplayName": "John Doe",
  "speakers": ["John Doe", "Jane Smith"],
  "image": "https://example.com/image.jpg",
  "transcriptions": {
    "en": {
      "language": "English",
      "sentences": [
        {
          "timestamp": "7000",
          "text": "This is the first sentence of the transcript."
        }
      ],
      "raw": "This is the full transcript in English."
    },
    "it": {
      "language": "Italian",
      "sentences": [
        {
          "timestamp": "7000",
          "text": "Questo e' la prima frase della trascrizione."
        }
      ],
      "raw": "Questo e' la trascrizione completa in italiano."
    }
  }
}
```

### 3.1 Decisione importante: no nuova normalizzazione ETL

Non creare una nuova fase di normalizzazione pesante.

Glue ha gia' prodotto il dato processed. La Lambda AI deve solo costruire un contesto comodo per il modello, senza cambiare semanticamente il dato.

Chiamare questa parte:

```text
AI Input Adapter
```

oppure:

```text
AI Context Builder
```

Non chiamarla `normalizer`, per evitare confusione con ETL.

### 3.2 Cosa fa l'AI Input Adapter

L'AI Input Adapter puo' fare solo trasformazioni leggere e reversibili:

- scegliere la lingua da usare;
- estrarre `sentences` dalla trascrizione scelta;
- convertire timestamp stringa in millisecondi/secondi per comodita' del modello;
- preparare metadati principali: `id`, `title`, `slug`, `url`, `duration`, `tags`, `presenterDisplayName`, `speakers`, `image`;
- mantenere il JSON originale disponibile per audit/debug;
- calcolare un `sourceHash` del contenuto rilevante.

Non deve:

- ripulire semanticamente il transcript;
- riscrivere i campi prodotti da Glue;
- correggere tags o speaker in modo invasivo;
- spostare responsabilita' ETL dalla Glue job alla Lambda.

---

## 4. Decisioni architetturali gia' fissate

### 4.1 Fino a SQS e' gia' implementato

Non implementare o riprogettare:

- CSV dataset;
- transcript fetcher;
- S3 raw;
- Glue ETL;
- S3 processed;
- dispatcher;
- SQS queue.

Partire da SQS.

### 4.2 Lambda salva su MongoDB

Decisione finale: il salvataggio su MongoDB non viene delegato al modello tramite MCP.

La Lambda deve salvare in modo deterministico.

Motivazione:

- idempotenza piu' semplice;
- retry SQS piu' sicuri;
- meno rischio di salvataggi duplicati o parziali;
- gestione prevedibile di `processingStatus`;
- controllo migliore di `pipelineVersion`, `sourceHash` e replace/upsert;
- debug piu' semplice.

Formula architetturale:

```text
AI decide il contenuto.
MCP guida e controlla il ragionamento.
Lambda salva.
```

### 4.3 MCP deve essere usato attivamente dai modelli

MCP non deve essere solo una libreria chiamata dalla Lambda.

Il modello Bedrock deve avere accesso agli MCP tools e deve usarli attivamente durante il processo per:

- leggere lo schema snack;
- leggere regole del mixer;
- controllare snack esistenti o duplicati;
- validare candidati;
- validare il set finale;
- canonicalizzare tag;
- eventualmente recuperare risorse utili alla generazione.

La Lambda puo' fare pre-check deterministici e salvataggio, ma non deve usare MCP come scorciatoia al posto del modello per la parte AI.

### 4.4 Pre-check MongoDB prima di Bedrock

Prima di invocare Bedrock, la Lambda deve controllare se il talk e' gia' stato processato.

Questo serve a:

- risparmiare costo Bedrock;
- ridurre latenza;
- evitare lavoro duplicato;
- gestire retry SQS;
- garantire idempotenza.

Criterio consigliato per saltare AI:

```text
Skip AI se:
- esiste talk con slug uguale;
- language uguale;
- aiPipelineVersion uguale;
- sourceHash uguale;
- processingStatus = completed;
- snackCount >= MIN_SNACKS;
- gli snacks associati esistono realmente in collection `snacks`.
```

### 4.5 MCP non fa il commit finale

MCP puo' avere eventualmente tool di salvataggio per demo o test, ma nel path produttivo MVP non deve essere il writer finale.

Il modello deve restituire alla Lambda un JSON finale validato.

La Lambda poi:

- valida nuovamente in modo deterministico;
- salva il talk;
- salva/reinserisce gli snacks;
- aggiorna stato processing.

---

## 5. Architettura finale target

```text
SQS Queue
   |
   v
Lambda AI Orchestrator
   - parse SQS record
   - read processed JSON from S3
   - choose language
   - compute sourceHash
   - pre-flight MongoDB check
   - acquire processing lock
   - invoke Bedrock AI Orchestrator with MCP tools
   - final deterministic validation
   - deterministic MongoDB persistence
   - return SQS batch item failures if needed
   |
   v
Bedrock AI Orchestrator
   - inspect talk context
   - use MCP schema/rules tools
   - segment transcript
   - generate quote/summary/topic
   - tag/rank candidates
   - use MCP validation/dedup tools
   - repair invalid candidates
   - select final snacks
   - return final JSON + report
   |
   v
MCP Server ShorTED
   - exposes schemas
   - exposes mixer rules
   - validates candidates
   - validates final snack set
   - finds duplicates/similar snacks
   - canonicalizes tags
   - optionally exposes read-only Mongo context
   |
   v
MongoDB Atlas
   - talks
   - snacks
   - users
```

---

## 6. Lambda AI Orchestrator

### 6.1 Responsabilita'

La Lambda AI Orchestrator deve:

1. ricevere messaggi da SQS;
2. leggere il JSON processed da S3;
3. costruire il contesto AI senza rifare ETL;
4. calcolare `sourceHash`;
5. controllare MongoDB per skip/idempotenza;
6. acquisire un lock di processing;
7. invocare Bedrock AI Orchestrator con accesso MCP;
8. ricevere `final_snacks` e `processing_report`;
9. validare output in modo deterministico;
10. salvare talk e snacks su MongoDB;
11. aggiornare `processingStatus`;
12. gestire errori e retry SQS.

### 6.2 Responsabilita' escluse

La Lambda non deve:

- segmentare direttamente il transcript con logica manuale;
- generare quote/summary/tag senza modello;
- chiamare MCP al posto del modello per la parte creativa;
- fare salvataggi non idempotenti;
- modificare il formato prodotto da Glue in modo permanente.

### 6.3 Struttura file consigliata

```text
lambda_ai/
  handler.py
  config.py
  sqs_parser.py
  s3_processed_reader.py
  ai_context_builder.py
  source_hash.py
  mongo_repository.py
  processing_lock.py
  bedrock_orchestrator_client.py
  final_validator.py
  persistence.py
  errors.py
  models.py
  prompts/
    orchestrator_system_prompt.py
    output_schema.py
```

### 6.4 Variabili ambiente Lambda

```text
PROCESSED_BUCKET=shorted-processed
MONGODB_SECRET_NAME=shorted/mongodb-uri
MONGODB_DB=shorted
BEDROCK_REGION=eu-central-1 oppure us-east-1
BEDROCK_MODEL_ID=<model-id>
MCP_SERVER_URL=https://<mcp-server-url>
PIPELINE_VERSION=v1
DEFAULT_LANGUAGE=it oppure en
MIN_SNACKS=4
MAX_SNACKS=8
LOCK_TTL_SECONDS=900
```

Usare Secrets Manager per MongoDB URI. Non hardcodare credenziali.

### 6.5 IAM minimo

La Lambda ha bisogno di:

```text
s3:GetObject su bucket processed
sqs:ReceiveMessage
sqs:DeleteMessage
sqs:GetQueueAttributes
bedrock:InvokeModel
bedrock:InvokeModelWithResponseStream, se streaming usato
secretsmanager:GetSecretValue
logs:CreateLogGroup
logs:CreateLogStream
logs:PutLogEvents
```

---

## 7. Flusso Lambda dettagliato

### 7.1 Pseudocodice handler

```python
def handler(event, context):
    batch_failures = []

    for record in event["Records"]:
        try:
            message = parse_sqs_record(record)

            processed_json = read_processed_json_from_s3(
                bucket=message.bucket,
                key=message.key,
            )

            ai_context = build_ai_context(
                processed_json=processed_json,
                preferred_language=message.language or DEFAULT_LANGUAGE,
            )

            source_hash = compute_source_hash(ai_context)

            skip_result = mongo.should_skip_ai(
                talk_slug=ai_context.slug,
                language=ai_context.language,
                pipeline_version=PIPELINE_VERSION,
                source_hash=source_hash,
                min_snacks=MIN_SNACKS,
            )

            if skip_result.should_skip:
                log_skip(ai_context.slug, skip_result.reason)
                continue

            lock_acquired = mongo.acquire_processing_lock(
                talk_slug=ai_context.slug,
                language=ai_context.language,
                pipeline_version=PIPELINE_VERSION,
                source_hash=source_hash,
                ttl_seconds=LOCK_TTL_SECONDS,
            )

            if not lock_acquired:
                # Another Lambda is processing the same talk.
                # Choose policy: either ack as duplicate or fail for later retry.
                log_lock_not_acquired(ai_context.slug)
                continue

            ai_result = invoke_bedrock_orchestrator(
                ai_context=ai_context,
                mcp_server_url=MCP_SERVER_URL,
                pipeline_version=PIPELINE_VERSION,
            )

            final_validator.validate_ai_result(
                ai_result=ai_result,
                ai_context=ai_context,
                min_snacks=MIN_SNACKS,
                max_snacks=MAX_SNACKS,
            )

            persistence.save_talk_and_replace_snacks(
                processed_json=processed_json,
                ai_context=ai_context,
                ai_result=ai_result,
                source_hash=source_hash,
                pipeline_version=PIPELINE_VERSION,
            )

            mongo.mark_completed(
                talk_slug=ai_context.slug,
                language=ai_context.language,
                pipeline_version=PIPELINE_VERSION,
                source_hash=source_hash,
                snack_count=len(ai_result.final_snacks),
            )

        except PermanentInputError as e:
            mongo.mark_failed_if_possible(...)
            # Depending on DLQ strategy, either fail or ack.
            batch_failures.append({"itemIdentifier": record["messageId"]})

        except Exception as e:
            mongo.mark_failed_if_possible(...)
            batch_failures.append({"itemIdentifier": record["messageId"]})

    return {"batchItemFailures": batch_failures}
```

### 7.2 Batch item failures

Usare la partial batch response di SQS Lambda, cosi' se fallisce un record non vengono ritentati tutti gli altri.

---

## 8. Pre-flight check e idempotenza

### 8.1 `sourceHash`

Calcolare un hash stabile del contenuto rilevante usato per generare gli snack.

Input consigliato per hash:

```text
slug
title
speaker/speakers
language
transcription.raw oppure sentences con timestamp+text
source tags
duration
```

Non includere campi volatili come timestamp di processing.

### 8.2 Regola `should_skip_ai`

```python
def should_skip_ai(talk_slug, language, pipeline_version, source_hash, min_snacks):
    talk = talks.find_one({
        "slug": talk_slug,
        "language": language,
        "processingStatus": "completed",
        "aiPipelineVersion": pipeline_version,
        "sourceHash": source_hash,
    })

    if not talk:
        return False

    count = snacks.count_documents({
        "talkSlug": talk_slug,
        "language": language,
        "aiPipelineVersion": pipeline_version,
        "sourceHash": source_hash,
    })

    return count >= min_snacks
```

### 8.3 Lock di processing

Prima di chiamare Bedrock acquisire un lock logico su MongoDB.

Campi consigliati su `talks`:

```json
{
  "processingStatus": "processing",
  "lockExpiresAt": "2026-06-01T10:15:00Z",
  "processingStartedAt": "2026-06-01T10:00:00Z",
  "aiPipelineVersion": "v1",
  "sourceHash": "..."
}
```

Regole:

```text
completed + same version/hash + enough snacks -> skip
processing + lock valido -> non chiamare AI
processing + lock scaduto -> puo' riprendere
failed -> puo' ritentare
outdated version/hash -> rigenera
```

---

## 9. Bedrock AI Orchestrator

### 9.1 Ruolo

Il Bedrock AI Orchestrator e' il componente intelligente della pipeline.

Deve:

- analizzare il talk;
- segmentare il transcript;
- generare candidati snack;
- assegnare tag e score;
- usare MCP tools per schema, regole, validazione e deduplica;
- riparare candidati invalidi;
- selezionare il set finale;
- restituire JSON finale alla Lambda.

### 9.2 Non deve

Non deve:

- salvare su MongoDB;
- decidere da solo di terminare senza output valido;
- ignorare i tool MCP obbligatori;
- inventare quote non presenti nel transcript;
- restituire markdown al posto di JSON;
- restituire snack fuori schema.

### 9.3 Tool-use obbligatorio

Il prompt di sistema deve dire esplicitamente che il modello deve usare MCP per:

1. leggere schema snack;
2. leggere regole mixer;
3. validare candidati;
4. controllare duplicati/similarita';
5. validare il set finale.

Il salvataggio e' escluso.

---

## 10. Prompt strategy

### 10.1 System prompt concettuale

```text
You are the ShorTED AI Orchestrator.
Your task is to transform one processed TED/TEDx talk into 4-8 high-quality snack documents.

You have access to MCP tools. You must use them for schema discovery, mixer rules, candidate validation, duplicate checking and final set validation.

You must not save data. Persistence is handled by the Lambda Orchestrator.

Do not invent facts. Quotes must be grounded in the transcript. Prefer exact or near-exact transcript excerpts for quote.

Return only valid JSON matching the final output schema.
```

### 10.2 Sequenza desiderata interna al modello

```text
1. Read snack schema via MCP.
2. Read mixer rules via MCP.
3. Inspect talk metadata and transcript.
4. Segment the transcript into candidate thematic sections.
5. Generate quote, summary, topic and tags for each candidate.
6. Rank candidates.
7. Call MCP validation for candidates.
8. Repair invalid candidates.
9. Call MCP duplicate/similarity check.
10. Select 4-8 final snacks.
11. Call MCP final set validation.
12. Return final JSON to Lambda.
```

### 10.3 Output richiesto dal modello

```json
{
  "talk": {
    "talkId": "...",
    "slug": "...",
    "title": "...",
    "speaker": "...",
    "speakers": ["..."],
    "url": "...",
    "duration": 0,
    "imageUrl": "...",
    "sourceTags": ["..."],
    "language": "it"
  },
  "final_snacks": [
    {
      "segmentId": "seg_001",
      "talkId": "...",
      "talkSlug": "...",
      "speaker": "...",
      "talkTitle": "...",
      "topic": "...",
      "quote": "...",
      "summary": "...",
      "tags": ["..."],
      "score": 0.87,
      "startTime": 120,
      "endTime": 165,
      "talkUrl": "https://www.ted.com/talks/<slug>?t=120",
      "language": "it"
    }
  ],
  "processing_report": {
    "candidateSegments": 0,
    "candidateSnacks": 0,
    "finalSnacks": 0,
    "mcpToolsUsed": ["..."],
    "warnings": [],
    "status": "completed"
  }
}
```

---

## 11. MCP Server ShorTED

### 11.1 Nome consigliato

```text
shorted_mcp_server.py
```

### 11.2 Responsabilita'

Il server MCP deve fornire strumenti ufficiali al modello.

Responsabilita' principali:

- esporre schema `snack`;
- esporre schema `talk`;
- esporre regole del mixer;
- validare candidati;
- validare il set finale;
- controllare duplicati/similarita';
- canonicalizzare tag;
- costruire URL con timestamp;
- leggere snack esistenti per contesto/deduplica.

### 11.3 Non responsabilita' nel path MVP

Nel path MVP non deve:

- fare commit finale su MongoDB;
- sostituire la Lambda nel salvataggio;
- gestire retry SQS;
- essere l'unico punto di controllo dell'idempotenza.

### 11.4 Struttura consigliata

```text
mcp_server/
  shorted_mcp_server.py
  config.py
  mongo_client.py
  schemas.py
  validation.py
  duplicate_detection.py
  tag_utils.py
  resources.py
  prompts.py
```

### 11.5 Mongo connection

Usare variabili ambiente o Secrets Manager. Non hardcodare credenziali.

```text
MONGODB_URI=<from env/secret>
MONGODB_DB=shorted
```

### 11.6 Tool MCP consigliati

#### `get_processing_context`

Read-only. Utile al modello per sapere se esistono snack simili, ma non sostituisce il pre-check Lambda.

```python
@mcp.tool()
async def get_processing_context(talk_slug: str, language: str, pipeline_version: str) -> dict:
    """Return existing talk/snack metadata useful for duplicate checks."""
```

#### `get_existing_snacks`

```python
@mcp.tool()
async def get_existing_snacks(talk_slug: str, language: str | None = None, limit: int = 20) -> list[dict]:
    """Return existing snacks for a talk, without internal MongoDB ids unless needed."""
```

#### `validate_snack_candidate`

```python
@mcp.tool()
async def validate_snack_candidate(snack: dict) -> dict:
    """Validate one snack candidate against deterministic schema and business rules."""
```

Return example:

```json
{
  "valid": false,
  "errors": [
    {"field": "quote", "message": "quote exceeds max length"}
  ],
  "warnings": []
}
```

#### `validate_snack_candidates`

```python
@mcp.tool()
async def validate_snack_candidates(snacks: list[dict]) -> dict:
    """Validate multiple candidate snacks."""
```

#### `validate_final_snack_set`

```python
@mcp.tool()
async def validate_final_snack_set(snacks: list[dict], rules: dict | None = None) -> dict:
    """Validate the final selected snack set for count, spacing, duplicates and schema."""
```

Checks:

- count between MIN_SNACKS and MAX_SNACKS;
- no duplicate `segmentId`;
- no duplicate or near-duplicate quote;
- `startTime < endTime`;
- score in [0, 1];
- tags count in allowed range;
- no missing required fields.

#### `find_similar_snacks`

```python
@mcp.tool()
async def find_similar_snacks(talk_slug: str, candidate_snacks: list[dict]) -> dict:
    """Find similar existing or intra-batch snacks using deterministic heuristics."""
```

Initial heuristics:

- same `topic` lowercase;
- same/near same `quote`;
- overlapping start times;
- high tag overlap;
- same segmentId.

Future evolution: embeddings.

#### `canonicalize_tags`

```python
@mcp.tool()
async def canonicalize_tags(tags: list[str]) -> list[str]:
    """Normalize tags to lowercase, remove duplicates, strip spaces and map aliases."""
```

Examples:

```text
Artificial Intelligence -> ai
Machine Learning -> machine-learning
Self improvement -> self-improvement
```

#### `build_talk_url`

```python
@mcp.tool()
async def build_talk_url(base_url: str, start_time: int) -> str:
    """Build a talk URL with timestamp query parameter."""
```

Expected:

```text
https://www.ted.com/talks/<slug>?t=120
```

If the source URL already has query params, handle properly.

### 11.7 MCP resources

#### `shorted://schemas/snack`

Return canonical snack schema.

#### `shorted://schemas/talk`

Return canonical talk schema.

#### `shorted://rules/mixer`

Return rules such as:

```json
{
  "minSnacks": 4,
  "maxSnacks": 8,
  "minSegmentDurationSeconds": 20,
  "maxSegmentDurationSeconds": 150,
  "minDistanceSeconds": 45,
  "maxQuoteChars": 180,
  "maxSummaryChars": 500,
  "minTags": 3,
  "maxTags": 6
}
```

#### `shorted://rules/grounding`

Rules:

```text
- Quotes must be grounded in transcript.
- Do not invent facts.
- Summary must not introduce claims absent from transcript.
- Prefer self-contained segments.
- Avoid overly generic motivational statements.
```

### 11.8 MCP prompts

Prompts utili:

```python
@mcp.prompt()
def generate_snacks_prompt() -> str:
    ...
```

```python
@mcp.prompt()
def repair_invalid_snacks_prompt(validation_errors: str) -> str:
    ...
```

---

## 12. Snack Mixer: decisione finale

Il mixer non deve essere solo codice rigido, ma nemmeno completamente libero.

Scelta finale:

```text
Snack Mixer = AI-driven selection guided by MCP rules and validated by deterministic code.
```

Il modello sceglie i migliori snack, ma:

- legge le regole via MCP;
- valida candidati via MCP;
- controlla duplicati via MCP;
- valida set finale via MCP;
- restituisce solo output strutturato;
- la Lambda fa un'ultima validazione deterministica prima di salvare.

---

## 13. Schema MongoDB consigliato

### 13.1 Collection `talks`

```json
{
  "_id": "example-transcript:it:v1:<sourceHash>",
  "talkId": "1",
  "slug": "example-transcript",
  "title": "Example Transcript",
  "speaker": "John Doe",
  "speakers": ["John Doe", "Jane Smith"],
  "url": "https://example.com/transcripts/example-transcript",
  "duration": 3600,
  "imageUrl": "https://example.com/image.jpg",
  "sourceTags": ["example", "transcript"],
  "languages": ["en", "it"],
  "language": "it",
  "aiPipelineVersion": "v1",
  "sourceHash": "...",
  "processingStatus": "completed",
  "snackCount": 6,
  "processingStartedAt": "2026-06-01T10:00:00Z",
  "processedAt": "2026-06-01T10:03:00Z",
  "lockExpiresAt": null,
  "lastError": null
}
```

Alternative `_id`: usare `slug` come `_id` e mettere `language`, `pipelineVersion`, `sourceHash` come campi. Per supportare piu' lingue/versioni contemporaneamente, meglio un `_id` composto o un indice unique composto.

### 13.2 Collection `snacks`

```json
{
  "_id": "example-transcript:it:v1:seg_001",
  "segmentId": "seg_001",
  "talkId": "1",
  "talkSlug": "example-transcript",
  "speaker": "John Doe",
  "talkTitle": "Example Transcript",
  "topic": "Opening idea",
  "quote": "This is the first sentence of the transcript.",
  "summary": "The speaker introduces the central idea of the talk.",
  "tags": ["example", "transcript"],
  "score": 0.86,
  "startTime": 7,
  "endTime": 75,
  "talkUrl": "https://example.com/transcripts/example-transcript?t=7",
  "language": "it",
  "aiPipelineVersion": "v1",
  "sourceHash": "...",
  "createdAt": "2026-06-01T10:03:00Z"
}
```

### 13.3 Indici consigliati

```text
talks:
- unique(slug, language, aiPipelineVersion, sourceHash)
- index(processingStatus)
- index(lockExpiresAt)

snacks:
- unique(talkSlug, language, aiPipelineVersion, sourceHash, segmentId)
- index(talkSlug)
- index(tags)
- index(score)
- index(language)
- compound index(tags, score)
- compound index(talkSlug, language, aiPipelineVersion, sourceHash)
```

### 13.4 Persistenza idempotente

La Lambda deve salvare in modo atomico per quanto possibile:

1. upsert talk con `processingStatus = processing` o metadati aggiornati;
2. delete/replace snacks per stesso `(talkSlug, language, pipelineVersion, sourceHash)`;
3. insert final snacks;
4. update talk con `processingStatus = completed`, `snackCount`, `processedAt`, `lastError = null`.

Se MongoDB transaction non e' disponibile/configurata, implementare ordine sicuro e recovery:

- non marcare `completed` prima dell'inserimento snack;
- in caso di errore, marcare `failed` o lasciare lock scadere;
- usare replace by key per idempotenza.

---

## 14. Lingua

Il formato processed contiene piu' lingue in `transcriptions`.

Decisione configurabile:

```text
DEFAULT_LANGUAGE=it oppure en
```

Regola consigliata:

```text
1. usare DEFAULT_LANGUAGE se disponibile;
2. fallback su `en` se disponibile;
3. altrimenti usare la prima lingua disponibile;
4. salvare sempre `language` in talk e snack.
```

Per un'app italiana, `it` puo' essere preferita se disponibile.

---

## 15. Validazione finale in Lambda

Anche se il modello ha gia' usato MCP validation, la Lambda deve fare una validazione finale prima di salvare.

Controlli obbligatori:

```text
- output e' JSON valido;
- `final_snacks` e' lista;
- count tra MIN_SNACKS e MAX_SNACKS;
- ogni snack ha campi obbligatori;
- talkSlug coerente con il talk processato;
- language coerente;
- startTime >= 0;
- endTime > startTime;
- endTime <= duration se duration disponibile;
- quote non vuota;
- summary non vuoto;
- tags non vuoti e numero nel range;
- score tra 0 e 1;
- segmentId presente e unico;
- talkUrl presente;
- nessun duplicato evidente.
```

Se la validazione fallisce:

- non salvare;
- marcare `processingStatus = failed` o lasciare retry SQS;
- loggare errori con slug, language, pipelineVersion, sourceHash;
- valutare un retry Bedrock se l'errore e' riparabile.

---

## 16. Error handling

### 16.1 Errori permanenti

Esempi:

```text
- S3 object non trovato;
- JSON processed non valido;
- nessuna trascrizione disponibile;
- transcript vuoto;
- formato processed incompatibile.
```

Gestione:

- marcare talk `failed` se possibile;
- inviare a DLQ dopo retry configurati;
- non loopare indefinitamente.

### 16.2 Errori temporanei

Esempi:

```text
- timeout Bedrock;
- throttling Bedrock;
- errore rete MongoDB;
- MCP server temporaneamente non disponibile;
- Lambda timeout.
```

Gestione:

- lasciare fallire record per retry SQS;
- usare batch item failures;
- lock con scadenza per evitare blocchi permanenti.

### 16.3 Errori AI output

Esempi:

```text
- JSON non parseabile;
- schema errato;
- meno di MIN_SNACKS;
- quote mancanti;
- tool MCP obbligatori non usati;
- validation failed.
```

Gestione consigliata:

1. tentare una repair call al modello, passando errori di validazione;
2. se fallisce ancora, marcare failed e lasciare retry/DLQ secondo policy.

---

## 17. Osservabilita'

Loggare sempre:

```json
{
  "talkSlug": "example-transcript",
  "language": "it",
  "pipelineVersion": "v1",
  "sourceHash": "...",
  "status": "completed",
  "skipped": false,
  "candidateSegments": 12,
  "candidateSnacks": 10,
  "finalSnacks": 6,
  "mcpToolsUsed": [
    "get_snack_schema",
    "get_mixer_rules",
    "validate_snack_candidates",
    "find_similar_snacks",
    "validate_final_snack_set"
  ],
  "durationMs": 123456
}
```

Metriche utili:

```text
- AI invocations count
- skipped count
- failed count
- average snacks per talk
- Bedrock latency
- MCP latency
- MongoDB write latency
- validation failure count
- retry count
```

---

## 18. Testing

### 18.1 Unit test

Testare:

```text
- SQS parser;
- S3 processed reader;
- AI context builder;
- language fallback;
- sourceHash deterministico;
- should_skip_ai;
- lock acquire/release;
- final validator;
- persistence idempotente;
- MCP validation tools;
- duplicate detection;
- tag canonicalization.
```

### 18.2 Integration test locale

Usare `processed_data_example.json`.

Scenario:

```text
1. simulare messaggio SQS;
2. leggere JSON locale o S3 mock;
3. invocare modello mock o Bedrock test;
4. far usare MCP tools;
5. ricevere final_snacks;
6. validare;
7. salvare in MongoDB dev;
8. rilanciare lo stesso messaggio e verificare skip.
```

### 18.3 Test idempotenza

Eseguire due volte lo stesso input.

Atteso:

```text
- prima esecuzione: AI chiamata, snacks salvati;
- seconda esecuzione: AI non chiamata, skip;
- numero snack invariato;
- nessun duplicato.
```

### 18.4 Test sourceHash

Modificare transcript o lingua.

Atteso:

```text
- hash cambia;
- AI viene richiamata;
- nuovo set snack salvato con nuovo sourceHash.
```

### 18.5 Test lock

Simulare due Lambda concorrenti sullo stesso talk.

Atteso:

```text
- solo una acquisisce lock;
- l'altra non chiama Bedrock;
- niente duplicati.
```

---

## 19. Piano di implementazione consigliato

### Fase 1 - Mongo repository e idempotenza

Implementare:

```text
- connection Mongo da secret/env;
- should_skip_ai;
- acquire_processing_lock;
- mark_completed;
- mark_failed;
- save_talk_and_replace_snacks;
- indici MongoDB.
```

### Fase 2 - AI Input Adapter

Implementare:

```text
- lettura processed JSON;
- scelta lingua;
- estrazione sentences/raw;
- contesto AI;
- sourceHash.
```

### Fase 3 - MCP server ShorTED

Implementare:

```text
- resources schema/rules;
- validation tools;
- duplicate tools;
- canonicalize_tags;
- build_talk_url;
- read-only existing snacks.
```

### Fase 4 - Bedrock Orchestrator client

Implementare:

```text
- system prompt;
- output schema;
- MCP tool integration;
- parsing JSON;
- repair call in caso di output invalido.
```

### Fase 5 - Lambda handler end-to-end

Integrare:

```text
SQS -> S3 -> pre-check -> lock -> Bedrock+MCP -> validation -> MongoDB -> SQS response
```

### Fase 6 - Test e hardening

Testare:

```text
- skip;
- retry;
- lock;
- output invalido;
- transcript vuoto;
- MCP non disponibile;
- MongoDB non disponibile;
- Bedrock throttling.
```

---

## 20. Frase architetturale finale da mantenere nella documentazione

```text
The AI Orchestrator actively uses the MCP server for schema discovery, generation rules, duplicate detection and validation. However, the final MongoDB persistence is intentionally handled by the Lambda Orchestrator through deterministic code, to guarantee idempotency, safe retries and predictable database writes.
```

Versione italiana:

```text
L'AI Orchestrator usa attivamente il server MCP per scoprire gli schemi, leggere le regole di generazione, rilevare duplicati e validare gli snack. Tuttavia, la persistenza finale su MongoDB viene gestita intenzionalmente dalla Lambda Orchestrator con codice deterministico, per garantire idempotenza, retry sicuri e scritture prevedibili sul database.
```

---

## 21. Checklist finale per l'agente implementatore

Prima di considerare completa l'implementazione, verificare:

```text
[ ] La Lambda parte da SQS e non modifica componenti precedenti.
[ ] Il processed JSON viene usato come fonte valida prodotta da Glue.
[ ] Non esiste una seconda normalizzazione ETL.
[ ] Esiste un AI Context Builder leggero.
[ ] La Lambda fa pre-check MongoDB prima di Bedrock.
[ ] Esiste sourceHash stabile.
[ ] Esiste lock di processing.
[ ] Il modello Bedrock usa MCP tools attivamente.
[ ] MCP espone schema snack/talk.
[ ] MCP espone mixer rules.
[ ] MCP valida candidati.
[ ] MCP controlla duplicati/similarita'.
[ ] MCP valida set finale.
[ ] Il modello NON salva su MongoDB.
[ ] La Lambda valida output finale.
[ ] La Lambda salva in MongoDB in modo idempotente.
[ ] I retry SQS non producono duplicati.
[ ] I talk gia' processati vengono skippati senza chiamare Bedrock.
[ ] Esistono test con processed_data_example.json.
[ ] Credenziali non sono hardcoded.
[ ] Log e metriche sono sufficienti per debug.
```

---

## 22. Output atteso finale del lavoro

Alla fine dell'implementazione devono esistere:

```text
1. Lambda AI Orchestrator funzionante.
2. Server MCP ShorTED funzionante.
3. Integrazione Bedrock con MCP tool-use.
4. Pre-check e lock MongoDB.
5. Validazione finale Lambda.
6. Salvataggio idempotente su MongoDB.
7. Test end-to-end con processed_data_example.json.
8. Documentazione aggiornata dell'architettura.
```

