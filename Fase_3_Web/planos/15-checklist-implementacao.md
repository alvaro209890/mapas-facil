# W-15 — Checklist de implementação (vivo)

Marque `[x]` **no mesmo commit** que fecha a tarefa, com o hash na coluna do relatório de rodada
(ver [W-16](16-protocolo-do-agente.md)). A descrição completa de cada tarefa está no plano
indicado; aqui fica o índice para o agente não se perder.

## Gap analysis — requisito → plano → estado → onde

| # | Requisito (pedido do Álvaro) | Plano | Estado | Arquivo/pasta principal |
|---|---|---|---|---|
| RW01 | Site com login ligado a backend no server | W-01, W-03, W-11, W-12 | ausente | `Fase_3_Web/servidor/`, `Fase_3_Web/web/` |
| RW02 | Chat de IA que cria e edita o mapa conforme o pedido | W-05 | parcial — agente existe no núcleo (27 tools); falta ponte web | `servidor/api/mensagens.py`, `nucleo/agente/tools.py` |
| RW03 | Cada mapa é um projeto | W-02 | ausente | `servidor/api/projetos.py`, `banco/` |
| RW04 | Escolher retrato/paisagem e A4…A0 ao criar | W-02, W-06, W-09 | ausente (só A4) | `nucleo/motores/folhas.py`, `web/src/telas/NovoMapa/PassoFolha.tsx` |
| RW05 | Importar o `.zip` com os dados | W-02 | ausente | `servidor/importacao/`, `web/src/api/upload.ts` |
| RW06 | Animações enquanto a IA trabalha (zoom de câmera, camadas acendendo, montagem da folha) | W-03, W-07 | ausente (desktop tem M8 simples) | `nucleo/motion.py`, `web/src/palco/` |
| RW07 | Eventos `job.progresso`, `viewport.foco`, `camada.renderizada` (+ `layout.elemento`) | W-03 | parcial — `job.progresso` existe | `nucleo/protocolo.py`, `progresso.py` |
| RW08 | `.mxd` sem ArcMap (manipulação binária CFBF) | W-08 | parcial — T2 por offset; biblioteca no `C:\GIS\MXD_RE` | `nucleo/mxd_binario/` |
| RW09 | PDF vetorial nativo com paridade do acervo | W-09 | parcial — A4 19/20 na anatomia | `nucleo/motores/nativo.py`, `perfil_pagina.py` |
| RW10 | Escala e enquadramento automáticos por geometria e orientação | W-10 | parcial — algoritmo de 7 passos | `nucleo/motores/enquadramento.py` |
| RW11 | Metadados técnicos automáticos (SIRGAS/UTM, datas de mosaico, fontes) | W-10 | parcial | `nucleo/motores/metadados.py` |
| RW12 | Checks HARD: links quebrados, texto sobreposto, áreas × recibo do CAR | W-10 | parcial — H01–H14 | `nucleo/validacao/saida.py` |
| RW13 | Cadastro aberto; admin bloqueia conta | W-11, W-03, W-06 | ausente | `servidor/auth/`, `web/src/telas/Entrar.tsx` |
| RW14 | IA = 9Router da VPS, `ag/gemini-3.8-flash-high`, raciocínio `high` | W-05 | ausente — o núcleo só tem o cliente DeepSeek | `nucleo/agente/provedor.py` |
| RW15 | Pacote sempre liberado, organizado em `MXD/ SHP/ Mapas/` | W-08 | ausente | `nucleo/mxd_binario/pacote.py` |
| RW16 | Enquadramento "zoom na camada" como no ArcMap (Análise PH) | W-10 | parcial — algoritmo com lista fixa | `nucleo/motores/enquadramento.py` |
| RW17 | Regras e armadilhas das skills de MXD do Hermes/Claude incorporadas | W-17 | ausente | vários (ver W-17) |

## W0 — Fundação

