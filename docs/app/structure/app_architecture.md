# ShorTED Flutter App Architecture

## Obiettivo

La V1 dell'app ShorTED usa un'architettura a layer per separare accesso ai dati, logica applicativa e UI.

Questa scelta evita che le schermate conoscano dettagli di HTTP, `SharedPreferences`, parsing JSON o composizione del feed. Prepara inoltre la sostituzione futura di `get_talks_by_tags` con `getFeed` e l'introduzione di Cognito/MongoDB users in V2.

## Stato Implementazione

Questa architettura e' stata implementata nella V1 corrente dell'app Flutter in `flutter/shorted`.

Implementato:

- separazione `data`, `domain`, `application`, `presentation`, `theme`;
- `Repository Pattern` per snack e profilo;
- `Data Source Pattern` per API remote e storage locale;
- `DTO Pattern` per separare formato API/storage dai modelli di dominio;
- `Application Services` per feed, onboarding e profilo;
- `ChangeNotifier` controller per stato UI;
- state classes immutabili per feed, onboarding, edit tags e app root;
- dependency injection manuale tramite `AppDependencies`;
- screens e widgets senza accesso diretto a HTTP o `SharedPreferences`.

Verifica eseguita dopo il refactor:

```text
flutter analyze
flutter test
```

Entrambi i comandi passano.

## Struttura

```text
lib/
  main.dart
  src/
    app.dart
    app_dependencies.dart
    data/
      datasources/
      dto/
      repositories/
    domain/
      models/
      repositories/
    application/
      services/
    presentation/
      controllers/
      states/
      screens/
      widgets/
    theme/
```

## Data Layer

Il data layer contiene implementazioni tecniche e dettagli esterni.

Responsabilita':

- chiamate HTTP agli endpoint AWS API Gateway;
- accesso a `SharedPreferences`;
- parsing JSON tramite DTO;
- implementazione concreta dei repository.

Componenti:

- `ShortedRemoteDataSource`: legge tag e snack dal backend.
- `ProfileLocalDataSource`: legge/scrive il profilo locale.
- `SnackDto`: rappresenta la response API degli snack e la converte in domain model.
- `UserProfileDto`: rappresenta il profilo persistito localmente e lo converte in domain model.
- `SnackRepositoryImpl`: implementa il repository snack usando il remote data source.
- `ProfileRepositoryImpl`: implementa il repository profilo usando il local data source.

Regola:

- I DTO non escono dal data layer.

## Domain Layer

Il domain layer contiene il modello concettuale dell'app e i contratti.

Responsabilita':

- definire `Snack` e `UserProfile` come modelli usati dall'app;
- definire i repository astratti;
- non dipendere da Flutter UI, HTTP, storage o implementation details.

Nota pragmatica V1:

- `UserProfile` usa `ThemeMode`, quindi dipende da Flutter foundation/material. Se in futuro il dominio dovesse diventare completamente framework-agnostic, `ThemeMode` potra' essere sostituito da un enum proprietario (`AppThemeMode`). Per la V1 questa dipendenza e' accettata per semplicità.

## Application Layer

L'application layer contiene i casi d'uso e l'orchestrazione.

Responsabilita':

- validare le regole dell'onboarding;
- gestire composizione e paginazione feed V1;
- applicare shuffle lato app;
- aggiornare profilo, tag e tema.

Componenti:

- `FeedService`: carica pagine di snack e applica shuffle V1.
- `OnboardingService`: carica tag e crea profili validi.
- `ProfileService`: legge/salva/modifica profilo locale.

## Presentation Layer

Il presentation layer contiene stato UI, controller e widget.

Responsabilita':

- rappresentare loading/error/data state;
- reagire agli input utente;
- chiamare application services;
- renderizzare schermate e widget.

Componenti:

- Controllers basati su `ChangeNotifier`.
- State classes immutabili.
- Screens.
- Widgets riusabili.

La UI non istanzia direttamente data source, repository o API client.

## Dependency Injection

La V1 usa dependency injection manuale tramite `AppDependencies`.

Motivazione:

- evita dipendenze esterne premature;
- mantiene leggibile il wiring per una V1 piccola;
- rende esplicite le dipendenze tra layer;
- permette di valutare Riverpod dopo il refactor su una base già ordinata.

## Pattern Usati

- Repository Pattern.
- Data Source Pattern.
- DTO Pattern.
- Application Service Pattern.
- Controller + State con `ChangeNotifier`.
- Manual Dependency Injection.

## Pattern Non Introdotti In V1

- Riverpod.
- Provider package.
- BLoC.
- GetIt/service locator.

Questi pattern non sono esclusi in modo definitivo. Dopo il refactor e' stata fatta una prima rivalutazione di Riverpod: la decisione corrente e' non introdurlo ancora nella V1 perche' il wiring manuale resta contenuto e i controller sono ancora locali alle rispettive schermate.

## Regole Di Dipendenza

- `presentation` dipende da `application` e `domain`.
- `application` dipende da `domain`.
- `data` dipende da `domain` per implementare i repository.
- `domain` non dipende da `data`.
- DTO e data source restano nel `data layer`.
- Screen e widget non fanno HTTP, parsing JSON o accesso diretto a `SharedPreferences`.

## Decisioni Gia' Prese

- `flutter/shorted` e' l'app ShorTED.
- `flutter/mytedx_2026` e' un'app separata dello stesso progetto universitario.
- La V1 usa profilo locale.
- La V1 usa `get_all_tags` e `get_talks_by_tags`.
- La V1 applica shuffle lato app.
- La V1 usa WebView TED embed fullscreen integrata nel feed.
- `getFeed`, Cognito e MongoDB users sono rimandati a versioni future.

## Decision Log

### Separazione A Layer

Decisione:

