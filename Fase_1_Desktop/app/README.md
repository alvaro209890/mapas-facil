# app/ — shell Electron + React (Fase 1, bloco C)

Planos: [F1-02](../planos/02-ui-chat-e-workspace.md) (layout e comportamento),
[F1-16](../planos/16-design-system-dark.md) (tokens, tipografia, animações),
[F1-01](../planos/01-arquitetura.md) (protocolo NDJSON e fronteiras).

## Estado — 2026-07-26

**Roda.** O corte vertical do shell está fechado: a janela abre, os quatro painéis existem e são
redimensionáveis, e a barra de progresso reage a `job.progresso` de verdade. `pnpm install`,
`typecheck`, `test` (17 testes) e `build` foram executados nesta rodada e ficaram verdes.

O que ainda **não** existe é conteúdo de painel: árvore da pasta, chat do agente, galeria,
preview e doctor são C7–C11 e marcos posteriores. Os painéis mostram placeholder que diz de qual
marco cada coisa é — nenhum deles inventa dado do núcleo.

| # | Tarefa (F1-13 bloco C) | Estado | Onde |
|---|---|---|---|
| C1 | Scaffold Electron + Vite + React 19 + TS | **feito** | `index.html`, `src/main.tsx`, `src/App.tsx`, `package.json`, `vite.config.ts`, `vitest.config.ts`, `tsconfig*.json`, `electron/main.ts`, `electron/preload.ts` |
| C2 | Ponte NDJSON (spawn, reinício, `UI-001`) | **feito** | `electron/nucleo/ponte.ts` + `tests/ponte.test.ts` |
| C3 | Tokens de cor, tipografia e movimento | **feito** | `src/estilos/tokens.css`, `src/estilos/reset.css`, `src/motion/tokens.ts` |
| C4 | Fontes embarcadas | **feito** | `src/estilos/fontes/` (+ licenças OFL) |
| C5 | `AppShell` com 4 painéis redimensionáveis | **feito** | `src/layout/AppShell.tsx`, `TopoApp.tsx`, `Divisor.tsx`, `src/estado/preferencias.ts` |
| C6 | `barra-progresso-job` consumindo `job.progresso` | **feito** | `src/componentes/BarraProgressoJob.tsx`, `src/estado/progressoJob.ts` + teste |
| C7–C11 | workspace, doctor, estados vazios, `Ctrl+K`, testes visuais | **não iniciado** | — |

### O que a rodada de C1–C6 mudou no que já existia

- `electron/nucleo/ponte.ts` — **defeito corrigido**: depois de `reiniciar()`, o `exit` do
  processo antigo era tratado como queda do novo (zerava `this.processo`, rejeitava as pendentes
  e agendava outro reinício). Agora cada ouvinte é amarrado ao processo que o registrou. Achado
  pelo teste, não por leitura.
- `src/estado/eventos.ts` — ganhou o `peso` de cada etapa (espelho de `progresso.py`, soma 100) e
  `pctAoConcluir`; o type predicate de `ehJobProgresso` não compilava e foi consertado.
- `package.json` — `pnpm.onlyBuiltDependencies` com `electron` e `esbuild`: sem isso o pnpm 10
  ignora os postinstall e o binário do Electron nunca é baixado.
- `vitest.config.ts` — a configuração de teste saiu do `vite.config.ts`: o `defineConfig` do
  Vitest 2 carrega os tipos do Vite 5 e conflita com o Vite 6 usado no build.

## O que falta, na ordem

1. `src/paineis/Workspace.tsx` (C7) — árvore da pasta com metadados inline; depende de
   `workspace.abrir` e do diálogo de pasta no processo main.
2. `src/componentes/Doctor*.tsx` (C8) e `src/componentes/EstadoVazio.tsx` (C9).
3. `src/paleta/PaletaComandos.tsx` (C10) e os atalhos de F1-02.
4. `tests/visual/` (C11) — contraste com `axe-core` (ainda não é dependência) e varredura de
   `prefers-reduced-motion`.
5. Chat, preview e galeria: M4, M6 e M7 — dependem de eventos que o núcleo ainda não emite.

## Arquitetura

```
app/
  index.html                 #raiz, tema escuro no HTML, CSP sem origem externa
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
    main.tsx                 monta o React; fontes → tokens → reset; tema escuro default
    App.tsx                  tema salvo + banner UI-001 com "reiniciar o núcleo"
    layout/                  AppShell (4 painéis), TopoApp, Divisor
    componentes/             BarraProgressoJob
    estado/                  eventos.ts, ponte.ts, progressoJob.ts, preferencias.ts, tema.ts
    motion/                  tokens.ts, useReducedMotion.ts
    estilos/                 tokens.css, reset.css, fontes/
  tests/                     ponte.test.ts, barra-progresso-job.test.tsx
```

### Fronteiras respeitadas

- O renderer **não** recebe `fs`, `child_process` nem caminho absoluto: só métodos NDJSON
  (fronteira 1 de F1-01). `contextIsolation: true`, `sandbox: true`, `nodeIntegration: false`.
- O transporte é stdio, nunca porta TCP (AP-14).
- Núcleo caído → `UI-001`, com as requisições pendentes **rejeitadas**, não penduradas; a ponte
  tenta 3 reinícios automáticos antes de ficar em `caido`, e o banner do `App` chama `reiniciar()`.
- Fora do Electron (vitest, `vite dev` no navegador) a ponte é no-op explícito: nenhuma tela finge
  que o núcleo respondeu.

### Honestidade de progresso (AP-07)

`BarraProgressoJob` só desenha barra e porcentagem quando chega `job.progresso` — o único evento
que o núcleo emite hoje (A9, v0.4.0). Sem evento, o texto é "gerando…", sem número. `pct` vem do
evento e é monotônico; não há `setInterval` em `src/motion/` nem em `src/componentes/`.

## Comandos

```bash
cd Fase_1_Desktop/app
pnpm install
pnpm typecheck        # tsc -b (projetos app + node)
pnpm test             # vitest run — 17 testes
pnpm build            # renderer (Vite) + main/preload (esbuild)
pnpm dev              # servidor Vite em :5273
pnpm dev:electron     # compila main/preload e abre a janela
```

O `pnpm dev:electron` procura o Python em `../nucleo/.venv/`; se não achar, cai em `python3` do
`PATH`. Rode `pip install -e ".[dev]"` no núcleo antes, senão a ponte sobe direto para `UI-001`.