- [x] W0-01 D22–D39 em `planos/00-visao-e-duas-fases.md` (tabela de decisões + "Fora da v1" revisado)
- [x] W0-02 `AGENT_BRIEF.md`: AP-01 e AP-12 com a revisão da Fase 3; seção "Fase 3" no snapshot
- [x] W0-03 `planos/README.md`: linha da Fase 3
- [x] W0-04 `Fase_3_Web/servidor/` esqueleto (`pyproject.toml`, `mapasfacil_servidor/__init__.py`, `__main__.py --version`, `config.py`, `erros.py`)
- [x] W0-05 `Fase_3_Web/deploy/`, `Fase_3_Web/fixtures/` com README
- [x] W0-10 `Fase_3_Web/web/` Vite + React 19 + TS estrito
- [x] W0-20 `deploy/scripts/preflight.sh` + `docs/fase3-w0-preflight.md`
- [x] W0-30 `.github/workflows/fase3.yml` (`guardas`, `desktop`)
- [x] W0-40 P1–P10 respondidas pelo Álvaro e registradas em W-00 (2026-11-03, na conversa de planejamento)

## W1 — Núcleo em modo servidor + `MapSpec` v3

- [x] W1-01 `motores/folhas.py` + CLI `folhas --json` ([W-02](02-projeto-folha-e-upload.md))
- [x] W1-02 `config.modo_servidor()`
- [x] W1-03 `cofre.py` por env
- [x] W1-04 `sessao.py` + `AUTH-090`
- [x] W1-05 `agente/provisao.py` desligado
- [x] W1-06 `workspace/watcher.py` desligado
- [x] W1-07 `.servidor/projeto.json` na memória de trabalho
- [x] W1-08 Saída `Mapas/vNNN/` em modo servidor
- [x] W1-09 Vagas por `flock`
- [ ] W1-10 `doctor.py` modo servidor — **bloqueada**: `nucleo/mapasfacil_nucleo/doctor.py` está na lista do Álvaro de arquivos de outro trabalho ("não mexa neles"). Feito o equivalente fora dele: `workspace.servico._doctor_resumido()` responde modo/motor binário sem sondar ArcMap, e o `/api/v1/saude` (W3) virá do `config`. Falta a autorização dele para tocar o arquivo.
- [x] W1-11 Nunca `arcpy` em modo servidor
- [x] W1-12 `MapSpec` v3 (`folha`) + migração v2 + `planos/02-mapspec-contrato.md`
- [x] W1-13 `tests/test_modo_servidor.py`

## W2 — Ponte

- [x] W2-01 `ponte/worker.py`
- [x] W2-02 `ponte/pool.py`
- [x] W2-03 `ponte/allowlist.py` + teste
- [x] W2-04 `ponte/fake_nucleo.py` + 4 roteiros
- [x] W2-05 Registro de versão — `ponte/versao.py` monta o registro (artefatos, `conforme` pelos HARD, miniatura); o **insert** entra no W3, quando existir o schema
- [x] W2-06 Integração com núcleo real (3 testes `nucleo_real`, rodados aqui contra o venv do núcleo)

## W3 — API base

- [x] W3-01 Migração `0001_inicial.sql`
- [x] W3-02 `ProjetosRepo` + máquina de estados (`SV-090`)
- [x] W3-03 `api/projetos.py`
- [x] W3-10 `app.py` + rotas + `api/modelos.py`
- [x] W3-11 `erros.py` + handler
- [x] W3-20 Tabelas `usuarios`/`sessoes`/`auditoria`
- [x] W3-21 `auth/` (senhas, sessões, CSRF, limitador)
- [x] W3-22 Dependências de permissão — a matriz vive em `tests/test_api_base.py` (dono × alheio × admin × anônimo); arquivo próprio não foi criado, o conteúdo está coberto
- [x] W3-23 CLI `conta` (criar, listar, bloquear, desbloquear) ponta a ponta
- [x] W3-24 Redação de logs (`logs_redigidos.py`, usada também pelo worker)
- [x] W3-25 `POST /auth/cadastrar` + bloqueio de conta + admin pelo `MF_ADMIN_EMAIL`

