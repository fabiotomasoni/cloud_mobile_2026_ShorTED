# Componente 5.2 — SQS Queue

## Ruolo nel sistema
Coda di distribuzione del lavoro. Riceve i messaggi dal Dispatcher (5.1) e li distribuisce alla Lambda AI (Componente 6), gestendo parallelismo, retry automatici e isolamento degli errori per singolo talk.

## Posizione nel pipeline
- **Input da:** Componente 5.1 (Lambda Dispatcher) — un messaggio per talk
- **Output verso:** Componente 6 (Lambda AI Processing) — trigger automatico per ogni messaggio

## Cosa fa
Ogni messaggio in coda rappresenta un talk da processare. La Lambda AI viene triggerata automaticamente da SQS per ogni messaggio, potenzialmente in parallelo su più talk contemporaneamente. Se una Lambda AI fallisce su un talk, SQS rimette il messaggio in coda e riprova automaticamente — senza impatto sui talk già processati con successo.

## Decisioni prese
**Tool:** AWS SQS (Simple Queue Service).

**Perché SQS e non Step Functions:** il workflow di processing per ogni talk è lineare (un solo passo), senza condizioni o dipendenze tra talk. SQS è il pattern AWS standard per distribuire lavoro batch su Lambda in modo scalabile e robusto. Step Functions sarebbe sovradimensionato per questo caso d'uso.
