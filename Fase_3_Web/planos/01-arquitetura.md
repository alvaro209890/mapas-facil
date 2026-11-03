# W-01 — Arquitetura

## Objetivo

Fixar as peças da Fase 3, quem fala com quem, por qual protocolo, onde cada byte mora e o que é
reaproveitado do desktop. Os planos 02–13 implementam o que está aqui; se um deles divergir,
**este ganha** e a divergência é corrigida no mesmo commit.

## Estado atual vs alvo

| Peça | Estado | Nota |
|---|---|---|
| Núcleo `mapasfacil_nucleo` | **existe** (v0.4.x, 47 métodos NDJSON, 10 eventos) | ganha "modo servidor" no W1 ([W-04](04-ponte-nucleo-servidor.md)) |
| Ponte NDJSON | **existe em TypeScript** (`Fase_1_Desktop/app/electron/nucleo/ponte.ts`) | é portada para Python asyncio no W2 |
| Backend HTTP | **ausente** | `Fase_3_Web/servidor/` |
| App web | **ausente** | `Fase_3_Web/web/` |
| Componentes de chat React | **existem no desktop** (`Fase_1_Desktop/app/src/componentes/`, `src/estado/`, `src/chat/`) | copiados com proveniência no W6 |
| Motor PDF nativo | **existe** (A4 retrato/paisagem) | ganha folhas no W9 |
| Motor `.mxd` T2 (patch por offset sentinela) | **existe** (`motores/patch_mxd.py`) | é a base do motor binário do W10 |
| Biblioteca binária MXD | **existe fora do repo** (`C:\GIS\MXD_RE\ferramentas\{cfbf,mxd_bin}.py`) | é trazida para o núcleo no W10 |

## Diagrama

```
┌──────────────── navegador ─────────────────┐
│ web/ (SPA React 19)                         │
│  ├─ telas: Entrar · Projetos · NovoMapa ·   │
│  │         Projeto · Admin                  │
│  ├─ estado/ (zustand)  ◀── SSE ──┐          │
│  └─ palco/ (MapLibre + SVG + motion)        │
└──────────────┬─────────────────────┬────────┘
               │ fetch /api/v1/…     │ EventSource /api/v1/projetos/{id}/eventos
               ▼                     │
        Cloudflare Tunnel (mapasfacil-app.cursar.space → 127.0.0.1:3130)
               ▼                     │
┌──────────── server-desktop ─────────────────────────────────────────────┐
│ mapasfacil_servidor (FastAPI, 1 processo uvicorn, 127.0.0.1:3130)        │
│  ├─ api/        rotas REST (auth, projetos, uploads, mensagens, versões) │
│  ├─ eventos/    log por projeto (NDJSON em disco) + fan-out SSE          │
│  ├─ ponte/      pool de workers, allowlist de métodos, timeouts          │
│  ├─ importacao/ montagem de partes, verificação e extração segura do ZIP │
│  ├─ banco/      SQLite WAL: usuários, sessões, projetos, versões         │
│  └─ estaticos/  serve o build do web/ em "/"                             │
│        │ stdin/stdout NDJSON (1 processo por projeto ativo)              │
│        ▼                                                                │
│  python -m mapasfacil_nucleo  (MAPASFACIL_MODO=servidor)                 │
│   ├─ workspace = dados/projetos/<id>/                                    │
│   ├─ agente (ag/gemini-3.8-flash-high) ──tailnet──▶ 9Router VPS :20128   │
│   ├─ camadas (WFS/WMS SEMA, IBAMA, FUNAI, INCRA, MapBiomas, Planet)      │
│   ├─ motores: nativo (PDF) · binário (.mxd) · quantitativos (.xlsx)      │
│   └─ vagas de job: dados/vagas/*.lock (flock) — no máximo N gerações     │
│                                                                          │
│  disco: /home/server/mapasfacil → HD Backup (1,9 TB)                     │
└──────────────────────────────────────────────────────────────────────────┘
```

## Modelo de processos

