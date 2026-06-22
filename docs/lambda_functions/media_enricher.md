# Lambda Media Enricher

## Ruolo
Arricchisce i JSON processed con asset media TED e scrive il risultato su S3 enriched.

## Input evento
Supporta evento diretto:

```json
{
  "bucket": "shorted-processed",
  "file_key": "videos/10005.json"
}
```

Supporta anche record S3/SQS con gli stessi campi logici.

## Output
Scrive `s3://shorted-processed-enriched/videos/<id>.json` con campi media aggiunti:

- `embedUrl`
- `thumbnailUrlFullHd`
- `hlsUrl`
- `mp4Url`
- `mediaExtractionStatus`

## Responsabilità escluse
Non salva su MongoDB, non invoca Bedrock, non genera snack e non modifica i transcript.
