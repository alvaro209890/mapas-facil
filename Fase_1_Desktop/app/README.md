# app/ — shell Electron + React (Fase 1, bloco C)

Planos: [F1-02](../planos/02-ui-chat-e-workspace.md) (layout e comportamento),
[F1-16](../planos/16-design-system-dark.md) (tokens, tipografia, animações),
[F1-01](../planos/01-arquitetura.md) (protocolo NDJSON e fronteiras).

## Estado — 2026-07-26

**Parcial e não executável ainda.** A pasta saiu do zero nesta rodada; o que existe é o
scaffold, a ponte com o núcleo e a base visual. **Não há entrada do renderer** (`index.html`,
`src/main.tsx`, `App.tsx`), então `pnpm build` e `pnpm dev` **não rodam**. Nenhum
`pnpm install` foi executado neste repositório — não há `pnpm-lock.yaml`.

| # | Tarefa (F1-13 bloco C) | Estado | Onde |
|---|---|---|---|
| C1 | Scaffold Electron + Vite + React 19 + TS | **parcial** | `package.json`, `tsconfig*.json`, `vite.config.ts`, `scripts/build-electron.mjs`, `electron/main.ts`, `electron/preload.ts` |
| C2 | Ponte NDJSON (spawn, reinício, `UI-001`) | **parcial** — código completo, **sem teste executado** | `electron/nucleo/ponte.ts` |
| C3 | Tokens de cor, tipografia e movimento | **feito** | `src/estilos/tokens.css`, `src/estilos/reset.css` |
| C4 | Fontes embarcadas | **feito** | `src/estilos/fontes/` (+ licenças OFL) |
| C5 | `AppShell` com 4 painéis redimensionáveis | **não iniciado** | — |
| C6 | `barra-progresso-job` consumindo `job.progresso` | **não iniciado** | — |
| C7–C11 | workspace, doctor, estados vazios, `Ctrl+K`, testes visuais | **não iniciado** | — |

O núcleo já emite `job.progresso` (A9, v0.4.0), então **C6 está desbloqueado**: o contrato do
evento está tipado em `src/estado/eventos.ts`, incluindo os rótulos pt-BR das 10 etapas.

## O que falta, na ordem

1. `index.html` + `src/main.tsx` + `src/App.tsx` — a entrada do renderer, importando
   `estilos/fontes/fontes.css`, `estilos/tokens.css`, `estilos/reset.css` e fixando
   `document.documentElement.dataset.tema = "escuro"` como default (D15/AP-08).
2. `src/layout/AppShell.tsx` + `TopoApp.tsx` e os quatro painéis (`barra-chats`,
   `painel-workspace`, `painel-chat`, `painel-direito`), redimensionáveis, com as larguras
   persistidas via `window.mapasfacil.gravarPreferencias` (C5).
3. `src/componentes/BarraProgressoJob.tsx` (C6): 10 segmentos nomeados, `role="progressbar"`
   com `aria-valuenow`. Sem evento → texto "gerando…" **sem** barra de porcentagem (AP-07).
4. `src/motion/tokens.ts` e `useReducedMotion.ts` espelhando o CSS.
5. Testes: `tests/ponte.test.ts` (sidecar de mentira em Node, reinício, `UI-001`) e
   `tests/barra-progresso-job.test.tsx` (evento injetado, `pct` monotônico).
6. `pnpm install` + `pnpm typecheck` + `pnpm test` + `pnpm build` — nada disso foi rodado.

## Arquitetura do que já existe

```
app/
  electron/                  processo main — Node, sem acesso do renderer
    main.ts                  janela 1280×800 mín., tema escuro, IPC, ciclo da ponte
    preload.ts               contextBridge → window.mapasfacil (chamar, eventos, preferências)
    preferencias.ts          config.json em %APPDATA%\MapasFacil\ (sem segredo)
    ipc/canais.ts            nomes dos canais IPC
    nucleo/
      ponte.ts               spawn do sidecar, framing NDJSON, reinício, UI-001
      protocolo.ts           tipos do envelope req/res/evt
      localizar.ts           onde está o Python (venv no dev, PyInstaller no pacote)
      ulid.ts                ULID local, sem dependência
  src/                       renderer — React
    estado/eventos.ts        os 8 eventos do contrato; só job.progresso tem emissor hoje
    estado/ponte.ts          acesso tipado a window.mapasfacil (no-op fora do Electron)
    estilos/                 tokens.css, reset.css, fontes/
```

### Fronteiras respeitadas

- O renderer **não** recebe `fs`, `child_process` nem caminho absoluto: só métodos NDJSON
  (fronteira 1 de F1-01). `contextIsolation: true`, `sandbox: true`, `nodeIntegration: false`.
- O transporte é stdio, nunca porta TCP (AP-14).
- Núcleo caído → `UI-001`, com as requisições pendentes **rejeitadas**, não penduradas; a ponte
  tenta 3 reinícios automáticos antes de ficar em `caido`, e `reiniciar()` é o botão do banner.

## Comandos (quando a entrada do renderer existir)

```bash
cd Fase_1_Desktop/app
pnpm install
pnpm typecheck
pnpm test
pnpm build            # renderer (Vite) + main/preload (esbuild)
pnpm dev              # servidor Vite; pnpm dev:electron abre a janela
```

O `pnpm dev:electron` procura o Python em `../nucleo/.venv/`; se não achar, cai em `python3` do
`PATH`. Rode `pip install -e ".[dev]"` no núcleo antes.
