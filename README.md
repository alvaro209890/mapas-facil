# Mapas Fácil

Agente de engenharia florestal que conversa em linguagem natural, inspeciona o projeto e entrega
**PDF nativo padrão IMAP**, PNG e planilhas XLSX. O fluxo web é **PDF-first**, sem ArcMap/MXD.
O export `.mxd` legado foi preservado: só entra mediante pedido explícito e `MF_MXD=1`.

## Fase 3 — agente PDF-first (2026-11-06)

- Chat público usa o serviço/orquestrador com histórico existente e registro modular V2; plano,
  passos, arquivos e preview são persistidos por projeto e acompanhados na interface.
- `LayoutSpec` versionado com caixas em mm e perfis medidos A4–A0; geração e medição reais.
- Vários imóveis no mesmo projeto, com PDFs individuais, atlas, XLSX combinado e fontes separadas.
- Aprovação destrutiva fora do modelo, com owner/CSRF, ação/alvo/hash/TTL e uso único.
- `python_exec` **não implementa um sandbox seguro** e permanece desligado, inclusive com flags.
- Pacote padrão: `Mapas/`, `SHP/`, `XLSX/`. Download MXD exige também `?mxd=1`.

Contratos: [agente](docs/agente-v2.md), [layout](docs/layout-pdf.md),
[multi-imóvel](docs/multi-imovel.md), [segurança](docs/seguranca-agente.md),
[migração PDF-first](docs/migracao-mxd-para-pdf.md).
Estado de verificação/implantação: [plano vivo](planos/06-agente-pdf-first.md).
Os marcos desktop e as decisões antigas abaixo são histórico; não substituem a política PDF-first.

O modelo mental é o de um agente de programação (Cursor, Codex, Claude Code), trocando código por
cartografia: **você aponta uma pasta e conversa.**

> **Agente de IA: comece por [`AGENT_BRIEF.md`](AGENT_BRIEF.md)** — snapshot do que falta, estado
> real do código, ordem dos marcos, gap analysis e anti-padrões vinculantes.

**Análise de área (2026-07-29):** de um shapefile só, o sistema descobre o imóvel (município e
CAR), busca as camadas na SEMA/FUNAI/IBAMA/MapBiomas e entrega a **série de 20 mapas** do padrão
IMAP em PDF, mais o compilado — cada página medida contra o modelo do acervo. Como funciona:
[`docs/analise-de-area-serie.md`](docs/analise-de-area-serie.md).

## As duas fases

| Fase | O quê | Prioridade |
|---|---|---|
| **1 — App desktop Windows** | chat + pasta do PC → `.mxd` + `.pdf` + `.xlsx` | **principal** — é onde o `.mxd` nasce |
| 2 — Site de distribuição | landing + download do instalador (sem login, sem mapa) | **no ar** — https://mapasfacil.cursar.space |

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
| [`Fase_2_Site/`](Fase_2_Site/README.md) | site de distribuição — https://mapasfacil.cursar.space |
| [`docs/`](docs/analise-de-area-serie.md) | rodadas e operação: série Análise de área, entrega ao cliente, site/download, handoff Windows |
| [`shared/`](shared/README.md) | catálogo de camadas, schema do `MapSpec`, templates operacionais, [anatomia medida dos modelos](shared/padrao-imap/README.md) |
| [`Referencias_IMAP/`](Referencias_IMAP/README.md) | acervos reais (PDFs-modelo + `.mxd`) — gabarito visual |
| [`ferramentas/`](ferramentas/README.md) | chaves nos `.mxd`, preparação B1/B2, medição dos modelos, publicação das análises |

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

## Estado atual (2026-08-10)

| Marco | Status |
|---|---|
| M0 — Planos e contratos | **fechado** |
| M1 — Núcleo + `MapSpec` + `fsguard` | **bloco A fechado** · bloco B **parcial** (precisa ArcMap para fechar) |
| M2 — Motor `.mxd` | **parcial** — 25/25 templates `pronto`; auditoria ArcPy 21/21 e smoke M9 com motor `arcpy` (6/6 HARD, MXD sem links quebrados) em 2026-08-10; smoke da série na Aruanã pendente (dado gitignored) |
| M3–M8 — shell, galeria, auth, chats, agente, motion | **fechados** (+ épico sem ArcMap: F1-07, 41/41 camadas, eventos, UI) |
| M9–M11 — Harmonia, instalador, piloto | **M9 parcial** — diff raster ~81–82% (par de imóveis diferentes); **M10 quase** — instalador 0.5.2 reproduzido (144 MB), falta Authenticode e PC limpo; **M11 não iniciado** |
| Fase 2 | planos **reescritos** (D21 = distribuição); site **no ar** — https://mapasfacil.cursar.space |

**Backlog desktop sem ArcMap: esgotado.** No Linux Mint deste projeto só sobra polish opcional;
o eixo que falta é **M2 → M9 → M10 → M11** em PC Windows.

**No Windows agora:** siga o guia passo a passo  
[`Fase_1_Desktop/GUIA_WINDOWS.md`](Fase_1_Desktop/GUIA_WINDOWS.md).

Eventos NDJSON emitidos: `job.progresso`, `chat.delta`, `chat.tool`, `job.artefato_parcial`,
`workspace.mudou`, `mapspec.atualizado`, `job.log`, `aviso` (vocabulário completo).

## Licença

A definir antes do primeiro release público.