| Processo | Quantos | Vive quanto | Quem inicia |
|---|---|---|---|
| `mapasfacil_servidor` (uvicorn) | 1 | sempre (systemd `--user`) | systemd |
| worker `mapasfacil_nucleo` | 0..`MF_MAX_WORKERS` (padrão 6) | do primeiro pedido do projeto até `MF_WORKER_OCIOSO_S` (padrão 900 s) sem atividade | ponte, sob demanda |
| `cloudflared` (túnel do app) | 1 | sempre | systemd |

Por que **um processo por projeto** e não o núcleo importado como biblioteca:

1. o núcleo tem estado de processo (workspace aberto, índice, conversa ativa, MapSpec em memória
   — ver `agente/tools.py::_estado`). Importar como biblioteca obrigaria a reescrever esse estado
   como "por requisição", tocando metade do núcleo;
2. isolamento: matplotlib/GDAL/geopandas vazando memória ou travando derruba **um** projeto,
   não o servidor;
3. o `fsguard` já confina leitura/escrita a uma raiz — a raiz é a pasta do projeto;
4. é exatamente o protocolo que o Electron usa: o mesmo teste de contrato vale para os dois.

Custo aceito: ~300–600 MB por worker com geopandas+matplotlib carregados. Com 15 GB de RAM no
server e teto de 6 workers, sobra folga para o resto da frota.

## Fluxos principais (sequência)

### Criar projeto e importar

```
web            servidor                              worker(núcleo)
 │ POST /projetos {nome, folha}                         │
 │──────────────▶ cria linha + pasta dados/projetos/<id>/
 │◀────────────── 201 {projeto, estado:"aguardando_zip"}
 │ POST /uploads {nome,tamanho}                         │
 │ PUT  /uploads/{u}/partes/{n}  (×k, 8 MiB cada)       │
 │ POST /uploads/{u}/concluir {hash_partes}             │
 │ POST /projetos/{id}/importacao {upload_id}           │
 │──────────────▶ verifica sha256 → extrai seguro em <id>/entrada/
 │   SSE importacao.progresso (por arquivo)             │
 │               ├─ spawn worker ──────────────────────▶│ (modo servidor)
 │               ├─ workspace.abrir {pasta:<id>} ──────▶│ indexa, lê recibo
 │   SSE nucleo: workspace.mudou, viewport.foco ◀───────│
 │               ├─ chat.criar_conversa ───────────────▶│
 │   SSE projeto.estado {estado:"pronto", resumo}       │
```

### Turno de chat que gera mapa

```
web            servidor                              worker(núcleo)
 │ POST /projetos/{id}/mensagens {texto}                │
 │──────────────▶ grava log, chat.enviar ──────────────▶│ orquestrador (9Router/Gemini)
 │   SSE chat.raciocinio / chat.delta ◀─────────────────│
 │   SSE chat.tool {nome:"criar_mapa"} ◀────────────────│
 │   SSE mapspec.atualizado {versao:1} ◀────────────────│
 │   SSE chat.tool {nome:"gerar_mapa"} ◀────────────────│ pega vaga (flock)
 │   SSE viewport.foco nivel=estado/municipio/imovel ◀──│
 │   SSE camada.renderizada (×n) ◀──────────────────────│
 │   SSE job.progresso (10 etapas) ◀────────────────────│
 │   SSE layout.elemento (×m) ◀─────────────────────────│ motor nativo desenha
 │   SSE job.artefato_parcial {tipo:"pdf"} ◀────────────│
 │   SSE chat.delta (resumo final) ◀────────────────────│
 │   SSE nucleo.res {req_id, ok} ◀──────────────────────│
 │               └─ registra versão no banco            │
```

## Estrutura de pastas a criar

