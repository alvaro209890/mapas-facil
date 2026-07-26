# Mapas Fácil

Agente de engenharia florestal que conversa em linguagem natural, olha a pasta do projeto do
usuário e entrega os mapas da série IMAP — `.mxd` abrível no ArcMap, `.pdf` pronto para entrega
e `.xlsx` de quantitativos — com o padrão garantido por validação automática.

O modelo mental é o de um agente de programação (Cursor, Codex, Claude Code), trocando código por
cartografia: **você aponta uma pasta e conversa.**

> Este repositório contém **planos, contratos, referências visuais** e o **núcleo Python**
> da Fase 1 (sidecar). A UI Electron ainda não foi iniciada.
>
> **Agente de IA: comece por [`AGENT_BRIEF.md`](AGENT_BRIEF.md)** — estado real do código, ordem
> dos marcos, gap analysis e anti-padrões vinculantes. Os planos são escritos para serem
> executados por agentes, não lidos por humanos.

## As duas fases

O produto tem duas metades, com prioridades **muito** diferentes:

| Fase | O quê | Prioridade |
|---|---|---|
| **1 — App desktop Windows** | chat + pasta do PC → `.mxd` + `.pdf` + `.xlsx` | **principal** — é onde o `.mxd` nasce |
| 2 — Site e backend | projetos persistentes, mapa por CAR, vitrine pública | depois da Fase 1 validada |

Detalhes, escopo, riscos e decisões D1–D9 em [`planos/00-visao-e-duas-fases.md`](planos/00-visao-e-duas-fases.md).

```
Fase 1 (Windows)                    Fase 2 (depois)
┌─────────────────────────┐         ┌─────────────────────────┐
│ Electron + React        │         │ Next.js (site)          │
│ sidecar Python          │  reuso  │ FastAPI (neste PC)      │
│ arcpy → .mxd → .pdf     │ ──────▶ │ tunnel Cloudflare       │
│ pasta local do usuário  │ MapSpec │ PDF/PNG (sem .mxd)      │
└─────────────────────────┘         └─────────────────────────┘
```

## Estrutura do repositório

| Pasta | O que é |
|---|---|
| [`AGENT_BRIEF.md`](AGENT_BRIEF.md) | **entrada para agentes**: estado real, ordem de marcos, gap analysis, anti-padrões |
| [`planos/`](planos/README.md) | planos comuns às duas fases (visão, `MapSpec`, Harmonia, segurança) |
| [`Fase_1_Desktop/`](Fase_1_Desktop/README.md) | app desktop Windows — **produto principal** |
| [`Fase_2_Site/`](Fase_2_Site/README.md) | site + backend neste PC via Cloudflare Tunnel |
| [`shared/`](shared/README.md) | catálogo de camadas, schema do `MapSpec`, templates operacionais |
| [`Referencias_IMAP/`](Referencias_IMAP/README.md) | 21 PDFs-modelo + 24 `.mxd` reais — gabarito visual |
| [`ferramentas/`](ferramentas/README.md) | chaves nos `.mxd`, preparação B1/B2 de templates, ZIP truncado |

## Por que desktop primeiro

1. **O `.mxd` é o entregável que importa**, e ele só existe no Windows do usuário.
2. O [NexoGeo Ambiental](https://github.com/alvaro209890/NexoGeo-Ambiental) já provou a metade
   web (chat → `MapSpec` → PDF IMAP) e **falhou exatamente no `.mxd`**, que ficou como "quando
   ArcMap estiver disponível" e nunca saiu do papel.
3. A Fase 1 valida o produto com usuário real sem nenhuma infraestrutura.

## Leitura recomendada

1. [`AGENT_BRIEF.md`](AGENT_BRIEF.md) — **primeiro de tudo** se você é um agente implementador
2. [`planos/00-visao-e-duas-fases.md`](planos/00-visao-e-duas-fases.md) — visão, escopo, decisões D1–D20
3. [`Fase_1_Desktop/planos/12-roadmap.md`](Fase_1_Desktop/planos/12-roadmap.md) — marcos M0–M11 e critérios de saída
4. [`Fase_1_Desktop/planos/13-checklist-implementacao.md`](Fase_1_Desktop/planos/13-checklist-implementacao.md) — blocos A–I, o que fazer agora
5. [`planos/02-mapspec-contrato.md`](planos/02-mapspec-contrato.md) — o contrato de dados central

## Estado atual

| Marco | Status |
|---|---|
| M0 — Planos e contratos | **fechado**; reescritos para agentes em 2026-07-25 |
| M1 — Núcleo + `MapSpec` + `fsguard` | **bloco A fechado** · **bloco B parcial** (v0.3.6) — ver checklist |
| M2 — Motor `.mxd` | parcial (T2 copia template preparado; T1 esqueleto; B1 não testado) |
| M3–M8 — shell, galeria, auth, conversas, agente, motion | **não iniciados** — `Fase_1_Desktop/app/` está vazia |
| M9–M11 — Harmonia, instalador, piloto | não iniciados |
| Fase 2 — identidade (bloqueia o M5) | não iniciada |
| Fase 2 — restante | não iniciado; começa depois do M11 |

Nenhum evento NDJSON é emitido hoje: `protocolo.envelope_evt` existe sem chamador. Isso bloqueia
a barra de progresso e as animações de construção do mapa — é o item A9 do checklist.

## Licença

A definir antes do primeiro release público.
