# 07 — IA, tools e MapSpec

Como o chat vira `MapSpec` válido. Este documento cobre o loop de orquestração, o catálogo de
tools, o system prompt, os guard rails e a escolha de modelo. Os nomes de campo do `MapSpec`, os
eventos SSE e as rotas são os de [`01-arquitetura.md`](01-arquitetura.md); os defaults
cartográficos são os de [`06-padrao-imap.md`](06-padrao-imap.md).

## Princípio de segurança: a IA não escreve código nem o spec inteiro

Duas proibições absolutas: **a IA nunca gera código** (nem Python, nem `arcpy`, nem expressão de
label — o backend não tem caminho de execução para código vindo do modelo) e **a IA nunca reescreve
o `MapSpec` inteiro** (ela opera por *tools atômicas* sobre o spec em memória, uma alteração mínima
por chamada, e o resultado é validado por schema antes de virar job).

O motivo é operacional. A alternativa óbvia — pedir ao modelo que gere um script `arcpy` — falha em
três frentes ao mesmo tempo:

| Problema | Consequência concreta |
|---|---|
| Insegurável | script arbitrário rodando na máquina do cliente, com acesso a disco e rede, é execução remota de código com etapas extras. Nenhuma allowlist de pastas sobrevive a isso |
| Indebugável | quando o mapa sai errado, a pergunta "por que a AVN ficou magenta" não tem resposta auditável: a causa está numa linha de código gerada e descartada |
| Não determinístico | o mesmo pedido gera scripts diferentes. Dois mapas da mesma série ficam diferentes — que é exatamente o problema que o produto existe para resolver |

Com tools atômicas, cada alteração é um registro (`tool`, `args`, `resultado`) no histórico, o spec
resultante é comparável com o anterior campo a campo, e o agente recebe só dados declarativos que
ele mesmo sabe traduzir (decisões D4/D5 em [`00-visao-e-escopo.md`](00-visao-e-escopo.md)).

Reescrever o spec inteiro por resposta, mesmo sem código, também foi descartado: o modelo
"reconstrói" campos que não deveria tocar e produz **regressões silenciosas** — a legenda que
estava certa volta ao default, o `crs` muda de zona, a matrícula do lote desaparece do rótulo.

## Loop de orquestração

O loop vive no backend, num serviço por turno de conversa. Nada dele roda no navegador.

```
messages = [{role: system, content: <system prompt versionado>},
            {role: user,   content: <pedido + contexto permitido + mapspec atual>}]

repetir (máx. 12 passos, máx. 300 s no total):
    resposta = provedor(messages, TOOL_SCHEMAS)
    se resposta não tem tool_calls: é a resposta final em texto → encerra o turno
    para cada tool_call:
        resultado = executar(tool, args, spec_em_memoria)
        messages += {role: assistant, tool_calls: [...]}
        messages += {role: tool, tool_call_id: <id>, content: resultado}
        emitir SSE tool.call e tool.result
    se a tool foi `finalizar`: encerra o turno
```

Detalhes que não são negociáveis:

- **Limite de 12 passos** e **timeout de 300 s** por turno. Estourar limite não é erro: o turno
  encerra com aviso, o spec parcial fica salvo como nova versão e o usuário continua na mensagem
  seguinte.
- **Nenhuma tool derruba o loop.** Argumento inválido vira uma string `erro: ...` devolvida ao
  modelo como `role: tool`, e o spec anterior é preservado. Exceção que escapa é bug do backend.
- **`listar_camadas_locais` e `inspecionar_camada` fazem RPC no agente local** pelo WebSocket
  (`fs.list` / `fs.inspect` do [`01`](01-arquitetura.md)), com timeout de 5 s. Agente offline
  devolve `erro: agente offline` e o modelo é instruído a perguntar em vez de inventar caminhos.
- **Streaming:** cada etapa emite os eventos SSE já definidos no [`01`](01-arquitetura.md)
  (`tool.call`, `tool.result`, `mapspec.updated`, `job.created`…). A UI mostra as tool calls
  abertas, estilo Cursor.
- **Cancelamento:** `POST /v1/conversations/{id}/cancel` interrompe entre passos; uma tool em
  execução não é abortada no meio (elas são rápidas e puras, exceto os RPCs).

