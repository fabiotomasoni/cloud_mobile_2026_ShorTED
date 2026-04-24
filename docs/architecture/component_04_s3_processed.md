# Componente 4 — Amazon S3 Processed Bucket

## Ruolo nel sistema
Layer di storage dei dati trasformati ("gold layer"). Riceve l'output di Glue e lo rende disponibile al sistema di processing AI. È il confine tra la fase di ingestion/ETL e la fase di analisi.

## Posizione nel pipeline
- **Input da:** Componente 3 (AWS Glue ETL)
- **Output verso:** Componente 5 (SQS + Lambda Dispatcher)

## Contenuto
Un documento JSON per talk, prodotto da Glue, che unifica tutti i dati grezzi:
```
{
  id, slug, title, speaker, url,
  description, duration, publishedAt,
  imageUrl,
  tags: [ ... ],
  transcript: [ { time, text }, ... ]
}
```

## Decisioni prese

**Nome bucket:** `shorted-processed`

**Separazione da raw:** bucket distinto da `shorted-raw` — policy di accesso diverse, ciclo di vita diverso. Il processed può essere ricalcolato da zero ripartendo dal raw.

**Formato:** JSON, un file per talk, identificato dallo slug.

## Note
Il Componente 5 (SQS) include una Lambda dispatcher che, al termine del job Glue, legge la lista dei documenti presenti in questo bucket e popola la coda SQS per avviare il processing AI.