```
Fase_3_Web/
├── README.md
├── planos/                         (estes arquivos)
├── servidor/
│   ├── pyproject.toml              # pacote mapasfacil_servidor; depende do núcleo por caminho
│   ├── mapasfacil_servidor/
│   │   ├── __init__.py             # __version__
│   │   ├── __main__.py             # CLI: serve | conta criar | conta listar | migrar | limpar-lixeira
│   │   ├── config.py               # leitura de env (tabela abaixo), validação no boot
│   │   ├── erros.py                # ErroServidor(codigo, mensagem, status_http, detalhes)
│   │   ├── app.py                  # FastAPI(): rotas, middlewares, estáticos
│   │   ├── banco/
│   │   │   ├── conexao.py          # sqlite3 WAL, foreign_keys=ON, busy_timeout
│   │   │   ├── migracoes/0001_inicial.sql …
│   │   │   └── repositorios.py     # usuarios, sessoes, projetos, versoes, uploads, auditoria
│   │   ├── auth/
│   │   │   ├── senhas.py           # reusa mapasfacil_nucleo.contas.senha (Argon2id)
│   │   │   ├── sessoes.py          # token 256 bits, hash sha256 no banco, cookie
│   │   │   ├── csrf.py
│   │   │   └── limitador.py        # anti-abuso de login (não é quota — D18)
│   │   ├── api/
│   │   │   ├── auth.py  admin.py  projetos.py  uploads.py
│   │   │   ├── mensagens.py  versoes.py  arquivos.py  bases.py  saude.py
│   │   ├── importacao/
│   │   │   ├── partes.py           # montagem e sha256 das partes
│   │   │   └── extrair.py          # zip-slip, zip-bomba, allowlist de extensões
│   │   ├── eventos/
│   │   │   ├── vocabulario.py      # frozenset dos eventos do servidor
│   │   │   ├── log.py              # append NDJSON com seq por projeto
│   │   │   └── sse.py              # fan-out, replay, heartbeat
│   │   ├── ponte/
│   │   │   ├── worker.py           # 1 processo núcleo: spawn, stdin/stdout, timeouts
│   │   │   ├── pool.py             # mapa projeto→worker, teto, ociosidade
│   │   │   ├── allowlist.py        # métodos do núcleo que o servidor pode chamar
│   │   │   └── fake_nucleo.py      # núcleo falso para testes (roteiro de eventos)
│   │   └── estaticos.py            # serve web/dist com fallback SPA
│   └── tests/
├── web/
│   ├── package.json  vite.config.ts  tsconfig.json  index.html
│   └── src/
│       ├── main.tsx  App.tsx  rotas.tsx
│       ├── api/          cliente.ts (fetch+CSRF) · eventos.ts (EventSource+replay) · tipos.ts
│       ├── estado/       sessao.ts · projetos.ts · projetoAtivo.ts · chat.ts · job.ts · palco.ts
│       ├── telas/        Entrar.tsx · Projetos.tsx · NovoMapa/ · Projeto.tsx · Admin.tsx
│       ├── herdados/     componentes copiados do desktop (com cabeçalho de proveniência)
│       ├── palco/        Palco.tsx · Camera.ts · Camadas.ts · Folha.tsx · coreografia.ts
│       ├── estilos/      tokens.css (do desktop) · fontes/
│       └── motion/       tokens.ts · useReducedMotion.ts (do desktop)
├── deploy/
│   ├── mapasfacil-app.service      # systemd --user
│   ├── mapasfacil-app-tunnel.service
│   ├── mapasfacil-app-tunnel.yml.example
│   └── scripts/  preflight.sh · atualizar.sh · backup.sh · rollback.sh
└── fixtures/
    ├── gerar_zip_sintetico.py      # monta ZIP fictício (ATP/AVN/AC/AUAS + recibo falso sem CPF)
    └── README.md
```

## Configuração do servidor (env)

Lidas em `config.py`; o boot **falha** com mensagem clara se uma obrigatória faltar.

