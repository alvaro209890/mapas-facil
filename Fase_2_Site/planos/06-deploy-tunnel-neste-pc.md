# F2-06 — Deploy do site (neste PC → PC servidor)

## Objetivo

Como o site de distribuição sai do desenvolvimento local e chega a `mapasfacil.cursar.space`
**sem** alterar tunnels Cloudflare de outros sistemas neste (ou no) PC servidor.

## Estado atual vs alvo

| Item | Atual | Alvo |
|---|---|---|
| Documento | legado (Vercel + Render + agente `.exe`) | site Next.js + host/tunnel dedicado |
| API | legado obrigatório | **ausente** na v1 ([F2-02](02-backend-api.md)) |
| Dev | — | `pnpm dev` neste PC (Windows ou Linux) |
| Prod | — | build no PC servidor (Linux, Cuiabá) ou artefato copiado daqui |

## Dependências

| Precisa de | Estado |
|---|---|
| [F2-04](04-frontend-site.md) implementado | depois dos planos |
| DNS / tunnel para `mapasfacil.cursar.space` | no PC servidor, quando for publicar |
| Instalador M10 | opcional para URL de download |

## Fluxo de trabalho

```
PC de desenvolvimento (agora)
  └── edita Fase_2_Site/web/ → pnpm build ok em localhost
        │
        │  git push / cópia / rsync
        ▼
PC servidor (Linux)
  └── pull → pnpm build → serve (Node ou estático)
        │
        └── Cloudflare Tunnel dedicado → mapasfacil.cursar.space
```

Regra: **desenvolver aqui; publicar lá**. Não misturar configs de tunnel de outros produtos.

## Contratos

### Artefato

| Artefato | Onde roda | Como chega |
|---|---|---|
| `web/` | PC servidor (ou CDN atrás do tunnel) | git + `pnpm build` |
| `backend/` | — | **não deploya** na v1 |
| Instalador `.exe` | storage/URL apontada por `NEXT_PUBLIC_DOWNLOAD_URL` | release M10 (não pelo Next “upload”) |

### Tunnel / DNS

| Host | v1 |
|---|---|
| `mapasfacil.cursar.space` | site |
| `mapasfacil-api.cursar.space` | **não criar** até existir API |

- Tunnel **novo** ou hostname novo no cloudflared do servidor.
- Arquivos/config de tunnels de **outros** sistemas: **intocados**.
- HTTPS via Cloudflare (TLS no edge).

### Headers (Next / reverse proxy)

`Strict-Transport-Security` (em HTTPS), `X-Content-Type-Options: nosniff`,
`Referrer-Policy`, `X-Frame-Options: DENY`, CSP básica adequada a site estático.

### Variáveis de produção

Só `NEXT_PUBLIC_*` do [F2-01](01-arquitetura.md). Segredos: nenhum no front.

## Tarefas agentáveis

### Neste PC (dev)

- [ ] `pnpm install` / `pnpm dev` / `pnpm build` documentados no README de `web/`
- [ ] `.env.example` sem segredos

### No PC servidor (quando for publicar)

- [ ] Clone/pull do repo
- [ ] Node LTS + `pnpm build`
- [ ] Serviço (systemd ou equivalente) **ou** servir `out/` estático
- [ ] Cloudflare Tunnel / DNS só para `mapasfacil.cursar.space`
- [ ] Conferir que configs de outros tunnels **não** foram editadas
- [ ] Smoke: `curl -I https://mapasfacil.cursar.space` → 200

## Critérios de aceite

- [ ] Site responde em HTTPS no domínio dedicado
- [ ] Diff de configs de tunnels alheios = vazio
- [ ] Sem container/API Postgres no deploy v1
- [ ] Download: URL configurada ou página “em breve”

## Fora de escopo

- Deploy na Vercel/Render como caminho **primário** (pode existir preview opcional; produção = PC servidor / D7)
- Pipeline que publique o agente Windows pelo backend
- `mapasfacil-api` na v1

## Anti-padrões

| Não faça | Por quê |
|---|---|
| Editar tunnel de outro sistema “só um hostname” | risco operacional (D7) |
| Subir FastAPI vazio só para ter API no DNS | F2-02 |
| Commitar `.env` com URLs internas sensíveis além do necessário | preferir env no servidor |
| Exigir ArcMap no servidor Linux para o site | site não gera mapa |

## Relação com o legado

O texto anterior (Vercel + Render + distribuição do agente via API) é **obsoleto** para a v1.
