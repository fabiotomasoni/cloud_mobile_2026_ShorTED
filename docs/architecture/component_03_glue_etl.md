# Componente 3 — AWS Glue (ETL)

## Ruolo nel sistema
Layer ETL ("silver layer"). Primo componente attivo della pipeline: legge i dati grezzi da `shorted-raw`, li trasforma in documenti strutturati e coerenti, e li scrive su `shorted-processed`. Non ha dipendenze esterne — opera esclusivamente su dati già presenti su S3.

## Posizione nel pipeline
- **Input da:** Componente 2 (S3 Raw Bucket) — CSV del dataset + transcript JSON
- **Output verso:** Componente 4 (S3 Processed Bucket) — documenti JSON arricchiti, uno per talk

## Cosa fa (ETL)

**Extract** — legge da `shorted-raw`:
- I cinque file CSV del dataset (talk, dettagli, tag, immagini, video correlati)
- I transcript JSON prodotti dal Componente 1b (`transcripts/<slug>.json`)

**Transform** — per ogni talk:
- Unisce (join) i dati dei cinque CSV in un unico documento
- Seleziona solo le colonne necessarie, scarta quelle ridondanti
- Aggrega i tag da righe multiple a un unico array
- Seleziona una sola immagine per talk
- Normalizza i formati (date, durate, ecc.)
- Attacca il transcript al documento del talk

**Load** — scrive su `shorted-processed`:
- Un file JSON per talk, identificato dallo slug

## Output — struttura del documento prodotto
Un documento JSON per talk che unifica tutti i dati grezzi:
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

**Tool:** AWS Glue con PySpark.

**Responsabilità:** ETL puro — nessuna chiamata esterna, nessuna logica AI. Legge solo da S3, scrive solo su S3.

**Formato output:** JSON, un file per talk. Scelto perché i dati sono naturalmente a documento (strutture annidate), il formato è nativo per MongoDB e leggibile direttamente dalle Lambda successive.

**Trigger:** manuale per ora, eseguito dopo il completamento dei Componenti 1a e 1b.

## Note
Parquet e CSV sono stati esclusi come formato output: Parquet non gestisce bene strutture annidate ed è pensato per analytics, CSV non supporta array e oggetti annidati.