## Catálogo de tools

24 tools, em quatro grupos. Convenção geral: tool de escrita devolve `{ok, mensagem, diff}`, tool de
leitura devolve JSON, e nenhuma tem efeito colateral fora do `MapSpec` em memória — exceto `gerar_mapa`.

### Contexto (leitura)

| Tool | O que faz | Parâmetros | Retorna | Erros |
|---|---|---|---|---|
| `estado_atual` | lê o `MapSpec` atual, as chaves válidas de `elementos_layout` e as escalas permitidas | — | `{mapspec, elementos_layout_chaves[], escalas_permitidas[]}` | — |
| `listar_camadas_locais` | **RPC no agente:** lista os shapefiles do imóvel nas pastas autorizadas, já classificados (lotes, AVN, AC, AUAS…) com estilo IMAP sugerido | `pasta?: string` | `{camadas_locais: [{id, nome, tema, arquivo, estilo_sugerido, rotulo_sugerido}]}` | `agente_offline`, `pasta_fora_da_allowlist` |
| `listar_camadas` | lista o catálogo de camadas externas (`shared/catalog/camadas.json`) | `tema?: string` | `{camadas: [{id, nome, tema, tipo, auth, descricao}]}` | — |
| `listar_templates` | lista os `mxd_template` e `layout_template` permitidos | — | `{templates: [{mxd_template, layout_template, serie, descricao}]}` | — |
| `inspecionar_camada` | **RPC no agente:** abre um shapefile e devolve metadados | `fonte: string` | `{geometria, crs, epsg, feicoes, campos[], bbox}` | `agente_offline`, `arquivo_invalido`, `prj_ausente` |

`listar_camadas_locais` é a tool que dá o caráter do produto: os mapas IMAP são feitos com os **dados
reais do imóvel**, não com camadas de serviço público, e o system prompt obriga a chamá-la antes de
montar qualquer mapa da série. `inspecionar_camada` existe para o modelo descobrir o nome real do campo
de rótulo (`NOME`, `PROPRIEDA`, `FAZENDA`…) em vez de adivinhar; ela nunca devolve geometria.

### Construção do mapa

| Tool | O que faz | Parâmetros | Erros |
|---|---|---|---|
| `criar_mapa` | cria um `MapSpec` novo com os defaults IMAP | `titulo`, `mxd_template`, `layout_template?`, `crs?`, `escala?` | `template_inexistente`, `titulo_vazio` |
| `definir_area_base` | define `area_base` (fonte + campo de rótulo) | `fonte`, `campo_rotulo` | `fonte_inexistente`, `campo_inexistente` |
| `adicionar_camada` | adiciona camada ao mapa | `fonte`, `id?`, `filtro?`, `estilo?`, `rotulo_texto?`, `legenda?` | `fonte_inexistente`, `camada_duplicada`, `segredo_ausente` |
| `remover_camada` | remove camada pelo id | `id` | `camada_inexistente`, `ultima_camada` |
| `reordenar_camadas` | define a ordem de desenho (primeiro = mais ao fundo) | `ids: string[]` | `ids_incompletos` |
| `editar_camada` | altera `estilo`, `filtro`, `rotulo_texto` ou `legenda` de uma camada | `id`, `estilo?`, `filtro?`, `rotulo_texto?`, `legenda?` | `camada_inexistente`, `estilo_invalido` |
| `definir_escala` | define `escala` | `escala: int \| "auto"` | `escala_nao_permitida` |
| `definir_crs` | define `crs` | `crs: string` | `crs_nao_projetado`, `zona_incompativel_com_uf` |

### Layout

