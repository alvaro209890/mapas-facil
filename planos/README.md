# Planos de desenvolvimento — Mapas Fácil

Fonte da verdade do projeto. Nada de código de produção ainda: estes documentos definem o que
vai ser construído, em que ordem e com quais contratos.

## Ordem de leitura

| # | Documento | Conteúdo |
|---|---|---|
| 00 | [Visão e escopo](00-visao-e-escopo.md) | Problema, proposta, dentro/fora da v1, critérios de sucesso |
| 01 | [Arquitetura](01-arquitetura.md) | **Contratos**: endpoints, WebSocket, jobs, MapSpec, modelo de dados |
| 02 | [Backend](02-backend-api.md) | FastAPI, fila, hub de agentes, LLM, SSE |
| 03 | [Frontend](03-frontend-chat.md) | Next.js, chat estilo Cursor, preview, pareamento |
| 04 | [Agente local](04-agente-local.md) | Windows, dois Pythons, allowlist, doctor, instalador |
| 05 | [Motor MXD/PDF](05-motor-mxd-pdf.md) | Templates ArcMap, arcpy, validação de saída |
| 06 | [Padrão IMAP](06-padrao-imap.md) | Anatomia da página, estilos, checks HARD/SOFT |
| 07 | [IA e tools](07-ia-e-tools.md) | Tool calling, system prompt, versionamento |
| 08 | [Dados e camadas](08-dados-e-camadas.md) | Shapefiles locais, WFS SEMA/IBGE, cache |
| 09 | [Segurança](09-seguranca-e-privacidade.md) | Pareamento, tokens, LGPD, ameaças |
| 10 | [Roadmap](10-roadmap.md) | Milestones M0–M7 com critérios de aceite |
| 11 | [Testes e QA](11-testes-e-qa.md) | Pirâmide, runner Windows, evals de IA |
| 12 | [Deploy](12-deploy-e-distribuicao.md) | Vercel, Render, instalador, CI/CD |
| 13 | [WFS e serviços geo](13-wfs-e-servicos-geo.md) | Receitas GeoForest + inventário live 135 layers SEMA + mosaicos + SIMCAR/SCCON |

Catálogo machine-readable: [`../shared/catalog/`](../shared/catalog/) —
`camadas.json`, `servicos_geo.json`, `sema_layers_live.json`, `mosaicos_sema.json`,
`simcar_template_map.json`.

## Regra de precedência

Se dois documentos divergirem, **[01-arquitetura.md](01-arquitetura.md) ganha**. Endpoints,
tipos de mensagem WebSocket, campos do `MapSpec` e tabelas do banco só mudam nele — e a mudança
deve atualizar os demais planos no mesmo PR.

## Referências visuais

Os PDFs-modelo e `.mxd` reais do padrão IMAP estão em
[`../Referencias_IMAP/`](../Referencias_IMAP/README.md). Use-os como gabarito em qualquer
ajuste de layout.