## W4 — Importação

- [x] W4-01 `importacao/upload.py` (nome do plano era `partes.py`)
- [x] W4-02 `api/importacao.py` (upload + importação no mesmo módulo)
- [x] W4-03 `web/src/api/upload.ts`: upload por partes com `X-Parte-SHA256` por parte, `hash_partes` = sha256 da concatenação dos hex (igual ao servidor, provado com `node:crypto`), retomada por `partes_ok` e cancelamento por `AbortSignal`
- [x] W4-04 `importacao/extrair.py`
- [x] W4-05 Rota de importação + estados (eventos por SSE ficam no W5; hoje o estado é `GET /importacoes/{id}`)
- [x] W4-06 Indexação e resumo (`workspace.abrir` pela ponte; sem worker, resumo sai com aviso `SV-123`)
- [x] W4-07 Reimportação (`entrada.anterior/<carimbo>/`)
- [x] W4-08 `fixtures/gerar_zip_sintetico.py` (ZIP válido, `testzip()` = None)
- [x] W4-09 Teste de CPF (varre respostas da API e as tabelas `projetos`/`importacoes`/`auditoria`)
- [ ] W4-10 SAD69 → SIRGAS 2000 — **pendente de propósito**: o núcleo só conhece EPSG:4326/4674 (`geo/area.py`, `geo/distancia.py`); criar `geo/crs.py` com a transformação oficial Helmert precisa do `.zip` real do SIMCAR para validar o deslocamento de ~60 m

## W5 — SSE + chat

- [x] W5-01 `eventos/log.py` (seq gravado antes de enviar, fsync 50/1 s, índice a cada 1.000 linhas, compactação para `desde=0`)
- [x] W5-02 `eventos/sse.py` (replay+ao vivo sob a mesma inscrição, dedupe por `seq`, heartbeat 15 s, desconexão limpa, rota `GET /projetos/{id}/eventos`)
- [x] W5-03 `eventos/vocabulario.py` (fechado; teste compara com o `protocolo.py` do núcleo)
- [x] W5-10 `api/mensagens.py` (GET mensagens, POST 202 com `req_id`, POST cancelar)
- [x] W5-11 Conversa principal (nasce no primeiro turno e fica na coluna `conversa_id`) + renomear acompanha o projeto
- [ ] W5-12 5 tools novas
- [x] W5-13 Prompt web (`_BLOCO_WEB` em `agente/prompt.py`, entra só em modo servidor; 1.072 de 2.500 tokens)
- [x] W5-14 Memória de trabalho com folha
- [ ] W5-15 Edição a partir de versão anterior
- [x] W5-16 Provedor `openai_compat` (9Router, `ag/gemini-3.8-flash-high`, `high`) + smoke de tools + contexto real — **medido em 03/11**: chave própria `mapasfacil-app` criada no 9Router; `ferramentas/provedor_smoke.py` verde em tools (32 schemas, `finish_reason=tool_calls`, argumentos JSON), paralelo (2 tool calls no mesmo turno), resultado de tool de 6.257 chars lido até a sentinela, raciocínio (1.000 chars de `reasoning_content`), stream (46 pedaços, 5.465 chars, `stop`). Contexto: prompt de 180.000 chars (~45 mil tokens reais) aceito; `usage.prompt_tokens` do pool é **inflado** (14.842 para ~900 tokens), então `MAPASFACIL_CONTEXTO_MAX=40000` é margem medida, não o anunciado 1M
- [~] W5-17 Os 7 roteiros como cassetes: **6 reproduzidos de verdade** (dinâmica, estilo, folha, qual folha, voltar, pergunta) em `tests/agente/cassetes/web_*.json` + `tests/test_agente_web_roteiros.py`; `web_hard` roda e chama `explicar_validacao`, mas **nenhum fixture sintético derruba check HARD hoje** — o caso do plano (H17, áreas × recibo) só existe a partir do W7/W9
- [x] W5-18 Sugestões de início
- [x] W5-19 Regras do escritório no prompt (dentro do `_BLOCO_WEB`: dinâmicas intermediárias sem quantitativo, outubro/Planet a partir de 2016, um processo = um mapa, pacote `MXD/ SHP/ Mapas/` e revínculo dos shapes)
- [x] W5-20 Visão pelo Gemini via 9Router — **obrigatória** (decisão 2026-11-03): `MAPASFACIL_MODELO_VISAO=ag/gemini-3.8-flash-high`, mesmo modelo do chat — **medido em 03/11**: payload `image_url` (print sintético de mapa, 16 KB, sem dado de cliente) voltou 200 e o modelo descreveu imóvel, TI, escala e legenda; `openai_compat.modelo_visao()` criado