| Tool | O que faz | Parâmetros | Erros |
|---|---|---|---|
| `alternar_elemento` | liga/desliga um elemento | `elemento` (uma das 12 chaves de `elementos_layout`), `visivel: bool` | `elemento_invalido` |
| `editar_estilo_elemento` | altera aparência de um elemento (fundo, cor, tamanho, borda) | `elemento`, `props: object` | `elemento_nao_estilizavel`, `prop_invalida` |
| `mover_elemento` | reposiciona um elemento por âncora | `elemento`, `posicao: {ancora, x, y}`, `tamanho?` | `elemento_nao_posicionavel`, `ancora_invalida`, `fora_da_pagina` |
| `editar_titulo` | altera `titulo` | `titulo` | `titulo_vazio` |
| `editar_legenda` | altera o texto de legenda das camadas e a ordem dos itens | `itens?: [{camada, legenda}]`, `ordem?: string[]` | `camada_inexistente` |
| `editar_tabela` | altera `tabela` (posição, colunas, linhas, total) | `posicao?`, `colunas?`, `linhas?`, `total?` | `colunas_e_linhas_incompativeis` |
| `editar_metadados_imagem` | preenche `metadados_imagem` | `satelite_sensor?`, `orbita_ponto?`, `data_aquisicao?`, `datum?` | `nenhum_campo_informado` |

Restrição da v1: o `MapSpec` de [`01-arquitetura.md`](01-arquitetura.md) só tem campo de posição para
a tabela (`tabela.posicao`), então `mover_elemento` e `editar_estilo_elemento` **funcionam apenas
para a tabela** e devolvem `elemento_nao_posicionavel` para os demais. Estender isso exige alterar
primeiro o contrato no [`01`](01-arquitetura.md), que ganha de qualquer outro documento (pendência P1).

### Fluxo

| Tool | O que faz | Parâmetros | Erros |
|---|---|---|---|
| `validar_mapspec` | roda o checklist IMAP em modo predição, sem render | — | — |
| `gerar_mapa` | valida, persiste a versão do spec e **cria o job** (`POST /v1/jobs`) | `agent_id?`, `saidas?`, `pasta_destino?`, `strict_mxd?` | `mapspec_invalido`, `agente_offline`, `pasta_fora_da_allowlist` |
| `sugerir_opcoes` | pergunta ao usuário quando há ambiguidade; não altera o mapa | `pergunta`, `opcoes: [{rotulo, valor}]` | `opcoes_insuficientes` |
| `finalizar` | encerra o turno com um resumo curto | `resumo?` | — |

### Assinaturas das tools centrais

```json
{"type": "function", "function": {
  "name": "criar_mapa",
  "description": "Cria um MapSpec novo com os defaults do padrão IMAP (A4 paisagem, grade DMS sem linhas, sem barra de escala, minimapa e logo ligados). Chame listar_templates antes se não souber o mxd_template.",
  "parameters": {"type": "object", "properties": {
    "titulo": {"type": "string", "description": "ex.: DINÂMICA DE USO DO SOLO - 2026"},
    "mxd_template": {"type": "string", "description": "id do manifesto de shared/templates/"},
    "layout_template": {"type": "string", "default": "dinamica_a4_paisagem"},
    "crs": {"type": "string", "enum": ["EPSG:31981", "EPSG:31982"]},
    "escala": {"type": ["integer", "string"], "description": "valor da lista permitida ou 'auto'"}
  }, "required": ["titulo", "mxd_template"]}
}}
```

```json
{"type": "function", "function": {
  "name": "adicionar_camada",
  "description": "Adiciona uma camada ao mapa. fonte = 'local.<id>' (shapefile do imóvel; veja listar_camadas_locais — traz estilo e rótulo IMAP prontos) ou o id de uma camada do catálogo externo (veja listar_camadas). O estilo informado sobrescreve o sugerido.",
  "parameters": {"type": "object", "properties": {
    "fonte": {"type": "string"},
    "id": {"type": "string", "description": "id no mapa; default = derivado da fonte"},
    "filtro": {"type": "string", "description": "SQL para camada local (ex.: LOTE = '65') ou CQL para WFS"},
    "estilo": {"type": "object", "properties": {
      "preenchimento": {"type": "string", "description": "hex ou 'none'; no padrão IMAP é sempre 'none'"},
      "linha": {"type": "string", "description": "cor hex do contorno"},
      "largura": {"type": "number"},
      "hachura": {"type": "string", "enum": ["xxx", "///", "\\\\\\", "---", "..."]}
    }},
    "rotulo_texto": {"type": "string", "description": "texto fixo no centroide, ex.: 'Fazenda Trevisol (Lote 65)\\nMatrícula 13.533'"},
    "legenda": {"type": "string", "description": "rótulo da camada na legenda"}
  }, "required": ["fonte"]}
}}
```

