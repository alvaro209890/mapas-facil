# Planos comuns às duas fases

Estes cinco documentos valem para o **app desktop (Fase 1)** e para o **site (Fase 2)**. Se um
plano de fase divergir de um destes, **este ganha** — e a divergência tem de ser corrigida no
mesmo PR.

| # | Documento | Conteúdo |
|---|---|---|
| 00 | [Visão e as duas fases](00-visao-e-duas-fases.md) | problema real, proposta, escopo, riscos, decisões D1–D9 |
| 01 | [Padrão IMAP — perfil Harmonia](01-padrao-imap-harmonia.md) | **fonte da verdade visual**: geometria medida, cores, checks HARD/SOFT |
| 02 | [`MapSpec` — o contrato](02-mapspec-contrato.md) | o JSON que descreve um mapa, campo a campo |
| 03 | [WFS e serviços geo](03-wfs-e-servicos-geo.md) | endpoints, receitas de request, gotchas de SEMA/IBAMA/FUNAI/INCRA |
| 04 | [Dados, camadas e o CAR](04-dados-camadas-e-car.md) | pasta de trabalho, validação de shapefile, recibo do CAR, cache |
| 05 | [Segurança e segredos](05-seguranca-e-segredos.md) | cofre de chaves, modelo de ameaças, LGPD, incidente 2026-07-25 |

## Planos por fase

| Fase | Onde | Prioridade |
|---|---|---|
| **1 — App desktop Windows** | [`../Fase_1_Desktop/planos/`](../Fase_1_Desktop/planos/README.md) | **principal** — é onde o `.mxd` nasce |
| 2 — Site e backend | [`../Fase_2_Site/planos/`](../Fase_2_Site/planos/README.md) | depois da Fase 1 validada |

## Dados versionados

| Pasta | Conteúdo |
|---|---|
| [`../shared/`](../shared/README.md) | catálogo de camadas e serviços, schema do `MapSpec`, perfil visual, manifesto de templates |
| [`../Referencias_IMAP/`](../Referencias_IMAP/README.md) | 21 PDFs-modelo + 24 `.mxd` reais — gabarito de qualquer ajuste de layout |
| [`../ferramentas/`](../ferramentas/README.md) | utilitários do repositório (hoje: remoção/reinjeção de chaves nos `.mxd`) |

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
| M0 — Planos e contratos | **fechado** |
| Fase 1 — núcleo | **M1 bloco A fechado** · bloco B parcial (v0.3.2) — ver [checklist](../Fase_1_Desktop/planos/13-checklist-implementacao.md) |
| Fase 2 — desenvolvimento | não iniciado |
