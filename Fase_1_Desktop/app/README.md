# app/ — shell Electron + React (Fase 1, bloco C + D + F)

Planos: [F1-02](../planos/02-ui-chat-e-workspace.md) (layout e comportamento),
[F1-16](../planos/16-design-system-dark.md) (tokens, tipografia, animações),
[F1-15](../planos/15-galeria-de-modelos.md) (galeria / M4),
[F1-17](../planos/17-persistencia-de-conversas.md) (chats / M6),
[F1-01](../planos/01-arquitetura.md) (protocolo NDJSON e fronteiras).

## Estado — 2026-07-26

**Blocos C (M3), D (M4), F (M6), G (M7) e H (M8) fechados/parciais + A12.** A janela abre, conecta pasta, indexa,
mostra doctor, responde a `Ctrl+K`/atalhos, lista a galeria, monta MapSpec, mantém histórico local
de conversas (`barra-chats`, `Ctrl+N` / `Ctrl+F`), conversa com o agente (streaming, cartões de
tool, "Parar") e mostra o `painel-preview` acompanhando a geração — esqueleto de camadas por
`job.progresso` e imagem real por `job.artefato_parcial`. O workspace atualiza sozinho via
`workspace.mudou` (debounce 500 ms) com realce de arquivo novo. `pnpm typecheck`, `test` e `build` verdes.

O que ainda **não** existe: menus/tray do processo main; microinteração A6 de troca de versão
(`mapspec.atualizado` ainda sem emissor — não simulada, AP-07).

| # | Tarefa (F1-13 bloco C) | Estado | Onde |
|---|---|---|---|
| C1 | Scaffold Electron + Vite + React 19 + TS | **feito** | `index.html`, `src/main.tsx`, `src/App.tsx`, `package.json`, `vite.config.ts`, `vitest.config.ts`, `tsconfig*.json`, `electron/main.ts`, `electron/preload.ts` |
| C2 | Ponte NDJSON (spawn, reinício, `UI-001`) | **feito** | `electron/nucleo/ponte.ts` + `tests/ponte.test.ts` |
| C3 | Tokens de cor, tipografia e movimento | **feito** | `src/estilos/tokens.css`, `src/estilos/reset.css`, `src/motion/tokens.ts` |
| C4 | Fontes embarcadas | **feito** | `src/estilos/fontes/` (+ licenças OFL) |
| C5 | `AppShell` com 4 painéis redimensionáveis | **feito** | `src/layout/AppShell.tsx`, `TopoApp.tsx`, `Divisor.tsx`, `src/estado/preferencias.ts` |
| C6 | `barra-progresso-job` consumindo `job.progresso` | **feito** | `src/componentes/BarraProgressoJob.tsx`, `src/estado/progressoJob.ts` + teste |
| C7 | `painel-workspace` com metadados inline | **feito** | `src/paineis/Workspace.tsx`, `src/estado/workspace.ts`, `src/formato/numeros.ts`, `electron/projetos.ts` + diálogo em `electron/main.ts` |
| C8 | `doctor-resumo` + diagnóstico completo | **feito** | `src/componentes/DoctorResumo.tsx`, `src/estado/doctor.ts` |
| C9 | Estados vazios e de erro | **feito** | `src/componentes/EstadoVazio.tsx` |
| C10 | Paleta `Ctrl+K` + atalhos | **feito** | `src/paleta/`, `src/componentes/Preferencias.tsx`, `tests/paleta-comandos.test.tsx` |
| C11 | Testes de tema, contraste e reduced-motion | **feito** | `tests/visual/` + `axe-core` |

| # | Tarefa (F1-13 bloco D) | Estado | Onde |
|---|---|---|---|
| D8 | `painel-galeria` + detalhe + `CartaoModelo` | **feito** | `src/paineis/Galeria*.tsx`, `src/componentes/CartaoModelo.tsx`, `src/estado/galeria.ts`, `tests/galeria.test.tsx` |

| # | Tarefa (F1-13 bloco F) | Estado | Onde |
|---|---|---|---|
| F6 | `barra-chats` + busca + filtro pasta | **feito** | `src/paineis/BarraChats.tsx`, `src/estado/conversas.ts`, `tests/barra-chats.test.tsx` |

### Conectar pasta — onde cada coisa acontece

```
renderer  "quero conectar"        →  window.mapasfacil.conectarPasta()
main      dialog.showOpenDialog      (só o main tem dialog e o caminho absoluto)
main      ponte.chamar("workspace.abrir", {caminho})
núcleo    WorkspaceGuard(raiz) + varredura            ← allowlist do fsguard
main      registra o projeto recente em config.json
renderer  recebe o índice pronto e desenha a árvore
```

O renderer não abre arquivo, não recebe `fs` e não manda caminho de disco: reabrir um projeto
recente é `abrirProjetoRecente(indice)`, e quem traduz índice → caminho é o main.