```json
{"type": "function", "function": {
  "name": "sugerir_opcoes",
  "description": "Pergunta ao usuário quando há ambiguidade (qual lote, qual satélite, qual série). NÃO finaliza o turno e NÃO altera o mapa. Use sempre que a resposta certa dependa de informação que você não tem — nunca adivinhe.",
  "parameters": {"type": "object", "properties": {
    "pergunta": {"type": "string"},
    "opcoes": {"type": "array", "minItems": 2, "items": {
      "type": "object",
      "properties": {"rotulo": {"type": "string"}, "valor": {"type": "string"}},
      "required": ["rotulo", "valor"]}}
  }, "required": ["pergunta", "opcoes"]}
}}
```

```json
{"type": "function", "function": {
  "name": "gerar_mapa",
  "description": "Valida o MapSpec, salva a versão e cria o job de geração no agente local. Chame só depois de validar_mapspec não acusar falha HARD. Se o agente estiver offline o job fica na fila.",
  "parameters": {"type": "object", "properties": {
    "agent_id": {"type": "string", "description": "default: o agente da conversa"},
    "saidas": {"type": "array", "items": {"type": "string", "enum": ["mxd", "pdf", "preview_png", "geojson"]}},
    "pasta_destino": {"type": "string", "description": "tem de estar na allowlist do agente"},
    "strict_mxd": {"type": "boolean", "description": "true = falha se o .mxd não puder ser gerado"}
  }}
}}
```

Retorno de `validar_mapspec` (mesmo vocabulário do `validacao.json` do agente, ver
[`06-padrao-imap.md`](06-padrao-imap.md)):

```json
{"ok": false,
 "checks": [
   {"id": "H03", "severidade": "hard", "ok": true,  "mensagem": "EPSG:31982 coerente com o datum"},
   {"id": "H10", "severidade": "hard", "ok": false, "mensagem": "metadados_imagem.data_aquisicao vazio"},
   {"id": "S04", "severidade": "soft", "ok": false, "mensagem": "escala 25000; o cliente prefere 22000"}],
 "nao_prediziveis": ["H01", "H08", "H12"]}
```

## System prompt

O prompt é longo de propósito e organizado em seções fixas:

| Seção | Conteúdo |
|---|---|
| Papel | operador cartográfico do Mapas Fácil, padrão IMAP, Mato Grosso; nunca escreve código, nunca reescreve o spec |
| Fluxo obrigatório | (1) `estado_atual` + `listar_camadas_locais`; (2) tools que o pedido exige; (3) `validar_mapspec`; (4) corrigir e revalidar, no máximo 2 tentativas; (5) `gerar_mapa`; (6) `finalizar` |
| Preferência por camadas locais | os mapas da série são feitos com os shapefiles do imóvel; catálogo externo só quando o pedido exige (embargos, alertas, terras indígenas) |
| Defaults do padrão IMAP | A4 paisagem, grade DMS só com rótulos, sem barra de escala, sem créditos, seta norte ArcMap, minimapa e logo ligados, `inset_tipologia` desligado exceto em Tipologia Vegetal |
| Guia de estilos e hachuras | a tabela de [`06`](06-padrao-imap.md) copiada com os hex exatos; nada é preenchido sólido; lote na legenda é polígono vazado |
| Regra de perguntar | havendo ambiguidade, `sugerir_opcoes` com 2+ opções rotuladas; nunca adivinhar lote, matrícula, satélite ou data |
| Proibições | não inventar id de camada, `mxd_template`, endpoint ou campo; não escrever código; não alterar `crs` sem motivo; não desligar legenda |

Duas exigências de engenharia: o prompt é **versionado junto com o código**, em
`backend/prompts/cartografo.v<N>.md`, com o número da versão gravado em `messages.usage` de cada
turno — sem isso, uma regressão de qualidade depois de um ajuste de prompt é impossível de rastrear,
e o prompt é código de produção, não configuração. E o prompt é **testado**: as prompts-fixture (ver
"Escolha de modelo") rodam contra um provedor mock em cada PR e contra o provedor real em cadência
baixa. Alterar o prompt sem rodar as fixtures é proibido.

## Versionamento por edição

