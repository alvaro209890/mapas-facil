# backend/

API da Fase 2 — previsto: FastAPI + Postgres neste PC (Cuiabá-MT), Cloudflare Tunnel
(`mapasfacil-api.cursar.space`).

**Status:** pasta só com este README. Nenhum `pyproject.toml` nem código de aplicação.
Planos em [`../planos/README.md`](../planos/README.md).

> `02-backend-api.md` e `06-deploy-tunnel-neste-pc.md` ainda descrevem o modelo legado
> (Render + hub WS de agentes). Destino D7: sem hub de agente na nuvem; `.mxd` só via ponte
> com o desktop.

## Quando existir código (ainda não)

```
backend/
  app/
  tests/
  alembic/
  pyproject.toml
```

Deploy: systemd + cloudflared neste PC — ver plano F2-06 (após reescrita).