## W6 — Frontend

- [x] W6-01 Herdados do desktop em `web/src/`: `estilos/` (tokens, reset, scrollbar e as fontes woff2 + licenças OFL), `herdados/` com 8 componentes de chat (+ CSS modules) e `timeline.ts`, todos com cabeçalho de proveniência; imports apontam para `herdados/tipos.ts` (não para as stores do desktop)
- [x] W6-02 `api/cliente.ts` (fetch com `credentials: include`, CSRF nas mutações, `ErroHttp` com `o_que_fazer`, 401 avisando a sessão uma vez, falha de rede = `REDE`), `api/eventos.ts` (EventSource `mf`, dedupe por `seq`, estados conectado/reconectando/offline) e `api/tipos.ts` com guarda de contrato contra `eventos/vocabulario.py`; `api/ponteWeb.ts` entrou junto com as stores (W6-03)
- [x] W6-03 Stores (`sessao`, `projetos`, `projetoAtivo`, `chat`, `job`, `palco`, `conexao`) + `api/ponteWeb.ts` com `despachar()` e `ligarProjeto()`; `seq` repetido é descartado no despachante. Testes: `estado/estado.test.ts` (16) e `estado/roteiro.test.ts` (4) — roteiro gravado de 16 eventos, replay sem duplicar
- [x] W6-04 `Entrar.tsx` + troca de senha: abas Entrar/Criar conta, erro com o código do servidor (`SV-001`, `SV-003`, `SV-005` com contagem regressiva real de `detalhes.espera_s`, `SV-010` com a regra mostrada antes de enviar), `trocar_senha` obrigatório para conta criada pela CLI, roteador (`App.tsx`) com guarda de sessão e `volta=` só de caminho interno
- [x] W6-05 `Projetos.tsx`: busca com debounce de 250 ms, filtro Ativos/Lixeira, grade de cartões (auto-fill, 1 coluna no celular), selo de folha e de estado (com o código quando `erro`), silhueta na proporção do formato quando não há miniatura, menu renomear/lixeira/restaurar, atalho `N`, estado vazio honesto. **Sem barra de progresso no cartão**: o percentual real só existe no SSE do projeto aberto. Veio junto `GET /projetos/{id}/arquivos/{caminho}` (`api/arquivos.py`, allowlist `Mapas/`+`MXD/`, `SV-401`/`SV-402`, `Range` 206, `?anexo=true`) — sem ele o cartão não teria miniatura nem o PDF teria download
- [x] W6-06 `NovoMapa/*` + `CartaoFolha.tsx`: 3 passos (folha → dados → resumo), cartão desenhado na proporção real (A0 = 16 folhas A4, paisagem gira), envio do `.zip` por partes com progresso real em partes, e **projeto criado só no fim** (falha no envio não deixa projeto vazio)
- [x] W6-07 `Projeto.tsx`: divisor chat|palco, chat com a timeline herdada (bolha que junta deltas, cartão de tool único ou grupo, raciocínio, pergunta com chips) alimentado pelo SSE, "Parar" por `req_id`, sugestões do servidor, faixa de versões clicável (`/versoes/:n` na URL) e downloads por `/arquivos/{caminho}?anexo=true`. Palco é **desenho estático** da folha com o número da versão até o W8 — nada de mapa falso
- [ ] W6-08 `Admin.tsx`, `Conta.tsx`
- [ ] W6-09 Modal de sessão expirada
- [ ] W6-10 `servidor/estaticos.py`

