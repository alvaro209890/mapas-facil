# F1-13 — Checklist de implementação

Lista operacional da Fase 1, por bloco. Complementa o [roadmap](12-roadmap.md), que dá a ordem e
os critérios de saída. **Quem fecha um item atualiza a caixa e a linha correspondente do gap
analysis em [`../../AGENT_BRIEF.md`](../../AGENT_BRIEF.md#gap-analysis--requisito--plano--estado--arquivo-a-editar) no mesmo commit.**

Legenda: `[x]` feito · `[~]` parcial (com nota) · `[ ]` não iniciado.

## Estado em 2026-07-26

| Bloco | Marco | Estado |
|---|---|---|
| A — fundação do núcleo | M1 | **fechado** exceto A10–A13 (A9 fechou em 2026-07-26) |
| A+ — quantitativos e validação | M1 | **fechado** exceto smoke visual (V3) |
| B — motor `.mxd` | M2 | **parcial** — B1 estendido e **não testado** (sem arcpy neste ambiente) |
| C — shell + design system | M3 | **fechado** — C1–C11 (shell, workspace, doctor, estados, paleta `Ctrl+K`, testes visuais/axe) |
| D — galeria | M4 | **não iniciado** |
| E — conta e auth | M5 | **não iniciado** |
| F — conversas | M6 | **não iniciado** |
| G — agente | M7 | **não iniciado** |
| H — motion e preview | M8 | **não iniciado** |
| I — conformidade / instalador / piloto | M9–M11 | **não iniciado** |

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
| **A10** | `mapa.cancelar` com `taskkill /T /F` | [ ] | |
| **A11** | `cofre.definir` / `existe` / `testar` | [ ] | Credential Manager; nunca devolve valor |
| **A12** | `workspace.mudou` (watcher, debounce 500 ms) | [ ] | |
| **A13** | `catalogo.listar` e `camada.resolver` | [ ] | WFS/WMS em runtime |

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
| V3 | Smoke Harmonia vs `Mapas/01` | [ ] | infra pronta; baseline real ainda não passa (PDF nativo é estrutural) |

## Bloco B — Motor `.mxd` (M2)

Detalhe: [`../nucleo/docs/bloco-b-sem-arcmap.md`](../nucleo/docs/bloco-b-sem-arcmap.md).

| # | Tarefa | Feito | Nota |
|---|---|---|---|
| B1 | Preparar template Dinâmica 2026 no ArcMap | [~] | `normalizar_mxd_arcpy.py` estendido para reaproveitar elemento existente (`TITULO` ← caixa "Ano: NNNN", `ROTULO_IMOVEL` ← rótulo solto, `MINIMAPA_RETANGULO`/`MINIMAPA_GUIA` por heurística, `LOGO` com arquivo real); **não testado** — sem arcpy/Windows neste ambiente. GUI só para o que sobrar no relatório |
| B2 | MANIFEST `sha256` + offsets | [~] | `dinamica_retrato` com `sha256` e `status: parcial`; offsets dependem de B1 |
| B3 | `arcpy_job.py` + ponte | [x] | esqueleto |
| B4 | Materializar `SHP/` | [~] | cópia + `ogr2ogr` opcional |
| B5 | Extent bbox `.shp` | [~] | via metadados |
| B6 | Textos / definition query | [~] | infra UTF-16LE; falta MANIFEST |
| B7 | Minimapa retângulo + guia | [~] | candidatos por heurística; confirmar rodando no ArcMap |
| B8 | Patch T2 sem ArcMap | [~] | cópia do template preparado (`resolver_caminho_preparado`) |
| B9 | Diff raster vs `Mapas/01` | [~] | `validacao/comparar_pdf.py` + testes; smoke manual pendente |

---

## Bloco C — Shell Electron + design system (M3)

Planos: [F1-02](02-ui-chat-e-workspace.md), [F1-16](16-design-system-dark.md).
**A pasta `Fase_1_Desktop/app/` roda** — estado detalhado em
[`../app/README.md`](../app/README.md). Em 2026-07-26 o bloco C (M3) fechou: C1–C11
com `pnpm typecheck` → `test` (71) → `build` verdes. Próximo marco sem ArcMap: M4 galeria.

| # | Tarefa | Feito | Arquivo |
|---|---|---|---|
| C1 | Scaffold Electron + Vite + React 19 + TS | [x] | `app/index.html`, `app/src/main.tsx`, `app/src/App.tsx` + scaffold anterior; `pnpm install/typecheck/test/build` verdes (2026-07-26) |
| C2 | Ponte NDJSON com o sidecar (spawn, reinício, `UI-001`) | [x] | `app/electron/nucleo/ponte.ts` + `app/tests/ponte.test.ts` (7 testes com sidecar real). O teste achou e o commit corrigiu: `exit` de processo já substituído derrubava o novo após `reiniciar()` |
| C3 | Tokens de cor, tipografia e movimento | [x] | `app/src/estilos/tokens.css` (+ `reset.css`); escuro default, claro em `[data-tema="claro"]`, reduced-motion ≤ 80 ms |
| C4 | Fontes embarcadas (Space Grotesk, IBM Plex Sans/Mono) | [x] | `app/src/estilos/fontes/` — woff2 latin/latin-ext + `@font-face` + licenças OFL; zero CDN |
| C5 | `AppShell` com os 4 painéis redimensionáveis e persistidos | [x] | `app/src/layout/AppShell.tsx`, `TopoApp.tsx`, `Divisor.tsx`, `app/src/estado/preferencias.ts` — arrasto + teclado, larguras e colapso em `config.json`. Workspace real (C7); chat/galeria/preview ainda honestos até M4/M6/M7 |
| C6 | `barra-progresso-job` consumindo `job.progresso` | [x] | `app/src/componentes/BarraProgressoJob.tsx` + `app/src/estado/progressoJob.ts`; `app/tests/barra-progresso-job.test.tsx` (10 testes: sem evento não há barra, 10 etapas pt-BR, `pct` monotônico) |
| C7 | `painel-workspace` com metadados inline | [x] | `app/src/paineis/Workspace.tsx`, `app/src/estado/workspace.ts`, `app/src/formato/numeros.ts` + diálogo nativo e recentes em `app/electron/main.ts`/`projetos.ts`; `app/tests/workspace.test.tsx` (11 testes, fixture gerada pelo núcleo) |
| C8 | `doctor-resumo` + tela completa | [x] | `app/src/componentes/DoctorResumo.tsx` + `app/src/estado/doctor.ts`; resumo colapsado + diagnóstico completo em `<details>`, `app/tests/doctor-resumo.test.tsx` (8 testes). `sondar_arcpy` fica sob demanda (Windows) |
| C9 | Estados vazios e de erro (tabela de F1-02) | [x] | `app/src/componentes/EstadoVazio.tsx` — casos com dado real (sem pasta, sem shapefile, `UI-001`, erro do núcleo, sem chave DeepSeek, sem ArcMap); login/sessão/offline esperam M5 e camadas externas |
| C10 | Paleta de comandos `Ctrl+K` + atalhos | [x] | `app/src/paleta/` (`PaletaComandos`, `comandos`, `useAtalhosGlobais`) + `Preferencias` (tema); atalhos Ctrl+O/K/N/F/, F1, Esc; `app/tests/paleta-comandos.test.tsx` (8 testes) |
| C11 | Testes de tema, contraste e reduced-motion | [x] | `app/tests/visual/` + `axe-core`; tokens AA, tema escuro default, reduced-motion ≤ 80 ms, layout 1280×800, hectares mono |

Fora da tabela, no mesmo marco: `app/src/motion/tokens.ts` e `useReducedMotion.ts` (F1-16
§Movimento) e `app/vitest.config.ts` separado do `vite.config.ts` — o `defineConfig` do Vitest 2
carrega os tipos do Vite 5 e conflita com o Vite 6 do build.

## Bloco D — Galeria (M4)

Plano: [F1-15](15-galeria-de-modelos.md).

| # | Tarefa | Feito | Arquivo |
|---|---|---|---|
| D1 | `modelos.json` com os 5 modelos + schema | [ ] | `shared/galeria/` |
| D2 | Previews PNG extraídos de `Referencias_IMAP/Mapas/01/` | [ ] | `shared/galeria/previews/` |
| D3 | Carga e validação do catálogo | [ ] | `nucleo/.../galeria/catalogo.py` |
| D4 | Cálculo de `status` (MANIFEST × índice) | [ ] | `nucleo/.../galeria/estado.py` |
| D5 | `montar_mapspec` — os 13 passos determinísticos | [ ] | `nucleo/.../galeria/montar.py` |
| D6 | Métodos `galeria.*` no roteador | [ ] | `nucleo/.../__main__.py` |
| D7 | Erros `NU-230`…`NU-234` | [ ] | `nucleo/.../erros.py` |
| D8 | `painel-galeria` + `painel-galeria-detalhe` + `CartaoModelo` | [ ] | `app/src/paineis/` |
| D9 | Testes de determinismo e de requisito ausente | [ ] | `nucleo/tests/test_galeria.py` |

## Bloco E — Conta e autenticação (M5)

Planos: [F1-14](14-auth-e-conta.md), [F2-05](../../Fase_2_Site/planos/05-auth-e-memoria.md).

| # | Tarefa | Feito | Arquivo |
|---|---|---|---|
| E1 | Backend de identidade (FastAPI, `/auth/*`, `/health`) | [ ] | `Fase_2_Site/backend/` |
| E2 | Tabelas `contas`, `sessoes`, `codigos_desktop` | [ ] | idem |
| E3 | Site de login com botão Google | [ ] | `Fase_2_Site/web/` |
| E4 | Tunnel dedicado + systemd (sem tocar nos existentes) | [ ] | ver F2-06 |
| E5 | PKCE + servidor loopback efêmero | [ ] | `app/electron/auth/` |
| E6 | Tokens no Credential Manager; renovação a cada 30 min | [ ] | `app/electron/auth/tokens.ts` |
| E7 | IPC `auth:*` + guarda de rota | [ ] | `app/electron/ipc/auth.ts` |
| E8 | `tela-login` com marca hero | [ ] | `app/src/telas/Login.tsx` |
| E9 | `sessao.definir` / `sessao.estado` + gate `AUTH-030` | [ ] | `nucleo/.../sessao.py` |
| E10 | Família de erros `AUTH-` | [ ] | `nucleo/.../erros.py` |
| E11 | Testes: `state` divergente, refresh 401 vs rede caída, offline com token válido | [ ] | |

## Bloco F — Persistência de conversas (M6)

Plano: [F1-17](17-persistencia-de-conversas.md).

| # | Tarefa | Feito | Arquivo |
|---|---|---|---|
| F1 | Esquema SQLite + FTS5 + triggers + migração 001 | [ ] | `nucleo/.../conversas/` |
| F2 | Repositório (CRUD, WAL, transações) | [ ] | `nucleo/.../conversas/repositorio.py` |
| F3 | Redator de CPF/chaves **antes do INSERT** | [ ] | `nucleo/.../conversas/redator.py` |
| F4 | Título automático + `title_manual` | [ ] | `nucleo/.../conversas/titulo.py` |
| F5 | Os 9 métodos `chat.*` de histórico | [ ] | `nucleo/.../__main__.py` |
| F6 | `barra-chats` + busca + menu de contexto | [ ] | `app/src/paineis/BarraChats.tsx` |
| F7 | Testes: ciclo completo, 200 mensagens < 300 ms, CPF ausente do arquivo | [ ] | `nucleo/tests/test_conversas.py` |

## Bloco G — Agente (M7)

Plano: [F1-06](06-agente-eng-florestal.md).

| # | Tarefa | Feito | Arquivo |
|---|---|---|---|
| G1 | Interface de provedor + cliente DeepSeek (stream, tools, cancelar) | [ ] | `nucleo/.../agente/` |
| G2 | `limites.py` com o orçamento de contexto | [ ] | idem |
| G3 | Montador de contexto + compressão (memória, transcript, diff) | [ ] | `nucleo/.../agente/contexto.py` |
| G4 | `compact_summary` com `deepseek-v4-flash` | [ ] | `nucleo/.../agente/resumo.py` |
| G5 | As 26 tools tipadas, incluindo `usar_modelo_da_galeria` | [ ] | `nucleo/.../agente/tools.py` |
| G6 | System prompt versionado + teste de teto | [ ] | `nucleo/.../agente/prompt.py` |
| G7 | `chat.enviar` / `chat.cancelar` + eventos `chat.delta`/`chat.tool` | [ ] | `nucleo/.../__main__.py` |
| G8 | Cassetes VCR + fixture de 120 turnos | [ ] | `nucleo/tests/agente/` |
| G9 | Teste de vazamento (WKT, CPF, caminho, chave) | [ ] | `nucleo/tests/test_contexto_vazamento.py` |
| G10 | Teste de paridade galeria ↔ chat | [ ] | `nucleo/tests/test_paridade_galeria_agente.py` |

## Bloco H — Motion e preview de construção (M8)

Plano: [F1-16](16-design-system-dark.md).

| # | Tarefa | Feito | Arquivo |
|---|---|---|---|
| H1 | `job.artefato_parcial` no núcleo (4 tipos, caminho relativo) | [ ] | `nucleo/.../motores/gerar.py` |
| H2 | A1 pensando · A2 streaming · A3 tool | [ ] | `app/src/componentes/` |
| H3 | A4 progresso segmentado (10 etapas) | [ ] | `app/src/componentes/BarraProgressoJob.tsx` |
| H4 | A5 fase 1 — esqueleto de camadas por `item` | [ ] | `app/src/paineis/Preview.tsx` |
| H5 | A5 fase 2 — rasterização real com crossfade | [ ] | idem, depende de H1 |
| H6 | A6 microinterações (pasta, galeria, versões, watcher) | [ ] | vários |
| H7 | Testes com evento injetado (≥ 3 animações) | [ ] | `app/tests/visual/` |

## Bloco I — Conformidade, instalador, piloto (M9–M11)

| # | Tarefa | Feito |
|---|---|---|
| I1 | Série completa da Harmonia com 14 HARD verdes | [ ] |
| I2 | Diff raster < 0,3% contra os 21 PDFs-modelo | [ ] |
| I3 | `.mxd` abrindo no ArcMap de outro PC | [ ] |
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
