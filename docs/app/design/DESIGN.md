# ShorTED Design

## Funzione app

ShorTED è un'applicazione multipiattaforma scritta con Flutter che si interfaccia con l'infrastruttura costruita in AWS e MongoDB per funzioni e dati.
Il suo scopo è quello di mostrare brevi frasi e video motivazionali riassunti e recuperati dal sito web di TEDx Talks come snakcable content, in stile TikTok o Instagram Reels.

## Stile generale
L'app dovrebbe avere uno stile moderno, pulito, che si conforma con lo stile nativo del sistema operativo ospitante (Android, iOS 26 ecc...) quindi favoriamo l'utilizzo di design nativi come ad esempio Liquid Glass o equivalenti per Android

## Pagine
### Pagina Principale - Feed

All'interno del feed, che è la prima pagina visualizzabile quando si apre l'app, l'utente può scrollare tra gli "snacks" con scorrimento continuo animato verticale.
Ogni snack mostra in evidenza un aforisma e una clip recuperata direttamente da TEDx collegata.
Ogni snack ha anche una descrizione ad espansione in cui mostriamo altri metadati del video: tags, speaker, titolo del talk.

#### Sottopagina Feed - Dettaglio Snack

Scorrendo a destra di uno snack apriamo invece una pagina dettagliata relativa allo snacks stesso che mostra tutti i metadati completi come titolo, speaker, tags, topic, quote, motivational text, aphorism e url originale.
In quest'ultima schermata abbiamo tante informazioni, in particolare motivational text e quote sono spesso anche stringhe lunghe dimensionalmente, quindi è importante valutare bene il design e posizionamento.


### Profilo Utente

La pagina profilo utente permette all'utente di visualizzare e gestire il suo profilo.

#### Sottopagina Profilo Utente - Impostazioni

Dalla pagina profilo deve essere possibile anche accedere alle impostazioni dell'app, dove troviamo impostazioni come il tema dell'app (dark/light) e simili.

#### Sottopagina Profilo Utente - Selezione Interessi

Una funzione fondamentale di questa pagina è la sezione che permette all'utente di selezionare i propri interessi, andando a cercare e salvare tags che gli interessano. Questa sarà la base sulla quale viene calcolato il feed dell'utente.


### Navbar

Per navigare tra feed e profilo utente usiamo una navbar nella parte bassa dello schermo.