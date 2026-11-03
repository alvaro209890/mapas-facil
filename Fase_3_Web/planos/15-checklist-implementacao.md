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
- [ ] W4-03 `web/src/api/upload.ts` — trilha B (web), não iniciada
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
- [ ] W5-16 Provedor `openai_compat` (9Router, `ag/gemini-3.8-flash-high`, `high`) + smoke de tools + contexto real
- [~] W5-17 Os 7 roteiros como cassetes: **6 reproduzidos de verdade** (dinâmica, estilo, folha, qual folha, voltar, pergunta) em `tests/agente/cassetes/web_*.json` + `tests/test_agente_web_roteiros.py`; `web_hard` roda e chama `explicar_validacao`, mas **nenhum fixture sintético derruba check HARD hoje** — o caso do plano (H17, áreas × recibo) só existe a partir do W7/W9
- [x] W5-18 Sugestões de início
- [x] W5-19 Regras do escritório no prompt (dentro do `_BLOCO_WEB`: dinâmicas intermediárias sem quantitativo, outubro/Planet a partir de 2016, um processo = um mapa, pacote `MXD/ SHP/ Mapas/` e revínculo dos shapes)
- [ ] W5-20 Visão pelo Gemini via 9Router — **obrigatória** (decisão 2026-11-03): `MAPASFACIL_MODELO_VISAO=ag/gemini-3.8-flash-high`, mesmo modelo do chat

## W6 — Frontend

- [ ] W6-01 Cópia de tokens, fontes, motion e componentes com proveniência
- [ ] W6-02 `api/cliente.ts`, `eventos.ts`, `ponteWeb.ts`, `tipos.ts`
- [ ] W6-03 Stores
- [ ] W6-04 `Entrar.tsx` + troca de senha
- [ ] W6-05 `Projetos.tsx`
- [ ] W6-06 `NovoMapa/*` + `CartaoFolha.tsx`
- [ ] W6-07 `Projeto.tsx`
- [ ] W6-08 `Admin.tsx`, `Conta.tsx`
- [ ] W6-09 Modal de sessão expirada
- [ ] W6-10 `servidor/estaticos.py`

## W7 — Eventos de motion

- [ ] W7-01 `nucleo/motion.py`
- [ ] W7-02 `EVENTOS` + plano F1-01
- [ ] W7-03 `RastreadorProgresso.foco/camada/elemento`
- [ ] W7-04 Pontos de emissão
- [ ] W7-05 Rota de palco + limpeza
- [ ] W7-06 Recortes PNG de elementos
- [ ] W7-07 `nucleo/palco.py` (GeoJSON simplificado)
- [ ] W7-08 Raster do basemap para o palco
- [ ] W7-09 `estilos --json`
- [ ] W7-10 Roteiros reais gravados

## W8 — Palco

- [ ] W8-01 `Palco.tsx`
- [ ] W8-02 `Camera.ts`
- [ ] W8-03 `Camadas.ts`
- [ ] W8-04 `Folha.tsx`
- [ ] W8-05 `coreografia.ts` + testes
- [ ] W8-06 `estado/palco.ts`
- [ ] W8-07 Fallback sem WebGL
- [ ] W8-08 Tokens de motion
- [ ] W8-09 Modo ocioso
- [ ] W8-10 Testes visuais

## W9 — PDF A4–A0

- [ ] W9-01 `perfil_para(folha)`
- [ ] W9-02 `nativo.py` por folha
- [ ] W9-03 `blocos.py` por `k`
- [ ] W9-04 `grade_dms.py`
- [ ] W9-05 Minimapa
- [ ] W9-06 Basemap por folha + S17
- [ ] W9-07 PNG da tabela
- [ ] W9-08 Anatomia por folha + H15
- [ ] W9-09 Fontes embutidas e texto extraível
- [ ] W9-10 Medição real
- [ ] W9-11 Comum `01-padrao`: "Folhas maiores"
- [ ] W9-12 Regras de layout das skills no motor nativo

## W10 — `.mxd` binário

- [ ] W10-01 Documentação do formato no repo
- [ ] W10-02 `cfbf.py` + corpus
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

- [ ] W12-01 Units e config de túnel
- [ ] W12-02 `atualizar.sh`, `rollback.sh`, `backup.sh` + timers
- [ ] W12-03 `requirements.lock` com hashes
- [ ] W12-04 CLIs de operação
- [ ] W12-05 Pedidos ao Álvaro
- [ ] W12-06 Primeiro deploy `web-v0.1.0` + vault
- [ ] W12-07 Piloto interno
- [ ] W12-08 Desligar `analises.cursar.space` (acer) sem derrubar a landing

## W17 — Conhecimento das skills

- [x] W17-01 Avisar o Álvaro da chave da Planet em claro na skill `analise-auas-planet` (2026-11-03)
- [ ] W12-20 `varrer-pii`
- [ ] W12-21 Permissão do `servidor.env`
- [ ] W12-22 Revisão de segurança final
