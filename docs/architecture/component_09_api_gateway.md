# Componente 9 — API Gateway

## Ruolo nel sistema
Punto di ingresso unico per tutte le chiamate HTTP provenienti dall'app Flutter. Gestisce il traffico, la sicurezza degli endpoint e l'instradamento verso le Lambda API.

## Posizione nel pipeline
- **Chiamato da:** Componente 11 (Flutter App)
- **Instrada verso:** Componente 8 (Lambda API Functions)
- **Delega autenticazione a:** Componente 10 (AWS Cognito) per gli endpoint protetti del target finale

## Cosa fa
Espone gli endpoint REST dell'app e inoltra ogni richiesta alla Lambda corrispondente. Gli endpoint V1 pubblici non richiedono autenticazione; nel target finale gli endpoint utente/feed protetti verranno validati tramite Cognito.

## Decisioni prese
**Tool:** AWS API Gateway.

## Note
Trattato esplicitamente nel corso nelle slide sul serverless (slide 7). Lavora in coppia con Cognito (Componente 10) per la gestione dell'autenticazione.
