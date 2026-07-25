# backend/

API da Fase 2 — FastAPI + Postgres, rodando **neste PC** (Cuiabá-MT), exposto por Cloudflare
Tunnel dedicado (`mapasfacil-api.cursar.space`).

**Status:** esqueleto. Planos em [`../planos/README.md`](../planos/README.md).

> `02-backend-api.md` e `06-deploy-tunnel-neste-pc.md` ainda descrevem o modelo legado
> (Render + hub WS de agentes). Destino D7: sem hub de agente na nuvem; `.mxd` só via ponte
> com o desktop.

## Quando existir código

```
backend/
  app/
    main.py
    api/v1/
    domain/
    db/
    llm/
    mapspec/
    services/             # WFS local, jobs PDF
  tests/
  alembic/
  pyproject.toml
```

Deploy: systemd + cloudflared neste PC — ver plano F2-06 (após reescrita).