Cada turno que altera o mapa gera **linha nova** em `map_specs` (com `parent_id` apontando para a
versão anterior) e, se o usuário pedir geração, **job novo** (com `parent_job_id`). Nada é
sobrescrito: `map_specs` e `job_events` são append-only por decisão do [`01`](01-arquitetura.md).

```
v1  criar_mapa + 4 camadas      → job_1
v2  "deixa a ATP amarela"       → job_2  (parent_job_id = job_1)
v3  "e tira a barra de escala"  → job_3  (parent_job_id = job_2)

diff exibido (evento mapspec.updated, comparação por caminho JSON):
  camadas[id=lote_principal].estilo.linha   "#c00000"  →  "#ffc000"
  elementos_layout.escala_grafica           true       →  false
```

Isso dá três coisas de graça: histórico navegável ("volta para a v2"), auditoria de quem mudou o quê,
e a possibilidade de reexecutar uma versão antiga quando o cliente pedir o mapa "como estava".

## Guard rails e validação

Três camadas, da mais barata para a mais caseira:

1. **Na tool.** Argumento fora do domínio é rejeitado na hora: camada inexistente no catálogo e na
   listagem do agente, `mxd_template` fora do manifesto, `escala` fora da lista, `saidas` fora de
   `{mxd, pdf, preview_png, geojson}`, `crs` geográfico, `area_base` divergente da fonte das camadas
   de lote, pasta fora da allowlist.
2. **No schema.** Antes de criar job, o spec passa por `shared/schemas/mapspec.schema.json` e pelas
   invariantes do [`01`](01-arquitetura.md). Rejeição, nunca correção silenciosa: corrigir sem
   avisar produz mapa que o técnico não pediu e não entende.
3. **No agente.** O agente revalida tudo antes de tocar em `arcpy`, porque ele não confia no
   backend por princípio (regra de fronteira 3 do [`01`](01-arquitetura.md)). É aqui que aparece a
   restrição mais dura do motor: cor e hachura vêm de uma biblioteca finita de `.lyr`, então um
   `estilo` com hex arbitrário resolve para o `.lyr` catalogado mais próximo ou é recusado com
   sugestão ([`05-motor-mxd-pdf.md`](05-motor-mxd-pdf.md)). O modelo pode pedir qualquer cor; o
   sistema entrega as que existem.

