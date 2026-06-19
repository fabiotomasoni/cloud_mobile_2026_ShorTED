# VERSION 1.0
# Funzione app

ShorTED è un'applicazione multipiattaforma scritta con Flutter che si interfaccia con l'infrastruttura costruita in AWS e MongoDB per funzioni e dati.
Il suo scopo è quello di mostrare brevi frasi e video motivazionali riassunti e recuperati dal sito web di TEDx Talks come snakcable content, in stile TikTok o Instagram Reels.


# Architettura Backend

L'applicazione si basa su dati e funzioni in AWS, come vediamo nella [documentazione dell'architettura][architecture-docs].
In particolare l'applicazione userà in modo diretto le api gateway che triggerano le lambda. 
[get-all-tags][get-all-tags-lambda] per recuperare l'elenco di tutti i tag dei talks da mongodb.
[get-talks-by-tags][get-talks-by-tags-lambda] per recuperare snacks e talks da mongodb in base ai tags passati.


# Funzionamento dell'app

## Design e struttura

Fare riferimento alla [documentazione del design][design-instructions].

## Logica e flusso d'utilizzo

### Primo utilizzo

L'utente alla prima apertura dell'app deve configurare il proprio profilo, inserendo l'username e selezionando almeno 3 tags di suo interesse, recuperati con [get-all-tags-lambda].
L'utente dovrebbe sempre avere almeno 3 tags selezionati, quindi ad ogni apertura bisogna verificare questo dato e, in caso, mostrare di nuovo la selezione tags.

### Salvataggio dati e profilo

I dati dell'utente, come appunto i tags selezionati e il profilo stesso, rimangono per ora salvati solo locamente nei dati dall'applicazione. In uno sviluppo futuro che comprende la configurazione e connessione all'app del servizio AWS Cognito, si può fare una transizione per salvare i dati dell'utente in cloud con sincronizzazione locale per maggior efficienza, portabilità e sicurezza dei dati. 

### Utilizzo principale

#### Schermata Feed 

Nella schermata del feed, con design come mostrato nelle [immagini di design mock][design-mock], dobbiamo mostrare all'utente i dati descritti nelle [istruzioni sul design][design-instructions] per la pagina principale del feed e del dettaglio.
Lo stile è quello delle principali applicazioni social, TikTok, Instragram, YouTube Shorts. Scorrimento verticale continuo del feed con gli snacks, video con autoplay in secondo piano e aforisma in primo, scorrimento laterale per i dettagli, descrizione e informazioni in basso.

#### Video 

I video vanno riprodotti automaticamente in sottofondo a schermo intero. Per farlo dobbiamo usare l'url contenuto nello snack [snack-data-example] nel campo "talkUrl" sostituendo www con embed, quindi ad esempio http://embed.ted.com/talks/isabel_allende_tales_of_passion?t=717


#### Ottimizzazione

Per evitare attese nel recupero degli snacks, è necessario implementare una logica ottimizzata, che salva in memoria n risultati a chiamata, invece che uno alla volta. Prepara i dati da mostrare e i video prima che siano attivamente visualizzati nell'app.

#### Schermata Dettaglio

Scorrendo a destra visualizziamo il dettaglio, descritto nella [documentazione del deisgn][design-instructions] e mostrato nel [design mock][design-mock].
Deve contenere le informazioni complete del talk. Rispetto all'immagine di riferimento escludiamo solo il pulsante "Read Transcript" perchè la nostra architettura attualmente non lo permette, mentre abbiamo a disposizione tutti gli altri dati.

#### Navbar 

Per spostarsi da una schermata all'altra usiamo una navbar nella parte bassa dello schermo, con due opzioni: feed e profilo. Serve una navbar poco invadente per migliorare l'esperienza utente di visione degli snacks, possono bastare delle icone senza label per indicare le schermate.

#### Schermata Profilo

Nella schermata profilo visualizziamo il profilo dell'utente come descritto nella [documentazione del deisgn][design-instructions] e mostrato nel [design mock][design-mock]. 
In questa schermata permettiamo di visualizzare e modificare i tag salvati dall'utente.
In alto a destra un pulsante con icona dell'ingranaggio, senza label, permette all'utente di accedere alle impostazioni.

#### Schermata Impostazioni 

Nella schermata di impostazioni facciamo gestire all'utente il proprio profilo, permettendo di modificare le informazioni associate ad esso e tema light e dark, che sono preferenze da salvare nei dati locali dell'app e design da implementare. 

#### Modifica tag salvati

Permettiamo all'utente di aggiungere e togliere tag ai propri tag salvati. Dobbiamo sempre controllare che siano almeno 3 i tag salvati, altrimenti rifiutiamo l'operazione prima di eseguirla. 





[design-instructions]: ../design/DESIGN.md 
[design-mock]: ../design/stitch_universal_mobile_design_system
[snack-data-example]: ../../ai_pipeline/snack_example.json
[architecture-docs]: ../../architecture/
[get-all-tags-lambda]: ../../../scripts/AWS/ShorTED/Lambda/Get_All_Tags/
[get-talks-by-tags-lambda]: ../../../scripts/AWS/ShorTED/Lambda/Get_Talks_By_Tags/