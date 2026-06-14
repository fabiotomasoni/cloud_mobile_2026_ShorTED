# AI Pipeline ShorTED — Documentazione Tecnica

## Panoramica

Questo documento descrive l'implementazione completa della AI pipeline ShorTED: dalla ricezione del messaggio SQS alla scrittura degli snack su MongoDB. Copre tutti i moduli Python, le decisioni architetturali, il protocollo MCP, la gestione degli errori e il workflow di test locale.

La documentazione istruttiva di alto livello si trova in [`ai_pipeline_instructions.md`](./ai_pipeline_instructions.md).

---

## Struttura dei componenti

```
scripts/AWS/ShorTED/
├── Lambda/
│   └── Orchestrator/               ← Lambda AI Orchestrator
│       ├── handler.py              ← Entry point Lambda
│       ├── config.py               ← Env vars + dotenv locale
│       ├── models.py               ← Dataclasses (SQSMessage, AIContext, SnackDoc, …)
│       ├── errors.py               ← Custom exceptions
│       ├── sqs_parser.py           ← Parsing record SQS
│       ├── s3_processed_reader.py  ← Lettura JSON da S3
│       ├── ai_context_builder.py   ← Selezione lingua + costruzione AIContext
│       ├── source_hash.py          ← SHA-256 stabile del contenuto talk
│       ├── mongo_repository.py     ← Skip check, lock, mark completed/failed
│       ├── persistence.py          ← Save idempotente (delete-before-insert)
│       ├── mcp_http_client.py      ← HTTP client MCP + Bedrock tool definitions
│       ├── bedrock_orchestrator_client.py  ← Bedrock Converse + tool-use loop
│       ├── final_validator.py      ← Validazione deterministica pre-MongoDB
│       ├── create_indexes.py       ← Script one-shot indici MongoDB
│       ├── prompts/
│       │   ├── orchestrator_system_prompt.py  ← System prompt builder
│       │   └── output_schema.py               ← JSON schema atteso dal modello
│       ├── test_local_full.py      ← Test locale completo (no AWS, no MongoDB)
│       ├── requirements.txt
│       └── .env.example
└── MCP/
    └── ShorTED/                    ← MCP Server ShorTED
        ├── shorted_mcp_server.py   ← Entry point FastMCP (uvicorn / Lambda)
        ├── config.py               ← Env vars + dotenv locale
        ├── mongo_client.py         ← Async MongoDB client (motor)
        ├── schemas.py              ← JSON schema snack e talk
        ├── validation.py           ← Logica validazione snack (candidato, batch, set)
        ├── duplicate_detection.py  ← Rilevamento duplicati (euristica)
        ├── tag_utils.py            ← Normalizzazione tag (alias map, lowercase, hyphen)
        ├── resources.py            ← MCP resources (schemi, regole)
        ├── prompts.py              ← MCP prompts riutilizzabili
        ├── requirements.txt
        └── .env.example
```

---

## Flusso end-to-end

```
SQS message (Dispatcher)
    │
    ▼
handler.py
    ├─ sqs_parser.py          → SQSMessage
    ├─ s3_processed_reader.py → processed JSON (da S3)
    ├─ ai_context_builder.py  → AIContext (lingua, sentences, raw_transcript)
    ├─ source_hash.py         → SHA-256 (idempotency key)
    ├─ mongo_repository.py    → should_skip_ai? (pre-flight)
    ├─ mongo_repository.py    → acquire_processing_lock (atomico)
    │
    ├─ bedrock_orchestrator_client.py
    │       │
    │       ├─ Bedrock Converse (Nova Lite) ←──────────────┐
    │       │       ↓ tool_use request                      │
    │       ├─ mcp_http_client.py → MCP Server ShorTED     │
    │       │       ↓ tool result                           │
    │       └───────────────────────────────────────────────┘
    │       ↓ end_turn (final JSON)
    │
    ├─ final_validator.py     → validazione deterministica
    ├─ persistence.py         → delete-before-insert snacks + upsert talk
    └─ mongo_repository.py    → mark_completed
         ↓
    MongoDB: talks + snacks
```

---

## Lambda AI Orchestrator

### `handler.py` — Entry point

Il Lambda handler processa una batch SQS e ritorna `batchItemFailures` per il meccanismo SQS partial batch response.

**Gestione errori:**