Quando o modelo insiste no erro: **limite de 2 tentativas por tool**. Na terceira tentativa da mesma
tool com o mesmo tipo de erro, o loop deixa de repassar o erro e força um `sugerir_opcoes` com as
alternativas válidas ("a camada `avn` não existe nesta pasta; escolha `car_avn` ou `simcar_avn` do
catálogo, ou informe a pasta correta"). Sem esse corte, o modelo queima os 12 passos tentando
variações do mesmo nome errado — comportamento observado no projeto anterior.

## Fallback determinístico sem IA

Um parser de regras que reconhece vocabulário fixo e aplica edições diretamente no spec:
`dinâmica`/`uso consolidado`/`tipologia`/`embargos`/`alertas` escolhem o `mxd_template` da série;
`escala 1:22.000` e `escala auto` viram `definir_escala`; `tira a/o <elemento>` e `liga a/o
<elemento>` viram `alternar_elemento`; `título <texto>` vira `editar_titulo`; `<camada> em <cor>`
com cores nomeadas vira `editar_camada`.

Ele serve para três coisas: desenvolvimento local sem gastar token, teste de integração determinístico
do resto da pipeline (o `.mxd` não deveria depender de LLM para ser testado), e degradação graciosa
quando o provedor cai — a UI avisa "modo sem IA" e o usuário fica com um subconjunto funcional em vez
de uma tela de erro. Ele **não** é o produto: não entende pedido composto nem trata ambiguidade.

## Escolha de modelo

| Candidato | A favor | Contra |
|---|---|---|
| **DeepSeek** | custo por token muito baixo; já usado e validado ao vivo com este catálogo de tools no projeto anterior | tool calling ocasionalmente devolve argumentos em string quando o schema pede objeto; latência variável |
| OpenAI (`gpt` com function calling) | tool calling mais confiável; melhor aderência a `enum` | custo por turno maior; dependência de fornecedor único |
| Anthropic (Claude) | melhor em seguir instruções longas de prompt; bom em pedir esclarecimento | custo; formato de tools diferente, exige camada de adaptação |

Decisão para a v1: **DeepSeek como default, atrás de uma interface de provedor** OpenAI-compatível,
para trocar por variável de ambiente sem tocar no loop. O requisito duro é **tool calling nativo
confiável** — parsear tool call de texto livre foi descartado: introduz uma classe inteira de falha
(JSON malformado) num ponto crítico.

Avaliação: **prompts-fixture** em `backend/tests/fixtures/prompts/`, cada um com pedido em português,
catálogo/listagem local simulados e o `MapSpec` esperado. A métrica é campo a campo, não texto:
quantos specs saem idênticos, quantos saem válidos mas diferentes, quantos falham a validação. Casos
obrigatórios: Dinâmica completa a partir de um pedido só, edição de cor, remoção de elemento, pedido
ambíguo (deve chamar `sugerir_opcoes`), camada inexistente (deve recusar), agente offline (deve
perguntar).

## Custo e latência

Estimativa de tokens de entrada por passo, com o catálogo de 24 tools no contexto:

| Componente | Tokens | Componente | Tokens |
|---|---|---|---|
| System prompt | 1.200 – 1.600 | `MapSpec` atual | 400 – 900 |
| Schemas das tools | 2.500 – 3.500 | Histórico útil (janela) | 500 – 2.000 |
| Contexto permitido (catálogo + templates) | 600 – 1.200 | Resultados de tool do turno | 300 – 1.500 |

Ou seja, 6k–11k tokens por passo, e um turno típico tem 4 a 7 passos. Mitigação: **cache de contexto**
do provedor para o bloco estável (system prompt + schemas + catálogo), idêntico entre passos e entre
turnos; **janela de histórico** (só as N últimas mensagens completas, o resto como resumo); e
**resultados de tool truncados** (`listar_camadas` devolve id/nome/tema/tipo, não o objeto inteiro).

O que **nunca** entra no contexto:

- **Geometria.** Nenhuma coordenada, nenhum WKT, nenhum GeoJSON. Só metadados: nome de camada, tipo
  de geometria, contagem de feições, lista de campos, bbox arredondado. Isso é ao mesmo tempo
  economia de token e regra de fronteira (nenhum dado geoespacial de cliente sobe para a nuvem —
  regra 2 do [`01`](01-arquitetura.md)).
- **Caminhos absolutos completos** de disco além do necessário para identificar a camada.
- **Segredos** (authkey da SEMA, chave Planet): vivem só no agente local, ver
  [`08-dados-e-camadas.md`](08-dados-e-camadas.md).
- **Conteúdo do `.dbf`** linha por linha. Quantitativos são calculados pelo agente, não pelo modelo:
  LLM somando hectares é fonte de erro sem upside.

## Pendências e decisões abertas

| # | Pendência | Por que ainda não decidido |
|---|---|---|
| P1 | `mover_elemento` e `editar_estilo_elemento` não têm campo de destino no `MapSpec` v1 (só `tabela.posicao`) | exige adicionar um mapa de posições/estilos por elemento no contrato do [`01`](01-arquitetura.md); decidir se vale antes do M4 |
| P2 | Prefixo das fontes de catálogo | o [`01`](01-arquitetura.md) diz "`local.<id>` ou id do catálogo"; um prefixo explícito (`catalogo.<id>`) seria mais legível para o modelo, mas muda o contrato |
| P3 | Quem calcula os quantitativos da tabela | hoje o plano é o agente calcular por overlay e o modelo só declarar as colunas; falta definir o formato de `tabela.linhas` quando é calculado |
| P4 | Modelo default definitivo | depende de rodar as prompts-fixture contra DeepSeek e ao menos um concorrente e comparar taxa de spec idêntico |
| P5 | Geração automática de título da conversa | o [`01`](01-arquitetura.md) prevê "título gerado depois pela IA"; falta decidir se é chamada separada e barata ou parte do primeiro turno |
| P6 | Comportamento com múltiplos agentes online | qual PC recebe o job quando o usuário não escolhe; hoje a tool aceita `agent_id` opcional sem regra de default |
| P7 | Cache de contexto entre usuários | o bloco estável é igual para todos; avaliar se o provedor permite compartilhar cache sem vazar contexto |
