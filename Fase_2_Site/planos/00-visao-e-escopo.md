# F2-00 — Visão e escopo do site

## O que é

A metade web do Mapas Fácil: site com login, projetos persistentes e histórico entre máquinas.
O backend roda **neste PC** (Linux, Cuiabá-MT) e é exposto por Cloudflare Tunnel dedicado —
decisão **D7** em [`../../planos/00-visao-e-duas-fases.md`](../../planos/00-visao-e-duas-fases.md).

Não é o produto principal. O `.mxd` nasce na [Fase 1](../../Fase_1_Desktop/README.md). Esta fase
dá o que o desktop sozinho não tem: memória de projeto, mapa por número do CAR sem instalar nada,
e uma vitrine pública.

> **Exceção de ordem (D10):** o **serviço de identidade** de
> [`05-auth-e-memoria.md`](05-auth-e-memoria.md) é dependência bloqueante do marco M5 da Fase 1,
> porque o app desktop exige login. Ele sobe **antes** do resto desta fase.

## Por que depois da Fase 1

1. O NexoGeo priorizou a web e deixou o `.mxd` para "depois" — nunca saiu.
2. Sem ArcMap no servidor, o site **não gera `.mxd`**. Entrega PDF/PNG e delega o `.mxd` ao desktop.
3. A Fase 1 valida o produto com usuário real sem infraestrutura.

## O que a v1 do site faz

- Login e projetos persistentes (histórico entre máquinas).
- "Mapa por número do CAR": digita `MT102042/2017`, recebe PDF/PNG.
- Espaço de trabalho no backend com memória do projeto e dos imóveis.
- Ponte com o app desktop, para o `.mxd` ser gerado na máquina Windows certa.
- Consultas WFS/WMS **deste PC** (IP brasileiro) — SEMA, IBAMA, FUNAI, etc.
- Backend em `mapasfacil-api.cursar.space`; site em `mapasfacil.cursar.space`.

## O que deliberadamente não faz

| Fora | Motivo |
|---|---|
| Gerar `.mxd` no servidor | sem ArcMap no Linux |
| Hospedar shapefiles de cliente na nuvem pública | LGPD; dados ficam no PC local ou no backend deste PC com consentimento |
| Backend em Render/Vercel como primário | SEMA bloqueia IP fora do Brasil |
| Reusar tunnels Cloudflare já existentes | risco aos outros sistemas |
| Cobrança | depois da validação |

## Critérios de aceite (rascunho)

1. Um usuário logado pede um mapa por CAR e recebe PDF sem instalar o desktop.
2. Consulta à SEMA funciona a partir deste PC (não de IP estrangeiro).
3. O desktop consegue pedir/receber um job de `.mxd` via ponte documentada em
   [`03-integracao-fase1.md`](03-integracao-fase1.md).
4. Deploy do tunnel **não** altera tunnels de outros projetos neste PC.

## Estado deste documento

Escopo alinhado à visão comum (D1, D7). Os planos `01`, `02`, `04` e `06` ainda estão em
formato **legado** (nuvem + agente WS) — ver [`README.md`](README.md).
