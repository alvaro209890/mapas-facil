# W-05 — Chat e agente na web

## Objetivo

Levar para o navegador o agente que já existe no núcleo (orquestrador — hoje com cliente DeepSeek, na web pelo 9Router com Gemini 3.8 Flash High —, 27 tools,
compressão de contexto, `chat.pergunta`, `MapSpec` versionado) e acrescentar só o que a web
precisa: **folha** como conceito de primeira classe, um comportamento de "pedido → plano curto →
execução" adequado a quem não vê a pasta, e sugestões de início. O agente continua editando
`MapSpec` — nunca código (AP-02).

## Estado atual vs alvo

| Item | Hoje | Alvo |
|---|---|---|
| Orquestrador | `agente/orquestrador.py`, provedor `agente/deepseek.py`, fake/VCR | igual |
| Tools | 27 reais (`agente/tools.py::_HANDLERS`) | 27 + `definir_folha`, `sugerir_enquadramento`, `explicar_validacao`, `listar_versoes`, `restaurar_versao` |
| Prompt | `agente/prompt.py` (persona "Ana", engenheira florestal) | + bloco de contexto web: folha atual, "o usuário não vê a pasta", formato de resposta |
| Memória de trabalho | `tools.py::montar_memoria_trabalho` | + `folha`, `projeto.nome`, resumo do imóvel |
| Persistência | `conversas/` SQLite FTS5 no APPDATA | o mesmo, em `<projeto>/.estado/chats/` (W1) |
| Provedor | BYOK do usuário, DeepSeek V4 | 9Router central da VPS, `ag/gemini-3.8-flash-high`, raciocínio `high`, chave própria do Mapas Fácil (D33) |

## Dependências

W1 (modo servidor), W2 (ponte), W5 (SSE). A UI está em [W-06](06-frontend-web-e-design.md).

## Contratos

### Turno

1. `POST /projetos/{id}/mensagens {texto}` → servidor grava `mensagem.criada` no log, chama
   `chat.enviar {conversa_id, texto}` na ponte, devolve `202 {req_id}`.
2. O núcleo emite `chat.raciocinio` (opcional), `chat.delta` (texto), `chat.tool` (início/fim de
   tool, com `nome`, `args_resumo`, `resultado_resumo`), `chat.pergunta`, `mapspec.atualizado` e,
   se gerar, todos os eventos de job.
3. `nucleo.res {req_id, ok}` fecha o turno; a mensagem final da IA já está no `chats.sqlite`.

Resposta a `chat.pergunta`: `POST /mensagens {texto: "<rótulo da opção>", resposta:{pergunta_id,
opcao_id}}` — o núcleo já trata a resposta como mensagem do turno seguinte (comportamento R27);
o servidor só repassa.

### Tools novas (todas em `agente/tools.py`, mesma forma das existentes: `args`, `ctx`, `_ok`/`_erro`)

| Tool | Args | Efeito | Erros |
|---|---|---|---|
| `definir_folha` | `{formato: "A4".."A0", orientacao: "retrato"|"paisagem"}` | muda `MapSpec.folha` via `_editar` (nova versão); se `escala` estava `auto`, recalcula na próxima geração; se o template não tem variante `.mxd` nessa folha, devolve aviso `MX-020` no resultado (o PDF continua possível) | `AG-201` formato inválido |
| `sugerir_enquadramento` | `{}` | roda `motores/enquadramento.py` ([W-10](10-inteligencia-cartografica.md)) para as 10 combinações folha × orientação e devolve a tabela `{folha, orientacao, escala, aproveitamento_pct}` — o agente usa para responder "qual folha fica melhor?" | `AG-202` sem perímetro |
| `explicar_validacao` | `{versao?: int}` | lê `validacao.json` da versão e devolve HARD/SOFT com mensagem humana e o que fazer | `AG-203` versão inexistente |
| `listar_versoes` | `{}` | versões com título, folha, conforme, data — para "volta para a versão 2" | — |
| `restaurar_versao` | `{versao: int}` | cria versão nova cujo conteúdo é o `MapSpec` da versão pedida, com `parent_id` dela | `AG-203` versão inexistente |

"Volta para a versão 2" = `restaurar_versao {versao: 2}` → vira **v4** com `parent_id` da v2
(nunca apaga a v3). Já é o modelo do `mapspec_store.py`; a tool só precisa aceitar a origem.