| Eccezione | Comportamento | SQS |
|---|---|---|
| `PermanentInputError` | mark_failed + log | → DLQ |
| `AIOutputInvalidError` | mark_failed + log | → DLQ |
| `LockNotAcquiredError` | silent skip | auto-delete |
| `MCPServerError` | mark_failed + retry | → coda (retry) |
| `MongoRepositoryError` | mark_failed + retry | → coda (retry) |
| Exception generico | mark_failed + retry | → coda (retry) |

### `ai_context_builder.py` — AI Input Adapter

Trasforma il processed JSON in un `AIContext` compatto per il modello. **Non è un secondo ETL** — si limita a:
- selezionare la lingua (fallback chain: `preferred → en → primo disponibile`)
- estrarre `sentences` normalizzando i timestamp in ms interi
- costruire il `raw_transcript` concatenato se assente

### `source_hash.py` — Idempotency Key

SHA-256 stabile dei campi content-determining (`slug`, `title`, `speakers`, `language`, `raw_transcript`, `source_tags`, `duration`). Cambia solo se il contenuto del talk cambia in modo significativo. Usato per:
- skip check pre-flight
- scoping della collection snacks (delete-before-insert)
- rilevamento di talk aggiornati da rigenerare

### `mongo_repository.py` — Lock + Status

Gestisce il ciclo di vita del lock di elaborazione con `find_one_and_update` (atomico):

**Lock grant conditions** (almeno una vera):
- Il documento non esiste ancora (`upsert`)
- `processingStatus` è `null` o `failed`
- `processingStatus` è `processing` E `lockExpiresAt` è scaduto
- `aiPipelineVersion` è cambiata (nuova versione pipeline)
- `sourceHash` è cambiato (contenuto aggiornato)

**TTL:** 900s (= timeout massimo Lambda). Un lock scaduto viene rilevato automaticamente al prossimo messaggio SQS.

### `persistence.py` — Delete-before-insert

Ordinamento di persistenza sicuro per retry SQS:
1. `delete_many` snacks per `(slug, language, pipelineVersion, sourceHash)` → stato pulito
2. `insert_many` nuovi snacks → `_id` deterministico: `{slug}:{language}:{version}:{segmentId}`
3. `update_one` (upsert) talk metadata — **senza** aggiornare `processingStatus`
4. `mark_completed` separato — chiamato solo dopo che `persistence.py` è tornato senza errori

Se il Lambda crasha dopo il punto 2 ma prima del punto 4, al retry:
- il talk ha ancora `processingStatus=processing`
- il lock è scaduto → viene riassegnato
- al passo 1 gli snacks parziali vengono rimossi → stato completamente pulito

---

## MCP Server ShorTED

### Modalità di esecuzione

| Modalità | Comando | Porta |
|---|---|---|
| Locale (sviluppo) | `python shorted_mcp_server.py` | `http://localhost:8080` |
| AWS Lambda Function URL | handler `shorted_mcp_server.lambda_handler` | HTTPS automatico |

### Tools esposti al modello AI

| Tool | Input | Output | Note |
|---|---|---|---|
| `get_processing_context` | slug, language, version | talk metadata + snack count | Read-only |
| `get_existing_snacks` | slug, language?, limit? | lista snack DB | Per cross-DB duplicate check |
| `validate_snack_candidate` | snack object | `{valid, errors, warnings}` | Singolo candidato |
| `validate_snack_candidates` | lista snack | `{results: [...]}` | Batch validation |
| `validate_final_snack_set` | lista snack | `{valid, errors, warnings, stats}` | Count, spacing, dedup |
| `find_similar_snacks` | slug, lista candidati | `{intraBatch, crossDb, hasDuplicates}` | Euristica 4 criteri |
| `canonicalize_tags` | lista tag raw | lista tag canonici | Lowercase, hyphen, alias |
| `build_talk_url` | base_url, start_time | URL con `?t=<start_time>` | Deterministico |

### Resources esposte

| URI | Contenuto |
|---|---|
| `shorted://schemas/snack` | JSON schema canonico snack |
| `shorted://schemas/talk` | JSON schema canonico talk |
| `shorted://rules/mixer` | Regole numeriche (count, duration, spacing, length) |
| `shorted://rules/grounding` | Regole qualità e grounding (testo) |

### `validation.py` — Regole di validazione

