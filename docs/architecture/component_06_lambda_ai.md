# Componente 6 — Lambda AI Processing

## Ruolo nel sistema
Cuore analitico della pipeline. Trasforma un documento talk (metadati + transcript) in un insieme di "bits" — i segmenti tematici strutturati che costituiscono il contenuto core di ShorTED.

## Posizione nel pipeline
- **Trigger da:** Componente 5.2 (SQS Queue) — una invocazione per talk
- **Legge da:** Componente 4 (S3 Processed Bucket) — documento JSON del talk
- **Scrive su:** Componente 7 (MongoDB) — collezioni `talks` e `bits`

## Cosa fa
Per ogni talk ricevuto dalla coda:
1. Legge il documento JSON completo da `shorted-processed`
2. Invia il transcript all'AI API (Bedrock) con le istruzioni di analisi
3. Riceve la segmentazione strutturata in risposta
4. Calcola i timestamp di inizio/fine per ogni segmento
5. Costruisce i documenti "bit" definitivi
6. Scrive il talk e i suoi bits su MongoDB

## Output — il "bit"
Unità fondamentale di contenuto di ShorTED. Ogni talk produce 4-8 bits.

```
{
  talkId, talkSlug, speaker, talkTitle,
  topic,       // argomento del segmento (es. "Why we avoid deep questions")
  quote,       // frase verbatim dal transcript, max 30 parole
  summary,     // 40-50 parole che descrivono il segmento
  tags[],      // per la personalizzazione del feed
  startTime,   // secondi dall'inizio del video
  talkUrl      // ted.com/talks/<slug>?t=<startTime>
}
```

## Decisioni prese

**Tool:** AWS Lambda (Python) + AWS Bedrock (AI API).

**Modello AI:** Claude Haiku su Bedrock — buon equilibrio tra qualità e costo. Modificabile senza impatti sull'architettura.

**Parallelismo:** gestito da SQS — più Lambda possono girare in contemporanea su talk diversi.

**Costo stimato Bedrock:** $2-5 per l'intero dataset. Ampiamente nei $300 di credito AWS Academy.

## Note
La scelta del modello AI (Bedrock vs OpenAI) non è architetturalmente critica — entrambi si chiamano via HTTP da Lambda. La decisione attuale è Bedrock per coerenza con lo stack AWS, ma è modificabile in qualsiasi momento.
