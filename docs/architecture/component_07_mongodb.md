# Componente 7 — MongoDB

## Ruolo nel sistema
Database centrale di ShorTED. È il punto di connessione tra la pipeline di elaborazione (Layer 1) e il backend API (Layer 2) — la Lambda AI scrive i risultati dell'analisi, le Lambda API leggono per servire il feed agli utenti.

## Posizione nel pipeline
- **Scrittura da:** Componente 6 (Lambda AI Processing) — talks e snacks prodotti dall'analisi
- **Lettura da:** Componente 8 (Lambda API Functions) — per servire feed, snacks, ricerche
- **Scrittura da:** Componente 8 — per la gestione dei profili utente

## Collezioni

**`talks`** — un documento per talk.
Metadati del talk: titolo, speaker, durata, immagine, tags, URL originale ted.com e campi media arricchiti.

**`snacks`** — N documenti per talk (4-8).
Unità fondamentale di contenuto: topic, quote, motivational text, aphorism, tags, startTime, endTime, talkUrl con timestamp e campi media copiati dal talk enriched. È la collezione più interrogata dall'app.

**`users`** — un documento per utente, creato al primo accesso.
Interessi selezionati, lista dei snacks già visualizzati (per evitare ripetizioni nel feed).

## Schema indicativo degli snacks

```json
{
  "talkId": "...",
  "talkSlug": "...",
  "speaker": "...",
  "talkTitle": "...",
  "topic": "...",
  "quote": "...",
  "summary": "...",
  "tags": ["..."],
  "score": 0.87,
  "startTime": 120,
  "endTime": 165,
  "talkUrl": "https://www.ted.com/talks/<slug>?t=120",
  "embedUrl": "https://embed.ted.com/talks/<slug>",
  "thumbnailUrlFullHd": "https://...jpg?w=1920&h=1080",
  "hlsUrl": "https://hls.ted.com/.../manifest.m3u8",
  "mp4Url": "https://py.tedcdn.com/...mp4"
}

## Decisioni prese

**Tool:** MongoDB Atlas — free tier permanente (512MB), sufficiente per il dataset del progetto.

**Perché non AWS DocumentDB:** costo minimo ~$200/mese, non sostenibile per un progetto universitario. Citabile come alternativa enterprise nel design.

**Perché MongoDB e non relazionale:** i dati sono naturalmente a documento (array di tags, interessi variabili per utente, strutture eterogenee). MongoDB gestisce queste strutture in modo nativo. È inoltre il database trattato esplicitamente nel corso.

## Note
DocumentDB (AWS) rimane menzionabile nell'architettura come alternativa managed per un deployment enterprise, ma la scelta operativa per il progetto è MongoDB Atlas.
