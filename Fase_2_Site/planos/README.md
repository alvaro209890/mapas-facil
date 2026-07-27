# Planos da Fase 2 — Site de distribuição

Site **público** para distribuir o Mapas Fácil (landing + download). Conta e mapas ficam no
[app desktop](../../Fase_1_Desktop/planos/README.md). Decisão **D21** (2026-07-27): sem login no
site, sem gerar mapa no browser. Publicação em `mapasfacil.cursar.space` no PC servidor —
[F2-06](06-deploy-tunnel-neste-pc.md) — **sem** tocar tunnels de outros sistemas.

> ## Conta = só no desktop
>
> Login/criar conta: [F1-14](../../Fase_1_Desktop/planos/14-auth-e-conta.md).
> [F2-05](05-auth-e-memoria.md) (conta nuvem) permanece **adiado** e **não** faz parte da v1 do site.

## Índice

| # | Documento | Conteúdo | Status |
|---|---|---|---|
| F2-00 | [Visão e escopo](00-visao-e-escopo.md) | distribuição only; critérios de aceite | **reescrito** (D21) |
| F2-01 | [Arquitetura](01-arquitetura.md) | Next.js; sem API/agente WS | **reescrito** |
| F2-02 | [Backend e API](02-backend-api.md) | backend **fora da v1** | **reescrito** |
| F2-03 | [Integração com a Fase 1](03-integracao-fase1.md) | só download do instalador | **reescrito** |
| F2-04 | [Frontend e site](04-frontend-site.md) | landing + **motion/vídeo de mapa**; download, contato | **reescrito** (+ motion) |
| F2-05 | [Identidade nuvem / memória](05-auth-e-memoria.md) | adiado; sem login no site | **adiado** |
| F2-06 | [Deploy](06-deploy-tunnel-neste-pc.md) | localhost → PC servidor → domínio | **reescrito** |

## Ordem de leitura

| # | Documento | Por quê |
|---|---|---|
| 00 | [Visão](00-visao-e-escopo.md) | o que a v1 é e não é |
| 01 | [Arquitetura](01-arquitetura.md) | fronteiras |
| 04 | [Frontend](04-frontend-site.md) | páginas a implementar |
| 03 | [Integração](03-integracao-fase1.md) | vínculo com o instalador |
| 02 | [Backend](02-backend-api.md) | confirma que não há API |
| 06 | [Deploy](06-deploy-tunnel-neste-pc.md) | como publicar |
| 05 | [Auth nuvem](05-auth-e-memoria.md) | só se o produto pedir depois |

## Planos comuns

Contratos do **mapa** continuam na Fase 1 / [`planos/`](../../planos/README.md). O site v1
**não** consome MapSpec nem catálogo WFS em runtime.

## Estado

| Marco | Status |
|---|---|
| Planos F2-00…F2-06 | alinhados a D21 (distribuição) |
| Código `web/` | **não iniciado** (só README) — motion especificado em F2-04; **não** implementar sem pedido |
| Código `backend/` | **fora da v1** (só README) |

Desenvolver o site em qualquer PC (`pnpm dev`); publicar depois no PC servidor.