## W7 — Eventos de motion

- [x] W7-01 `nucleo/motion.py` — `montar_dados_viewport/camada/layout`, `PRIORIDADE_PAPEL`, `NIVEIS_VIEWPORT`, `ELEMENTO_PARA_CAIXA`, `ORDEM_LAYOUT`; contrato em `tests/test_motion_contrato.py` (28 testes)
- [x] W7-02 `EVENTOS` (13) + `planos/01-arquitetura.md` §Eventos com os 3 novos, no mesmo commit
- [x] W7-03 `RastreadorProgresso.foco/camada/elemento` — contador de camadas próprio, `total` que só cresce, e recusa de nível voltando
- [x] W7-04 Pontos de emissão em `gerar.py` (estado/município via malha IBGE do repo, camadas + imóvel), `nativo.py` (enquadramento, folha, layout.elemento) e `agente/tools.py` (job_id também na tool do chat)
- [x] W7-05 `GET /projetos/{id}/palco/{job}/{sub}/{arquivo}` (allowlist `camadas|layout|raster`, `.geojson|.png`, cache privado 1 h) + `.preview` de job com mais de 7 dias apagado na manutenção — `tests/test_palco_api.py` (12 testes)
- [x] W7-06 `palco.gravar_recorte_elemento` recorta a página renderizada pela caixa do elemento (150 dpi) para `Mapas/.preview/<job>/layout/<elemento>.png`
- [x] W7-07 `nucleo/palco.py::gravar_geojson` — EPSG:4326, 6 casas, teto 2 MB/20.000 vértices dobrando a tolerância, área em CRS projetado
- [~] W7-08 `palco.gravar_raster` (PNG 1600 px + `bbox_4326`) ligado no `nativo` — **não exercitado** porque o fixture sintético não tem basemap; medir no anel 3 (server)
- [x] W7-09 `python -m mapasfacil_nucleo estilos [--json]`
- [~] W7-10 `servidor/tests/roteiros/palco_dinamica.ndjson` + `palco_dinamica/` (33 eventos, 5 focos, 2 camadas, 6 elementos, 10 assets) gravados por `gerar_palco.py` de um job real; `serie_analise` fica para o W9 e o `dinamica_falha_hard` do palco depende do H17 (W9)

## W8 — Palco

- [x] W8-01 `palco/Palco.tsx` (414 linhas + 351 de CSS): os 4 modos, um só relógio `requestAnimationFrame` consumindo os passos da coreografia — sem passo na fila, o palco fica parado
- [x] W8-02 `palco/Camera.ts` (218): wrapper do MapLibre (`criar`/`flyTo`/`fitBounds`/`jumpTo`/`snapshot`/`destruir`) com `MapaLike` injetável para teste — nada de estado global
- [x] W8-03 `palco/Camadas.ts` (357): source+layer por `camada_id`, `estilo` do evento traduzido para paint e ordem de pintura = ordem dos passos
- [x] W8-04 `Folha.tsx` em SVG com mm reais (viewBox proporcional à folha ISO A4–A0 retrato/paisagem), recorte PNG via `<image>`, texto via `<text>`, snapshot encaixado no quadro, ordem canônica `ORDEM_LAYOUT` e suporte a `prefers-reduced-motion`; 10 testes em `Folha.test.tsx`
- [x] W8-05 `palco/coreografia.ts` (716 linhas: tokens de duração por tipo, compressão por fila pendente com 3 faixas, voos intermediários viram salto acima de 10 pendentes, ondas de 3 camadas, `replay()` determinístico) + `coreografia.test.ts` (13 testes, com os 3 roteiros)
- [x] W8-06 `estado/palco.ts` evoluído (299 linhas): fila de eventos, passo corrente, `limpar()` ao trocar de job/versão, guarda contra evento de outro projeto, modo derivado (ocioso/mapa/folha/resultado) — `palco.test.ts` (16 testes)
- [x] W8-07 `palco/webgl.ts` + aviso no palco: sem WebGL cai em folha+resultado com o código **WB-001** e a mensagem única
- [x] W8-08 `palco/tokens.ts` (durações/easings do plano) + `useReducedMotion.ts` aplicado em todos os passos (movimento reduzido ⇒ salto, sem voo)
- [x] W8-09 modo `ocioso` mostra a versão aberta e o perímetro indexado, sem animação inventada
- [ ] W8-10 Testes visuais

