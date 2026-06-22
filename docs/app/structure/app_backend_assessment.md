# ShorTED App Backend Assessment

## Stato Backend Disponibile

La V1 dell'app puo' essere costruita con due endpoint gia' deployati:

- `get_all_tags`
- `get_talks_by_tags`

Questi endpoint leggono MongoDB e non richiedono autenticazione utente.

## Sufficienza per V1

Il backend attuale e' sufficiente per una V1 con profilo locale perche':

- l'app puo' recuperare tutti i tag disponibili;
- l'app puo' recuperare snack filtrati per i tag selezionati;
- la paginazione consente prefetch lato client;
- tutti i campi snack necessari al feed e al dettaglio sono ora esposti.

La V1 non richiede ancora Lambda per utenti, viste o salvataggi.

## Limiti Accettati in V1

- Randomizzazione lato app, non globale.
- Nessuna esclusione persistente degli snack gia' visti.
- Nessun profilo remoto.
- Nessuna autenticazione.
- Nessun salvataggio preferiti.
- Nessuna metrica reale nel profilo.

## Modifica Lambda Gia' Applicata

`Get_Talks_By_Tags` e' stata aggiornata per includere nella projection tutti i campi dello snack necessari:

```text
_id segmentId talkId talkSlug speaker talkTitle topic quote motivationalText aphorism tags score startTime endTime talkUrl language aiPipelineVersion sourceHash createdAt
```

Non e' stato aggiunto ordinamento server-side nella V1, per lasciare all'app lo shuffle temporaneo.

## Proposta V1.1: getFeed

Una Lambda `getFeed` dovrebbe sostituire in app la logica di composizione del feed.

Responsabilita':

- ricevere tag/interessi utente;
- applicare randomizzazione server-side;
- combinare ranking (`score`) e varieta' dei tag;
- evitare ripetizioni nella stessa sessione se viene passato un cursor o un elenco di ID gia' restituiti;
- restituire una pagina pronta per il feed.

Endpoint indicativo:

```text
GET /get_feed?tags=design,art,technology&limit=20&cursor=<opaque>
```

Response indicativa:

```json
{
  "items": [],
  "nextCursor": "..."
}
```

## Proposta V2: Utenti Cloud

La V2 introduce utenti reali e persistenza cloud.

Componenti:

- AWS Cognito per autenticazione.
- API Gateway con authorizer Cognito.
- Collezione MongoDB `users`.
- Lambda utenti/feed protette.

Collezione `users` indicativa:

```json
{
  "userId": "cognito-sub",
  "username": "Elena",
  "selectedTags": ["design", "art", "technology"],
  "seenSnackIds": ["..."],
  "savedSnackIds": ["..."],
  "createdAt": "2026-06-21T00:00:00.000Z",
  "updatedAt": "2026-06-21T00:00:00.000Z"
}
```

Lambda V2:

- `createUser`
- `getUserProfile`
- `updateInterests`
- `getFeed`
- `markSeen`
- `saveSnack`
- `unsaveSnack`

## Indici MongoDB Consigliati

Per `snacks`:

- `{ tags: 1 }`
- `{ score: -1 }`
- `{ talkSlug: 1 }`
- `{ tags: 1, score: -1 }` per feed filtrati e ranking.

Per `users` in V2:

- `{ userId: 1 }` unique.
- `{ updatedAt: -1 }` opzionale per manutenzione/analytics.
