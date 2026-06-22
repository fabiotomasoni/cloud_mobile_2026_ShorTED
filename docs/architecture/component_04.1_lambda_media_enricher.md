# Componente 4.1 — Lambda TED Media Enricher

## Ruolo nel sistema
Lambda batch/offline che arricchisce i JSON processed con metadati media TED. Non genera snack, non chiama modelli AI e non scrive MongoDB.

## Posizione nel pipeline
- **Input da:** Componente 4 (Amazon S3 Processed Bucket)
- **Output verso:** Componente 4.2 (Amazon S3 Processed Enriched Bucket)
- **Dipendenza esterna:** TED embed page e, come fallback, TED oEmbed

## Cosa fa
Per ogni JSON processed:
1. legge `slug` e `url`;
2. scarica `https://embed.ted.com/talks/<slug>`;
3. estrae il payload `__NEXT_DATA__`;
4. cerca URL HLS, MP4 e thumbnail;
5. normalizza la thumbnail in varianti HD e Full HD;
6. scrive un JSON enriched preservando tutti i campi originali.

## Campi aggiunti
- `embedUrl`
- `thumbnailUrl`
- `thumbnailUrlHd`
- `thumbnailUrlFullHd`
- `hlsUrl`
- `mp4Url`
- `mediaExtractedAt`
- `mediaExtractionVersion`
- `mediaExtractionStatus`
- `mediaExtractionError`, solo in caso di fallimento

## Decisioni prese
**Separazione da Glue:** Glue resta ETL puro e non fa chiamate esterne.

**Separazione dall'Orchestrator AI:** l'Orchestrator non fa scraping TED; propaga solo i campi media già presenti nel JSON enriched.

**Separazione dall'app:** Flutter non deve chiamare TED per recuperare thumbnail o video URL. L'app consuma dati già arricchiti dal backend.

**Fallback controllato:** se l'extraction fallisce, il JSON enriched viene comunque scritto con `mediaExtractionStatus: failed`, così il pipeline può proseguire e l'errore resta auditabile.

## Variabili ambiente
- `PROCESSED_BUCKET_NAME`: bucket sorgente, default operativo `shorted-processed`.
- `ENRICHED_BUCKET_NAME`: bucket destinazione, default operativo `shorted-processed-enriched`.
- `PROCESSED_PREFIX`: prefisso opzionale, tipicamente `videos/`.
- `ENRICHED_PREFIX`: prefisso opzionale, tipicamente `videos/`.
- `MEDIA_EXTRACTION_VERSION`: versione extractor.