Perguntas ao usuário: hoje não há tool `perguntar` — o `chat.pergunta` é emitido de dentro de
`tool_criar_mapa` (`_emitir_pergunta`, `tools.py:361`) quando falta dado. A Fase 3 mantém isso;
se o agente implementador precisar perguntar em outras tools, reusa `_emitir_pergunta`.

### Prompt de sistema — bloco web (em `agente/prompt.py`, só em modo servidor)

Conteúdo obrigatório (redação final do agente implementador, mas estes pontos não podem faltar):

1. "O usuário está num **site**, não vê a pasta nem os arquivos; refira-se a camadas pelo nome
   humano ("vegetação nativa"), não pelo nome do `.shp`, salvo se ele perguntar."
2. "A folha do projeto é **{formato} {orientacao}**. Troque só se o usuário pedir ou aceitar
   uma sugestão; ao trocar, diga a nova escala."
3. "Antes de gerar algo que demora (série completa, mais de 3 mapas), diga em uma linha o que vai
   fazer e **faça** — não peça confirmação para pedido claro. Pergunte só quando faltar dado que
   mude o resultado (ex.: qual ano da Dinâmica) — com opções, pelo `chat.pergunta`."
4. "Cada mudança gera uma **versão nova**; diga o número da versão ao terminar."
5. "Se um check HARD falhar, diga qual, por quê e o que o usuário pode fazer; não chame o mapa de
   pronto."
6. "Nunca escreva CPF, nunca cole coordenadas brutas longas, nunca invente camada fora do
   catálogo (`listar_catalogo`)."
7. Formato: respostas curtas, listas quando houver mais de 3 itens, números em pt-BR com 4 casas
   para hectare.

### Sugestões de início (cartões no chat vazio)

Montadas pelo servidor a partir de `galeria.listar` + resumo do imóvel. Cada sugestão é **texto
de mensagem** (o clique envia como se o usuário tivesse digitado — sem caminho paralelo):

| Condição | Sugestão |
|---|---|
| sempre | "Faz a Dinâmica {ano corrente}" |
| há AVN e AC | "Mapa de uso do solo com quantitativos" |
| sempre | "Série completa da Análise de área (20 mapas)" |
| imóvel alongado (razão do bbox > 1,6) e folha em retrato | "Qual folha deixa o mapa mais detalhado?" |

### Provedor de IA no servidor (D33)

Decisão do Álvaro (2026-11-03): **9Router da VPS com Gemini 3.8 Flash High e raciocínio `high`,
para o chat e para a operação de mapas** (o mesmo modelo nas duas pontas).

| Env (no `servidor.env`) | Valor | Uso |
|---|---|---|
| `MAPASFACIL_PROVEDOR` | `openai_compat` | cliente OpenAI-compatível (o 9Router fala esse formato) |
| `MAPASFACIL_PROVEDOR_URL` | `http://100.104.255.35:20128/v1` | 9Router central na VPS, pela tailnet (vault `02-projetos/9router.md`, memória `9router-central-vps`). **Não tem reserva**: se a VPS cair, o chat cai — a UI mostra `IA-0xx` "IA indisponível" e o job em curso termina o que não depende do LLM |
| `MAPASFACIL_PROVEDOR_CHAVE` | chave **dedicada** do Mapas Fácil criada no 9Router | uso aparece separado no painel e no grupo "9router" do WhatsApp; revogar não afeta a frota |
| `MAPASFACIL_MODELO_CHAT` | `ag/gemini-3.8-flash-high` | turnos do chat e tools de operação de mapa |
| `MAPASFACIL_MODELO_RAPIDO` | `ag/gemini-3.8-flash-high` | título de conversa e `compact_summary` (mesmo modelo, por decisão) |
| `MAPASFACIL_RACIOCINIO` | `high` | vai em `reasoning_effort`; o 9Router **ignora `max` em silêncio** (vault `01-infra/modelos-e-raciocinio-frota.md`) — por isso `high` |
| `MAPASFACIL_CONTEXTO_MAX` | medir no W5-16 | o 9Router anuncia o contexto das versões pagas, que pode não ser o real do pool; o `agente/limites.py` usa este teto, não o anunciado |
| alternativa: `MAPASFACIL_PROVEDOR=deepseek` + `MAPASFACIL_DEEPSEEK_API_KEY` | — | o caminho já testado do desktop, se um dia for preciso trocar |