**Regole per snack singolo:**
- Tutti i campi required presenti e non vuoti
- `score` in `[0.0, 1.0]`
- `startTime >= 0`, `endTime > startTime`
- Durata segmento: `[20s, 150s]` (warning, non error)
- `quote` ≤ 180 caratteri
- `motivationalText` ≤ 500 caratteri
- `aphorism` ≤ 100 caratteri
- `tags` count in `[3, 6]`

**Regole aggiuntive per set finale:**
- Count in `[4, 8]`
- Nessun `segmentId` duplicato
- Nessuna `quote` duplicata (case-insensitive)
- Distanza minima tra snack consecutivi: 45s (warning)

### `duplicate_detection.py` — Euristica similarità

| Criterio | Soglia |
|---|---|
| Stesso `topic` (case-insensitive) | = |
| `quote` similarity (SequenceMatcher) | ≥ 0.85 |
| `startTime` distance | < 45s |
| Tag Jaccard overlap | ≥ 80% |

Architettura predisposta per embeddings semantici futuri (stesso contratto di interfaccia).

### `tag_utils.py` — Alias map

La normalizzazione applica una alias map (`"Artificial Intelligence" → "ai"`, `"Machine Learning" → "machine-learning"`, ecc.) dopo la lowercasification e prima della deduplicazione. La alias map può essere estesa senza deploy grazie alla separazione config/codice.

---

## Bedrock AI Orchestrator

### Modello

**`amazon.nova-lite-v1:0`** — Bedrock Converse API (region: `us-east-1`)

| Metrica | Valore |
|---|---|
| Costo input | ~$0.06/1M token |
| Costo output | ~$0.24/1M token |
| Costo stimato/talk | ~$0.0021 |
| Costo totale 8.000 talk | ~$16.80 |
| Margine su budget $50 | ~$33 |

### Tool-use loop

```
user_message → Bedrock (Nova Lite)
    ├─ stopReason=tool_use → esegui MCP tools → loop
    ├─ stopReason=end_turn → estrai JSON finale
    ├─ stopReason=max_tokens → AIOutputInvalidError
    └─ max_loops (20) → AIOutputInvalidError
```

**Repair call:** se il JSON finale è invalido, viene fatta una seconda chiamata Bedrock con l'output originale e gli errori di validazione. Massimo 1 repair attempt.

### System prompt

Il system prompt contiene:
- Metadati del talk (title, speaker, slug, language, duration, tags, URL)
- Prime 20 sentences con timestamp
- Transcript completo
- Schema snack (inline)
- Regole mixer (inline)
- Regole grounding (inline) - CRITICAL: motivationalText al posto del summary
- Sequenza tool-use obbligatoria (ordinata)
- Hard constraints (talkSlug fisso, language fisso, no markdown, no persistence)
- Schema JSON dell'output richiesto

---

## MongoDB — Struttura documenti

### Collection `talks`

```json
{
  "_id": ObjectId,
  "slug": "tiago_forte_second_brain",
  "language": "en",
  "talkId": "42",
  "title": "How to Build a Second Brain",
  "speaker": "Tiago Forte",
  "speakers": ["Tiago Forte"],
  "url": "https://www.ted.com/talks/...",
  "duration": 1080,
  "imageUrl": "https://...",
  "sourceTags": ["productivity", "knowledge-management"],
  "aiPipelineVersion": "v1",
  "sourceHash": "d66429132f2d26cc...",
  "processingStatus": "completed",
  "snackCount": 6,
  "processedAt": "2026-06-02T00:35:31Z",
  "lockExpiresAt": null,
  "lastError": null
}
```

**Unique index:** `(slug, language, aiPipelineVersion)`

**Stati di `processingStatus`:**

```
null / assente → processing → completed
                             → failed
```

### Collection `snacks`

