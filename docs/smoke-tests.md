# Smoke Tests

## Health

```bash
curl -sS http://localhost:8080/v1/health
```

## Ingest

```bash
curl -sS -X POST http://localhost:8080/v1/ingest \
  -H "Authorization: Bearer test-api-key" \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: 22222222-2222-4222-8222-222222222222" \
  -H "X-Tenant-ID: ph-balta-doamnei" \
  -H "Idempotency-Key: 33333333-3333-4333-8333-333333333333" \
  -d '{
    "namespace_id": "legea_31_1990",
    "source_id": "s_47381",
    "source_type": "url",
    "url": "https://legislatie.just.ro/Public/DetaliiDocument/47381",
    "mime_type_hint": "text/plain",
    "metadata": {
      "source_title": "Legea 31/1990 privind societățile comerciale",
      "text": "Articolul 15. Aporturile în numerar sunt obligatorii la constituirea oricărei forme de societate."
      } 
  }'
```


## Query

```bash
curl -sS -X POST http://localhost:8080/v1/query \
  -H "Authorization: Bearer test-api-key" \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: 11111111-1111-4111-8111-111111111111" \
  -H "X-Tenant-ID: ph-balta-doamnei" \
  -d '{
    "question": "Ce spune articolul 15 din Legea 31/1990?",
    "language": "ro",
    "namespaces": ["legea_31_1990"],
    "top_k": 5,
    "hint_article_number": "15",
    "rerank": true,
    "include_answer": true
  }'
```
