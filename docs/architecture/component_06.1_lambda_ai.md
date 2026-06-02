# Componente 6 — Lambda AI Orchestrator

## Ruolo nel sistema
Cuore analitico della pipeline. Trasforma un documento talk (metadati + transcript) in un insieme di "snacks" — i contenuti snackable che costituiscono il contenuto core di ShorTED.

La Lambda AI mantiene la responsabilità di orchestrare il processo: riceve il messaggio da SQS, legge il talk da S3 processed, esegue la AI Snack Pipeline tramite Bedrock + MCP e salva il risultato finale su MongoDB in modo idempotente.

## Posizione nel pipeline
- **Trigger da:** Componente 5.2 (SQS Queue) — una invocazione per talk
- **Legge da:** Componente 4 (S3 Processed Bucket) — documento JSON del talk
- **Usa:** AWS Bedrock (Nova Lite) + MCP Server ShorTED per la generazione AI
- **Scrive su:** Componente 7 (MongoDB) — collezioni `talks` e `snacks`

## Cosa fa
Per ogni talk ricevuto dalla coda:
1. Parsing del messaggio SQS (bucket + file_key + language opzionale)
2. Lettura e validazione del JSON processed da S3
3. Costruzione dell'`AIContext` — selezione lingua, estrazione sentences, source hash SHA-256
4. Pre-flight check su MongoDB: skip se già completato con stesso hash e versione pipeline
5. Acquisizione lock atomico: evita elaborazioni parallele dello stesso talk
6. Invocazione Bedrock Converse (Nova Lite) in loop multi-turn con tool-use MCP
7. Validazione deterministica dell'output AI prima del salvataggio
8. Persistenza idempotente: delete-before-insert snacks + upsert talk
9. Mark completed e rilascio lock
10. SQS partial batch response: solo i messaggi falliti tornano in coda

## Output — lo "snack"
Unità fondamentale di contenuto di ShorTED. Ogni talk produce 4–8 snacks.

```json
{
  "segmentId": "seg_001",
  "talkId": "42",
  "talkSlug": "tiago_forte_second_brain",
  "speaker": "Tiago Forte",
  "talkTitle": "How to Build a Second Brain",
  "topic": "The four core capabilities of a Second Brain",
  "quote": "Your brain is for having ideas, not for storing them.",
  "motivationalText": "Forte identifies remembering, connecting, creating, and sharing as the four essential capabilities enabled by an external knowledge system.",
  "tags": ["knowledge-management", "productivity", "creativity"],
  "score": 0.97,
  "startTime": 122,
  "endTime": 205,
  "talkUrl": "https://www.ted.com/talks/tiago_forte_second_brain?t=122",
  "language": "en"
}
```

## Decisioni prese

**Modello AI:** `amazon.nova-lite-v1:0` via AWS Bedrock Converse API. Scelta cost-effective: ~$0.0021/talk, totale stimato ~$17 per 8.000 talk (budget $50).

**MCP Server:** server FastMCP separato (Lambda Function URL) che espone tools di validazione, duplicate detection e tag normalisation. Il modello li chiama durante il tool-use loop.

**Idempotenza:** pattern delete-before-insert per la collection snacks, scoped per `(slug, language, pipelineVersion, sourceHash)`. Lock atomico MongoDB (`find_one_and_update` con upsert) per evitare processing parallelo.

**Selezione lingua:** fallback chain `preferred → en → primo disponibile`. La lingua è campo esplicito su ogni documento snack.

**Parallelismo:** gestito da SQS — più Lambda possono girare in contemporanea su talk diversi. Il lock MongoDB garantisce che lo stesso talk non venga processato due volte.