```json
{
  "_id": "tiago_forte_second_brain:en:v1:seg_003",
  "segmentId": "seg_003",
  "talkId": "42",
  "talkSlug": "tiago_forte_second_brain",
  "speaker": "Tiago Forte",
  "talkTitle": "How to Build a Second Brain",
  "topic": "The four core capabilities of a Second Brain",
  "quote": "There are four essential capabilities that a second brain gives you: remembering, connecting, creating, and sharing.",
  "motivationalText": "A powerful knowledge system doesn't just save data; it enables action. It empowers you to remember fleeting insights, connect disparate concepts across domains, use accumulated knowledge as raw material for new work, and ultimately turn private insights into public value that helps others.",
  "aphorism": "From Capture to Creation: unlocking knowledge's full potential.",
  "tags": ["knowledge-management", "productivity", "creativity"],
  "score": 0.97,
  "startTime": 122,
  "endTime": 215,
  "talkUrl": "https://www.ted.com/talks/tiago_forte_second_brain?t=122",
  "language": "en",
  "aiPipelineVersion": "v1",
  "sourceHash": "d66429132f2d26cc...",
  "createdAt": "2026-06-02T00:35:31Z"
}
```

**Unique index:** `(talkSlug, language, aiPipelineVersion, sourceHash, segmentId)`

---

## Setup e configurazione

### Variabili ambiente (Lambda Orchestrator)

| Variabile | Obbligatoria | Default | Descrizione |
|---|---|---|---|
| `MONGODB_URI` | ✅ | — | MongoDB Atlas connection string |
| `MCP_SERVER_URL` | ✅ | — | URL MCP server (locale o Lambda Function URL) |
| `MONGODB_DB` | — | `shorted` | Nome database |
| `PROCESSED_BUCKET` | — | `shorted-processed` | S3 bucket processed |
| `BEDROCK_REGION` | — | `us-east-1` | AWS region Bedrock |
| `BEDROCK_MODEL_ID` | — | `amazon.nova-lite-v1:0` | Modello Bedrock |
| `PIPELINE_VERSION` | — | `v1` | Versione pipeline (usata come partition key) |
| `DEFAULT_LANGUAGE` | — | `en` | Lingua default se non specificata nel messaggio |
| `MIN_SNACKS` | — | `4` | Minimo snack per talk |
| `MAX_SNACKS` | — | `8` | Massimo snack per talk |
| `LOCK_TTL_SECONDS` | — | `900` | TTL lock elaborazione (= timeout Lambda max) |
| `MAX_TOOL_LOOPS` | — | `20` | Massimo iterazioni tool-use loop Bedrock |
| `MAX_REPAIR_ATTEMPTS` | — | `1` | Tentativi repair se output AI invalido |

### Variabili ambiente (MCP Server)

| Variabile | Obbligatoria | Default | Descrizione |
|---|---|---|---|
| `MONGODB_URI` | ✅ | — | MongoDB Atlas connection string |
| `MONGODB_DB` | — | `shorted` | Nome database |
| `MIN_SNACKS` | — | `4` | Minimo snack per talk |
| `MAX_SNACKS` | — | `8` | Massimo snack per talk |
| `MIN_SEGMENT_DURATION` | — | `20` | Durata minima segmento (s) |
| `MAX_SEGMENT_DURATION` | — | `150` | Durata massima segmento (s) |
| `MIN_DISTANCE_SECONDS` | — | `45` | Distanza minima tra snack (s) |
| `MAX_QUOTE_CHARS` | — | `180` | Lunghezza massima quote |
| `MAX_MOTIVATIONAL_CHARS` | — | `500` | Lunghezza massima motivationalText |
| `MAX_APHORISM_CHARS` | — | `100` | Lunghezza massima aphorism |
| `MIN_TAGS` | — | `3` | Minimo tag per snack |
| `MAX_TAGS` | — | `6` | Massimo tag per snack |
| `PORT` | — | `8080` | Porta uvicorn (solo locale) |

---

## Test locale

### `test_local_full.py` — Zero servizi esterni

Script di integrazione completo che sostituisce tutti i servizi AWS con mock in-memory:

| Servizio | Mock |
|---|---|
| S3 | JSON built-in (talk mock completo: 26 sentences, metadati reali) |
| MongoDB | `_MockCollection` in-memory (supporta `$or`, `$in`, `$lt`, `$ne`, upsert) |
| MCP Server | tools chiamati direttamente come funzioni Python (no HTTP) |
| Bedrock | Ollama `/api/chat` con modello locale (es. `gemma4:12b-mlx`) |

**Cosa verifica:**
1. Build AI context e source hash
2. Skip check (pre-flight) — run 1: `not_found`
3. Lock acquisition
4. AI tool-use loop con Ollama (MCP tools reali)
5. Final deterministic validation
6. Persist mock MongoDB (delete-before-insert)
7. Run 2: skip check → `already_completed` (idempotenza verificata)
8. Summary MongoDB (talks + snacks prodotti)

