# Planos da Fase 1 — App desktop Windows

Estes documentos descrevem o **produto principal** do Mapas Fácil: o aplicativo nativo Windows onde
o `.mxd` nasce. Se um plano da Fase 1 divergir de um [plano comum](../../planos/README.md), o comum
ganha — e a divergência tem de ser corrigida no mesmo PR.

## Índice

| # | Documento | Conteúdo |
|---|---|---|
| F1-00 | [Visão e escopo](00-visao-e-escopo.md) | o que é o app, por que desktop primeiro, critérios de aceite |
| F1-01 | [Arquitetura](01-arquitetura.md) | Electron + React + sidecar Python; fronteiras e IPC |
| F1-02 | [UI, chat e workspace](02-ui-chat-e-workspace.md) | pasta conectada, chat estilo Cursor, preview do mapa |
| F1-03 | [Núcleo Python](03-nucleo-python.md) | geo, CAR, WFS, cache, `MapSpec` → artefatos |
| F1-04 | [Motor `.mxd`](04-motor-mxd.md) | ArcPy + patch de template; o coração do produto |
| F1-05 | [Renderizador nativo](05-motor-pdf-nativo.md) | PDF/PNG sem ArcMap; preview e fallback |
| F1-06 | [Agente de eng. florestal](06-agente-eng-florestal.md) | tools, prompt, guard rails, modo determinístico |
| F1-07 | [Print → mapa](07-visao-print-e-zip.md) | "faz igual a esse print" e `.zip` de referência |
| F1-08 | [Planilhas e relatórios](08-planilhas-e-relatorios.md) | `.xlsx` de quantitativos no padrão Harmonia |
| F1-09 | [Validação de conformidade](09-validacao-conformidade.md) | checks HARD/SOFT na prática |
| F1-10 | [Testes e QA](10-testes-e-qa.md) | como testar sem ArcGIS no CI |
| F1-11 | [Empacotamento e instalador](11-empacotamento-instalador.md) | virar `.exe` assinado |
| F1-12 | [Roadmap](12-roadmap.md) | marcos M0–M11 com critério de saída |
| F1-13 | [Checklist de implementação](13-checklist-implementacao.md) | blocos A–I — o que fazer agora |
| F1-14 | [Conta local](14-auth-e-conta.md) | e-mail + senha em SQLite, gate `AUTH-030` (sem Google) |
| F1-15 | [Galeria de modelos](15-galeria-de-modelos.md) | catálogo, `galeria.*`, montagem determinística de `MapSpec` |
| F1-16 | [Design system dark e animações](16-design-system-dark.md) | tokens, tipografia, motion amarrado a evento real |
| F1-17 | [Persistência de conversas](17-persistencia-de-conversas.md) | `chats.sqlite`, sidebar, busca, ramificação |
| — | [**Guia Windows M2→M11**](../GUIA_WINDOWS.md) | **passo a passo no PC com ArcMap** — comece aqui no Windows |

## Ordem de leitura

**Agentes começam por [`../../AGENT_BRIEF.md`](../../AGENT_BRIEF.md)** — estado real do código,
ordem dos marcos, gap analysis e anti-padrões vinculantes. Depois, a ordem de
[F1-00](00-visao-e-escopo.md#ordem-de-leitura-dos-planos):

| # | Documento | Por quê |
|---|---|---|
| 01 | [Arquitetura](01-arquitetura.md) | contratos internos; leia antes de tudo |
| 02 | [UI e workspace](02-ui-chat-e-workspace.md) | os painéis e os estados |
| 16 | [Design system dark](16-design-system-dark.md) | tokens, tipografia, animações |
| 15 | [Galeria de modelos](15-galeria-de-modelos.md) | a porta determinística |
| 14 | [Conta e autenticação](14-auth-e-conta.md) | login, tokens, gate |
| 17 | [Persistência de conversas](17-persistencia-de-conversas.md) | histórico local |
| 06 | [Agente](06-agente-eng-florestal.md) | tools, prompt, orçamento de contexto |
| 04 | [Motor `.mxd`](04-motor-mxd.md) | o coração do produto e a parte mais difícil |
| 03 | [Núcleo Python](03-nucleo-python.md) | onde a geo acontece |
| 05 | [Renderizador nativo](05-motor-pdf-nativo.md) | preview e fallback |
| 07 | [Print → mapa](07-visao-print-e-zip.md) | "faz igual a esse aqui" |
| 08 | [Planilhas](08-planilhas-e-relatorios.md) | `.xlsx` de quantitativos |
| 09 | [Validação](09-validacao-conformidade.md) | os checks HARD/SOFT na prática |
| 10 | [Testes](10-testes-e-qa.md) | como se testa isso sem ArcGIS no CI |
| 11 | [Empacotamento](11-empacotamento-instalador.md) | virar `.exe` |
| 12 | [Roadmap](12-roadmap.md) | marcos e critérios de saída |
| 13 | [Checklist de implementação](13-checklist-implementacao.md) | kickoff do código |

Comece por [F1-00](00-visao-e-escopo.md) se ainda não leu a visão geral da fase.

## Planos comuns

Contratos que valem para as duas fases e vivem na raiz: [`planos/`](../../planos/README.md).

| # | Documento | O que traz para a Fase 1 |
|---|---|---|
| 01 | [Padrão IMAP — Harmonia](../../planos/01-padrao-imap-harmonia.md) | geometria, cores, checks HARD/SOFT |
| 02 | [`MapSpec` — contrato](../../planos/02-mapspec-contrato.md) | o JSON que descreve um mapa |
| 03 | [WFS e serviços geo](../../planos/03-wfs-e-servicos-geo.md) | endpoints SEMA, IBAMA, FUNAI, INCRA |
| 04 | [Dados, camadas e CAR](../../planos/04-dados-camadas-e-car.md) | pasta de trabalho, recibo, cache |
| 05 | [Segurança e segredos](../../planos/05-seguranca-e-segredos.md) | cofre de chaves, LGPD, incidente 2026-07-25 |

## Nota

**Esta é a fase principal.** O `.mxd` só existe no Windows do usuário; todo o valor do produto está
aqui. A [Fase 2](../../Fase_2_Site/planos/README.md) reusa o núcleo Python e o `MapSpec`, mas não
substitui nem antecede o desktop. Conta do app = **local** ([F1-14](14-auth-e-conta.md));
[F2-05](../../Fase_2_Site/planos/05-auth-e-memoria.md) é pós-M11 e **não** bloqueia o M5.

## Estado

| Marco | Status |
|---|---|
| Planos F1-00…F1-17 | escritos |
| M1 — núcleo | **A fechado** · **B parcial** |
| M2 — motor `.mxd` | **parcial** — **próximo** (Windows + ArcMap) |
| M3–M8 | **fechados** + épico sem ArcMap esgotado |
| M9–M11 | **não iniciados** |
| Eventos NDJSON | **os 8 do vocabulário** emitidos (`job.progresso` … `aviso`) |

**O que falta na Fase 1:** só M2 → M9 → M10 → M11. Ver
[`../../AGENT_BRIEF.md`](../../AGENT_BRIEF.md#snapshot--o-que-falta-2026-07-26).