## W9 — PDF A4–A0

- [x] W9-01 `perfil_para(folha)` + `escalar_perfil(perfil, folha)` em `perfil_pagina.py`: A4 devolve o objeto medido, o resto é A4 × `k` com **encaixe de borda** (o ISO não tem razão √2 exata: A3 é 297·1,41428 = 420,043 mm, e sem encaixe o minimapa vazava do papel); `NU-303` para `escala_elementos` diferente de `proporcional` — `tests/test_perfil_para.py` (57 testes)
- [x] W9-02 `nativo.py` usa `perfil_para`/`escalar_perfil` no `_perfil_do_mapspec` (o modelo medido da série manda na orientação, a folha só diz o tamanho) e `perfil.dpi_raster()` no `savefig` do PDF — 300 dpi até A2, teto de pixels em A1 (7.000 px ≈ 249 dpi) e A0 (9.000 px ≈ 226 dpi)
- [x] W9-03 `blocos.py` por `k`: toda espessura e todo halo passaram por `perfil.escalado()` (moldura, grade, rosa, minimapa, legenda, logo, selos) e `HALO_ESCURO/HALO_CLARO` viraram `halos(perfil, claro=)`; a quebra de linha é folha-invariante por construção (caixa e `pt` já vêm multiplicados por `k`) — `tests/test_blocos_por_folha.py` (8)
- [x] W9-04 `grade_dms.escolher_passo`: correção real — varrimento pequeno demais para 4 rótulos caía no passo de 1° e o mapa ficava **sem grade**; agora vale "pelo menos uma linha". Teste `tests/test_grade_por_folha.py` prova 4–8 rótulos por eixo em 5 folhas × 2 orientações × 7 escalas (S07)
- [x] W9-05 `minimapa.layout_de_perfil(perfil)` (caixa, lado do retângulo localizador e altura da página por folha) e a linha-guia do `blocos` passou a usar `perfil.escalado(1.5)` — `tests/test_minimapa_folha.py` (8, com S01 centrado em todas as folhas)
- [x] W9-06 `basemap.largura_para_folha(perfil)` (A4 2.321 px/300 dpi, A2 4.642, A1 5.449/249, A0 7.002/226 — igual à tabela do plano), `avaliar_resolucao()` e check **S17** no relatório — `tests/test_basemap_folha.py` (12). Falta só medir no server com mosaico real (W9-10)
- [x] W9-07 `png_tabela.renderizar_png_tabela(..., largura_cm=)`: o PNG cresce com a caixa da tabela no papel — A4 3.211 px (600 dpi), A2 4.796 px, A0 19.248 px, sempre ~600 dpi efetivos; teto de 80 MPix reduz a resolução e dispara `NU-123` em vez de estourar a memória (A0 com 22 classes → 377 dpi com aviso) — `tests/test_png_tabela_folha.py` (8)
- [x] W9-08 `anatomia.esperada_para_folha(golden_a4, folha)` (A4 × `k`), `conferir_folha()` = check **H15** (papel ±1 mm, com orientação trocada detectada) e `comparar(..., fator=k)` escalando a tolerância — `tests/test_anatomia_folha.py` (26) e `tests/test_golden_anatomia_folhas.py` (9, com render real de A4/A3/A0: H15 verde nas três e anatomia de A3/A0 conferida contra A4 × k)
- [x] W9-09 `matplotlib.rcParams["pdf.fonttype"] = 42`: o default do matplotlib gerava **Type 3** (fonte não embutida, `n/a` no `get_fonts`) — agora o PDF leva a fonte embutida de verdade e o texto continua extraível em A4/A3/A0 (`tests/test_golden_anatomia_folhas.py`). O golden de anatomia da A4 foi **regenerado uma vez** por causa da mudança de rasterização do glifo (0,72% de pixels, só texto), com a anatomia em mm inalterada
- [x] W9-10 medido no `server-desktop` (4 núcleos, 03/11): A4 **1,7 s** · A3 1,5 s · A2 1,6 s · A1 2,0 s · A0 **3,6 s**, PDF 0,06 MB cada e RSS pico **410 MB** (fixture sintética **sem basemap**); H15 verde nas cinco. Tabela §Tamanho do W-09 atualizada com os números e a condição da medição
- [x] W9-11 `planos/01-padrao-imap-harmonia.md` § **Folhas maiores (D31)** — tabela de `k` e do quadro por folha, o que escala e o que **não** escala (a escala do mapa é recalculada pelo enquadramento; a contagem de DMS não muda), o achado do encaixe de borda (ISO não tem √2 exata), a tabela de raster/dpi e as linhas de `H15`/`S17` no checklist
- [~] W9-12 em 2026-11-03: **feito** — legenda abaixo do quadro (regra PH de 0,5 cm no retrato; 3,5 mm medidos no paisagem, preservados), legenda encolhendo até caber (já existia), `pt_metadados_efetivo()` reduzindo o corpo do bloco a partir de 7 linhas (antes estourava a caixa em toda folha), check **H16** (`caixas_fora_da_pagina`) no relatório e hachura de AC/AVN conferida no catálogo — `tests/test_blocos_layout_regras.py` (82). **Falta**: quadro cadastral 2×4 em PNG (W-17 §8, dado pessoal) e a redução de corpo por célula do nome longo

