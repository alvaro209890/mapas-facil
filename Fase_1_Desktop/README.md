# Fase 1 — App desktop Windows

Aplicativo nativo Windows onde você conecta uma **pasta do PC** e conversa com um agente de
engenharia florestal. O modelo mental é o do Cursor / Codex / Claude Code, trocando código por
cartografia: o agente lê a pasta, entende o imóvel, consulta a SEMA e entrega os mapas da série
IMAP — `.mxd` abrível no ArcMap, `.pdf` pronto para entrega e `.xlsx` de quantitativos.

Esta é a **fase principal** do Mapas Fácil. O produto funciona sozinho, sem depender de servidor
nenhum. Login = conta **local** (e-mail + senha em SQLite) — [F1-14](planos/14-auth-e-conta.md).

> **Agentes:** [`../AGENT_BRIEF.md`](../AGENT_BRIEF.md) tem o snapshot do que falta.

## Stack

| Camada | Tecnologia | Papel |
|---|---|---|
| UI | Electron + React | chat, workspace, galeria, preview, menus/tray |
| Geo e `.mxd` | Python (sidecar NDJSON) | núcleo geo, motor `.mxd`, PDF nativo, planilhas, agente |
| IA | DeepSeek V4 Pro/Flash (BYOK) | chat + tools; **só texto na API** (sem visão multimodal) |
| ArcMap | `arcpy` (quando disponível) | geração fiel do `.mxd`; fallback por patch de template |

## Estrutura desta pasta

| Pasta | O que é |
|---|---|
| [`planos/`](planos/README.md) | F1-00…F1-17 |
| [`nucleo/`](nucleo/) | sidecar Python — M1 + agente + camadas + visão determinística + packaging/ |
| [`app/`](app/) | Electron + React — M3–M8 + polish; electron-builder (M10) |
| [`EMPACOTAMENTO.md`](EMPACOTAMENTO.md) | gerar `.exe`, tag `desktop-v*`, manifesto do site |
| [`GUIA_WINDOWS.md`](GUIA_WINDOWS.md) | M2→M9 no PC com ArcMap |

## Contratos e referências

- [`planos/`](../planos/README.md) — visão, `MapSpec`, Harmonia, segurança
- [`shared/`](../shared/README.md) — catálogo, schema, templates
- [`Referencias_IMAP/`](../Referencias_IMAP/README.md) — PDFs-modelo + `.mxd` reais

## Leitura recomendada

1. [`../AGENT_BRIEF.md`](../AGENT_BRIEF.md) — o que falta e gap analysis
2. [Visão e as duas fases](../planos/00-visao-e-duas-fases.md)
3. [F1-00 — Visão e escopo](planos/00-visao-e-escopo.md)
4. [Roadmap](planos/12-roadmap.md) · [Checklist](planos/13-checklist-implementacao.md)

## Estado (2026-07-27)

| Marco | Status |
|---|---|
| Planos F1-00…F1-17 | escritos |
| M1 — núcleo | A fechado · B parcial |
| **M3–M8** | **fechados** (shell, galeria, conta local, chats, agente 27/27 tools, motion) |
| Épico sem ArcMap | **esgotado** (F1-07, 41/41 camadas, 8 eventos, menus/tray, offline, Esc≠job, R14) |
| **M10** instalador | **infra feita** — [`EMPACOTAMENTO.md`](EMPACOTAMENTO.md); Authenticode/smoke Windows pendentes |
| **M2** motor `.mxd` | **parcial** — **próximo no ArcMap** |
| **M9** Harmonia | não iniciado (exige M2) |
| **M11** piloto | não iniciado |

### O que falta na Fase 1

1. **M2** — fechar motor `.mxd` (B1–B8 de verdade no ArcMap)
2. **M9** — conformidade Harmonia (14 HARD, diff &lt; 0,3%)
3. **M10** — validar instalador no Windows limpo + Authenticode
4. **M11** — piloto instala, loga e gera o 1º mapa

**Publicar `.exe`:** [`EMPACOTAMENTO.md`](EMPACOTAMENTO.md) (tag `desktop-v*`).  
**Guia ArcMap:** [`GUIA_WINDOWS.md`](GUIA_WINDOWS.md). Snapshot:
[`../AGENT_BRIEF.md`](../AGENT_BRIEF.md).