A12: o watcher do núcleo emite `workspace.mudou` (debounce 500 ms) e a árvore atualiza sozinha,
com realce de 2 s em arquivo novo. O botão de reindexar permanece como fallback.

### O que as rodadas de C1–C9 mudaram no que já existia

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
- `electron/main.ts` — **defeito corrigido**: `CANAL_ESTADO` só saía em transição de estado, e o
  renderer monta depois; quem abrisse a janela com o núcleo já pronto nunca recebia o estado.
  Agora o estado atual vai junto no `did-finish-load`.
- `src/paineis/Workspace.tsx` — o `doctor-resumo` sumia enquanto não havia pasta conectada.
  Achado pelo teste de fumaça do shell; o estado do ambiente é justamente o que interessa antes
  de conectar.

## O que falta, na ordem

1. Menus e tray do processo main (F1-02 ainda marca isso como parcial).
2. Aviso de arquivo novo no chat (sistema) — o evento já traz `resumo`; falta gravar no transcript.
3. Microinteração A6 de troca de versão (`mapspec.atualizado`).

## Arquitetura

```
app/
  index.html                 #raiz, tema escuro no HTML, CSP sem origem externa
  electron/                  processo main — Node, sem acesso do renderer
    main.ts                  janela 1280×800 mín., tema escuro, IPC, ciclo da ponte, diálogo de pasta
    projetos.ts              projetos recentes em config.json (o renderer só vê índice + nome)
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
    paineis/                 Workspace (árvore), Galeria + GaleriaDetalhe (M4)
    componentes/             BarraProgressoJob, DoctorResumo, EstadoVazio, Preferencias, CartaoModelo
    paleta/                  PaletaComandos + atalhos globais (C10)
    estado/                  eventos, ponte, progressoJob, workspace, doctor, preferencias, tema, galeria
    formato/                 numeros.ts (hectare pt-BR com 4 casas)
    motion/                  tokens.ts, useReducedMotion.ts
    estilos/                 tokens.css, reset.css, fontes/
  public/galeria/            cópia dos previews PNG para o Vite
  tests/                     ponte, barra, workspace, doctor, estado-vazio, app-shell, paleta,
                             galeria, visual/ (tema, contraste/axe, reduced-motion, layout) + fixtures/
```

### Fronteiras respeitadas

- O renderer **não** recebe `fs`, `child_process` nem caminho absoluto: só métodos NDJSON
  (fronteira 1 de F1-01). `contextIsolation: true`, `sandbox: true`, `nodeIntegration: false`.
- O transporte é stdio, nunca porta TCP (AP-14).
- Núcleo caído → `UI-001`, com as requisições pendentes **rejeitadas**, não penduradas; a ponte
  tenta 3 reinícios automáticos antes de ficar em `caido`, e o banner do `App` chama `reiniciar()`.
- Fora do Electron (vitest, `vite dev` no navegador) a ponte é no-op explícito: nenhuma tela finge
  que o núcleo respondeu.

### Fixtures dos testes

`tests/fixtures/*.json` **não são escritas à mão**: `tests/fixtures/gerar-fixture-workspace.py`
monta uma pasta com shapefiles de verdade, chama `workspace.abrir` e `doctor.rodar` e grava a
resposta. Assim a UI é testada contra o formato que o núcleo produz, e mudança de contrato quebra
o teste do app. Para regerar:

```bash
cd Fase_1_Desktop/nucleo
.venv/bin/python ../app/tests/fixtures/gerar-fixture-workspace.py
```

A raiz é reescrita para um caminho neutro e nenhum recibo do CAR entra na fixture (AP-09).

### Honestidade de progresso (AP-07)

`BarraProgressoJob` só desenha barra e porcentagem quando chega `job.progresso`. Sem evento, o
texto é "gerando…", sem número. `pct` vem do evento e é monotônico; não há `setInterval` em
`src/motion/` nem em `src/componentes/`.

O mesmo vale para o M8: o indicador "pensando" (A1) sai do estado real do turno, os cartões de
tool (A3) vêm de `chat.tool`, e o `painel-preview` (A5) só troca o esqueleto pela imagem quando
`job.artefato_parcial` traz um `preview_png` — cujos bytes são lidos pelo núcleo (`artefato.ler`),
nunca do disco pelo renderer. `tests/visual/motion-eventos.test.tsx` prova cada uma nas duas
metades: antes do evento não existe, depois do evento aparece.

## Comandos

```bash
cd Fase_1_Desktop/app
pnpm install
pnpm typecheck        # tsc -b (projetos app + node)
pnpm test             # vitest run — 73 testes
pnpm build            # renderer (Vite) + main/preload (esbuild)
pnpm dev              # servidor Vite em :5273
pnpm dev:electron     # compila main/preload e abre a janela
```

O `pnpm dev:electron` procura o Python em `../nucleo/.venv/`; se não achar, cai em `python3` do
`PATH`. Rode `pip install -e ".[dev]"` no núcleo antes, senão a ponte sobe direto para `UI-001`.
