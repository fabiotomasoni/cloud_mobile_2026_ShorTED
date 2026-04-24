# Componente 2 — Amazon S3 Raw Bucket

## Ruolo nel sistema
Layer di storage grezzo ("bronze layer"). Riceve i CSV dal bootstrap iniziale e li conserva immutati come fonte di verità del sistema. Non elabora dati, non contiene logica.

## Posizione nel pipeline
- **Input da:** Componente 1 (CSV Dataset) — upload manuale una tantum
- **Output verso:** Componente 3 (AWS Glue) — lettura dei CSV per l'ETL

## Contenuto
I cinque file CSV del dataset TEDx, così come sono, senza alcuna trasformazione.

## Decisioni prese

**Separazione raw/processed:** il progetto utilizza due bucket S3 distinti — uno per i dati grezzi, uno per i dati processati. Questo garantisce policy di accesso separate e chiarezza concettuale tra i layer della pipeline.

**Nome bucket:** `shorted-raw`

**Immutabilità:** il contenuto di questo bucket non viene mai modificato o sovrascritto dopo il bootstrap iniziale. È la fonte di verità da cui si può sempre ripartire in caso di errori nei layer successivi.

## Tool
Amazon S3.

## Note
Il bucket `shorted-processed` (Componente 4) è il corrispettivo per i dati elaborati da Glue.