**Esecuzione:**
```bash
cd scripts/AWS/ShorTED/Lambda/Orchestrator
python3 test_local_full.py
```

> **Prerequisiti:** Ollama installato e attivo con `gemma4:12b-mlx` (o altro modello con tool-use support).

**Output:** salvato in `test_output/` (gitignored) — vedi sezione successiva.

---

## Test MCP Server locale (con Ollama)

È possibile testare il server MCP in isolamento avviandolo localmente e interrogandolo con richieste HTTP dirette, senza bisogno di avviare l'intero orchestratore.

### 1. Avvio server MCP

```bash
cd scripts/AWS/ShorTED/MCP
# Crea .env copiando l'esempio e impostando MONGODB_URI
cp .env.example .env
# Avvia il server (uvicorn su porta 8080)
python shorted_mcp_server.py
```

### 2. Verifica health

```bash
curl http://localhost:8080/
```

### 3. Chiamata diretta a un tool MCP (HTTP)

```bash
curl -X POST http://localhost:8080/mcp/v1/tools/call \
  -H 'Content-Type: application/json' \
  -d '{"name": "canonicalize_tags", "arguments": {"tags": ["AI", "machine learning", "Productivity"]}}'
```

### 4. Test con Ollama come client MCP

Ollama può chiamare il server MCP locale direttamente usando `ollama run` con un tool-use prompt strutturato. Il modo più semplice è usare il test script già disponibile:

```bash
cd scripts/AWS/ShorTED/Lambda/Orchestrator
# Il test_local_full.py usa già Ollama come orchestratore con gli MCP tools mockati inline.
# Per testare contro il vero server MCP locale:
# 1. Avvia il server MCP in un terminale separato (vedi sopra)
# 2. Nel .env dell'orchestratore imposta: MCP_SERVER_URL=http://localhost:8080
# 3. Esegui il test (poi potrà usare HTTP reale verso il server MCP)
python test_local_full.py
```

> **Nota:** `test_local_full.py` usa i tool MCP come funzioni Python inline (senza HTTP) per massima semplicità e velocità. Per testare il server HTTP reale in produzione, usare il Bedrock client o un client MCP compatibile.

---

## Deploy su AWS Academy

### Lambda Orchestrator

```bash
cd scripts/AWS/ShorTED/Lambda/Orchestrator
pip install -r requirements.txt -t ./package
cp -r *.py prompts/ package/
cd package && zip -r ../orchestrator.zip . && cd ..
```

Upload `orchestrator.zip` nella console Lambda:
- **Handler:** `handler.handler`
- **Runtime:** Python 3.12
- **Timeout:** 15 minuti
- **Trigger:** SQS queue (`shorted-queue`)
- **Env vars:** dalla console (vedi `.env.example`)

### MCP Server (Lambda Function URL)

```bash
cd scripts/AWS/ShorTED/MCP
pip install -r requirements.txt -t ./package
cp *.py package/
cd package && zip -r ../mcp_server.zip . && cd ..
```

Upload `mcp_server.zip` nella console Lambda:
- **Handler:** `shorted_mcp_server.lambda_handler`
- **Runtime:** Python 3.12
- **Timeout:** 30 secondi
- **Function URL:** abilitata (auth: NONE per demo)
- Copiare la **Function URL** → impostare come `MCP_SERVER_URL` nella Lambda Orchestrator

### Indici MongoDB (una volta sola)

```bash
cd scripts/AWS/ShorTED/Lambda/Orchestrator
MONGODB_URI=mongodb+srv://... python3 create_indexes.py
```

---

## Checklist pre-deploy AWS

- [ ] `amazon.nova-lite-v1:0` abilitato in Bedrock Console → **Model access** (us-east-1)
- [ ] Cluster MongoDB ShorTED creato su Atlas (piano M0 free tier sufficiente per test)
- [ ] `create_indexes.py` eseguito contro il cluster ShorTED
- [ ] MCP Server deployato come Lambda e Function URL attiva
- [ ] Lambda Orchestrator: tutte le env vars configurate dalla console
- [ ] IAM role Lambda: permessi `bedrock:InvokeModel`, `s3:GetObject` su `shorted-processed`, `sqs:*` sulla queue
- [ ] Test locale con `test_local_full.py` passato prima di deployare
