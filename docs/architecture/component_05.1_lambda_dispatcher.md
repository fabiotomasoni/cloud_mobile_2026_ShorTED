# Componente 5.1 — Lambda Dispatcher

## Ruolo nel sistema
Ponte tra lo storage processato arricchito e la coda di lavoro. Si avvia dopo il media enrichment, legge la lista dei documenti presenti nel bucket enriched e inserisce un messaggio nella coda SQS per ogni talk da processare.

## Posizione nel pipeline
- **Input da:** Componente 4.2 (S3 Processed Enriched Bucket) — lista dei documenti JSON
- **Output verso:** Componente 5.2 (SQS Queue) — un messaggio per ogni talk
- **Trigger:** manuale per ora, al termine del Componente 3 (Glue)

## Cosa fa
Legge la lista dei file presenti nel bucket enriched e per ogni talk inserisce un messaggio SQS contenente `bucket`, `file_key` e opzionalmente `language`.

## Decisioni prese
**Tool:** AWS Lambda (Node.js).

**Bucket sorgente:** usa `ENRICHED_BUCKET_NAME` se presente, altrimenti mantiene fallback su `PROCESSED_BUCKET_NAME` per test e compatibilita locale.

**Trigger:** manuale nella fase attuale. Predisposto per essere triggerato automaticamente da un evento S3 o da EventBridge in futuro.

## Nota sulla convenzione di naming
Componente sequenziale del gruppo 5 (insieme a 5.2 SQS Queue). La notazione decimale indica sequenzialità, distinta dalla notazione letterale (es. 1a/1b) usata per componenti paralleli.
