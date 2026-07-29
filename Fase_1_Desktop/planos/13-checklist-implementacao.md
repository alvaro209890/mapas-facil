# F1-13 — Checklist de implementação

Lista operacional da Fase 1, por bloco. Complementa o [roadmap](12-roadmap.md), que dá a ordem e
os critérios de saída. **Quem fecha um item atualiza a caixa e a linha correspondente do gap
analysis em [`../../AGENT_BRIEF.md`](../../AGENT_BRIEF.md#gap-analysis--requisito--plano--estado--arquivo-a-editar) no mesmo commit.**

Legenda: `[x]` feito · `[~]` parcial (com nota) · `[ ]` não iniciado.

## Estado em 2026-07-29

| Bloco | Marco | Estado |
|---|---|---|
| A — fundação do núcleo | M1 | **fechado** — A1–A13 |
| A+ — quantitativos e validação | M1 | **fechado** exceto smoke visual (V3 — depende de motor bom / M9) |
| B — motor `.mxd` | M2 | **fechado** (2026-07-27) — template sem `!`, smoke T1/T2 Harmonia, B2 recalibrado (`ferramentas/fechar_m2_windows.ps1`) |
| C — shell + design system | M3 | **fechado** — C1–C11 + menus/tray + banner offline + Esc≠job |
| D — galeria | M4 | **fechado** |
| E — conta local (e-mail + senha) | M5 | **fechado** |
| F — conversas | M6 | **fechado** — F1–F7 + menu R14 completo |
| G — agente | M7 | **fechado** — 27/27 tools; F1-07 determinístico; API V4 sem visão (P1 negativa) |
| H — motion e preview | M8 | **fechado** — H1–H7 + H6 `mapspec.atualizado` |
| I — conformidade / instalador / piloto | M9–M11 | **M9 parcial** (2026-07-27) — pipeline checks + smoke; I1–I3 bloqueados por diff e série |
| J — Análise de área (série de 20 mapas) | — | **fechado no PDF** (2026-07-29) — 20/20 gerados na Aruanã, 19/20 aprovados na anatomia, publicados em `analises.cursar.space`. Falta card na galeria, progresso no front, Groq e os `.mxd` (Fase W) |

**Backlog desktop sem ArcMap: esgotado** (a série Análise de área foi a última coisa que dava
para fechar aqui). Ordem do que resta: **M9 → M10 → M11**. Fase 2 começa após M11.

**Operação no Windows:** [`../GUIA_WINDOWS.md`](../GUIA_WINDOWS.md) · handoff: [`../../docs/handoff-windows-fase1.md`](../../docs/handoff-windows-fase1.md).

## Pré-voo

- [x] Repositório em duas fases + planos comuns
- [x] Acervo `Mapas/01` (Harmonia), `02` (Trevisol), `03` (SIMCAR + L5)
- [x] Schema `MapSpec` + MANIFEST stub + fixture canônica
- [x] Chaves fora dos `.mxd` versionados
- [x] Núcleo Python com CI anel 1
- [x] `AGENT_BRIEF.md` + planos de auth, galeria, design system e conversas

---

## Bloco A — Fundação do núcleo (M1)

| # | Tarefa | Feito | Nota |
|---|---|---|---|
| A1 | Scaffold + NDJSON | [x] | |
| A2 | `fsguard` 100% cobertura | [x] | |
| A3 | Schema + validador + invariantes | [x] | CRS geo, pasta, minimapa, metadados, operadores `<>` |
| A4 | `workspace` abrir/reindexar/inspecionar | [x] | `id_local` = stem (sem colisão `ARL_*`) |
| A5 | Parser recibo CAR (sem CPF) | [x] | |
| A6 | CLI `doctor` | [x] | stub Linux; ArcMap/rede só no Windows |
| A7 | PDF nativo + `validacao.json` | [x] | ordem de desenho: menor `ordem` por cima |
| A8 | `pytest` + CI | [x] | anel 1 verde |
| **A9** | **Emissão de `job.progresso` nas 10 etapas** | [x] | v0.4.0 — `progresso.py` (etapas, pesos, `pct` monotônico), `protocolo.Emissor` + `Roteador.despachar(mensagem, emitir)`, `motores/gerar.py` nas 10 etapas com `item` nas camadas locais. `tests/test_job_progresso.py` (16 testes). Desbloqueia C6 e H1 |
| **A10** | `mapa.cancelar` com `taskkill /T /F` | [x] | `jobs.py`; cancel cooperativo + `taskkill` no Windows; loop NDJSON em thread para cancel chegar no meio |
| **A11** | `cofre.definir` / `existe` / `testar` | [x] | `cofre.py` via `keyring`; valor nunca no stdio; Preferências grava DeepSeek |
| **A12** | `workspace.mudou` (watcher, debounce 500 ms) | [x] | `workspace/watcher.py` + sink assíncrono; UI atualiza árvore + realce 2 s; `tests/test_workspace_watcher.py` |
| **A13** | `catalogo.listar` e `camada.resolver` | [x] | WFS em runtime (`wms_wfs`, 33/41 camadas — SEMA/FUNAI/MapBiomas/PRODES); `camadas/{catalogo,http,wfs,clip,cache,resolver}.py`; cache TTL por tema fora do workspace; `NU-101/102/110/120/130/140`; `consultar_sema`/`distancia_ate` saíram de `IA-022`. Os outros 3 tipos (`arcgis_rest`/`wfs_gml`/`wms_raster`) fecharam no épico seguinte — **41/41 camadas com cliente** |

## Bloco A+ — Quantitativos e validação (anel 1, sem ArcMap)

| # | Tarefa | Feito | Nota |
|---|---|---|---|
| Q1 | `quantitativos.calcular` a partir das camadas locais | [x] | áreas em ha, `TOTAL GERAL`, conferência com `MapSpec.tabela` |
| Q2 | Export `.xlsx` (F1-08) | [x] | abas Quantitativos, Detalhamento, Conferência, Avisos, Fontes |
| Q3 | `mapspec.diff` entre versões | [x] | diff por `id` de camada |
| Q4 | PNG da tabela ≥ 600 dpi (F1-08) | [x] | `recursos/tabela_quantitativos.png` |
| Q5 | Aba Conferência recibo × calculado | [x] | diferença em ha e % |
| Q6 | Overlay PNG da tabela no PDF nativo | [x] | posição Harmonia retrato; checks H14/S10 |
| V1 | `validacao.comparar_pdf` (diff raster B9) | [x] | PyMuPDF + numpy; tolerância 0,3% |
| V2 | Integração em `mapa.gerar` (`comparar_baseline`) | [x] | usa `baseline_pdf` do MANIFEST |
| V3 | Smoke Harmonia vs `Mapas/01` | [~] | `smoke_m9_harmonia.py`; diff ~81% — roteiro: [`docs/paridade-visual-harmonia.md`](../../docs/paridade-visual-harmonia.md) |

## Bloco J — Análise de área: a série de 20 mapas (anel 1, sem ArcMap)

Contrato: [`../../planos/GOAL_analise_de_area.md`](../../planos/GOAL_analise_de_area.md) ·
rodada: [`../../docs/analise-de-area-serie.md`](../../docs/analise-de-area-serie.md).

| # | Tarefa | Feito | Nota |
|---|---|---|---|
| J1 | Identidade do imóvel sem perguntar (município + CAR) | [x] | ponto-em-polígono na base IBGE local + maior IoU contra `car_atp`; lista branca de campos (AP-09) |
| J2 | Materializar as camadas da análise | [x] | 18 do catálogo, recorte no imóvel ou no extent, classe vira camada |
| J3 | Camadas derivadas que nenhum serviço publica | [x] | `AUAS − DLA`, anel de 3 km da UC, anel de 10 km da TI (aproximação declarada) |
| J4 | Anatomia medida dos 20 modelos | [x] | `ferramentas/medir_modelos_serie.py` → `shared/padrao-imap/anatomia_serie.json` |
| J5 | Cores amostradas dos modelos | [x] | `ferramentas/amostrar_cores_modelo.py`; corrigiu `ac` e `auas` |
| J6 | As 20 receitas (título, camadas, metadados, legenda) | [x] | `analise/serie.py` |
| J7 | Basemap por ano/sensor + recusa de cena furada | [x] | 43 mosaicos da SEMA; declara quando o ano pedido não existe |
| J8 | Executar a série sem que um mapa derrube os outros | [x] | `analise/executar.py`; relatório JSON por execução |
| J9 | PDF compilado na ordem de entrega | [x] | `Mapas/Analise_de_area.pdf`, 20 páginas |
| J10 | Validação de anatomia mapa a mapa | [x] | 19/20 verdes; a exceção é falta de dado (TCR), não de layout |
| J11 | Entrega ao cliente por link | [x] | `analises.cursar.space` — **sem senha**, ver [`../../docs/analise-entrega-cloudflare.md`](../../docs/analise-entrega-cloudflare.md) |
| J12 | Card "Análise de área" na galeria + progresso no front | [ ] | depende de destravar `galeria/estado.py` para saída nativa |
| J13 | Groq Vision na validação | [ ] | chave ainda não existe no cofre |
| J14 | Os 20 `.mxd` da série no Windows | [ ] | Fase W do GOAL — sem intervenção humana |

## Bloco B — Motor `.mxd` (M2)

**No Windows:** siga [`../GUIA_WINDOWS.md`](../GUIA_WINDOWS.md) §1.  
Detalhe histórico sem ArcMap: [`../nucleo/docs/bloco-b-sem-arcmap.md`](../nucleo/docs/bloco-b-sem-arcmap.md).

| # | Tarefa | Feito | Nota |
|---|---|---|---|
| B1 | Preparar template Dinâmica 2026 no ArcMap | [x] | **Fechado 2026-07-27**: script (`normalizar_mxd_arcpy` + `corrigir_template_b1_arcpy`) + GUI — `ROTULO_IMOVEL` criado à mão (arcpy não cria TextElement) e posicionado sobre o perímetro. `inspecionar_mxd_arcpy` confirma `pronto_b1: true` |
| B2 | MANIFEST `sha256` + offsets | [x] | `dinamica_retrato` **`status: pronto`** com offsets extent+escala (sentinelas pós-aspecto do ArcMap). **Recalibrado 2026-07-27** após o save da GUI do B1 — `sha256_ok`/`patch_ok` verdes no doctor. Backup: `Dinamica_retrato.pre_b2.bak` |
| B3 | `arcpy_job.py` + ponte | [x] | + minimapa IBGE (T1) |
| B4 | Materializar `SHP/` | [~] | cópia + `ogr2ogr` opcional |
| B5 | Extent bbox `.shp` | [~] | via metadados |
| B6 | Textos / definition query | [~] | T2 patch extent/escala ativo; textos UTF-16LE ainda sem slots no MANIFEST |
| B7 | Minimapa retângulo + guia | [x] | nomes canônicos + job T1 (`minimapa_job` / `mudar_municipio`) |
| B8 | Patch T2 sem ArcMap | [x] | offsets no MANIFEST; gera `.mxd` com extent/escala patchados |
| B9 | Diff raster vs `Mapas/01` | [~] | `comparar_pdf` + smoke M9; baseline no PDF ArcMap; Dinâmica ~81% |

---

## Bloco C — Shell Electron + design system (M3)

Planos: [F1-02](02-ui-chat-e-workspace.md), [F1-16](16-design-system-dark.md).
**A pasta `Fase_1_Desktop/app/` roda** — estado detalhado em
[`../app/README.md`](../app/README.md). Em 2026-07-26 o bloco C (M3) fechou: C1–C11
com `pnpm typecheck` → `test` → `build` verdes. Bloco D (M4) fechou em seguida (galeria).
Próximos marcos sem ArcMap: bloco I (conformidade/instalador/piloto) ou M2 quando houver ArcMap.

| # | Tarefa | Feito | Arquivo |
|---|---|---|---|
| C1 | Scaffold Electron + Vite + React 19 + TS | [x] | `app/index.html`, `app/src/main.tsx`, `app/src/App.tsx` + scaffold anterior; `pnpm install/typecheck/test/build` verdes (2026-07-26) |
| C2 | Ponte NDJSON com o sidecar (spawn, reinício, `UI-001`) | [x] | `app/electron/nucleo/ponte.ts` + `app/tests/ponte.test.ts` (7 testes com sidecar real). O teste achou e o commit corrigiu: `exit` de processo já substituído derrubava o novo após `reiniciar()` |
| C3 | Tokens de cor, tipografia e movimento | [x] | `app/src/estilos/tokens.css` (+ `reset.css`); escuro default, claro em `[data-tema="claro"]`, reduced-motion ≤ 80 ms |
| C4 | Fontes embarcadas (Space Grotesk, IBM Plex Sans/Mono) | [x] | `app/src/estilos/fontes/` — woff2 latin/latin-ext + `@font-face` + licenças OFL; zero CDN |
| C5 | `AppShell` com os 4 painéis redimensionáveis e persistidos | [x] | `app/src/layout/AppShell.tsx`, `TopoApp.tsx`, `Divisor.tsx`, `app/src/estado/preferencias.ts` — arrasto + teclado, larguras e colapso em `config.json`. Workspace (C7) + galeria (D8); chat/preview ainda honestos até M6/M7 |
| C6 | `barra-progresso-job` consumindo `job.progresso` | [x] | `app/src/componentes/BarraProgressoJob.tsx` + `app/src/estado/progressoJob.ts`; `app/tests/barra-progresso-job.test.tsx` (10 testes: sem evento não há barra, 10 etapas pt-BR, `pct` monotônico) |
| C7 | `painel-workspace` com metadados inline | [x] | `app/src/paineis/Workspace.tsx`, `app/src/estado/workspace.ts`, `app/src/formato/numeros.ts` + diálogo nativo e recentes em `app/electron/main.ts`/`projetos.ts`; `app/tests/workspace.test.tsx` (11 testes, fixture gerada pelo núcleo) |
| C8 | `doctor-resumo` + tela completa | [x] | `app/src/componentes/DoctorResumo.tsx` + `app/src/estado/doctor.ts`; resumo colapsado + diagnóstico completo em `<details>`, `app/tests/doctor-resumo.test.tsx` (8 testes). `sondar_arcpy` fica sob demanda (Windows) |
| C9 | Estados vazios e de erro (tabela de F1-02) | [x] | `EstadoVazio.tsx` — sem pasta/shapefile, `UI-001`, erro do núcleo, sem chave DeepSeek, sem ArcMap, **sem internet** (`useOnline` + banner); login/sessão cobertos em M5 |
| C10 | Paleta de comandos `Ctrl+K` + atalhos | [x] | `app/src/paleta/` (`PaletaComandos`, `comandos`, `useAtalhosGlobais`) + `Preferencias` (tema); atalhos Ctrl+O/K/N/F/, F1, Esc; `app/tests/paleta-comandos.test.tsx` (8 testes) |
| C11 | Testes de tema, contraste e reduced-motion | [x] | `app/tests/visual/` + `axe-core`; tokens AA, tema escuro default, reduced-motion ≤ 80 ms, layout 1280×800, hectares mono |

Fora da tabela, no mesmo marco: `app/src/motion/tokens.ts` e `useReducedMotion.ts` (F1-16
§Movimento) e `app/vitest.config.ts` separado do `vite.config.ts` — o `defineConfig` do Vitest 2
carrega os tipos do Vite 5 e conflita com o Vite 6 do build.

## Bloco D — Galeria (M4)

Plano: [F1-15](15-galeria-de-modelos.md).

| # | Tarefa | Feito | Arquivo |
|---|---|---|---|
| D1 | `modelos.json` com os 5 modelos + schema | [x] | `shared/galeria/modelos.json`, `schema.json`, `README.md` |
| D2 | Previews PNG extraídos de `Referencias_IMAP/Mapas/01/` | [x] | `shared/galeria/previews/` (+ cópia em `app/public/galeria/` para o renderer) |
| D3 | Carga e validação do catálogo | [x] | `nucleo/.../galeria/catalogo.py` |
| D4 | Cálculo de `status` (MANIFEST × índice) | [x] | `nucleo/.../galeria/estado.py` |
| D5 | `montar_mapspec` — os 13 passos determinísticos | [x] | `nucleo/.../galeria/montar.py` |
| D6 | Métodos `galeria.*` no roteador | [x] | `galeria.listar` / `detalhar` / `montar_mapspec` em `__main__.py` |
| D7 | Erros `NU-230`…`NU-234` | [x] | códigos usados em `catalogo`/`montar` via `ErroNucleo` |
| D8 | `painel-galeria` + `painel-galeria-detalhe` + `CartaoModelo` | [x] | `app/src/paineis/Galeria*.tsx`, `CartaoModelo.tsx`; `app/tests/galeria.test.tsx` |
| D9 | Testes de determinismo e de requisito ausente | [x] | `nucleo/tests/test_galeria.py` (9 testes) |

## Bloco E — Conta local (M5)

Plano: [F1-14](14-auth-e-conta.md). ([F2-05](../../Fase_2_Site/planos/05-auth-e-memoria.md) = Fase 2, **não** bloqueia.)

| # | Tarefa | Feito | Arquivo |
|---|---|---|---|
| E1 | Esquema `contas.sqlite` + migração (contas + sessoes_locais) | [x] | `nucleo/.../contas/` |
| E2 | Hash Argon2id + `conta.criar` / `conta.entrar` / `conta.sair` / `conta.estado` | [x] | idem |
| E3 | Restaurar sessão “lembrar neste PC” no boot | [x] | `contas/servico.restaurar_se_lembrada` no `loop_ndjson` |
| E4 | IPC via `nucleo:chamar` (`conta.*`) — senha não logada no renderer | [x] | `estado/auth.ts` + preload `chamar` |
| E5 | `tela-login` (criar + entrar) com marca hero | [x] | `app/src/telas/Login.tsx` |
| E6 | Store `auth` + guarda de rota | [x] | `app/src/estado/auth.ts`, `App.tsx` |
| E7 | `sessao.definir` / `sessao.estado` + gate `AUTH-030` | [x] | `nucleo/.../sessao.py` |
| E8 | Família de erros `AUTH-` (001, 002, 003, 030, 050, 070, 071) | [x] | via `ErroNucleo` nos handlers |
| E9 | Testes: criar/entrar, senha errada, e-mail duplicado, gate, senha ausente do arquivo | [x] | `test_conta_local.py`, `test_sessao.py`, `app/tests/login.test.tsx` |

## Bloco F — Persistência de conversas (M6)

Plano: [F1-17](17-persistencia-de-conversas.md).

| # | Tarefa | Feito | Arquivo |
|---|---|---|---|
| F1 | Esquema SQLite + FTS5 + triggers + migração 001 | [x] | `nucleo/.../conversas/esquema.sql`, `migracoes/001_inicial.sql` |
| F2 | Repositório (CRUD, WAL, transações) | [x] | `nucleo/.../conversas/repositorio.py`, `banco.py` |
| F3 | Redator de CPF/chaves **antes do INSERT** | [x] | `nucleo/.../conversas/redator.py` |
| F4 | Título automático + `title_manual` | [x] | `nucleo/.../conversas/titulo.py` |
| F5 | Os 9 métodos `chat.*` de histórico (+ `chat.gravar_mensagem` para modo determinístico) | [x] | `nucleo/.../conversas/servico.py` + `__main__.py` |
| F6 | `barra-chats` + busca + filtro por pasta + menu de contexto | [x] | `app/src/paineis/BarraChats.tsx`, `app/src/estado/conversas.ts`; menu R14 completo (renomear/arquivar/ramificar/apagar) em `app/tests/barra-chats-menu.test.tsx` |
| F7 | Testes: ciclo completo, escala, CPF ausente do arquivo, FTS, ramificar | [x] | `nucleo/tests/test_conversas.py`, `test_conversas_redator.py`, `app/tests/barra-chats.test.tsx` |
| F8 | Anexos no chat: 20 MB, cópia local, vínculo e histórico | [x] | `agente/anexos.py`, `conversas/repositorio.py`, `componentes/CampoEntrada.tsx`, `test_agente_anexos.py`, `campo-entrada.test.tsx` |

## Bloco G — Agente (M7)

Plano: [F1-06](06-agente-eng-florestal.md).

| # | Tarefa | Feito | Arquivo |
|---|---|---|---|
| G1 | Interface de provedor + cliente DeepSeek (stream, tools, cancelar) | [x] | `agente/provedor.py`, `deepseek.py`, `fake.py`, `chave.py` |
| G2 | `limites.py` com o orçamento de contexto | [x] | tetos F1-06; `tests/test_limites.py` |
| G3 | Montador de contexto + compressão (memória, transcript, diff) | [x] | `agente/contexto.py` |
| G4 | `compact_summary` com flash / heurística | [x] | `agente/resumo.py` (heurística no CI; LLM opcional) |
| G5 | Tools tipadas com schema de parâmetros (27 registradas) | [x] | 27/27 reais — `consultar_sema`/`distancia_ate` ligadas a `camada.resolver` (A13); `analisar_referencia` ligada a `agente/visao/` (F1-07, 2026-07-26) |
| G6 | System prompt versionado + teste de teto | [x] | `agente/prompt.py` |
| G7 | `chat.enviar` / `chat.cancelar` + eventos `chat.delta`/`chat.tool`/`chat.raciocinio` | [x] | `agente/orquestrador.py`, `servico.py`, `PainelChat.tsx` (botão “Parar”); reasoning só aparece se vier do provedor |
| G8 | Cassetes VCR + fixture de 120 turnos | [x] | `agente/vcr.py` + `tests/agente/cassetes/`; compressão 120 turnos em `test_agente.py` |
| G9 | Teste de vazamento (WKT, CPF, caminho, chave) | [x] | `tests/test_contexto_vazamento.py` |
| G10 | Teste de paridade galeria ↔ chat | [x] | `tests/test_agente.py::test_galeria_antes_de_criar_mapa` |
| G11 | Testes do loop: 12/13 rodadas, cancelamento com parcial, traces reais, passo do resumo | [x] | `tests/test_agente_orquestrador.py`, `tests/test_agente_tools.py`, `test_agente_vcr.py`, `app/tests/painel-chat.test.tsx` |
| G12 | `chat.pergunta` — agente pede escolha ao usuário em vez de chutar | [x] | **2026-07-27**, 9º evento do vocabulário. Shapefile sem papel canônico reconhecido vira pergunta com chips + campo livre, não `NU-233` seco. Resposta volta como mensagem do turno seguinte (sem estado de espera no backend). `protocolo.py`, `agente/tools.py`, `app/src/componentes/CartaoPergunta.tsx`, `PainelChat.tsx`. Ver [`../../docs/sessao-2026-07-27-pergunta-e-ui.md`](../../docs/sessao-2026-07-27-pergunta-e-ui.md) |

## Bloco H — Motion e preview de construção (M8)

Plano: [F1-16](16-design-system-dark.md).

| # | Tarefa | Feito | Arquivo |
|---|---|---|---|
| H1 | `job.artefato_parcial` no núcleo (4 tipos, caminho relativo) | [x] | `nucleo/.../artefatos.py`, `progresso.py`, `motores/gerar.py`, `motores/nativo.py`, `camadas/materializar.py` |
| H1b | `artefato.ler` — renderer lê o PNG **pelo núcleo** (fronteira 1) | [x] | `nucleo/.../leitor_artefato.py` |
| H2 | A1 pensando · A2 streaming · A3 tool | [x] | `componentes/IndicadorPensando.tsx`, `componentes/CartaoTool.tsx`, `paineis/PainelChat.tsx` |
| H3 | A4 progresso segmentado (10 etapas) | [x] | `app/src/componentes/BarraProgressoJob.tsx` (C6 + varredura do segmento ativo) |
| H4 | A5 fase 1 — esqueleto de camadas por `item` | [x] | `app/src/paineis/Preview.tsx` |
| H5 | A5 fase 2 — rasterização real com crossfade | [x] | `paineis/Preview.tsx` + `estado/artefatos.ts` |
| H6 | A6 microinterações | [x] | seleção na galeria (`CartaoModelo`), abas do painel direito, realce de arquivo novo (`workspace.mudou`) e **troca de versão** — `mapspec.atualizado` emitido em `agente/tools.py` (`_editar`/`criar_mapa`/`usar_modelo_da_galeria`) + `linha-versoes` (`estado/mapspecVersoes.ts`, `componentes/LinhaVersoes.tsx`) |
| H7 | Testes com evento injetado (≥ 3 animações) | [x] | `app/tests/visual/motion-eventos.test.tsx` (9), reduced-motion e axe estendidos, `nucleo/tests/test_artefato_parcial.py` (20) |
| H8 | Chat estilo Claude: timeline, markdown, tools/raciocínio retráteis e scrollbar dark | [x] | [`melhoria-front-chat/`](melhoria-front-chat/README.md), `app/src/chat/timeline.ts`, `BolhaMarkdown.tsx`, `GrupoTools.tsx`, `BlocoRaciocinio.tsx`, `scrollbar.css` |

## Bloco I — Conformidade, instalador, piloto (M9–M11)

**No Windows:** [`../GUIA_WINDOWS.md`](../GUIA_WINDOWS.md) §2–4.

| # | Tarefa | Feito |
|---|---|---|
| I1 | Série completa da Harmonia com 14 HARD verdes | [~] | 1/5 templates `pronto`; checks H01–H03/H06/H09/H10/S11 no validador |
| I2 | Diff raster < 0,3% contra os 21 PDFs-modelo | [ ] | medido ~81% (ArcMap) na Dinâmica 2026 — `output/m9_smoke_relatorio.json` |
| I3 | `.mxd` abrindo no ArcMap de outro PC | [ ] | paths relativos no T1; teste manual em outro PC pendente |
| I4 | PyInstaller onedir + `electron-builder` + NSIS | [ ] |
| I5 | Assinatura Authenticode + `sha256.txt` na release | [ ] |
| I6 | Auto-update N → N+1 | [ ] |
| I7 | Login funcionando a partir da build instalada | [ ] |
| I8 | Piloto instala, faz login e gera o primeiro mapa em < 15 min | [ ] |

---

## Regras de ouro

1. Nunca `Describe` / `replaceDataSource` / cursores no ArcPy desta família.
2. Geometria → `ogr2ogr`. Extent → header do `.shp`. Fonte → homônimo + `findAndReplaceWorkspacePaths`.
3. Baseline visual = `Referencias_IMAP/Mapas/01/`, nunca `02/`.
4. `ferramentas/chaves_mxd.py limpar` antes de qualquer commit que toque `.mxd`.
5. IA não gera código — só `MapSpec` validado.
6. Animação só existe amarrada a evento real do núcleo (AP-07).
7. Usuário autenticado não tem limite na v1 (AP-05 / D18).
8. CPF é descartado na entrada, nunca "filtrado na exibição" (AP-09).
9. Fechou item? Atualize esta tabela **e** o gap analysis do `AGENT_BRIEF.md` no mesmo commit.

## Leitura

1. [`../../AGENT_BRIEF.md`](../../AGENT_BRIEF.md)
2. [`01-arquitetura.md`](01-arquitetura.md)
3. [`12-roadmap.md`](12-roadmap.md)
4. O plano do bloco em que você vai trabalhar
5. [`04-motor-mxd.md`](04-motor-mxd.md) e [`DOCUMENTACAO_MXD_HARMONIA.md`](../../Referencias_IMAP/MXD/DOCUMENTACAO_MXD_HARMONIA.md) — só para o bloco B
