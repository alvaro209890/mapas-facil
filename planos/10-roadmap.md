# 10 — Roadmap

Milestones da v1, em ordem. Cada um tem critério de aceite binário: ou passa, ou não fecha.
Nada de "quase pronto".

## Visão geral

```
M0 Plano          ──▶  (este repositório, agora)
M1 Backend + chat ──▶  conversas e MapSpec sem agente
M2 Agente + MXD   ──▶  .mxd real no PC (smoke com ArcMap)
M3 IA + tools     ──▶  chat gera MapSpec via tools
M4 Conformidade   ──▶  100% checks HARD IMAP
M5 Frontend polido──▶  UX Cursor-like completa
M6 Segurança      ──▶  pareamento, allowlist, auditoria
M7 Release        ──▶  instalador + staging + primeiros piloto
```

Dependências: M2 pode começar em paralelo com M1 (contratos já estão no 01). M3 depende de
M1 (loop de tools no backend). M4 depende de M2+M3. M5 depende de M1+M3. M6 atravessa tudo,
mas o checklist formal fecha depois de M2. M7 fecha a v1.

## M0 — Plano e contratos

**Status:** em andamento (este repo).

| Entrega | Critério de aceite |
|---|---|
| Planos 00–13 escritos | cada documento em `planos/` com pendências listadas |
| Contratos no 01 | endpoints, WS, MapSpec, tabelas fechados |
| Catálogo geo | `shared/catalog/camadas.json` + `servicos_geo.json` (32 camadas) |
| Receitas WFS | plano [13](13-wfs-e-servicos-geo.md) com BBOX, authkey, gotchas GeoForest |
| Repo público no GitHub | `alvaro209890/mapas-facil` com `main` |
| Esqueleto de pastas | `web/`, `backend/`, `agent/`, `shared/` com README |
| Referências IMAP | PDFs e MXDs modelo versionados em `Referencias_IMAP/` |

## M1 — Backend + conversas (sem agente)

Objetivo: site e API conversando; MapSpec criado e versionado à mão (sem IA ainda).

| Entrega | Critério de aceite |
|---|---|
| Auth magic link | login por e-mail, JWT + refresh |
| CRUD de conversas | criar, listar, renomear, arquivar, soft delete |
| Mensagens + SSE | turno com `text.delta` streaming (texto stub) |
| `map_specs` append-only | edição cria nova versão com `parent_id` |
| Validação MapSpec | rejeita cada invariante do [01](01-arquitetura.md) |
| Catálogo servido | `GET /v1/catalog/*` lê de `shared/` |
| Postgres + Alembic | migrações aplicam do zero; health checks verdes |
| Deploy staging | backend no Render + web na Vercel (preview) |

Fora deste milestone: agente, arcpy, tool calling real.

## M2 — Agente local + `.mxd` real

Objetivo: um `MapSpec` conhecido, enviado pelo backend, vira `.mxd` + `.pdf` no PC com ArcMap.

| Entrega | Critério de aceite |
|---|---|
| Pareamento | código 8 chars → `agent_token`; agent aparece online |
| WebSocket | `hello`, heartbeat, `job.dispatch` → `job.done` |
| Doctor | detecta ArcMap 10.x / Pro, Python, licença, templates |
| `fsguard` | rejeita caminho fora da allowlist (testes unitários) |
| Cliente WFS (receitas [13](13-wfs-e-servicos-geo.md)) | BBOX+clip local; fallback paginação; authkey no keyring |
| Catálogo `shared/catalog/` | agente resolve `embargos_siga`, `car_atp`, etc. a partir do JSON |
| Fixture WFS gravada | smoke com SEMA offline usando resposta cacheada |
| Script ArcPy | abre template, reponta fontes, salva `.mxd`, exporta PDF |
| Check de fontes quebradas | `ListBrokenDataSources` vazio no `.mxd` entregue |
| Smoke manual | Dinâmica 2026 a partir de fixture, em máquina com ArcMap |
| Instalador beta | `.exe` instala, autostart, ícone na bandeja |

Sem ArcMap, o job falha com `license_unavailable` / `arcpy_failed` — o fallback PDF nativo
entra só em M4 como preview, não como entregável.

## M3 — IA e tools

Objetivo: o usuário digita em português e o MapSpec sai do loop de tools.