## W10 — `.mxd` binário

- [x] W10-01 `docs/mxd-formato-binario.md` e `docs/arcmap-wms-crash.md` (de `C:\GIS\MXD_RE\docs`, autoria preservada `Hermes-windows | 2026-10-14`)
- [x] W10-02 `mxd_binario/cfbf.py` (leitor/escritor MS-CFB v3 puro stdlib, FAT/MiniFAT, substituição de stream pequena e grande com crossover) + `tests/test_cfbf_corpus.py`: 52 testes round-trip byte a byte contra os 47 MXDs do corpus (`shared/templates` + `Referencias_IMAP/MXD`), validado contra `olefile`
- [ ] W10-03 `blocos.py` + teste
- [ ] W10-04 Spike S0
- [ ] W10-05 Spikes S1–S11
- [ ] W10-06 `slots.py`, `documento.py`
- [ ] W10-07 `gates.py` + sabotagem
- [ ] W10-08 Fábrica + MANIFEST `variantes`
- [ ] W10-09 G4 automatizado
- [ ] W10-10 `pacote.py` + rota
- [ ] W10-11 `motor="binario"` no `gerar.py`
- [ ] W10-12 H18–H20
- [ ] W10-13 Laboratório REA (Frida nas leituras de stream do ArcMap + pares A/A′ da fábrica; descompilação em sala limpa liberada)
- [ ] W10-14 Checklist da fábrica (lições das skills) + teste do pacote em caminho com espaço/acento

## W11 — Inteligência cartográfica

- [ ] W11-01 `enquadramento.py` + testes
- [ ] W11-02 Ligar no `gerar.py` e no binário
- [ ] W11-03 Zona 20S
- [ ] W11-04 Escala redonda por degrau + escala única por série + minimapa + comum (H05 → S20)
- [ ] W11-05 `metadados.py` (imagem por ano, grafias do escritório)
- [ ] W11-06 Calibração H17/S12 (S12 sempre SOFT)
- [ ] W11-07 Checks H15–H22/S12–S20 + mensagens
- [ ] W11-08 Margem e degraus com o acervo e a Análise PH
- [ ] W11-09 `sugerir_enquadramento`
- [ ] W11-10 Comum `01-padrao`: checklist
- [ ] W11-11 Série Dinâmica (3 marcos), hachura AC/AVN, AVN = AIR − AC − água, desmate autorizado × não autorizado
- [ ] W11-12 Distâncias AEQD (TI e zona de amortecimento separadas)

