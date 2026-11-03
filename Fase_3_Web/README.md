# Fase 3 — Mapas Fácil Web (site + chat de IA + backend no server)

> **Agente de codificação?** Leia nesta ordem, inteiro, antes de tocar em código:
> 1. [`planos/16-protocolo-do-agente.md`](planos/16-protocolo-do-agente.md) — como trabalhar aqui
> 2. [`planos/00-visao-e-decisoes.md`](planos/00-visao-e-decisoes.md) — o que é, as decisões D22–D39 e as respostas do Álvaro (P1–P10)
> 3. [`planos/01-arquitetura.md`](planos/01-arquitetura.md) — peças, processos e pastas
> 4. [`planos/14-roadmap-marcos.md`](planos/14-roadmap-marcos.md) — a ordem W0 → W12
> 5. o plano do marco em que você vai trabalhar + [`planos/15-checklist-implementacao.md`](planos/15-checklist-implementacao.md)
> 6. se o marco mexe em mapa: [`planos/17-conhecimento-das-skills.md`](planos/17-conhecimento-das-skills.md)
>
> E também, do repositório: [`../AGENT_BRIEF.md`](../AGENT_BRIEF.md) (anti-padrões AP-01…AP-15
> continuam valendo, com as revisões escritas em `00-visao-e-decisoes.md`).

## O que é

O Mapas Fácil vira um **site**. A pessoa entra com e-mail e senha, cria um **projeto** (um
projeto = um mapa), escolhe **folha** (A4, A3, A2, A1, A0) e **orientação** (retrato ou
paisagem), envia **um `.zip`** com os dados do imóvel (shapefiles, recibo do CAR, `.zip` do
SIMCAR) e **conversa** com a IA: "faz a Dinâmica 2026", "clareia a vegetação", "tira a tabela",
"passa para A3 paisagem". Enquanto a IA trabalha, o **palco do mapa** mostra o que o núcleo
está fazendo de verdade: a câmera desce do estado ao município e ao imóvel, as camadas acendem
uma a uma, a folha se monta peça por peça. No fim, a pessoa baixa `.pdf`, `.xlsx` e o pacote
`.mxd` (que abre no ArcMap de qualquer máquina) — **gerados sem ArcMap**, no servidor.

```
 navegador ──HTTPS──▶ Cloudflare Tunnel ──▶ server-desktop
                                             ├─ mapasfacil_servidor (FastAPI, :3130)
                                             │    ├─ API REST  /api/v1/…
                                             │    ├─ SSE       /api/v1/projetos/{id}/eventos
                                             │    └─ SPA       /  (build do web/)
                                             └─ pool de workers: 1 processo
                                                `python -m mapasfacil_nucleo` por projeto
                                                (o MESMO núcleo do desktop, NDJSON por stdio)
```

## Pastas desta fase

| Pasta | O que é | Estado |
|---|---|---|
| [`planos/`](planos/) | 18 planos executáveis, W-00…W-17 (este README é o índice) | **escritos 2026-11-03**, decisões do Álvaro incorporadas |
| `servidor/` | backend Python `mapasfacil_servidor` (FastAPI + pool de workers) | ausente — nasce no W0/W2 |
| `web/` | app React (Vite + React 19 + TS + zustand + MapLibre + motion) | ausente — nasce no W0/W6 |
| `deploy/` | units systemd `--user`, config do túnel, scripts de operação | ausente — nasce no W12 |
| `fixtures/` | ZIPs **sintéticos** de teste (nunca dado de cliente) | ausente — nasce no W4 |

## Índice dos planos

Convenção de nomes: **`W-NN`** (com hífen) é um **plano** deste diretório; **`WNN`** (sem hífen)
é um **marco** do roadmap; **`WNN-MM`** é uma **tarefa** do marco `WNN` (lista no
[checklist](planos/15-checklist-implementacao.md)). Os números de plano e de marco não coincidem
(ex.: o plano W-08 é implementado no marco W10).