| Entrega | Critério de aceite |
|---|---|
| Loop IA↔tools | até `finalizar`, máx. 12 passos / 300 s |
| Tools do [07](07-ia-e-tools.md) | catálogo completo implementado |
| `listar_camadas_locais` | RPC real no agente, timeout 5 s |
| Streaming de tools | UI mostra `tool.call` / `tool.result` |
| Validação pós-tools | MapSpec inválido não cria job |
| Fallback determinístico | sem chave de IA, parser de regras responde |
| Evals iniciais | ≥10 prompts-fixture com MapSpec esperado |

## M4 — Conformidade IMAP

Objetivo: mapa gerado passa 100% dos checks HARD de [06](06-padrao-imap.md).

| Entrega | Critério de aceite |
|---|---|
| Checks HARD | todos implementados; falha bloqueia `succeeded` |
| Checks SOFT | avisam na UI, não bloqueiam |
| Estilos oficiais | ATP/AVN/AC/AUAS batem hex/hachura do padrão |
| Grade DMS + minimapa + metadados | presentes no PDF e no `.mxd` |
| Regressão visual | PNG gerado vs baseline com tolerância documentada |
| Série Dinâmica | pelo menos Dinâmica 2026 e Embargos IBAMA verdes |

## M5 — Frontend polido

Objetivo: UX no nível Cursor/Claude — conversas, versões, preview, doctor.

| Entrega | Critério de aceite |
|---|---|
| Sidebar de conversas | busca, fixar, arquivar, agrupamento por data |
| Painel direito | abas Mapa / MapSpec / Camadas / Log |
| Progresso do job | 9 etapas nomeadas, cancelar, retomada |
| Histórico de versões | miniatura + "voltar para esta versão" |
| Seletor de agente | online/offline, doctor visual, CTA de download |
| Atalhos | nova conversa, enviar, cancelar, alternar painel |
| E2E Playwright | fluxo completo com backend e agente falsos |

## M6 — Segurança e privacidade

Objetivo: checklist pré-release de [09](09-seguranca-e-privacidade.md) fechado.

| Entrega | Critério de aceite |
|---|---|
| Token no Credential Manager | nunca em texto plano no disco |
| Allowlist só local | backend não altera pastas autorizadas |
| MapSpec-only | nenhum caminho de executável aceito pelo agente |
| Segredos | gitleaks no pre-commit e CI; `.env.example` sem valores |
| Auditoria | pareamento, revogação, job, allowlist, login registrados |
| LGPD | política de retenção + exclusão de conta |
| Rate limit | por IP e por conta nos endpoints públicos |

## M7 — Release v1

Objetivo: usuários piloto geram mapa real de ponta a ponta.

| Entrega | Critério de aceite |
|---|---|
| Instalador estável assinado | download com SHA-256; SmartScreen tratado |
| Staging → prod | promoção documentada; rollback testado |
| Critérios de sucesso do [00](00-visao-e-escopo.md) | <3 min, 100% HARD, 15 min first map, zero shapefile na nuvem |
| Runbook | incidentes do [12](12-deploy-e-distribuicao.md) ensaiados |
| 3 usuários piloto | feedback coletado; bugs bloqueantes zerados |

## Fora do roadmap da v1

- Billing / planos pagos
- Multiusuário no mesmo agente
- QGIS (`.qgz`)
- Linux/macOS no agente
- Microserviços / multi-réplica com Redis (entra quando a escala exigir)

## Ordem sugerida de PRs no código

1. `shared/` — schemas + catálogo + manifesto de templates (contratos versionados)
2. `backend/` — auth + conversas + MapSpec (M1)
3. `web/` — shell do chat + SSE (M1)
4. `agent/` — doctor + WS + fsguard (M2)
5. `agent/scripts/` — ArcPy export + templates reais (M2)
6. `backend/` — loop IA + tools (M3)
7. Conformidade + evals (M4)
8. Polimento UI (M5)
9. Segurança formal + instalador (M6–M7)

## Pendências e decisões abertas

- Domínio definitivo (`mapasfacil.app` ou outro) — registrar antes do M1 staging.
- Certificado de assinatura de código (EV vs standard) — custo vs SmartScreen no M7.
- Quantos usuários piloto e em qual consultoria — definir no início do M7.
- ArcGIS Pro como caminho oficial de `.mxd` (hoje é secundário; ver [05](05-motor-mxd-pdf.md)).
