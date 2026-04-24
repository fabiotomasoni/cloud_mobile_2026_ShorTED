# Componente 5.1 — Lambda Dispatcher

## Ruolo nel sistema
Ponte tra lo storage processato e la coda di lavoro. Si avvia al termine del job Glue, legge la lista dei documenti presenti in `shorted-processed` e inserisce un messaggio nella coda SQS per ogni talk da processare.

## Posizione nel pipeline
- **Input da:** Componente 4 (S3 Processed Bucket) — lista dei documenti JSON
- **Output verso:** Componente 5.2 (SQS Queue) — un messaggio per ogni talk
- **Trigger:** manuale per ora, al termine del Componente 3 (Glue)

## Cosa fa
Legge la lista dei file presenti in `shorted-processed` e per ogni talk inserisce un messaggio SQS contenente lo slug (o il path S3) del documento da processare.

## Decisioni prese
**Tool:** AWS Lambda (Python).

**Trigger:** manuale nella fase attuale. Predisposto per essere triggerato automaticamente da un evento S3 o da EventBridge in futuro.

## Nota sulla convenzione di naming
Componente sequenziale del gruppo 5 (insieme a 5.2 SQS Queue). La notazione decimale indica sequenzialità, distinta dalla notazione letterale (es. 1a/1b) usata per componenti paralleli.