`agente/provedor.py` já abstrai o provedor; o cliente `openai_compat` nasce como irmão do
`deepseek.py` (mesmo SSE e mesmo formato de tool calling), com três cuidados:

1. **Tool calling**: o 9Router homologou tool calls no `ag/gemini-3.8-flash-medium` (vault
   `02-projetos/9router.md`, tabela de 2026). Antes de ligar, o W5-16 roda um smoke com as 32 tools
   (27 + 5 novas) no `-high`: `finish_reason=tool_calls`, argumentos JSON válidos, chamadas em
   paralelo, e uma resposta de tool longa (resumo de camadas) voltando ao modelo.
2. **Raciocínio**: o Gemini devolve raciocínio em campo próprio pelo 9Router; mapear para o
   evento `chat.raciocinio` (o desktop já tem o evento).
3. **Erros e limites**: 429/5xx do 9Router viram `IA-0xx` com nova tentativa exponencial (3×);
   `stream` interrompido no meio fecha o turno com o texto parcial marcado.

Uso de tokens por turno vai para o log técnico do servidor por projeto (observabilidade, **não
quota** — D18). Os cassetes/VCR e o `FakeProvedor` continuam independentes de provedor: o CI não
fala com o 9Router.

Privacidade do que vai ao provedor: inalterada — AP-06 e AP-09, testes `test_contexto_vazamento.py`
já cobrem (sem WKT, sem CPF). O teste ganha um caso com o `projeto.json` e o resumo do imóvel.

### Roteiros de conversa (são testes — `Fase_1_Desktop/nucleo/tests/agente/cassetes/web_*.json`)

Gravados com o `FakeProvedor`/VCR existente. Cada um afirma a sequência de tools e o estado
final do `MapSpec`:

| Roteiro | Mensagens | Tools esperadas (ordem) | Afirmação final |
|---|---|---|---|
| `web_dinamica` | "faz a dinâmica 2026" | `estado_do_projeto` → `ler_recibo_car` → `usar_modelo_da_galeria`/`criar_mapa` → `validar_mapspec` → `gerar_mapa` | v1 com `folha` = a do projeto, `saidas ⊇ [pdf,xlsx]` |
| `web_estilo` | (após v1) "clareia a vegetação e tira a tabela" | `editar_camada` → `alternar_elemento` → `gerar_mapa` | v2, `elementos_layout.tabela=false`, `parent_id`=v1 |
| `web_folha` | (após v2) "passa pra A3 paisagem" | `definir_folha` → `gerar_mapa` | v3, `folha={A3,paisagem}`, escala ≤ a da v2 |
| `web_qual_folha` | "qual folha fica melhor?" | `sugerir_enquadramento` | nenhuma versão nova; resposta cita escala por folha |
| `web_hard` | "faz a dinâmica" com AUAS fora da ATP e recibo divergente | … → `gerar_mapa` → `explicar_validacao` | resposta menciona o check H17 e não diz "pronto" |
| `web_voltar` | "volta pra versão 1" | `listar_versoes` → `restaurar_versao` | v4 com `parent_id`=v1 |
| `web_pergunta` | "faz um mapa" sem dizer qual, com vários modelos possíveis | `criar_mapa` (emite a pergunta) | evento `chat.pergunta` com ≥ 2 opções; nenhuma versão gerada |

## Tarefas agentáveis

