# Componente 7 — MongoDB

## Ruolo nel sistema
Database centrale di ShorTED. È il punto di connessione tra la pipeline di elaborazione (Layer 1) e il backend API (Layer 2) — la Lambda AI scrive i risultati dell'analisi, le Lambda API leggono per servire il feed agli utenti.

## Posizione nel pipeline
- **Scrittura da:** Componente 6 (Lambda AI Processing) — talks e bits prodotti dall'analisi
- **Lettura da:** Componente 8 (Lambda API Functions) — per servire feed, bits, ricerche
- **Scrittura da:** Componente 8 — per la gestione dei profili utente

## Collezioni

**`talks`** — un documento per talk.
Metadati del talk: titolo, speaker, durata, immagine, tags, URL originale ted.com.

**`bits`** — N documenti per talk (4-8).
Unità fondamentale di contenuto: topic, quote, summary, tags, startTime, talkUrl con timestamp. È la collezione più interrogata dall'app.

**`users`** — un documento per utente, creato al primo accesso.
Interessi selezionati, lista dei bits già visualizzati (per evitare ripetizioni nel feed).

## Decisioni prese

**Tool:** MongoDB Atlas — free tier permanente (512MB), sufficiente per il dataset del progetto.

**Perché non AWS DocumentDB:** costo minimo ~$200/mese, non sostenibile per un progetto universitario. Citabile come alternativa enterprise nel design.

**Perché MongoDB e non relazionale:** i dati sono naturalmente a documento (array di tags, interessi variabili per utente, strutture eterogenee). MongoDB gestisce queste strutture in modo nativo. È inoltre il database trattato esplicitamente nel corso.

## Note
DocumentDB (AWS) rimane menzionabile nell'architettura come alternativa managed per un deployment enterprise, ma la scelta operativa per il progetto è MongoDB Atlas.
