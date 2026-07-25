# Fase 1 — App desktop Windows

Aplicativo nativo Windows onde você conecta uma **pasta do PC** e conversa com um agente de
engenharia florestal. O modelo mental é o do Cursor / Codex / Claude Code, trocando código por
cartografia: o agente lê a pasta, entende o imóvel, consulta a SEMA e entrega os mapas da série
IMAP — `.mxd` abrível no ArcMap, `.pdf` pronto para entrega e `.xlsx` de quantitativos.

Esta é a **fase principal** do Mapas Fácil. O produto funciona sozinho, sem depender de servidor
nenhum.

## Stack

| Camada | Tecnologia | Papel |
|---|---|---|
| UI | Electron + React | chat, workspace da pasta, preview do mapa |
| Geo e `.mxd` | Python (sidecar) | núcleo geo, motor `.mxd`, renderizador nativo, planilhas |
| IA | DeepSeek V4 Pro (BYOK) | agente conversacional; chave no Windows Credential Manager |
| ArcMap | `arcpy` (quando disponível) | geração fiel do `.mxd`; fallback por patch de template |

## Estrutura desta pasta

| Pasta | O que é |
|---|---|
| [`planos/`](planos/README.md) | plano de desenvolvimento da Fase 1 (F1-00…F1-12) |
| [`nucleo/`](nucleo/) | núcleo Python sidecar — **M1 bloco A fechado**, bloco B parcial (v0.3.2) |
| [`app/`](app/) | shell Electron + React *(a implementar)* |

## Contratos e referências

Valem para as duas fases e vivem na raiz do repositório:

- [`planos/`](../planos/README.md) — visão geral, `MapSpec`, padrão Harmonia, segurança
- [`shared/`](../shared/README.md) — catálogo de camadas, schema, templates
- [`Referencias_IMAP/`](../Referencias_IMAP/README.md) — 21 PDFs-modelo + 24 `.mxd` reais

## Leitura recomendada

1. [Visão e as duas fases](../planos/00-visao-e-duas-fases.md) — contexto do produto inteiro
2. [F1-00 — Visão e escopo](planos/00-visao-e-escopo.md) — escopo e critérios da Fase 1
3. [Índice dos planos](planos/README.md) — ordem de leitura dos demais documentos
4. [Checklist de implementação](planos/13-checklist-implementacao.md) — kickoff do código

## Estado

| Marco | Status |
|---|---|
| Planos | F1-00…F1-13 escritos |
| Núcleo Python | **bloco A fechado** · bloco B parcial — v0.3.4, CI anel 1 verde |
| UI Electron | não iniciado |
