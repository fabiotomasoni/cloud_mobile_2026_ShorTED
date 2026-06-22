# Componente 11 — Flutter App

## Ruolo nel sistema
Applicazione mobile cross-platform (iOS e Android). È il punto di contatto finale con l'utente — tutto il sistema esiste per supportare quello che l'app mostra.

## Posizione nel pipeline
- **Autenticazione tramite:** Componente 10 (AWS Cognito) nel target finale; profilo locale nella V1
- **Dati tramite:** Componente 9 (API Gateway) → Componente 8 (Lambda API)
- **Link esterno a:** ted.com con timestamp per il video originale

## Schermate principali

**Onboarding** — selezione degli interessi al primo accesso, dopo la registrazione. Usa i tag del dataset come opzioni.

**Feed** — schermata principale. Lista di snacks filtrati per interessi: thumbnail TED fullscreen, aforisma, argomento, speaker e pulsante play.

**Dettaglio snack** — quote completa, riassunto, link a ted.com con timestamp al punto esatto del video.

**Profilo / Impostazioni** — modifica degli interessi, logout.

## Decisioni prese

**Tool:** Flutter — framework hybrid cross-platform, un solo codebase per iOS e Android. Trattato esplicitamente nel corso (slide 10).

**Autenticazione:** target finale delegato a Cognito. La V1 mantiene profilo locale per username, tag e tema.

**Video:** nessun contenuto video ospitato internamente. L'app usa thumbnail e URL media arricchiti dal backend; l'embed TED resta fallback/player fullscreen, mentre `hlsUrl` e `mp4Url` preparano il player nativo futuro.
