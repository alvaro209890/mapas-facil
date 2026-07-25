# Mapas Fácil

Agente de engenharia florestal que conversa em linguagem natural, olha a pasta do projeto do
usuário e entrega os mapas da série IMAP — `.mxd` abrível no ArcMap, `.pdf` pronto para entrega
e `.xlsx` de quantitativos — com o padrão garantido por validação automática.

O modelo mental é o de um agente de programação (Cursor, Codex, Claude Code), trocando código por
cartografia: **você aponta uma pasta e conversa.**

> Este repositório contém **planos, contratos, referências visuais** e o **núcleo Python**
> da Fase 1 (sidecar). A UI Electron ainda não foi iniciada. Comece por
> [`planos/`](planos/README.md) e o [checklist de implementação](Fase_1_Desktop/planos/13-checklist-implementacao.md).

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
| [`planos/`](planos/README.md) | planos comuns às duas fases (visão, `MapSpec`, Harmonia, segurança) |
| [`Fase_1_Desktop/`](Fase_1_Desktop/README.md) | app desktop Windows — **produto principal** |
| [`Fase_2_Site/`](Fase_2_Site/README.md) | site + backend neste PC via Cloudflare Tunnel |
| [`shared/`](shared/README.md) | catálogo de camadas, schema do `MapSpec`, perfil visual, templates |
| [`Referencias_IMAP/`](Referencias_IMAP/README.md) | 21 PDFs-modelo + 24 `.mxd` reais — gabarito visual |
| [`ferramentas/`](ferramentas/README.md) | utilitários do repositório (remoção/reinjeção de chaves nos `.mxd`) |

## Por que desktop primeiro

1. **O `.mxd` é o entregável que importa**, e ele só existe no Windows do usuário.
2. O [NexoGeo Ambiental](https://github.com/alvaro209890/NexoGeo-Ambiental) já provou a metade
   web (chat → `MapSpec` → PDF IMAP) e **falhou exatamente no `.mxd`**, que ficou como "quando
   ArcMap estiver disponível" e nunca saiu do papel.
3. A Fase 1 valida o produto com usuário real sem nenhuma infraestrutura.

## Leitura recomendada

1. [`planos/00-visao-e-duas-fases.md`](planos/00-visao-e-duas-fases.md) — visão, escopo, decisões
2. [`Fase_1_Desktop/planos/13-checklist-implementacao.md`](Fase_1_Desktop/planos/13-checklist-implementacao.md) — **comece a implementar por aqui**
3. [`Fase_1_Desktop/planos/README.md`](Fase_1_Desktop/planos/README.md) — índice da fase principal
4. [`planos/02-mapspec-contrato.md`](planos/02-mapspec-contrato.md) — o contrato de dados central

## Estado atual

| Marco | Status |
|---|---|
| M0 — Planos e contratos | **fechado** |
| M1 — Núcleo + MapSpec + fsguard | **A fechado** · **B parcial** (v0.3.1) — ver checklist |
| Fase 2 — desenvolvimento | não iniciado |
| Fase 2 — desenvolvimento | não iniciado |

## Licença

A definir antes do primeiro release público.
