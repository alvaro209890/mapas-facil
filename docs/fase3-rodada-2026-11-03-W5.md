# Rodada 2026-11-03 — W5 (parcial): stream de eventos

Marco: **W5** (plano [W-03](../Fase_3_Web/planos/03-api-http-e-eventos.md) §Stream de eventos)
Branch: `planos/fase3-web-chat` · executor: Hermes-windows · delegação: nenhuma

Esta rodada fechou **W5-01, W5-02 e W5-03**. O chat (W5-10 a W5-20) é a próxima etapa.

## Feito

| Tarefa | Arquivo | O que ficou |
|---|---|---|
| W5-01 | `eventos/log.py` | NDJSON append-only por projeto em `.servidor/eventos.ndjson`; `seq` inteiro crescente **gravado antes de enviar**; `fsync` a cada 50 eventos ou 1 s; índice de offsets a cada 1.000 linhas; leitura tolerante a linha truncada por queda |
| W5-02 | `eventos/sse.py` + `api/eventos.py` | inscrição no fan-out **antes** da leitura do log (sem vão entre replay e ao vivo), descarte por `seq` já entregue, heartbeat `: ♥` a cada 15 s, cabeçalhos `no-cache`/`X-Accel-Buffering: no`, desconexão limpa, compactação na reabertura |
| W5-03 | `eventos/vocabulario.py` | eventos do núcleo (13, inclusive os 3 do palco) + 7 do servidor, origens fechadas, `EVENTOS_DE_JOB` |
| — | `api/importacao.py` | a importação agora publica `projeto.estado` e `importacao.progresso` no log e no hub — o stream mostra a extração ao vivo |

## Comandos e resultados

```
cd Fase_3_Web/servidor
.venv/Scripts/python.exe -m pytest -q tests/     → 121 testes, 0 falhas
```

Critérios de aceite do W-03 §SSE, medidos:

| Critério | Teste |
|---|---|
| 500 eventos gravados, `desde=250` recebe 251–500 | `test_replay_de_500_com_desde_250` |
| reconexão com `Last-Event-ID` não duplica | `test_replay_e_ao_vivo_sem_duplicata` (+ `test_replay_usa_indice_e_nao_duplica` no log) |
| `desde=0` com jobs terminados recebe versão compactada | `test_compactacao_quando_desde_zero_e_arquivo_grande` |
| heartbeat chega no prazo | `test_heartbeat_chega_quando_nao_ha_evento` |
| duas abas recebem o mesmo fluxo | `test_duas_abas_recebem_o_mesmo_evento` |
| rota HTTP real entrega `text/event-stream` com os eventos da importação | `test_sse_entrega_eventos_da_importacao` |

## Decisões de implementação

1. **Compactação sempre que `desde == 0`**, não só acima de 500 eventos. Job **terminado**
   (`nucleo.res`) vira 1 progresso final + camadas/layout/viewport + o próprio `nucleo.res`;
   job **em andamento** é reenviado inteiro, como o plano manda.
2. **Caminho com espaço é mascarado só até o espaço.** `/media/server/HD Backup/x` sai como
   `<caminho removido> Backup/x`. O prefixo que identifica a máquina não vaza; mascarar o
   resto exigiria adivinhar onde o caminho termina dentro de texto livre. Registrado no teste.
3. **`check_same_thread=False` no SQLite.** Rota `async def` executa a dependência síncrona
   em outro thread; a conexão é por requisição, então não há concorrência real sobre ela.
   Foi o que quebrou o primeiro teste HTTP do SSE.

## Pendências

- 🟠 **W1-10 (`doctor.py`)** continua bloqueada pela ordem do Álvaro.
- 🟡 **W5-10..W5-20 (chat)**: mensagens, conversa principal, tools, prompt web, provedor
  `openai_compat` no 9Router e a **visão obrigatória** (`MAPASFACIL_MODELO_VISAO`).
- 🟡 **`nucleo.res`** ainda não é emitido pela ponte ao fim de cada requisição — entra junto
  com o chat, que é quem sabe quando o turno acabou.

## Próximo

W5 (chat): `api/mensagens.py`, conversa principal, relay `chat.enviar` pela ponte e o
provedor `openai_compat` apontando para o 9Router da VPS.

---

## Adendo — W5-10 e W5-11 (chat do projeto)

| Tarefa | Arquivo | O que ficou |
|---|---|---|
| W5-10 | `api/mensagens.py` | `GET /projetos/{id}/mensagens` (via `chat.carregar_anteriores`), `POST` devolve `202 {req_id}` e roda o turno em background, `POST /cancelar` |
| W5-11 | `api/mensagens.py` + `api/projetos.py` + migração `0002` | conversa principal nasce no **primeiro turno** (`chat.criar_conversa` com o nome do projeto) e fica em `projetos.conversa_id`; renomear o projeto renomeia a conversa |
| — | `ponte/worker.py` | `MAPASFACIL_DADOS` e `MAPASFACIL_CHATS_DIR` apontam para `.estado/` **dentro do projeto** — um projeto não enxerga o chat do outro e nada vai para APPDATA |
| — | `eventos` | o turno emite `mensagem.criada`, repassa `chat.delta`/`chat.raciocinio`/`chat.tool`/`chat.pergunta` para o log+hub e fecha com `nucleo.res {req_id, ok}` |

