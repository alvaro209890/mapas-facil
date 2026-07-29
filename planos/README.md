# Planos comuns às duas fases

> **Agente de IA?** Comece por [`../AGENT_BRIEF.md`](../AGENT_BRIEF.md): estado real do código,
> ordem dos marcos, gap analysis e anti-padrões vinculantes.

Estes seis documentos valem para o **app desktop (Fase 1)** e para o **site (Fase 2)**. Se um
plano de fase divergir de um destes, **este ganha** — e a divergência tem de ser corrigida no
mesmo commit.

| # | Documento | Conteúdo |
|---|---|---|
| 00 | [Visão e as duas fases](00-visao-e-duas-fases.md) | problema real, proposta, escopo, riscos, decisões **D1–D21** |
| 01 | [Padrão IMAP — perfil Harmonia](01-padrao-imap-harmonia.md) | **fonte da verdade visual**: geometria medida, cores, checks HARD/SOFT |
| 02 | [`MapSpec` — o contrato](02-mapspec-contrato.md) | o JSON que descreve um mapa, campo a campo |
| 03 | [WFS e serviços geo](03-wfs-e-servicos-geo.md) | endpoints, receitas de request, gotchas de SEMA/IBAMA/FUNAI/INCRA |
| 04 | [Dados, camadas e o CAR](04-dados-camadas-e-car.md) | pasta de trabalho, validação de shapefile, recibo do CAR, cache |
| 05 | [Segurança e segredos](05-seguranca-e-segredos.md) | cofre de chaves, modelo de ameaças, LGPD, incidente 2026-07-25 |

## Metas abertas

| Meta | Documento | Estado |
|---|---|---|
| Análise de área — série completa de mapas com a ATP Aruanã | [`GOAL_analise_de_area.md`](GOAL_analise_de_area.md) | **série em PDF entregue** (2026-07-29): 20/20 mapas gerados na Aruanã, 19/20 aprovados na anatomia, publicados em https://analises.cursar.space. Falta o card na galeria, o progresso no front, a visão Groq e a Fase W (`.mxd` no Windows, §11 — sem intervenção humana). Rodada: [`../docs/analise-de-area-serie.md`](../docs/analise-de-area-serie.md) · confira o documento com `python3 ferramentas/validar_goal_analise.py` |

## Planos por fase

| Fase | Onde | Prioridade |
|---|---|---|
| **1 — App desktop Windows** | [`../Fase_1_Desktop/planos/`](../Fase_1_Desktop/planos/README.md) | **principal** — é onde o `.mxd` nasce |
| 2 — Site de distribuição | [`../Fase_2_Site/planos/`](../Fase_2_Site/planos/README.md) | landing + download (D21); sem login/mapa no site |

## Dados versionados

| Pasta | Conteúdo |
|---|---|
| [`../shared/`](../shared/README.md) | catálogo de camadas e serviços, schema do `MapSpec`, manifesto de templates |
| [`../Referencias_IMAP/`](../Referencias_IMAP/README.md) | 21 PDFs-modelo + 24 `.mxd` reais — gabarito de qualquer ajuste de layout |
| [`../ferramentas/`](../ferramentas/README.md) | chaves nos `.mxd`, preparação B1/B2 de templates, recuperação de ZIP truncado |

## Regra de precedência

```
01-padrao-imap-harmonia.md   ← vence em tudo que é visual
02-mapspec-contrato.md       ← vence em tudo que é formato de dado
        ↓
planos das fases             ← implementam; nunca redefinem
```

Mudar um campo do `MapSpec`, um endpoint ou uma cor do padrão só acontece nos documentos comuns.
O PR que muda tem de atualizar os planos de fase afetados junto.

## Estado

| Marco | Status |
|---|---|
| M0 — Planos e contratos | **fechado**; reescritos para agentes em 2026-07-25 (D10–D20) |
| Fase 1 — núcleo | **M1 bloco A fechado** · bloco B parcial (v0.4.0) — ver [checklist](../Fase_1_Desktop/planos/13-checklist-implementacao.md) |
| Fase 1 — app Electron, galeria, auth local, conversas, agente, motion | M3–M4–M6–M8 fechados/parciais; **M5 conta local** ainda não iniciado |
| Fase 2 — site distribuição ([F2-00](../Fase_2_Site/planos/00-visao-e-escopo.md)) | planos **reescritos** (D21); código `web/` não iniciado |
| Fase 2 — conta nuvem ([F2-05](../Fase_2_Site/planos/05-auth-e-memoria.md)) | **adiada**; **não** é a v1 do site |
