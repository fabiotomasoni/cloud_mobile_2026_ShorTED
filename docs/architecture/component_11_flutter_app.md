# Componente 11 — Flutter App

## Ruolo nel sistema
Applicazione mobile cross-platform (iOS e Android). È il punto di contatto finale con l'utente — tutto il sistema esiste per supportare quello che l'app mostra.

## Posizione nel pipeline
- **Autenticazione tramite:** Componente 10 (AWS Cognito)
- **Dati tramite:** Componente 9 (API Gateway) → Componente 8 (Lambda API)
- **Link esterno a:** ted.com con timestamp per il video originale

## Schermate principali

**Onboarding** — selezione degli interessi al primo accesso, dopo la registrazione. Usa i tag del dataset come opzioni.

**Feed** — schermata principale. Lista di bits personalizzati per interessi: quote breve, argomento, speaker. Tap su un bit apre il dettaglio.

**Dettaglio bit** — quote completa, riassunto, link a ted.com con timestamp al punto esatto del video.

**Profilo / Impostazioni** — modifica degli interessi, logout.

## Decisioni prese

**Tool:** Flutter — framework hybrid cross-platform, un solo codebase per iOS e Android. Trattato esplicitamente nel corso (slide 10).

**Autenticazione:** delegata a Cognito (Componente 10) — email/password, Google, Apple.

**Video:** nessun contenuto video ospitato internamente. L'app linka direttamente a ted.com con il parametro timestamp (`?t=<seconds>`), aprendo il video originale al punto esatto del bit selezionato.