- usare una struttura esplicita `data/domain/application/presentation/theme`.

Motivazione:

- impedisce alla UI di dipendere direttamente da API, storage e parsing JSON;
- rende piu' chiaro dove collocare nuove funzionalita';
- prepara la sostituzione di `get_talks_by_tags` con `getFeed` senza riscrivere le schermate;
- rende piu' semplice introdurre Cognito e utenti cloud in V2.

Conseguenza:

- piu' file rispetto a una V1 monolitica;
- maggiore chiarezza delle responsabilita';
- refactor futuro piu' contenuto.

### Data Sources

Decisione:

- isolare chiamate HTTP in `ShortedRemoteDataSource`;
- isolare `SharedPreferences` in `ProfileLocalDataSource`.

Motivazione:

- permette di cambiare endpoint o storage locale senza toccare UI e domain;
- rende testabili repository e servizi con data source alternativi;
- prepara una futura sorgente cloud per il profilo.

### DTO

Decisione:

- introdurre `SnackDto` e `UserProfileDto` nel data layer.

Motivazione:

- il formato API/storage non deve coincidere per forza con il modello dell'app;
- eventuali campi mancanti o variazioni del backend vengono gestiti nel data layer;
- i domain model restano piu' stabili.

### Repository Pattern

Decisione:

- definire contratti repository nel domain layer;
- implementare i repository nel data layer.

Motivazione:

- application e presentation dipendono da astrazioni;
- `getFeed` potra' sostituire `get_talks_by_tags` dentro `SnackRepositoryImpl` o in una nuova implementazione;
- Cognito/MongoDB users potranno essere introdotti in `ProfileRepositoryImpl` senza cambiare le schermate.

### Application Services

Decisione:

- usare `FeedService`, `OnboardingService`, `ProfileService`.

Motivazione:

- evita di mettere regole applicative nei controller;
- centralizza paginazione, shuffle, validazione profilo e aggiornamenti;
- mantiene i repository focalizzati su accesso dati.

### Controllers E States

Decisione:

- usare controller `ChangeNotifier` e state classes immutabili.

Motivazione:

- e' una soluzione nativa Flutter senza dipendenze extra;
- sufficiente per la complessita' V1;
- separa stato/loading/error dalla UI;
- rende possibile una migrazione futura a Riverpod senza riscrivere data/domain/application.

### Dependency Injection Manuale

Decisione:

- cablare le dipendenze in `AppDependencies`.

Motivazione:

- V1 ha poche dipendenze;
- il wiring resta esplicito e comprensibile;
- si evita un service locator globale;
- Riverpod puo' essere introdotto dopo, se il wiring cresce.

### Riverpod Non Introdotto Subito

Decisione:

- non aggiungere Riverpod nella V1 corrente.

Motivazione:

- i controller sono ancora usati quasi sempre da una singola schermata;
- lo stato condiviso e' limitato al profilo/app root;
- il passaggio di dipendenze nei costruttori e' ancora gestibile;
- aggiungere Riverpod ora aumenterebbe la complessita' senza un beneficio immediato proporzionato.

Conseguenza:

- si mantiene `ChangeNotifier` manuale;
- la scelta resta aperta e va rivalutata appena crescono stato condiviso, auth o feed server-side.

## Valutazione Riverpod Dopo Refactor

Valutazione corrente dopo il refactor:

- non introdurre Riverpod immediatamente;
- mantenere `ChangeNotifier` e dependency injection manuale per la V1;
- rivalutare Riverpod quando si implementano funzionalita' che aumentano stato condiviso o lifecycle complexity.

Passare a Riverpod diventa consigliato se:

- il dependency wiring manuale cresce troppo;
- molti controller devono condividere stato;
- servono override/test delle dipendenze più comodi;
- iniziano troppi passaggi di dipendenze nei costruttori;
- serve lifecycle/cache più robusto.

Restare con `ChangeNotifier` manuale e' accettabile se:

- ogni controller resta vicino a una schermata;
- le dipendenze restano poche;
- il codice rimane leggibile;
- i test restano semplici.

## Roadmap Architetturale

### V1 Corrente

- `ChangeNotifier` controllers.
- Manual dependency injection.
- Profilo locale.
- Feed service con shuffle lato app.
- Repository che usa `get_talks_by_tags`.

### V1.1 Con getFeed

Possibili modifiche:

- `SnackRepositoryImpl` usa `getFeed` invece di `get_talks_by_tags` per il feed;
- `FeedService` delega ranking/randomizzazione al backend;
- introduzione di cursor/nextCursor se il backend lo supporta;
- possibile revisione di `FeedState` per gestire cursor invece di page number.

Riverpod in V1.1:

- da rivalutare se il feed mantiene cache condivisa tra schermate o se piu' controller devono leggere/scrivere lo stesso stato feed.

### V2 Con Cognito E Users Cloud

Possibili modifiche:

- `ProfileRepositoryImpl` integra remote profile data source;
- nuovo `AuthRepository` e `AuthService`;
- nuovo app/auth state globale;
- gestione sessione, token, refresh e logout;
- sincronizzazione locale/cloud degli interessi.

Riverpod in V2:

- consigliato se auth state, profile state e feed state devono essere condivisi tra molte schermate;
- utile per override delle dipendenze nei test;
- utile per lifecycle/cache dei repository e dei controller.

### Possibile Migrazione A Riverpod

Se si decide di migrare:

- mantenere invariati domain, data layer e application services;
- sostituire `AppDependencies` con provider di repository/services/controllers;
- sostituire `AnimatedBuilder` sui controller con consumer/provider equivalenti;
- evitare di spostare logica applicativa nei provider: i provider devono solo esporre dipendenze e stato.

La migrazione non deve cambiare il contratto dei repository o i modelli di dominio.