Comandos: `pytest tests/` → **129 testes, 0 falhas** (8 novos de chat, todos pela ponte real com o núcleo falso).

Decisões que custaram sangue:

1. **Rotas de chat são `async def` e usam `await pool.chamar`.** Com `asyncio.run()` por
   requisição, cada chamada criava e fechava um *event loop* novo, e o subprocesso do worker
   ficava preso ao loop antigo (`Event loop is closed`, `I/O operation on closed pipe`).
   Um loop só, o do uvicorn — é o que o `TestClient` também usa.
2. **`lifespan` encerra os workers no desligamento.** Antes, o subprocesso ficava órfão.
3. **`SV-240` quando não há pool**: sem worker o chat responde 503 explicando, em vez de
   fingir que mandou a mensagem.

## Adendo 2 — W5-15 e as tools do chat web (W5-12, 4 de 5)

**`mapspec_store.py` (novo, W5-15).** Cada versão gerada deixa o seu `mapspec.json` ao lado
dos artefatos — `Mapas/vNNN/mapspec.json` no servidor, `Mapas/_versoes/vNNN/` no desktop.
`tool_gerar_mapa` grava na pasta do PDF assim que a geração termina, então o registro existe
mesmo que o worker morra logo depois. `listar()` devolve versão, título, folha, orientação,
escala, `parent_id` e os tipos de artefato presentes — sem geometria.

**Tools (W5-12).**

| Tool | Comportamento |
|---|---|
| `definir_folha` | troca `folha.formato`/`orientacao`/`escala_elementos`; formato fora de A4–A0 volta `NU-001` com a lista válida |
| `listar_versoes` | versões da mais nova para a mais antiga + qual é a atual da conversa |
| `restaurar_versao` | conteúdo volta inteiro numa **versão nova**, com `parent_id` = id da versão de origem; artefato antigo intacto; valida contra a pasta atual antes de aceitar |
| `explicar_validacao` | lê o último `*_validacao.json` e traduz os checks HARD em português (`H17` = "as áreas do imóvel não conferem com o recibo do CAR"), separando falha de aviso |

`sugerir_enquadramento` **não** foi feita: depende de `motores/enquadramento.py` (W11), que ainda
não existe. Fica registrada como pendência do W5-12, não como tarefa cumprida.

Comandos: `pytest tests/test_agente_tools_web.py` → **13 testes**; suíte do núcleo inteira
**561 desktop** e **551 com `MAPASFACIL_MODO=servidor -m "not desktop"`** (eram 548/538).

Dois ajustes que a implementação exigiu: `escala` no MapSpec v3 é **string**, não objeto
(`_valor_escala` aceita os dois); e restaurar não pode passar por `_editar`, porque `nova_versao`
sobrescreve o `parent_id` com a versão corrente — a restauração monta a versão à mão.

## Adendo 3 — W5-13, W5-14 e W5-19 (prompt e memória de trabalho)

**W5-13 — bloco web do prompt.** `agente/prompt.py` ganhou `_BLOCO_WEB`, anexado por
`texto_system_prompt()` **só quando `modo_servidor()`**. Ele cobre os sete pontos obrigatórios do
plano e muda o vocabulário: o usuário está no navegador, não vê pasta nem `.shp`, e a IA fala em
"vegetação nativa", não em `AVN.shp`. Custo medido: **1.072 de 2.500 tokens** com o bloco, contra
~600 sem ele — `cabe_no_teto(incluir_web=...)` deixa isso verificável em teste.
`VERSAO_PROMPT` subiu para **2**.

**W5-19 — regras do escritório.** Entraram no mesmo bloco, como texto que a IA **explica** quando
perguntarem: dinâmicas intermediárias sem quantitativo (o número é o do ano de referência), série
com uma imagem por ano e outubro como mês de referência a partir de 2016, um processo = um mapa,
e o pacote `MXD/ SHP/ Mapas/` com caminhos relativos — "como abro no meu ArcMap" tem resposta
pronta (revincular os shapes de `SHP/`). O nome do proprietário não vai no texto do mapa nem na
resposta.

**W5-14 — memória de trabalho.** `montar_memoria_trabalho()` já trazia `projeto.nome` e
`projeto.folha` desde o W1; agora traz também `folha_texto` ("A3 paisagem", do jeito que a IA fala)
e `mapspec_atual.folha`, para o agente comparar a folha do projeto com a da versão corrente sem
deduzir nada.

**Códigos de erro alinhados ao plano:** as tools novas devolvem `AG-201` (formato/orientação
inválidos) e `AG-203` (versão inexistente / sem relatório de validação) em vez de `NU-001`
genérico.

Comandos: núcleo **564 testes desktop** e **554 em modo servidor** (eram 561/551); app desktop
**180 testes, 27 arquivos**, verde e sem alteração.
