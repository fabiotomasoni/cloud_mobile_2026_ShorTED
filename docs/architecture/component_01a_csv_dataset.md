# Componente 1a — CSV Dataset

## Ruolo nel sistema
Sorgente dati del progetto. Rappresenta il punto di ingresso dell'intera pipeline. È un componente passivo: non esegue logica, non si aggiorna dinamicamente.

## Contenuto
Cinque file CSV che costituiscono il catalogo TEDx:

| File | Contenuto |
|---|---|
| `final_list.csv` | Lista dei talk: id, slug, speaker, titolo, URL |
| `details.csv` | Dettagli: descrizione, durata, data pubblicazione, presenter |
| `tags.csv` | Tag associati ai talk (relazione N:M, una riga per tag) |
| `images.csv` | URL immagini dei talk (più aspect ratio per talk) |
| `related_videos.csv` | Talk correlati con view count |

## Decisioni prese

**Upload:** manuale, una tantum, come operazione di bootstrap prima dell'avvio della pipeline.

**Pre-processing prima dell'upload:** nessuno. I CSV entrano su S3 così come sono. Qualsiasi trasformazione (selezione colonne, join, pulizia) è responsabilità del layer ETL (Componente 3 — AWS Glue).

**Aggiornamenti:** il dataset è statico per questo progetto. Non è previsto un meccanismo di aggiornamento automatico.

## Output verso il componente successivo
I file CSV vengono caricati su **Amazon S3 — Raw Bucket** (`shorted-raw`, Componente 2), che li rende disponibili al resto della pipeline.

## Tool
Nessuno strumento attivo. La destinazione è Amazon S3.