- [ ] **W5-10** `api/mensagens.py`: `GET` (via `chat.carregar_anteriores`), `POST` (turno, `SV-210`, `SV-011`), `POST /cancelar`.
- [ ] **W5-11** Criação da conversa principal na indexação (`chat.criar_conversa`), `conversa_id` no projeto; renomear projeto → `chat.renomear`.
- [ ] **W5-12** `agente/tools.py`: as 5 tools novas + registro em `_HANDLERS` + esquema JSON das tools para o provedor.
- [ ] **W5-13** `agente/prompt.py`: bloco web (só em modo servidor).
- [ ] **W5-14** `tools.py::montar_memoria_trabalho`: `folha`, nome do projeto, resumo do imóvel.
- [ ] **W5-15** Origem de edição a partir de versão anterior (`mapspec_store.py`) para "voltar".
- [ ] **W5-16** `agente/provedor.py`: cliente `openai_compat` + envs da tabela; smoke `ferramentas/provedor_smoke.py --9router` (tool calls com as 32 tools, raciocínio, stream longo) e medição do contexto real para `MAPASFACIL_CONTEXTO_MAX`; pedir ao Álvaro a chave dedicada do Mapas Fácil no 9Router.
- [ ] **W5-17** Os 7 roteiros como cassetes + testes.
- [ ] **W5-18** Sugestões de início: rota `GET /projetos/{id}/sugestoes` montando a tabela acima.
- [ ] **W5-20** (**obrigatória** desde 2026-11-03 — decisão do Álvaro, W-00 §Decisões tomadas) Testar se o 9Router repassa imagem ao `ag/gemini-3.8-flash-high` (payload `image_url` com um print de mapa do acervo, sem dado de cliente); ligar `MAPASFACIL_MODELO_VISAO=ag/gemini-3.8-flash-high` — **o mesmo modelo do chat** — e reabrir a interpretação de print/PDF de referência do F1-07 (`analisar_referencia`) na web. Só se o 9Router recusar a imagem: registrar o erro medido, manter `IA-060` e avisar o Álvaro.
- [ ] **W5-19** Bloco do prompt com as regras do escritório que o agente precisa **explicar** ao usuário ([W-17](17-conhecimento-das-skills.md)): dinâmicas intermediárias sem quantitativo, imagem por ano (Planet de outubro a partir de 2016), um processo = um mapa, pacote `MXD/ SHP/ Mapas/` e como revincular os shapes; o nome do proprietário nunca aparece no texto da IA.
- [x] **W5-22** (D41) Abertura do projeto com a leitura do `.zip`: turno automático do servidor (origem `sistema`, motivo `importacao_concluida`), resumo factual, `perguntar` com modelos da galeria (`multipla=true`), Plano B determinístico se 9Router fora, eventos reais `viewport.foco` e `camada.renderizada`, reload idempotente.
- [x] **W5-21** (D40) Tool `perguntar` em qualquer momento da conversa: emite `chat.pergunta`, encerra o turno e aguarda resposta no `POST /mensagens` (`{resposta: ...}`) ou texto livre; 4 cassetes cobrindo os casos obrigatórios (`web_pergunta_dois_cars`, `web_pergunta_camada_ambigua`, `web_serie_plano`, `web_pergunta_ano_dinamica`). que o agente precisa **explicar** ao usuário ([W-17](17-conhecimento-das-skills.md)): dinâmicas intermediárias sem quantitativo, imagem por ano (Planet de outubro a partir de 2016), um processo = um mapa, pacote `MXD/ SHP/ Mapas/` e como revincular os shapes; o nome do proprietário nunca aparece no texto da IA.

## Critérios de aceite

- [ ] Os 7 roteiros verdes no CI (sem rede, com `FakeProvedor`).
- [ ] Smoke ao vivo no server (`ferramentas/provedor_smoke.py --9router --web`): "faz a dinâmica" no `imovel_ficticio.zip`, com `ag/gemini-3.8-flash-high`, termina com PDF em `Mapas/v001/` e a sequência de tools do roteiro `web_dinamica`.
- [ ] `test_contexto_vazamento.py` cobre o bloco web e continua verde.
- [ ] Mandar 2 mensagens seguidas rápido: a segunda volta `409 SV-210` e a UI mostra "a IA ainda está respondendo".
- [ ] `listar_versoes` + "volta pra versão 1" nunca apaga artefato de versão posterior.

## Fora de escopo

- Várias conversas por projeto, ramificação de conversa na web (o núcleo tem; a web não expõe na v1).
- Upload de imagem no chat: o **envio** de print pelo usuário não entra na v1; a visão (W5-20)
  interpreta referência (print/PDF) que o usuário indica ao agente — `MAPASFACIL_MODELO_VISAO`.
- Voz.

## Anti-padrões

- Tool que gera mapa sem passar por `validar_mapspec` antes.
- A IA "confirmar" com o usuário um pedido claro só para parecer cuidadosa (gasta turno e paciência).
- Sugestão de início que chama endpoint especial em vez de mandar texto pelo chat.
