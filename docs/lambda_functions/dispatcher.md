# Lambda Dispatcher

## Ruolo
Legge i JSON nel bucket `shorted-processed-enriched` e invia un messaggio alla coda `SQS-dispatcher` per ogni file da processare con la Lambda AI.

## Input
Configurazione tramite `.env` o variabili ambiente:

```env
ENRICHED_BUCKET_NAME=shorted-processed-enriched
ENRICHED_PREFIX=videos/
SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/<account>/SQS-dispatcher
```

## Output SQS
Ogni messaggio contiene:

```json
{
  "bucket": "shorted-processed-enriched",
  "file_key": "videos/10005.json"
}
```

## Note
Il fallback su `PROCESSED_BUCKET_NAME` esiste per test locali, ma il flusso corretto usa il bucket enriched.