| Variável | Padrão | Obrigatória | Para quê |
|---|---|---|---|
| `MF_RAIZ` | `/home/server/mapasfacil` | sim | raiz de dados (symlink para o HD) |
| `MF_HOST` / `MF_PORTA` | `127.0.0.1` / `3130` | — | bind do uvicorn (nunca `0.0.0.0`) |
| `MF_URL_PUBLICA` | `https://mapasfacil-app.cursar.space` | sim em produção | cookies `Secure`, CORS fechado, links |
| `MF_PYTHON_NUCLEO` | `<venv>/bin/python` | sim | intérprete dos workers |
| `MF_MAX_WORKERS` | `6` | — | teto de processos núcleo vivos |
| `MF_MAX_JOBS` | `2` | — | vagas simultâneas de geração (flock) |
| `MF_WORKER_OCIOSO_S` | `900` | — | mata worker ocioso |
| `MF_TIMEOUT_REQ_S` | `1800` | — | teto de uma requisição ao núcleo (série de 20 mapas cabe) |
| `MF_UPLOAD_MAX_MB` | `2048` | — | tamanho máximo do `.zip` |
| `MF_UPLOAD_PARTE_MB` | `8` | — | tamanho da parte (Cloudflare corta corpo > 100 MB) |
| `MF_EXTRAIDO_MAX_MB` | `8192` | — | teto do conteúdo descompactado (anti zip-bomba) |
| `MF_SEGREDOS` | `$MF_RAIZ/segredos/servidor.env` | sim | arquivo 600 com chaves (9Router do Mapas Fácil, SEMA, Planet; DeepSeek só se usar o provedor alternativo) |
| `MF_ADMIN_EMAIL` | — | só no primeiro boot | marca como admin a conta com esse e-mail (fica no `servidor.env`, nunca no repo público) |

Variáveis que o servidor **injeta** em cada worker (o núcleo já lê todas estas, salvo as
marcadas como novas — ver [W-04](04-ponte-nucleo-servidor.md)):

| Variável | Valor | Já existe no núcleo? |
|---|---|---|
| `MAPASFACIL_MODO` | `servidor` | **nova** (W1) |
| `MAPASFACIL_DADOS` | `<projeto>/.estado` | sim (`dados.py`) |
| `MAPASFACIL_CHATS_DIR` | `<projeto>/.estado/chats` | sim (`conversas/banco.py`) |
| `MAPASFACIL_CONTAS_DIR` | `<projeto>/.estado/contas` (não usado em modo servidor) | sim |
| `MAPASFACIL_CACHE_DIR` | `$MF_RAIZ/dados/cache` (compartilhado entre projetos) | sim |
| `MAPASFACIL_ACERVO_RASTERS` | `$MF_RAIZ/dados/acervo_rasters` (compartilhado) | sim |
| `MAPASFACIL_SESSAO_SERVIDOR` | id do usuário dono do turno | **nova** (W1) |
| `MAPASFACIL_VAGAS_DIR` / `MAPASFACIL_MAX_JOBS` | `$MF_RAIZ/dados/vagas` / `2` | **novas** (W1) |
| `MAPASFACIL_TEMPLATES_DIR` | `$MF_RAIZ/dados/templates` (variantes de folha) | **nova** (W10) |
| `MAPASFACIL_PROVEDOR`, `MAPASFACIL_PROVEDOR_URL`, `MAPASFACIL_PROVEDOR_CHAVE`, `MAPASFACIL_MODELO_CHAT`, `MAPASFACIL_MODELO_RAPIDO`, `MAPASFACIL_RACIOCINIO` | `openai_compat`, `http://100.104.255.35:20128/v1`, chave do Mapas Fácil no 9Router, `ag/gemini-3.8-flash-high` (os dois), `high` — [W-05](05-chat-agente-web.md) | **novas** (W1/W5) |
| `MAPASFACIL_SEMA_AUTHKEY`, `MAPASFACIL_PLANET_API_KEY` (e `MAPASFACIL_DEEPSEEK_API_KEY` se o provedor for `deepseek`) | do `servidor.env` | **novas** (W1 — o cofre lê env em modo servidor) |

## Prefixos de código de erro

Os prefixos do núcleo (`NU-`, `AG-`, `IA-`, `UI-`, `AUTH-`) continuam. A Fase 3 acrescenta:

| Prefixo | Faixa | Dono |
|---|---|---|
| `SV-0xx` | autenticação, sessão, permissão | `servidor/auth`, `servidor/api` |
| `SV-1xx` | upload e importação | `servidor/importacao` |
| `SV-2xx` | workers, fila, timeouts | `servidor/ponte` |
| `SV-3xx` | eventos/SSE | `servidor/eventos` |
| `SV-4xx` | arquivos e downloads | `servidor/api/arquivos.py` |
| `NU-3xx` | folha, perfil derivado, enquadramento | núcleo (W1, W9, W11) |
| `MX-0xx` | motor `.mxd` binário | núcleo `mxd_binario/` (W10) |
| `WB-0xx` | erros só do navegador (EventSource caiu, WebGL ausente) | `web/` |

