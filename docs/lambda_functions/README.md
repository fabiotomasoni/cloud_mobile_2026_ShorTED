# ShorTED Lambda Functions — Non-AI

Questa sezione documenta le Lambda ShorTED che non fanno parte della pipeline AI. La documentazione della Lambda AI, MCP e snack generation resta in `docs/ai_pipeline/`.

## Funzioni documentate
- `Dispatcher`: sposta il lavoro dal bucket enriched alla coda SQS.
- `Media_Enricher`: arricchisce i processed JSON con metadati media TED.
- `Get_All_Tags`: espone la lista tag per onboarding e profilo.
- `Get_Talks_By_Tags`: espone gli snack filtrati per tag all'app Flutter.

## Confine con la pipeline AI
Queste Lambda non generano snack con modelli AI. Preparano input, espongono dati o collegano componenti. La generazione semantica degli snack resta responsabilità di `Orchestrator` e della AI Snack Pipeline.

## File codice
- `scripts/AWS/ShorTED/Lambda/Dispatcher/`
- `scripts/AWS/ShorTED/Lambda/Media_Enricher/`
- `scripts/AWS/ShorTED/Lambda/Get_All_Tags/`
- `scripts/AWS/ShorTED/Lambda/Get_Talks_By_Tags/`
