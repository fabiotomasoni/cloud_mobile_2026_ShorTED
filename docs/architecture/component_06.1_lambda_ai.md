# Componente 6 — Lambda AI Orchestrator

## Ruolo nel sistema
Cuore analitico della pipeline. Trasforma un documento talk (metadati + transcript) in un insieme di "snacks" — i contenuti snackable che costituiscono il contenuto core di ShorTED.

La Lambda AI mantiene la responsabilità di orchestrare il processo: riceve il messaggio da SQS, legge il talk da S3 processed, richiama la AI Snack Pipeline descritta nel Componente 6a e salva il risultato finale su MongoDB.

## Posizione nel pipeline
- **Trigger da:** Componente 5.2 (SQS Queue) — una invocazione per talk
- **Legge da:** Componente 4 (S3 Processed Bucket) — documento JSON del talk
- **Scrive su:** Componente 7 (MongoDB) — collezioni `talks` e `snacks`

## Cosa fa
Per ogni talk ricevuto dalla coda:
1. Legge il documento JSON completo da `shorted-processed`
2. Estrae transcript e metadati principali del talk
3. Richiama la AI Snack Pipeline, che usa Bedrock per segmentazione, generazione, tagging/ranking e Snack Mixer
4. Riceve in risposta gli snack candidati già strutturati
5. Calcola o normalizza i timestamp di inizio/fine per ogni segmento
6. Costruisce i documenti "snack" definitivi
7. Scrive il talk e i suoi snacks su MongoDB

## Output — lo "snack"
Unità fondamentale di contenuto di ShorTED. Ogni talk produce 4-8 snacks.

```
{
  talkId, talkSlug, speaker, talkTitle,
  topic,       // argomento dello snack
  quote,       // frase breve e significativa, preferibilmente dal transcript
  summary,     // descrizione sintetica del segmento
  tags[],      // per la personalizzazione del feed
  score,       // punteggio interno opzionale prodotto dal ranking AI
  startTime,   // secondi dall'inizio del video
  endTime,     // fine del segmento, se disponibile
  talkUrl      // ted.com/talks/<slug>?t=<startTime>
}
```

## Decisioni prese

**Tool:** AWS Lambda (Python) + AWS Bedrock (AI API) multi-model in AI pipeline.

**Modello AI:** Diversi modelli in base alla task della pipeline su Bedrock.

**Parallelismo:** gestito da SQS — più Lambda possono girare in contemporanea su talk diversi.
