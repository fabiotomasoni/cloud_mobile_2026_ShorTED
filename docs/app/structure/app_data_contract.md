# ShorTED App Data Contract

## Endpoint V1

### Get All Tags

Endpoint:

```text
GET https://nk1cgmp9kh.execute-api.us-east-1.amazonaws.com/default/get_all_tags
```

Response `200 application/json`:

```json
["art", "design", "technology"]
```

Formato reale:

- Array JSON di stringhe.
- Tag gia' normalizzati come stringhe non vuote.
- Ordinamento alfabetico lato Lambda.

Uso in app:

- Onboarding.
- Modifica interessi nel profilo.

### Get Talks By Tags

Endpoint:

```text
GET https://zjvrmg44s2.execute-api.us-east-1.amazonaws.com/default/get_talks_by_tags?tags=design,art&doc_per_page=20&page=1
```

Query parameters:

| Parametro | Tipo | Obbligatorio | Descrizione |
| --- | --- | --- | --- |
| `tags` | string | si | Lista di tag separati da virgola. Esempio: `design,art`. |
| `doc_per_page` | number | no | Numero di documenti da restituire. Default Lambda: `10`. V1 app: `20`. |
| `page` | number | no | Pagina 1-based. Default Lambda: `1`. |

Response `200 application/json`:

```json
[
  {
    "_id": "billy_collins_two_poems_about_what_dogs_think_probably:en:v1:seg_007",
    "segmentId": "seg_007",
    "talkId": "103404",
    "talkSlug": "billy_collins_two_poems_about_what_dogs_think_probably",
    "speaker": "Billy Collins",
    "talkTitle": "Two poems about what dogs think (probably)",
    "topic": "The difference between human and canine understanding",
    "quote": "the dogs in poetry, the cats and all the others in prose.",
    "motivationalText": "This concluding thought suggests that while humans attempt to capture the animal experience through structured language...",
    "aphorism": "Poetry captures the soul; prose describes the mundane.",
    "tags": ["creativity", "language", "art"],
    "score": 0.95,
    "startTime": 211,
    "endTime": 218,
    "talkUrl": "https://www.ted.com/talks/billy_collins_two_poems_about_what_dogs_think_probably?t=211",
    "language": "en",
    "aiPipelineVersion": "v1",
    "sourceHash": "c21d01588e41cec118ede0c641489846394944dfecfb6b35de930555ef94f458",
    "createdAt": "2026-06-03T02:12:15.100Z"
  }
]
```

Risultato vuoto:

```json
[]
```

Errori verificati:

| Caso | Status | Content-Type | Body |
| --- | --- | --- | --- |
| `tags` assente o vuoto | `400` | `text/plain` | `Could not fetch the talks. Tags parameter is missing or empty.` |
| `doc_per_page <= 0` o `page <= 0` | `400` | `text/plain` | `doc_per_page and page must be valid numbers greater than 0.` |

## Modello Snack App

Campi principali usati dalla V1:

| Campo | Tipo | Uso |
| --- | --- | --- |
| `_id` | string | Identificatore stabile dello snack. |
| `segmentId` | string | Segmento nel talk. |
| `talkId` | string | Identificatore talk. |
| `talkSlug` | string | Costruzione URL embed, fallback se serve. |
| `speaker` | string | UI feed/dettaglio. |
| `talkTitle` | string | UI feed/dettaglio. |
| `topic` | string | UI feed/dettaglio. |
| `quote` | string | Citazione originale. |
| `motivationalText` | string | Spiegazione nel dettaglio. |
| `aphorism` | string | Testo principale in overlay feed. |
| `tags` | string[] | Chip e matching interessi. |
| `score` | number | Non usato per ordinamento V1, utile per versioni future. |
| `startTime` | number | Timestamp di inizio. |
| `endTime` | number | Timestamp di fine. |
| `talkUrl` | string | URL TED originale con timestamp. |
| `language` | string | Lingua contenuto. |
| `aiPipelineVersion` | string | Versione pipeline. |
| `sourceHash` | string | Tracciabilita' dato sorgente. |
| `createdAt` | string | Data creazione documento. |

## Trasformazione TED Embed

Input:

```text
https://www.ted.com/talks/isabel_allende_tales_of_passion?t=717
```

Output:

```text
https://embed.ted.com/talks/isabel_allende_tales_of_passion?t=717
```

Regola app:

- Sostituire host `www.ted.com` con `embed.ted.com`.
- Conservare path e query string.
- Se `talkUrl` non e' valido ma `talkSlug` e `startTime` sono presenti, costruire `https://embed.ted.com/talks/<talkSlug>?t=<startTime>`.

## Profilo Locale V1

```json
{
  "username": "Elena",
  "selectedTags": ["design", "art", "technology"],
  "themeMode": "dark"
}
```

Regole:

- `username` non vuoto.
- `selectedTags.length >= 3`.
- `themeMode`: `light`, `dark` o `system` se supportato.
- La V1 usa persistenza locale Flutter, non MongoDB.
