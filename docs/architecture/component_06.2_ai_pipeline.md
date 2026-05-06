# Componente 6a — AI Snack Pipeline

## Ruolo nel sistema
Sotto-componente logico della Lambda AI Processing. Descrive la parte AI più specifica dell'architettura: invece di usare un singolo prompt monolitico, il transcript viene analizzato tramite più passaggi specializzati e i risultati vengono combinati in uno "snack" finale.

L'obiettivo è migliorare la qualità dei contenuti prodotti da ShorTED: ogni snack deve essere breve, interessante, coerente con il talk originale e utile per costruire un feed personalizzato.

## Posizione nel pipeline
- **Attivata da:** Componente 6 (Lambda AI Processing)
- **Input da:** Componente 4 (S3 Processed Bucket) — documento JSON del talk con transcript
- **Usa:** AWS Bedrock — uno o più modelli/prompt specializzati
- **Output verso:** Componente 7 (MongoDB) — collezioni `talks` e `snacks`

## Idea architetturale
La Lambda AI resta il componente che riceve il messaggio da SQS e coordina il lavoro. Al suo interno, però, viene introdotta una pipeline AI composta da più fasi:

```
Transcript del talk
   ↓
AI Orchestrator
   ├── Segmenter
   ├── Quote & Summary Generator
   ├── Tagger / Ranker
   ↓
Snack Mixer
   ↓
Snakcs finali su MongoDB
```

Questa struttura permette di separare responsabilità diverse che, in una versione più semplice, sarebbero concentrate in una sola chiamata al modello.

## Cosa fa
Per ogni talk ricevuto dalla Lambda AI:

1. Riceve il transcript e i metadati principali del talk
2. Divide il transcript in sezioni tematiche candidate
3. Genera per ogni sezione una citazione breve e un riassunto
4. Associa tag e topic utili per la personalizzazione del feed
5. Valuta quali segmenti sono più adatti a diventare snack
6. Combina i risultati nel formato finale dei `snacks`
7. Restituisce alla Lambda AI i documenti pronti da salvare su MongoDB

## Sotto-componenti AI

### Segmenter
Analizza il transcript e individua i cambi di argomento più rilevanti. Produce una lista di segmenti candidati con timestamp di inizio e fine.

Esempio di output logico:
```
{
  startTime,
  endTime,
  topicCandidate,
  transcriptExcerpt
}
```

### Quote & Summary Generator
Lavora sui segmenti candidati. Per ogni segmento estrae o genera:
- una quote breve e significativa
- un summary di poche righe
- un titolo/tema leggibile nell'app

Questa fase è importante perché trasforma il testo lungo del talk in contenuto immediato, adatto a un consumo rapido.

### Tagger / Ranker
Arricchisce ogni candidato snack con tag e punteggi. I tag servono per collegare il contenuto agli interessi dell'utente, mentre lo score aiuta a scegliere i segmenti migliori.

Possibili criteri di ranking:
- chiarezza del segmento
- valore informativo
- presenza di una citazione forte
- coerenza con i tag del talk
- lunghezza adatta a uno snack

### Snack Mixer
È il punto finale della pipeline AI. Riceve i risultati dei passaggi precedenti e costruisce i `snacks` definitivi.

Il Mixer:
- rimuove duplicati o segmenti troppo simili
- scarta segmenti deboli o poco chiari
- controlla che quote e summary siano coerenti con il transcript
- seleziona un numero limitato di snack per talk, indicativamente 4-8
- produce documenti nel formato atteso da MongoDB

## Output — lo snack / snacks finale
Il risultato finale resta compatibile con la struttura già prevista dal Componente 6.

```
{
  talkId,
  talkSlug,
  speaker,
  talkTitle,
  topic,
  quote,
  summary,
  tags: [ ... ],
  score,
  startTime,
  endTime,
  talkUrl
}
```

Il campo `score` può essere usato internamente per ordinare gli snack o per decidere quali mostrare prima nel feed. Non è obbligatorio esporlo direttamente all'utente.

## Decisioni prese

**Approccio:** pipeline AI multi-step. Non si chiede a un singolo prompt di fare tutto, ma si separano segmentazione, generazione, tagging/ranking e fusione finale.

**Tool:** AWS Bedrock, invocato dalla Lambda AI. La pipeline può usare lo stesso modello con prompt diversi oppure modelli diversi a seconda del task.

**Orchestrazione:** dentro la Lambda AI. Non viene introdotto un nuovo servizio obbligatorio, così l'architettura resta semplice e compatibile con il progetto universitario.

**Output compatibile:** la pipeline produce sempre i `snacks` già previsti, quindi MongoDB, API e app Flutter non devono cambiare struttura di base.

## Perché è utile

Questa aggiunta rende più forte la parte AI dell'architettura perché:
- migliora la qualità degli snack generati
- rende più controllabile il comportamento dell'AI
- permette di cambiare un singolo passaggio senza riscrivere tutta la pipeline
- consente di confrontare modelli o prompt diversi
- valorizza il concetto centrale del progetto, cioè trasformare talk lunghi in contenuti brevi e personalizzati

## Possibili evoluzioni

In una versione successiva, il componente potrebbe essere esteso con:
- un controllo automatico di qualità sugli snack generati
- un modello diverso per lingua, se si supportano transcript multilingua
- un sistema di feedback utente per migliorare il ranking
- A/B test tra prompt o modelli diversi
- salvataggio degli score per personalizzare meglio il feed
- uso di Step Functions se la pipeline AI diventasse più lunga o complessa

## Note
Il Componente 6a non sostituisce il Componente 6. È una sua espansione logica: il Componente 6 descrive la Lambda che riceve i talk da SQS e scrive su MongoDB, mentre il Componente 6a descrive come avviene internamente la generazione AI degli snack.
