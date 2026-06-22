# Componente 8 — Lambda API Functions

## Ruolo nel sistema
Layer serverless che espone i dati di MongoDB verso l'app Flutter. È il confine tra backend e frontend — ogni operazione dell'app che coinvolge dati passa da qui.

## Posizione nel pipeline
- **Legge/scrive su:** Componente 7 (MongoDB)
- **Chiamato da:** Componente 9 (API Gateway)

## Funzioni
Funzioni V1 già operative:

- `get_all_tags` — lista dei tag disponibili per onboarding e profilo locale.
- `get_talks_by_tags` — snack filtrati per tag, con campi media arricchiti.

Funzioni target V2:

- `createUser` — crea il profilo utente al primo accesso.
- `getFeed` — restituisce feed personalizzato server-side.
- `markSeen` — registra la visualizzazione di uno snack.
- `updateInterests` — aggiorna gli interessi cloud.

## Decisioni prese
**Tool:** AWS Lambda. Le API V1 sono implementate in Node.js; il target finale può includere altre Lambda protette da Cognito.

**Lista funzioni:** da considerarsi base di partenza, da rifinire prima dell'implementazione.

## Note
Cognito (autenticazione utenti) è previsto come componente dedicato nell'architettura. La lista di funzioni sarà rivista e completata nella fase di implementazione.
