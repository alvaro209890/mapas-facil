# F2-00 — Visão e escopo do site

## Objetivo

Definir o que a Fase 2 é na v1: um **site público de distribuição do produto** — vitrine,
explicação e download do instalador Windows. O mapa, a conta e o chat vivem **só** no
[app desktop](../../Fase_1_Desktop/README.md).

## Estado atual vs alvo

| Item | Atual | Alvo (v1) |
|---|---|---|
| Papel do site | planos legados (login, mapa por CAR, chat) | **só distribuição** |
| Login / criar conta no site | descrito no legado | **fora** — conta é [F1-14](../../Fase_1_Desktop/planos/14-auth-e-conta.md) no desktop |
| Gerar mapa / PDF / `.mxd` no site | descrito no legado | **fora** — só no desktop |
| Código em `web/` | só `README.md` | Next.js landing + download (após estes planos) |
| Código em `backend/` | só `README.md` | **fora da v1** — sem FastAPI/Postgres para distribuição |

## Dependências

| Precisa de | Estado |
|---|---|
| Fase 1 com instalador (M10) para link real de download | em andamento; até lá o site usa placeholder “em breve” |
| Domínio / PC servidor para publicar | depois — desenvolver em `localhost` neste PC |

Não depende de ArcMap, SEMA, MapSpec runtime nem conta nuvem.

## Decisões

| # | Decisão | Alternativa descartada |
|---|---|---|
| **D21** *(2026-07-27)* | Fase 2 v1 = **site de distribuição** (landing + download + contato). Sem login no site. Sem gerar mapa no site | site com chat, mapa por CAR, projetos, conta nuvem na v1 |
| D10 | Conta = **só no desktop** (e-mail + senha local) | login Google / portal web como entrada do produto |
| D7 *(recontextualizada)* | Publicar o site no PC servidor via tunnel/host dedicado (`mapasfacil.cursar.space`), **sem** tocar tunnels de outros sistemas. API geo neste PC **não** é requisito da v1 do site | Render/Vercel como caminho primário; reusar tunnels existentes |

## O que a v1 do site faz

- Landing **cinematográfica**: marca + headline + CTA e âncora visual de **mapa sendo gerado**
  (vídeo do app e/ou animação CSS/SVG) — ver [F2-04](04-frontend-site.md).
- CTA claro para **baixar o app** (instalador quando M10 existir; senão “em breve”).
- Página ou seção de **requisitos** (Windows; ArcMap opcional; chave DeepSeek BYOK).
- Contato / links úteis.
- Deploy possível em `mapasfacil.cursar.space` a partir do PC servidor.

## O que deliberadamente não faz

| Fora | Motivo |
|---|---|
| Login, criar conta, “entrar com Google” | conta é local no desktop (D10 / D21) |
| Chat, MapSpec, jobs, preview de mapa | produto é o app |
| Mapa por número do CAR / PDF no browser | mapa só no desktop |
| FastAPI + Postgres + WFS no site | sem backend na v1 de distribuição |
| Hospedar shapefiles / dados de cliente | LGPD; fica no PC do usuário |
| Cobrança, planos, trial | D18 / fora da v1 do produto |

## Critérios de aceite

1. Visitante abre a home, vê a cena de mapa em motion e entende o produto em uma tela
   (marca + o que faz + CTA download).
2. Há rota/página de download: com instalador → link funcional; sem instalador → “em breve” sem 404 mentiroso.
3. Nenhuma rota de `/login`, `/signup`, `/chat` ou geração de mapa no escopo v1.
4. `grep` nos planos F2 reescritos: sem prometer mapa/PDF/CAR no site como entrega da v1.
5. Deploy documentado em [F2-06](06-deploy-tunnel-neste-pc.md) **não** altera tunnels de outros projetos.
6. Motion do hero especificado em [F2-04](04-frontend-site.md) (storyboard + vídeo opcional + reduced-motion).

## Fora de escopo

- Implementação do Next.js (próxima rodada, após planos).
- Conta nuvem / memória ([F2-05](05-auth-e-memoria.md)) — adiado.
- Ponte desktop ↔ servidor para jobs de `.mxd`.

## Anti-padrões

| Não faça | Por quê |
|---|---|
| Copiar o legado (agente WS, mapa por CAR, auth no site) | D21 |
| Exigir backend/Postgres para publicar a landing | distribuição não precisa |
| Colocar login no site “porque o desktop tem” | login é F1-14 |
| Gerar PDF no servidor “só um stub” | mapa só no desktop |

## Estado deste documento

Reescrito 2026-07-27 (D21). Planos `01`–`06` alinhados ao mesmo escopo.
