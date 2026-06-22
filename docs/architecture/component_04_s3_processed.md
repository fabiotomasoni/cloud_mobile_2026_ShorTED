# Componente 4 — Amazon S3 Processed Bucket

## Ruolo nel sistema
Layer di storage dei dati trasformati ("gold layer"). Riceve l'output di Glue e lo rende disponibile al sistema di processing AI. È il confine tra la fase di ingestion/ETL e la fase di analisi.

## Posizione nel pipeline
- **Input da:** Componente 3 (AWS Glue ETL)
- **Output verso:** Componente 4.1 (Lambda TED Media Enricher)

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
Il Componente 4.1 arricchisce questi documenti con metadati media e li scrive nel Componente 4.2. Il Dispatcher legge dal bucket enriched, non direttamente da questo bucket, così Glue resta un ETL puro e riproducibile.
