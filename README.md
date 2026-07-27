# Mapas Fácil

Agente de engenharia florestal que conversa em linguagem natural, olha a pasta do projeto do
usuário e entrega os mapas da série IMAP — `.mxd` abrível no ArcMap, `.pdf` pronto para entrega
e `.xlsx` de quantitativos — com o padrão garantido por validação automática.

O modelo mental é o de um agente de programação (Cursor, Codex, Claude Code), trocando código por
cartografia: **você aponta uma pasta e conversa.**

> **Agente de IA: comece por [`AGENT_BRIEF.md`](AGENT_BRIEF.md)** — snapshot do que falta, estado
> real do código, ordem dos marcos, gap analysis e anti-padrões vinculantes.

## As duas fases

| Fase | O quê | Prioridade |
|---|---|---|
| **1 — App desktop Windows** | chat + pasta do PC → `.mxd` + `.pdf` + `.xlsx` | **principal** — é onde o `.mxd` nasce |
| 2 — Site de distribuição | landing + download do instalador (sem login, sem mapa) | D21 — planos reescritos; código `web/` ainda não |

Detalhes em [`planos/00-visao-e-duas-fases.md`](planos/00-visao-e-duas-fases.md).

```
Fase 1 (Windows)                    Fase 2 (distribuição)
┌─────────────────────────┐         ┌─────────────────────────┐
│ Electron + React        │         │ Next.js (landing)       │
│ sidecar Python          │         │ download do instalador  │
│ arcpy → .mxd → .pdf     │         │ mapasfacil.cursar.space │
│ conta local + pasta     │         │ sem login / sem mapa    │
└─────────────────────────┘         └─────────────────────────┘
```

## Estrutura do repositório

| Pasta | O que é |
|---|---|
| [`AGENT_BRIEF.md`](AGENT_BRIEF.md) | **entrada para agentes**: o que falta, estado real, gap analysis, anti-padrões |
| [`planos/`](planos/README.md) | planos comuns às duas fases (visão, `MapSpec`, Harmonia, segurança) |
| [`Fase_1_Desktop/`](Fase_1_Desktop/README.md) | app desktop Windows — **produto principal** (`app/` + `nucleo/`) |
| [`Fase_2_Site/`](Fase_2_Site/README.md) | site de distribuição — planos D21; código `web/` não iniciado |
| [`shared/`](shared/README.md) | catálogo de camadas, schema do `MapSpec`, templates operacionais |
| [`Referencias_IMAP/`](Referencias_IMAP/README.md) | acervos reais (PDFs-modelo + `.mxd`) — gabarito visual |
| [`ferramentas/`](ferramentas/README.md) | chaves nos `.mxd`, preparação B1/B2, smoke DeepSeek |

## Por que desktop primeiro

1. **O `.mxd` é o entregável que importa**, e ele só existe no Windows do usuário.
2. O [NexoGeo Ambiental](https://github.com/alvaro209890/NexoGeo-Ambiental) priorizou a web e
   deixou o `.mxd` para "depois" — nunca saiu.
3. A Fase 1 valida o produto com usuário real sem infraestrutura de site.

## Leitura recomendada

1. [`AGENT_BRIEF.md`](AGENT_BRIEF.md) — **primeiro** (snapshot + gap analysis)
2. [`planos/00-visao-e-duas-fases.md`](planos/00-visao-e-duas-fases.md)
3. [`Fase_1_Desktop/planos/12-roadmap.md`](Fase_1_Desktop/planos/12-roadmap.md)
4. [`Fase_1_Desktop/planos/13-checklist-implementacao.md`](Fase_1_Desktop/planos/13-checklist-implementacao.md)
5. [`planos/02-mapspec-contrato.md`](planos/02-mapspec-contrato.md)

## Estado atual (2026-07-26)

| Marco | Status |
|---|---|
| M0 — Planos e contratos | **fechado** |
| M1 — Núcleo + `MapSpec` + `fsguard` | **bloco A fechado** · bloco B **parcial** (precisa ArcMap para fechar) |
| M2 — Motor `.mxd` | **parcial** — próximo grande passo (Windows + ArcMap) |
| M3–M8 — shell, galeria, auth, chats, agente, motion | **fechados** (+ épico sem ArcMap: F1-07, 41/41 camadas, eventos, UI) |
| M9–M11 — Harmonia, instalador, piloto | **não iniciados** |
| Fase 2 | planos **reescritos** (D21 = distribuição); código `web/` não iniciado |

**Backlog desktop sem ArcMap: esgotado.** No Linux Mint deste projeto só sobra polish opcional;
o eixo que falta é **M2 → M9 → M10 → M11** em PC Windows.

**No Windows agora:** siga o guia passo a passo  
[`Fase_1_Desktop/GUIA_WINDOWS.md`](Fase_1_Desktop/GUIA_WINDOWS.md).

Eventos NDJSON emitidos: `job.progresso`, `chat.delta`, `chat.tool`, `job.artefato_parcial`,
`workspace.mudou`, `mapspec.atualizado`, `job.log`, `aviso` (vocabulário completo).

## Licença

A definir antes do primeiro release público.
