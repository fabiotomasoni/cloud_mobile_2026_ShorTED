# AWS Glue ETL Processing

## Overview

Questo componente implementa il job AWS Glue sviluppato per trasformare i dati TEDx grezzi in documenti JSON strutturati e pronti per essere utilizzati dall’applicazione MyTEDx e dai servizi AI della piattaforma.

Il job legge dati eterogenei salvati nel bucket S3 `project-tedx-raw-data`, li unifica attraverso l’id del video e genera un singolo file JSON completo per ogni talk all’interno del bucket `project-tedx-processed-data`.

---

## Input Dataset

Il job utilizza diverse sorgenti CSV e JSON:

| File | Contenuto |
|---|---|
| `final_list.csv` | Lista principale dei talk |
| `details.csv` | Metadati aggiuntivi dei video |
| `tags.csv` | Tag associati ai talk |
| `related_videos.csv` | Relazioni tra video suggeriti |
| `images.csv` | URL immagini thumbnail |
| `transcriptions/*.json` | Trascrizioni multilingua raw |

Le trascrizioni provengono direttamente dalla struttura JSON TED GraphQL e contengono paragrafi, cue temporizzati e informazioni sulla lingua.

---

## Processing Pipeline

Il job Glue esegue le seguenti operazioni:

1. Lettura dei dataset CSV dal bucket raw
2. Raggruppamento dei dati multivalore (`tags`, `related_videos`)
3. Join dei dataset tramite l’id del video
4. Parsing delle trascrizioni JSON multilingua
5. Costruzione del documento finale strutturato
6. Scrittura del JSON finale nel bucket processed

L’elaborazione finale viene eseguita tramite `foreachPartition()` per distribuire il carico sui worker Spark.

---

## Distributed Processing

Per migliorare la scalabilità, il job utilizza elaborazione distribuita PySpark.

Ogni worker:
- inizializza un client S3 locale
- legge le trascrizioni associate ai video della propria partizione
- costruisce il JSON finale
- salva direttamente il risultato nel bucket processed

Questo approccio evita di collezionare tutti i dati sul driver centrale e permette di gestire dataset di dimensioni elevate.

---

## Final JSON Schema

Per ogni video viene generato un file:

```text
s3://project-tedx-processed-data/videos/{id}.json
```

con struttura:

```json
{
    "id": 521813,
    "title": "...",
    "slug": "...",
    "url": "...",
    "duration": 360,
    "tags": [],
    "related_videos": [],
    "presenterDisplayName": "...",
    "speakers": [],
    "image": "...",
    "transcriptions": {
        "en": {
            "language": "English",
            "sentences": [],
            "raw": "..."
        },
        "it": {
            "language": "Italian",
            "sentences": [],
            "raw": "..."
        }
    }
}
```

---

## Transcription Processing

Le trascrizioni vengono convertite da struttura TED GraphQL a formato applicativo semplificato.

Per ogni lingua vengono salvati:
- nome lingua
- lista frasi con timestamp
- testo completo concatenato (`raw`)

Questo permette:
- sincronizzazione video/testo
- ricerca full-text
- summarization AI
- generazione snack educativi
- embedding e semantic search

---

## Error Handling

Il job include alcune logiche di protezione:
- gestione di valori nulli
- cast numerici sicuri tramite `safe_int()`
- skip automatico di record corrotti
- gestione assenza trascrizioni
- fallback su liste vuote

Questo evita crash durante l’elaborazione distribuita.

---

## Technical Challenges

Le principali criticità affrontate sono:

- integrazione di dataset con granularità diverse
- gestione dati multivalore
- parsing JSON annidati TED
- supporto multilingua
- gestione dati mancanti o inconsistenti
- differenza tra TED internal id e dataset id

---

## Possible Evolutions

Possibili miglioramenti futuri:

- elaborazione incrementale
- validazione schema JSON
- supporto Parquet per analytics
- indicizzazione OpenSearch
- pipeline AI automatica post-processing
- enrichment semantico dei contenuti
- supporto streaming/event-driven ETL