| # | Plano | Pilar | Marco(s) |
|---|---|---|---|
| 00 | [Visão, jornada e decisões D22–D39](planos/00-visao-e-decisoes.md) | todos | W0 |
| 01 | [Arquitetura](planos/01-arquitetura.md) | base | W0–W2 |
| 02 | [Projeto, folha e importação do ZIP](planos/02-projeto-folha-e-upload.md) | produto | W3–W4 |
| 03 | [API HTTP e stream de eventos](planos/03-api-http-e-eventos.md) | base | W3–W5 |
| 04 | [Ponte servidor ↔ núcleo e modo servidor](planos/04-ponte-nucleo-servidor.md) | base | W1–W2 |
| 05 | [Chat e agente na web](planos/05-chat-agente-web.md) | produto | W5–W6 |
| 06 | [Frontend web e design](planos/06-frontend-web-e-design.md) | 1 | W6 |
| 07 | [Motion: o palco do mapa](planos/07-motion-palco-do-mapa.md) | **1** | W7–W8 |
| 08 | [Motor `.mxd` binário (sem ArcMap)](planos/08-motor-mxd-binario.md) | **2** | W10 |
| 09 | [PDF nativo em todas as folhas](planos/09-motor-pdf-nativo-e-folhas.md) | **2** | W9 |
| 10 | [Inteligência cartográfica](planos/10-inteligencia-cartografica.md) | **3** | W11 |
| 11 | [Segurança, contas e LGPD](planos/11-seguranca-contas-e-lgpd.md) | base | W3, W12 |
| 12 | [Deploy no server e operação](planos/12-deploy-servidor-e-operacao.md) | base | W0, W12 |
| 13 | [Testes e QA](planos/13-testes-e-qa.md) | base | todos |
| 14 | [Roadmap por dependência (W0–W12)](planos/14-roadmap-marcos.md) | — | — |
| 15 | [Checklist de implementação](planos/15-checklist-implementacao.md) | — | todos |
| 16 | [Protocolo do agente implementador](planos/16-protocolo-do-agente.md) | — | todos |
| 17 | [O que as skills de MXD e GIS ensinam](planos/17-conhecimento-das-skills.md) | 2 e 3 | W4, W5, W9–W11 |

Os três pilares pedidos pelo Álvaro:

1. **Experiência visual e animações com zoom** → planos 06 e 07 (+ eventos novos no 03 e no 04).
2. **Independência do ArcMap** → planos 08 (`.mxd` binário) e 09 (PDF vetorial nativo).
3. **Inteligência cartográfica** → plano 10.

## Estado (atualize no mesmo commit que fechar um marco)

| Marco | Nome | Estado |
|---|---|---|
| W0 | Fundação e alinhamento documental | **fechado** — 2026-11-03 (`docs/fase3-rodada-2026-11-03-W0.md`) |
| W1 | Núcleo em modo servidor + `MapSpec` v3 (`folha`) | **fechado com 1 pendência** — 2026-11-03 (`docs/fase3-rodada-2026-11-03-W1.md`); W1-10 (`doctor.py`) bloqueada pelo Álvaro |
| W2 | Ponte e pool de workers | **fechado** — 2026-11-03 (`docs/fase3-rodada-2026-11-03-W2.md`) |
| W3 | API base: contas, sessões, projetos | **fechado** — 2026-11-03 (`docs/fase3-rodada-2026-11-03-W3.md`) |
| W4 | Importação do ZIP e indexação | **quase fechado** — 2026-11-03 (`docs/fase3-rodada-2026-11-03-W4.md`); faltam W4-03 (web) e W4-10 (SAD69) |
| W5 | Stream de eventos + chat relay | **em andamento** — W5-01/02/03/10/11 fechados 2026-11-03 (`docs/fase3-rodada-2026-11-03-W5.md`); chat (W5-10..20) pendente |
| W6 | Frontend: shell, login, projetos, assistente, chat | não iniciado |
| W7 | Eventos de motion no núcleo | não iniciado |
| W8 | Palco do mapa (câmera, camadas, folha) | não iniciado |
| W9 | PDF nativo A4–A0 | não iniciado |
| W10 | Motor `.mxd` binário | não iniciado |
| W11 | Inteligência cartográfica | não iniciado |
| W12 | Deploy no server + piloto interno | não iniciado |

**MVP utilizável** = W0–W8 + W9 (pelo menos A4 e A3) + W12. O pacote `MXD/ SHP/ Mapas/` sai
sempre, sem validação manual (D37). Até o W10, o `.mxd` do pacote vem do motor T2 que já existe
(cópia do template A4 pronto + extent/escala por sentinela) e só para as folhas que têm template;
nas outras, o pacote leva `SHP/` e `Mapas/` e avisa que o `.mxd` daquela folha ainda não é gerado.
O W10 amplia para todas as folhas e para os demais pontos variáveis do layout.

## Regras que valem para qualquer arquivo desta pasta

- Nada de estimativa em dias/semanas (AP-13). Ordem é dependência técnica.
- Nada de dado de cliente no git: recibo do CAR, CPF, shapefile real, `.mxd` com `authkey` (AP-03, AP-09).
- Animação só amarrada a evento real do núcleo (AP-07). Sem spinner falso, sem timer fingindo etapa.
- A IA edita `MapSpec`; nunca escreve código, `arcpy`, SQL ou URL (AP-02).
- O servidor **nunca** roda ArcMap/ArcPy (AP-01 revisado por D24).
