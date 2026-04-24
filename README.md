# ShorTED — Architettura del Servizio

ShorTED è un servizio che analizza i talk TED e li scompone in **contenuti snackable**: segmenti di video e citazioni, con link diretti ai video originali TEDx. Gli utenti ricevono un feed personalizzato in base ai propri interessi, tramite un'app mobile Flutter.

---

## I tre layer

L'architettura è divisa in tre layer con responsabilità distinte.

**Layer 1 — Data Pipeline:** elaborazione batch dei dati, asincrona e schedulata. Trasforma il dataset grezzo TED in bits strutturati pronti per essere serviti.

**Layer 2 — Backend API:** layer serverless real-time. Espone i dati agli utenti tramite API REST protette.

**Layer 3 — Mobile:** app Flutter cross-platform (iOS e Android) che presenta il feed all'utente.

---

## Componenti e flusso

### 1a · CSV Dataset
Il punto di partenza. Cinque file CSV forniti dal corso con metadati dei talk TED (titoli, speaker, descrizioni, tag, immagini, video correlati). Vengono caricati manualmente una sola volta sul bucket S3 raw come operazione di bootstrap.

### 1b · Lambda Transcript Fetcher
Una Lambda function che, dopo il caricamento dei CSV, scarica il transcript verbatim di ogni talk da ted.com — completo di timestamp in millisecondi per ogni cue — e lo salva su S3 raw come file JSON separato per talk. È il secondo flusso di ingestion raw, parallelo al caricamento dei CSV.

### 2 · Amazon S3 Raw (`shorted-raw`)
Bucket di storage grezzo. Contiene i CSV originali e i transcript JSON scaricati dalla Lambda. Dati immutati, fonte di verità del sistema. Tutto il resto può essere ricalcolato ripartendo da qui.

### 3 · AWS Glue (PySpark ETL)
Il primo componente attivo della pipeline. Legge i CSV e i transcript da S3 raw, unisce i dati dei cinque file in un unico documento per talk (join, aggregazione tag in array, selezione immagine, normalizzazione), e scrive un JSON arricchito per ogni talk su S3 processed. Non fa chiamate esterne — lavora solo su dati già presenti su S3.

### 4 · Amazon S3 Processed (`shorted-processed`)
Bucket dei dati trasformati. Contiene un JSON per talk con tutti i metadati unificati e il transcript allegato. Dati pronti per l'analisi AI. Separato da S3 raw per policy di accesso e ciclo di vita distinti.

### 5.1 · Lambda Dispatcher
Al termine del job Glue, questa Lambda legge la lista dei documenti presenti in S3 processed e inserisce un messaggio SQS per ogni talk da processare. È il ponte tra lo storage e la coda di lavoro.

### 5.2 · Amazon SQS
Coda di distribuzione del lavoro. Ogni messaggio rappresenta un talk da analizzare. Gestisce il parallelismo (più Lambda AI girano in contemporanea) e i retry automatici: se una Lambda fallisce su un talk specifico, il messaggio torna in coda senza impatto sugli altri.

### 6 · Lambda AI Processing
Viene triggerata da SQS per ogni talk. Legge il documento JSON da S3 processed, invia il transcript ad AWS Bedrock per la segmentazione tematica, riceve in risposta i segmenti strutturati, calcola i timestamp e costruisce i documenti definitivi. Scrive i risultati su MongoDB.

### AWS Bedrock (dipendenza esterna)
Usato dalla Lambda AI. Analizza il transcript e restituisce la segmentazione strutturata in JSON. 

---

### 7 · MongoDB Atlas
Database centrale del sistema — il punto di connessione tra pipeline e backend. La Lambda AI ci scrive i risultati, le Lambda API ci leggono per servire il feed.

### 8 · Lambda API Functions
Layer serverless che espone i dati di MongoDB verso l'app. Un insieme di funzioni chiamate tramite API Gateway.

### 9 · API Gateway
Punto di ingresso unico per tutte le chiamate HTTP dell'app. Riceve le richieste, verifica l'autenticazione tramite Cognito e le instrada alla Lambda corretta. Espone gli endpoint REST su HTTPS.

### 10 · AWS Cognito
Gestione completa dell'autenticazione utenti. Supporta registrazione e login con email/password, Google e Apple. Dopo il login emette un token JWT che l'app allega ad ogni richiesta — API Gateway lo verifica automaticamente prima di inoltrarla a Lambda. Usato anche direttamente da Flutter per le schermate di accesso.

---

### 11 · Flutter App
Applicazione mobile cross-platform (iOS e Android). Si autentica tramite Cognito, recupera il feed personalizzato tramite API Gateway, e mostra i contenuti all'utente.

---