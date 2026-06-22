# ShorTED App V1 Plan

## Obiettivo

La versione 1 di ShorTED deve fornire una prima app Flutter funzionante, autonoma lato profilo utente e collegata al backend esistente solo per recuperare tag e snack.

L'obiettivo UX e' un feed verticale in stile Reels/TikTok: contenuto video TED fullscreen sullo sfondo, aforisma e metadati in overlay, dettaglio raggiungibile con swipe orizzontale.

## Scope V1

- App Flutter in `flutter/shorted`.
- Architettura Flutter a layer come descritta in [app_architecture.md](./app_architecture.md).
- Onboarding al primo avvio con username e selezione di almeno 3 tag.
- Recupero tag da `get_all_tags`.
- Recupero snack da `get_talks_by_tags` usando i tag scelti dall'utente.
- Feed verticale paginato con prefetch.
- Shuffle lato app dei risultati ricevuti, per simulare un feed meno deterministico.
- Video TED embed fullscreen come sfondo integrato nella schermata, senza apertura del player nativo esterno.
- Dettaglio snack tramite swipe orizzontale verso destra.
- Profilo locale con visualizzazione username e tag selezionati.
- Modifica tag dal profilo, mantenendo sempre almeno 3 tag.
- Impostazioni locali con modifica username e tema light/dark.
- Persistenza locale di username, tag e tema.

## Fuori Scope V1

- Cognito.
- Profilo utente in MongoDB.
- `getFeed` server-side.
- Tracking cloud degli snack visti.
- Salvataggio preferiti.
- Statistiche reali del profilo.
- Sincronizzazione multi-dispositivo.
- Transcript completo.

## Flusso Primo Avvio

1. L'app carica il profilo locale.
2. Se il profilo non esiste, oppure ha meno di 3 tag, mostra onboarding.
3. L'onboarding recupera i tag da `get_all_tags`.
4. L'utente inserisce username e seleziona almeno 3 tag.
5. L'app salva localmente username, tag e tema di default.
6. L'app apre il feed.

## Flusso Feed

1. L'app legge i tag locali.
2. Chiama `get_talks_by_tags` con `doc_per_page = 20` e `page = 1`.
3. Applica shuffle lato app alla pagina ricevuta.
4. Mostra gli snack in un `PageView` verticale.
5. Quando restano circa 5 snack nel buffer, carica la pagina successiva.
6. Le pagine successive vengono aggiunte al buffer e mescolate localmente.

La randomizzazione lato app e' una scelta temporanea di V1. In una versione futura verra' spostata nel backend con `getFeed`.

## Video

Il feed usa l'URL `talkUrl` dello snack per costruire l'embed TED.

Regola:

```text
https://www.ted.com/talks/<slug>?t=<seconds>
```

diventa:

```text
https://embed.ted.com/talks/<slug>?t=<seconds>
```

La V1 mostra nella card feed la thumbnail del talk TED come sfondo non interattivo, senza player TED direttamente cliccabile e senza overlay play nativo dell'embed. La thumbnail viene recuperata tramite oEmbed TED, normalizzata a Full HD (`1920x1080`) e mantenuta in cache lato app durante la sessione.

L'interazione video principale avviene tramite un pulsante play esplicito posizionato sotto il box descrizione/tag, vicino alla navbar. Quando l'utente preme play, l'app apre una schermata player fullscreen dedicata con l'embed TED senza overlay descrittivi. La schermata player prova ad avviare subito il video embedded tramite parametri autoplay e JavaScript post-load; se l'embed TED o la piattaforma bloccano l'avvio automatico, restano disponibili i controlli del player nella stessa schermata, senza aprire un browser esterno.

## Navigazione

- Bottom navigation con due sezioni: feed e profilo.
- Il dettaglio snack si apre con swipe orizzontale verso destra dalla card feed.
- Se lo swipe dovesse confliggere troppo con WebView o scroll verticale, la soluzione potra' essere sostituita da un pulsante nella UI, ma la V1 parte con swipe.

## Profilo Locale

Campi persistiti:

- `username`
- `selectedTags`
- `themeMode`

Non vengono persistiti in V1:

- snack visti
- snack salvati
- statistiche feed
- credenziali o identita' cloud

## Versioni Future

### V1.1 Backend Feed

- Introduzione di `getFeed`.
- Randomizzazione e ranking server-side.
- Esclusione opzionale di snack gia' restituiti nella sessione.
- Miglior controllo di paginazione/cursor.
- Rivalutazione di Riverpod se il feed richiede cache condivisa, stato piu' complesso o piu' controller dipendenti dallo stesso stato.
- Pipeline backend dedicata per recuperare thumbnail TED, salvarle/cacharle, generare resize multipli e scrivere nello snack finale URL espliciti per thumbnail e video embed.

### V2 Utenti Cloud

- AWS Cognito per registrazione/login.
- Collezione MongoDB `users`.
- Salvataggio interessi in cloud.
- Tracking snack visti.
- Preferiti/saved.
- Sincronizzazione multi-dispositivo.
- Probabile introduzione di un layer auth dedicato (`AuthRepository`, `AuthService`, auth state globale).
- Riverpod consigliato se auth, profilo e feed diventano stati condivisi tra molte schermate.
