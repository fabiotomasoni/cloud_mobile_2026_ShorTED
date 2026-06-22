# Componente 4.2 — Amazon S3 Processed Enriched Bucket

## Ruolo nel sistema
Bucket intermedio che conserva i documenti processed dopo l'arricchimento media. Mantiene separato l'output ETL puro di Glue dall'output arricchito con dati recuperati da TED.

## Posizione nel pipeline
- **Input da:** Componente 4.1 (Lambda TED Media Enricher)
- **Output verso:** Componente 5.1 (Lambda Dispatcher)
- **Letto da:** Componente 6.1 (Lambda AI Orchestrator), tramite messaggi SQS generati dal Dispatcher

## Contenuto
Un JSON per talk con tutti i campi del processed bucket e i campi media aggiunti:

```json
{
  "id": 10005,
  "slug": "isabel_allende_tales_of_passion",
  "title": "Tales of passion",
  "url": "https://www.ted.com/talks/isabel_allende_tales_of_passion",
  "transcriptions": {},
  "embedUrl": "https://embed.ted.com/talks/isabel_allende_tales_of_passion",
  "thumbnailUrl": "https://...jpg",
  "thumbnailUrlHd": "https://...jpg?w=1280&h=720",
  "thumbnailUrlFullHd": "https://...jpg?w=1920&h=1080",
  "hlsUrl": "https://hls.ted.com/.../manifest.m3u8?...",
  "mp4Url": "https://py.tedcdn.com/...-1200k.mp4",
  "mediaExtractedAt": "2026-06-22T...Z",
  "mediaExtractionVersion": "ted-media-enricher-v1",
  "mediaExtractionStatus": "completed"
}
```

## Decisioni prese
**Nome bucket:** `shorted-processed-enriched`.

**Separazione dal processed bucket:** il bucket `shorted-processed` resta output riproducibile di Glue. Il bucket enriched contiene invece dati che dipendono da chiamate esterne a TED e possono essere rigenerati separatamente.

**Sorgente per AI:** Dispatcher e Orchestrator devono usare il bucket enriched, così gli snack salvati in MongoDB includono già i campi media necessari all'app.

**Backfill:** per dati esistenti si può rigenerare il bucket enriched partendo da `shorted-processed` e poi aggiornare MongoDB senza rieseguire la pipeline AI.