## W12 — Deploy + piloto

- [x] W12-01 `deploy/`: `mapasfacil-app.service`, `mapasfacil-app-tunnel.service`, `mapasfacil-app-tunnel.yml.example`, `mapasfacil-app-backup.{service,timer}`, `mapasfacil-app-saude.{service,timer}` e `scripts/checar_hd.sh` (espera o HD, testa escrita real porque o fuseblk aceita tudo como 777)
- [x] W12-02 `scripts/atualizar.sh <tag>` (preflight → tag → deps → backup → migração → SPA → symlink `atual` → restart → smoke com `versao==tag`), `rollback.sh` (sem desfazer migração) e `backup.sh` (`.backup` + retenção 14 dias); `bash -n` limpo nos 5 scripts
- [x] W12-03 `servidor/requirements.lock` gerado por `uv pip compile pyproject.toml --generate-hashes --python-version 3.12 --python-platform linux` (665 linhas, 610 hashes, sem dev); `tests/test_requirements_lock.py` (5) garante hash em toda dependência, versões iguais às do `pyproject` e ausência de faixa aberta
- [x] W12-04 CLIs de operação: `serve`, `migrar`, `limpar-lixeira`, `conta` (W3) + **`sonda-saude`** (3 falhas seguidas → `logs/alertas.log`; 1 falha isolada não alarma) e **`varrer-pii`** (CPF em banco/eventos/logs com validação de dígito verificador, sai 1 no achado e **nunca imprime o valor**). Falta `amostras-mxd`, que é do W10-09
- [x] W12-05 `deploy/PEDIDOS-AO-ALVARO.md`: as **duas chaves geo** que não existem em cofre nenhum, o túnel+DNS `mapasfacil-app` com os comandos exatos, e o desligamento do `analises` — mais o estado medido do preflight (9 OK, 1 falta)
- [~] W12-06 app **de pé no server** em 03/11: `mapasfacil-app.service` (`systemd --user`) active/enabled, schema 2, `/api/v1/saude` respondendo, `servidor.env` 0600; smoke ponta a ponta vai de cadastro a importação pronta em ~6 s e chat com o LLM real. **Falta**: `web/dist` buildado (SPA ainda `false`), túnel + DNS `mapasfacil-app` (Álvaro) e o PDF pelo chat (prompt do W5). Detalhe medido em `docs/fase3-rodada-2026-11-03-W12.md`
- [~] W12-07 roteiro e tabela do piloto prontos em `docs/piloto-fase3.md` (3 pessoas × 5 imóveis, com o que se mede e a regra de não citar dado de cliente); **execução bloqueada** pelo túnel/DNS e pelas duas chaves
- [ ] W12-08 Desligar `analises.cursar.space` (acer) sem derrubar a landing

## W17 — Conhecimento das skills

- [x] W17-01 Avisar o Álvaro da chave da Planet em claro na skill `analise-auas-planet` (2026-11-03)
- [~] W12-20 `varrer-pii` implementado e testado (`mapasfacil_servidor/pii.py` + `tests/test_cli_varrer_pii.py`, 17) e `mapasfacil-app-pii.{service,timer}` (03:10 diário) no `deploy/`; falta a medição do critério do W-00 (importar `imovel_ficticio.zip` no server e conferir **zero** achados)
- [x] W12-21 `servidor.env` em `600` e diretório em `700` (medido no server em 03/11: `/home/server/segredos-mapasfacil/servidor.env`), fora do git, com symlink em `mapasfacil/segredos/`
- [ ] W12-22 Revisão de segurança final
