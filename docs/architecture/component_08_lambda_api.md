# Componente 8 — Lambda API Functions

## Ruolo nel sistema
Layer serverless che espone i dati di MongoDB verso l'app Flutter. È il confine tra backend e frontend — ogni operazione dell'app che coinvolge dati passa da qui.

## Posizione nel pipeline
- **Legge/scrive su:** Componente 7 (MongoDB)
- **Chiamato da:** Componente 9 (API Gateway)

## Funzioni (base)
- `createUser` — crea il profilo utente al primo accesso con gli interessi selezionati
- `getFeed` — restituisce bits filtrati per interessi dell'utente, esclusi i già visti
- `markSeen` — registra la visualizzazione di un bit
- `getTags` — lista dei tag disponibili per l'onboarding
- `updateInterests` — aggiorna gli interessi dell'utente

## Decisioni prese
**Tool:** AWS Lambda (Python).

**Lista funzioni:** da considerarsi base di partenza, da rifinire prima dell'implementazione.

## Note
Cognito (autenticazione utenti) è previsto come componente dedicato nell'architettura. La lista di funzioni sarà rivista e completata nella fase di implementazione.
