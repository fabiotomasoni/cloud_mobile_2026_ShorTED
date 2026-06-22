# ShorTED Media Backfill

Script per popolare i metadati media senza rigenerare gli snack con AI.

## Fasi

1. `enrich-s3`: invoca `Media_Enricher` per i JSON in `shorted-processed/videos/` e crea gli equivalenti in `shorted-processed-enriched/videos/`.
2. `mongo-media`: legge i JSON enriched e aggiorna MongoDB:
   - `talks` dove `slug == <slug>`;
   - `snacks` dove `talkSlug == <slug>`.

Lo script e' dry-run di default. Per scrivere davvero usare `--apply`.

## Esempi

Install dipendenze locali:

```bash
python3 -m pip install -r requirements.txt
```

Dry-run su 5 file:

```bash
python3 media_backfill.py --mode all --limit 5
```

Creare/aggiornare solo gli enriched JSON mancanti:

```bash
python3 media_backfill.py --mode enrich-s3 --limit 50 --apply
```

Aggiornare MongoDB dagli enriched JSON gia' presenti:

```bash
MONGODB_URI='mongodb+srv://...' python3 media_backfill.py --mode mongo-media --limit 50 --apply
```

Backfill completo:

```bash
MONGODB_URI='mongodb+srv://...' python3 media_backfill.py --mode all --apply
```

Backfill solo per talk gia' presenti in MongoDB e ancora senza media:

```bash
MONGODB_URI='mongodb+srv://...' python3 media_backfill.py --mode all --only-mongo-slugs --apply
```

Backfill Mongo-only con invocazioni Lambda concorrenti controllate:

```bash
MONGODB_URI='mongodb+srv://...' python3 media_backfill.py --mode all --only-mongo-slugs --workers 5 --apply
```

Backfill locale senza invocare Lambda, arricchendo tutti i JSON processed e aggiornando Mongo dove esiste lo slug:

```bash
MONGODB_URI='mongodb+srv://...' python3 media_backfill.py --mode all --local-extract --workers 5 --apply
```

## Config default

- Processed bucket: `shorted-processed`
- Enriched bucket: `shorted-processed-enriched`
- Prefix: `videos/`
- Lambda: `Media_Enricher`
- Mongo DB: `shorted`

## Note

- Non invoca l'Orchestrator AI.
- Non ricrea gli snack.
- Salta gli enriched JSON gia' presenti, salvo `--no-skip-existing-enriched`.
- Aggiorna Mongo solo se `mediaExtractionStatus == completed`, salvo `--include-failed-media`.
- Con `--only-mongo-slugs` arricchisce solo i talk gia' presenti in MongoDB; di default considera solo quelli senza media completi.
- Con `--local-extract` non invoca Lambda: scarica i JSON da S3, chiama TED dal computer locale e carica gli enriched JSON su S3.
