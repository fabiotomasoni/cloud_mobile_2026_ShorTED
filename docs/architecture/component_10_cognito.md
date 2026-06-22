# Componente 10 — AWS Cognito

## Ruolo nel sistema
Gestione completa dell'autenticazione utenti nel target finale. Copre registrazione, login, sessioni e token senza costruire logica di auth da zero.

## Posizione nel pipeline
- **Usato da:** Componente 9 (API Gateway) — verifica JWT su ogni richiesta in ingresso
- **Usato da:** Componente 11 (Flutter App) — login, registrazione, gestione sessione

## Cosa fa
- Gestisce registrazione e login degli utenti
- Emette token JWT dopo l'autenticazione
- API Gateway verifica il token prima di inoltrare ogni richiesta a Lambda
- Fornisce SDK per Flutter per integrare le schermate di accesso

## Decisioni prese

**Tool:** AWS Cognito.

**Metodi di accesso supportati:**
- Email e password
- Google (social login)
- Apple (social login — obbligatorio su iOS se si offrono altri social login)

I social login sono configurazione nativa in Cognito (Identity Providers), non richiedono codice custom.

## Note
Incluso nel design fin dall'inizio per non dover riprogettare l'architettura. La V1 Flutter usa profilo locale e non Cognito; Cognito resta componente target per V2.
