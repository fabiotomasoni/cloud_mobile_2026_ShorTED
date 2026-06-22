# ShorTED — Architettura del Servizio

ShorTED è un servizio che analizza i talk TED e li trasforma in contenuti snackable: segmenti brevi, citazioni, aforismi e metadati video pronti per essere serviti via API a un'app Flutter.

L'architettura documenta il target finale del sistema, mantenendo però allineati anche i componenti oggi già introdotti nella pipeline reale, come il media enrichment backend e il bucket enriched.

---

## I tre layer

**Layer 1 — Data Pipeline**
Elaborazione batch e asincrona: ingestion, ETL, media enrichment e generazione AI dei talk.

**Layer 2 — Backend API**
Layer serverless real-time che legge MongoDB ed espone endpoint REST verso l'app mobile.

**Layer 3 — Mobile**
App Flutter cross-platform che presenta feed, dettaglio, player e profilo utente.

---

## Componenti e flusso

### 1a · CSV Dataset
Cinque file CSV forniti dal corso con metadati TED/TEDx: titoli, speaker, descrizioni, tag, immagini e relazioni tra talk.

### 1b · Lambda Transcript Fetcher
Funzione di ingestion che scarica i transcript timestamped da TED e li salva su S3 raw come JSON separati per talk.

### 2 · Amazon S3 Raw (`shorted-raw`)
Bucket di storage grezzo. Contiene CSV originali e transcript JSON. È la fonte di verità ricalcolabile dell'intera pipeline.

### 3 · AWS Glue (PySpark ETL)
Legge i dati raw, unifica metadati e transcript e scrive un JSON processed per talk. Non fa chiamate esterne.

### 4 · Amazon S3 Processed (`shorted-processed`)
Bucket dei documenti JSON prodotti da Glue. Contiene i talk pronti per i passaggi successivi.

### 4.1 · Lambda TED Media Enricher
Legge i JSON processed, estrae dai payload TED i metadati media necessari all'app (`embedUrl`, thumbnail, `hlsUrl`, `mp4Url`) e scrive il risultato nel bucket enriched.

### 4.2 · Amazon S3 Processed Enriched (`shorted-processed-enriched`)
Bucket intermedio dei documenti processed arricchiti con metadati media. Diventa la sorgente dati per Dispatcher e Orchestrator AI.

### 5.1 · Lambda Dispatcher
Legge i JSON nel bucket enriched e inserisce un messaggio SQS per ogni talk da processare dalla pipeline AI.

### 5.2 · Amazon SQS
Coda di distribuzione del lavoro AI. Ogni messaggio rappresenta un talk; la coda gestisce parallelismo, retry e isolamento degli errori.

### 6.1 · Lambda AI Orchestrator
Riceve i messaggi da SQS, legge il talk enriched da S3, esegue la pipeline AI tramite Bedrock + MCP e salva talks/snacks in MongoDB in modo idempotente.

### 6.2 · AI Snack Pipeline
Pipeline logica multi-step: segmentazione, estrazione quote, generazione testi, tagging, ranking, deduplica e snack mixing finale.

### AWS Bedrock (dipendenza esterna)
Motore LLM della pipeline AI. Non viene usato per media extraction, che resta separata nella Lambda 4.1.

### 7 · MongoDB Atlas
Database centrale del sistema. Contiene i documenti `talks`, `snacks` e, nel target finale, anche `users`.

### 8 · Lambda API Functions
Lambda applicative che espongono tag, snack e feed verso l'app. Oggi esistono endpoint V1 pubblici; nel target finale il layer include anche endpoint autenticati per profilo e feed personalizzato.

### 9 · API Gateway
Espone gli endpoint HTTP e instrada verso le Lambda API. Nel target finale gestisce anche endpoint protetti con Cognito.

### 10 · AWS Cognito
Componente di autenticazione del target finale: registrazione, login e JWT per API protette.

### 11 · Flutter App
App mobile iOS/Android che mostra il feed, il dettaglio snack, il player e il profilo. Nel target finale usa Cognito; nella V1 attuale usa ancora profilo locale.

---

## Documentazione correlata

- Architettura per componenti: `docs/architecture/`
- Pipeline AI e Lambda AI: `docs/ai_pipeline/`
- Lambda non-AI: `docs/lambda_functions/`
- App Flutter e contratto dati: `docs/app/`
