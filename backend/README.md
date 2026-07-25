# backend/

API e orquestração — FastAPI (Python 3.11), Postgres, hub WebSocket de agentes, loop IA↔tools.

**Status:** esqueleto. Implementação começa no milestone M1 ([planos/10-roadmap.md](../planos/10-roadmap.md)).

Plano detalhado: [planos/02-backend-api.md](../planos/02-backend-api.md).
Contratos: [planos/01-arquitetura.md](../planos/01-arquitetura.md).

## Quando existir código

```
backend/
  app/
    main.py
    api/v1/               # routers
    domain/
    db/
    llm/
    agentctl/             # hub WebSocket
    mapspec/
    services/
  tests/
  alembic/
  pyproject.toml
  Dockerfile
  .env.example
```

Deploy previsto: Render (1 réplica na v1 — registry WebSocket em memória).