Formato do corpo de erro HTTP (igual ao `ErroNucleo.para_dict()` do núcleo, mais `status`):

```json
{ "erro": { "codigo": "SV-104", "mensagem": "O .zip tem um caminho que sai da pasta (../).",
            "porque": "Arquivos com '..' podem sobrescrever outros projetos.",
            "o_que_fazer": "Gere o .zip de novo a partir da pasta do imóvel.",
            "detalhes": { "entrada": "../../etc/x.shp" } } }
```

## Matriz de reaproveitamento

| Do desktop | Como entra na Fase 3 |
|---|---|
| `mapasfacil_nucleo` inteiro | **como está**, com modo servidor (W1) |
| `contas/senha.py` (Argon2id) | importado pelo servidor |
| `electron/nucleo/ponte.ts` + `protocolo.ts` | **portados** para `servidor/ponte/` (mesma semântica: req/res/evt, timeouts, reinício) |
| `src/estado/*.ts` (eventos, progressoJob, mapspecVersoes, artefatos, logJob, conversas) | copiados para `web/src/estado/`; a fonte de eventos troca de IPC para SSE |
| `src/componentes/*` do chat (BolhaMarkdown, CartaoTool, GrupoTools, CartaoPergunta, IndicadorPensando, BlocoRaciocinio, LinhaVersoes, BarraProgressoJob, CampoEntrada, EstadoVazio) | copiados para `web/src/herdados/` |
| `src/estilos/tokens.css`, fontes woff2 + OFL | copiados |
| `src/motion/tokens.ts`, `useReducedMotion.ts` | copiados e estendidos (W8) |
| `src/telas/Login.tsx` (cena de mapa animada) | adaptado para `web/src/telas/Entrar.tsx` |

Toda cópia leva no topo: `// Origem: Fase_1_Desktop/app/src/<caminho> @ <hash do commit>`.
Unificar num pacote compartilhado fica **fora** da Fase 3 (risco de quebrar o build do desktop).

## Dependências (versões exatas são fixadas no W0 e nunca com `^`/`~`)

| Lado | Pacote | Uso |
|---|---|---|
| servidor | `fastapi`, `uvicorn[standard]`, `python-multipart`, `argon2-cffi` (já no núcleo), `python-ulid` (já no núcleo) | API |
| servidor (testes) | `pytest`, `pytest-asyncio`, `httpx` | anel 1/2 |
| web | `react@19`, `react-dom@19`, `zustand@5` (iguais ao desktop), `vite`, `typescript` | app |
| web | `maplibre-gl` | câmera e camadas vetoriais (licença BSD-3, sem token) |
| web | `motion` (ex-Framer Motion) | montagem da folha e transições de tela |
| web (testes) | `vitest`, `@testing-library/react`, `@playwright/test` | anéis 1–3 |
| sistema (server) | `gdal-bin` (ogr2ogr), `fonts-liberation`, Python 3.12 | o núcleo já usa ogr2ogr e cai para Liberation Sans quando não há Arial |

## Critérios de aceite deste plano

- [ ] Todo arquivo citado na árvore acima existe ao fim do marco que o cria (ver [W-15](15-checklist-implementacao.md)).
- [ ] `grep -rn "0.0.0.0" Fase_3_Web/servidor Fase_3_Web/deploy` → vazio.
- [ ] `python -m mapasfacil_servidor serve` sem `MF_SEGREDOS` falha com `SV-000` e mensagem que diz qual arquivo falta.
- [ ] Nenhum módulo em `Fase_3_Web/servidor` importa `mapasfacil_nucleo.motores`, `.camadas`, `.quantitativos` ou `.agente` (só `contas.senha` e utilitários puros). Teste: `tests/test_fronteira_nucleo.py` varre os imports.

## Fora de escopo

- Kubernetes, Docker para o app, filas externas (Redis/RQ/Celery): um processo + flock resolve o porte de um escritório.
- Múltiplos servidores.
- CDN própria para o SPA (o túnel serve).

## Anti-padrões

Os de [W-00](00-visao-e-decisoes.md) §Anti-padrões (AW-01…AW-08) + AP-01…AP-15 do `AGENT_BRIEF.md`.
