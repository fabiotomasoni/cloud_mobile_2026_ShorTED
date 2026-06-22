# Lambda Get Talks By Tags

## Ruolo
Endpoint API V1 per recuperare snack associati a uno o più tag.

## Input
Query string:

```text
GET /get_talks_by_tags?tags=design,art&doc_per_page=20&page=1
```

## Query MongoDB
Legge `snacks` con filtro:

```js
{ tags: { $in: tags } }
```

## Campi esposti
Espone campi snack, metadati AI e campi media:

- `segmentId`, `talkId`, `talkSlug`, `speaker`, `talkTitle`
- `topic`, `quote`, `motivationalText`, `aphorism`, `tags`, `score`
- `startTime`, `endTime`, `talkUrl`, `language`
- `embedUrl`, `thumbnailUrl`, `thumbnailUrlHd`, `thumbnailUrlFullHd`
- `hlsUrl`, `mp4Url`
- `mediaExtractedAt`, `mediaExtractionVersion`, `mediaExtractionStatus`, `mediaExtractionError`
- `aiPipelineVersion`, `sourceHash`, `createdAt`

## Uso app
La V1 Flutter usa questo endpoint per costruire il feed lato client. In futuro potrà essere sostituito da `getFeed` server-side.
