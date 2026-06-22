# VERSION 1.1
# Funzione app

ShorTED e' un'applicazione multipiattaforma scritta con Flutter che si interfaccia con l'infrastruttura costruita in AWS e MongoDB per funzioni e dati.

Il suo scopo e' mostrare brevi frasi, citazioni e video motivazionali ricavati da TED/TEDx Talks come snackable content, in stile TikTok, Instagram Reels o YouTube Shorts.

La documentazione operativa della V1 e' descritta nel [piano V1][app-v1-plan], il contratto dati/API e' descritto nel [data contract][app-data-contract] e la struttura Flutter e' descritta nella [documentazione architetturale app][app-architecture].

# Architettura Backend

L'applicazione si basa su dati e funzioni in AWS, come descritto nella [documentazione dell'architettura][architecture-docs].

## Backend usato nella V1

La V1 non usa Cognito e non salva utenti in cloud. Il profilo utente resta locale nell'app.

Endpoint usati direttamente dall'app:

- [get_all_tags][get-all-tags-lambda]: recupera da MongoDB l'elenco completo dei tag disponibili.
- [get_talks_by_tags][get-talks-by-tags-lambda]: recupera da MongoDB gli snack associati ai tag scelti.

Endpoint reali V1:

```text
GET https://nk1cgmp9kh.execute-api.us-east-1.amazonaws.com/default/get_all_tags
GET https://zjvrmg44s2.execute-api.us-east-1.amazonaws.com/default/get_talks_by_tags?tags=design,art&doc_per_page=20&page=1
```

La risposta, i campi e gli errori verificati sono documentati nel [data contract][app-data-contract].

## Backend futuro

La valutazione backend e la roadmap sono descritte nel [backend assessment][app-backend-assessment].

In sintesi:

- V1: profilo locale, feed composto lato app usando `get_talks_by_tags`.
- V1.1: introduzione di `getFeed` per randomizzazione, ranking e composizione server-side.
- V2: Cognito, utenti MongoDB, interessi cloud, snack visti, preferiti e sincronizzazione multi-dispositivo.

# Funzionamento dell'app

## Design e struttura

Fare riferimento alla [documentazione del design][design-instructions] e ai [design mock][design-mock].

Lo stile target e' moderno, nativo e poco invasivo: feed fullscreen, overlay leggibili, pannelli glass/liquid, bottom navigation minimale.

## Primo utilizzo

Alla prima apertura l'utente deve configurare il proprio profilo locale:

- inserire username;
- selezionare almeno 3 tag di interesse recuperati con `get_all_tags`.

L'utente deve sempre avere almeno 3 tag selezionati. Ad ogni avvio l'app verifica il profilo locale e, se mancano username o tag minimi, mostra nuovamente l'onboarding.

## Salvataggio dati e profilo V1

Nella V1 i dati utente restano solo localmente nei dati dell'applicazione:

- username;
- tag selezionati;
- tema light/dark.

Non vengono salvati in V1:

- snack visti;
- snack preferiti;
- statistiche profilo;
- identita' cloud.

Questi elementi sono rimandati alla V2 con Cognito e MongoDB `users`.

## Schermata Feed

La schermata feed mostra snack in scorrimento verticale continuo.

Ogni snack contiene:

- video TED embed fullscreen sullo sfondo;
- aforisma in primo piano;
- speaker e titolo talk;
- topic;
- tag principali;
- metadati espandibili o leggibili in overlay.

La V1 recupera gli snack con `get_talks_by_tags`, usando i tag locali dell'utente. Il feed viene randomizzato con shuffle lato app. Questa logica e' temporanea: quando verra' introdotta `getFeed`, ranking e randomizzazione passeranno al backend.

## Video

I video devono restare nel contesto dell'app e occupare lo sfondo fullscreen della card feed.

L'app usa l'URL contenuto nello snack nel campo `talkUrl`, sostituendo `www.ted.com` con `embed.ted.com`.

Esempio:

```text
https://www.ted.com/talks/isabel_allende_tales_of_passion?t=717
```

diventa:

```text
https://embed.ted.com/talks/isabel_allende_tales_of_passion?t=717
```

La V1 non mostra piu' il player TED embedded direttamente come sfondo cliccabile della card feed. La card usa la thumbnail del talk TED come sfondo non interattivo, recuperata tramite oEmbed TED e normalizzata a Full HD (`1920x1080`), cosi' non compaiono controlli video giganti nel feed e non ci sono conflitti tra gesture del feed, overlay e player embedded.

La card mostra un pulsante play sotto il box descrizione/tag, vicino alla navbar. Premendo play viene aperta una schermata player fullscreen dedicata, con l'embed TED senza overlay informativi. La schermata player tenta l'avvio immediato del video embedded tramite autoplay e JavaScript post-load; se la piattaforma o TED lo impediscono, l'utente usa comunque i controlli del player nella stessa schermata, restando dentro l'app e senza aprire un browser esterno.

## Ottimizzazione Feed

Per evitare attese, la V1 mantiene un buffer locale di snack.

Parametri V1:

- `doc_per_page = 20`;
- prefetch quando restano circa 5 snack nel buffer;
- shuffle lato app su ogni pagina caricata.

## Schermata Dettaglio

Scorrendo a destra su uno snack si visualizza il dettaglio.

Il dettaglio contiene:

- titolo talk;
- speaker;
- topic;
- quote;
- motivational text;
- aphorism;
- tag;
- URL originale TED;
- metadati tecnici utili se opportuno: lingua, start/end time.

Rispetto al mock, la V1 esclude il pulsante `Read Transcript`, perche' l'architettura app attuale non espone transcript completi.

Se lo swipe orizzontale dovesse creare conflitti importanti con WebView o scroll verticale, potra' essere sostituito in futuro da un pulsante informativo. La V1 parte comunque dallo swipe.

## Navbar

La navigazione usa una bottom navbar poco invasiva con due sezioni:

- feed;
- profilo.

Le icone possono bastare senza label se la leggibilita' resta buona.

## Schermata Profilo

La schermata profilo visualizza:

- username;
- tag selezionati;
- accesso alla modifica interessi;
- pulsante impostazioni in alto a destra.

La V1 non mostra statistiche reali di visualizzazioni o salvataggi, perche' questi dati non vengono ancora tracciati.

## Schermata Impostazioni

La schermata impostazioni permette di modificare:

- username;
- tema light/dark.

Le preferenze sono salvate localmente.

## Modifica tag salvati

L'utente puo' aggiungere e togliere tag dai propri interessi locali.

Regola obbligatoria:

- devono restare sempre almeno 3 tag selezionati.

Se l'utente tenta di scendere sotto 3 tag, l'app rifiuta l'operazione o disabilita la rimozione.


[app-v1-plan]: ./app_v1_plan.md
[app-data-contract]: ./app_data_contract.md
[app-backend-assessment]: ./app_backend_assessment.md
[app-architecture]: ./app_architecture.md
[design-instructions]: ../design/DESIGN.md
[design-mock]: ../design/stitch_universal_mobile_design_system
[snack-data-example]: ../../ai_pipeline/snack_example.json
[architecture-docs]: ../../architecture/
[get-all-tags-lambda]: ../../../scripts/AWS/ShorTED/Lambda/Get_All_Tags/
[get-talks-by-tags-lambda]: ../../../scripts/AWS/ShorTED/Lambda/Get_Talks_By_Tags/
