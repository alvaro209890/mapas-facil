# Planos da Fase 2 — Site e backend

Estes documentos descrevem o **site de engenharia florestal** e o backend que roda **neste PC**
(Linux, Cuiabá-MT), exposto por **Cloudflare Tunnel** dedicado. A Fase 2 começa depois que a
[Fase 1](../../Fase_1_Desktop/planos/README.md) estiver validada com usuário real.

Decisão **D7** ([`00-visao-e-duas-fases.md`](../../planos/00-visao-e-duas-fases.md)): o backend
fica neste PC porque `sema.mt.gov.br` bloqueia IP fora do Brasil. **Render e Vercel não são o
caminho primário** — o tunnel `mapasfacil-api.cursar.space` expõe a API; o site fica em
`mapasfacil.cursar.space`.

> ## ⚠ Exceção: identidade vem antes
>
> A decisão **D10** tornou o **login obrigatório no app desktop**. O serviço de identidade
> descrito em [`05-auth-e-memoria.md`](05-auth-e-memoria.md) — backend FastAPI neste PC + site
> `/login` — é **dependência bloqueante do marco M5 da Fase 1**, não "depois da Fase 1".
>
> Um agente que for implementar auth trabalha em `Fase_2_Site/backend/` e `Fase_2_Site/web/`
> **agora**, seguindo F2-05 e [F1-14](../../Fase_1_Desktop/planos/14-auth-e-conta.md). Todo o
> resto desta pasta (mapa por CAR, memória de projeto, vitrine) continua depois do M11.

## Índice desejado

| # | Documento | Conteúdo | Status |
|---|---|---|---|
| F2-00 | [Visão e escopo](00-visao-e-escopo.md) | o que o site acrescenta, o que não faz, critérios de aceite | rascunho |
| F2-01 | [Arquitetura](01-arquitetura.md) | Next.js + FastAPI neste PC; fronteiras; sem agente WS na nuvem | **LEGADO — reescrever** |
| F2-02 | [Backend e API](02-backend-api.md) | FastAPI, Postgres, jobs, consultas geo locais | **LEGADO — reescrever** |
| F2-03 | [Integração com a Fase 1](03-integracao-fase1.md) | reuso do núcleo/`MapSpec`; ponte desktop para `.mxd` | rascunho |
| F2-04 | [Frontend e site](04-frontend-site.md) | Next.js, chat, projetos, mapa por número do CAR | **LEGADO — reescrever** |
| F2-05 | [Identidade, auth e memória](05-auth-e-memoria.md) | **serviço de identidade (bloqueia o M5 da Fase 1)**; memória de projeto fica para depois | **agentável — implementar agora** |
| F2-06 | [Deploy e tunnel neste PC](06-deploy-tunnel-neste-pc.md) | Cloudflare Tunnel, systemd, domínios, sem tocar nos tunnels existentes | **LEGADO — reescrever** |

### Sobre os arquivos LEGADO

Os quatro arquivos existentes (`01`, `02`, `04`, `06`) foram escritos para o modelo antigo
**nuvem + agente WebSocket** (Vercel + Render + `agent/` no PC do usuário). O corpo ainda descreve
esse desenho. Mantêm-se no repositório como referência histórica até serem reescritos para o
modelo **D7**: backend neste PC, tunnel dedicado, site estático ou SSR apontando para a API
local, **sem gerar `.mxd` no servidor**.

O que muda na reescrita:

| Antes (legado) | Depois (D7) |
|---|---|
| `backend/` no Render | FastAPI neste PC, exposto por tunnel |
| `web/` na Vercel como primário | site em `mapasfacil.cursar.space`, API em `mapasfacil-api.cursar.space` |
| agente WS na nuvem orquestrando o PC | ponte opcional com o app desktop; `.mxd` só no Windows |
| shapefiles sobem para a nuvem | dados sensíveis ficam no backend local ou no desktop |

## Ordem de leitura (quando os planos estiverem prontos)

| # | Documento | Por quê |
|---|---|---|
| 00 | [Visão e escopo](00-visao-e-escopo.md) | o que a Fase 2 acrescenta e o que deliberadamente não faz |
| 01 | [Arquitetura](01-arquitetura.md) | como site, API e tunnel se encaixam |
| 03 | [Integração com a Fase 1](03-integracao-fase1.md) | o que reusa do desktop e o que delega |
| 05 | [Auth e memória](05-auth-e-memoria.md) | projetos persistentes — o diferencial do site |
| 02 | [Backend e API](02-backend-api.md) | implementação da API |
| 04 | [Frontend e site](04-frontend-site.md) | implementação do site |
| 06 | [Deploy e tunnel](06-deploy-tunnel-neste-pc.md) | como sobe e mantém neste PC |

## Planos comuns

Contratos compartilhados com a Fase 1: [`planos/`](../../planos/README.md).

| # | Documento | O que traz para a Fase 2 |
|---|---|---|
| 02 | [`MapSpec` — contrato](../../planos/02-mapspec-contrato.md) | o JSON que descreve um mapa (reuso direto) |
| 03 | [WFS e serviços geo](../../planos/03-wfs-e-servicos-geo.md) | consultas geo feitas pelo backend local |
| 04 | [Dados, camadas e CAR](../../planos/04-dados-camadas-e-car.md) | mapa por número do CAR, cache |
| 05 | [Segurança e segredos](../../planos/05-seguranca-e-segredos.md) | LGPD, cofre de chaves, dados de cliente |

## Nota

A Fase 2 **não gera `.mxd`**. Sem ArcMap no servidor Linux, o site entrega PDF/PNG (e delega o
`.mxd` ao [app desktop](../../Fase_1_Desktop/README.md) quando o usuário precisar editar no ArcMap).

## Estado

| Marco | Status |
|---|---|
| **F2-05 — identidade** | **reescrito e agentável; bloqueia o M5 da Fase 1** (D10) |
| F2-00, F2-03 | rascunhos alinhados a D7 |
| F2-01, F2-02, F2-04, F2-06 | legado — corpo descreve modelo antigo (nuvem + agente WS) |
| Código de produção | não iniciado; `backend/` e `web/` só têm `README.md` |

**Ao reescrever qualquer plano legado**, o modelo é o dos planos da Fase 1 reescritos em
2026-07-25: Objetivo → Estado atual vs alvo → Dependências → Contratos → Tarefas agentáveis com
caminho de arquivo → Critérios de aceite verificáveis → Fora de escopo → Anti-padrões. Ver
[`../../AGENT_BRIEF.md`](../../AGENT_BRIEF.md#como-ler-um-plano).
