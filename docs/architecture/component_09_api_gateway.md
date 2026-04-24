# Componente 9 — API Gateway

## Ruolo nel sistema
Punto di ingresso unico per tutte le chiamate HTTP provenienti dall'app Flutter. Gestisce il traffico, la sicurezza degli endpoint e l'instradamento verso le Lambda API.

## Posizione nel pipeline
- **Chiamato da:** Componente 11 (Flutter App)
- **Instrada verso:** Componente 8 (Lambda API Functions)
- **Delega autenticazione a:** Componente 10 (AWS Cognito)

## Cosa fa
Espone gli endpoint REST dell'app, verifica l'autenticazione di ogni richiesta tramite Cognito, e la inoltra alla Lambda corrispondente. Gestisce HTTPS.

## Decisioni prese
**Tool:** AWS API Gateway.

## Note
Trattato esplicitamente nel corso nelle slide sul serverless (slide 7). Lavora in coppia con Cognito (Componente 10) per la gestione dell'autenticazione.
