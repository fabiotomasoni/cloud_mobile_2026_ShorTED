# Componente 1b — Transcript Fetcher (Lambda)

## Ruolo nel sistema
Secondo flusso di ingestion raw. Scarica i transcript testuali dei talk TED (con timestamp) da ted.com e li deposita su `shorted-raw`, completando il dato grezzo insieme ai CSV del Componente 1a.

## Posizione nel pipeline
- **Dipende da:** Componente 1a (CSV Dataset) — legge la lista degli slug da `shorted-raw`
- **Output verso:** Componente 2 (S3 Raw Bucket) — scrive i transcript come file JSON
- **Precede:** Componente 3 (AWS Glue) — deve completarsi prima dell'avvio dell'ETL

## Cosa fa
Per ogni talk presente nel dataset, scarica il transcript da ted.com (testo verbatim + timestamp per ogni cue) e lo salva come file JSON separato su S3.

## Output su S3
Un file per talk, nella cartella dedicata del bucket raw:
```
shorted-raw/
  └── transcripts/
        ├── <slug>.json
        ├── <slug>.json
        └── ...
```

## Decisioni prese

**Tool:** AWS Lambda (Python).

**Trigger:** manuale — operazione di bootstrap, da eseguire una volta dopo l'upload dei CSV e prima dell'avvio di Glue. Predisposta per future automazioni tramite EventBridge.

**Granularità output:** un file JSON per talk, identificato dallo slug. Questo permette di ritrasferire singoli transcript in caso di errore senza rieseguire l'intera Lambda.

## Note
I transcript TED sono verbatim (non riassunti) e includono i timestamp di ogni cue in millisecondi. Questi timestamp sono il dato fondamentale per collegare ogni segmento analizzato al punto esatto del video originale.
