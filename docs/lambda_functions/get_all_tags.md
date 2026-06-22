# Lambda Get All Tags

## Ruolo
Endpoint API per recuperare tutti i tag disponibili dagli snack salvati in MongoDB.

## Query MongoDB
Legge la collection `snacks` ed esegue `distinct('tags')`.

## Output
Response `200 application/json`:

```json
["art", "design", "technology"]
```

I tag vengono filtrati, normalizzati come stringhe non vuote e ordinati alfabeticamente.

## Uso app
Usato da onboarding e modifica interessi del profilo.
