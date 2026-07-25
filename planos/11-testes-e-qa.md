# 11 — Testes e QA

Estratégia de testes dos três componentes de [`01-arquitetura.md`](01-arquitetura.md), organizada em
torno de um problema que define tudo o mais: **a parte mais crítica do produto não roda em CI
hospedada**.

## O problema central

Gerar `.mxd` exige `arcpy`, que exige Windows com ArcMap 10.6+ (ou ArcGIS Pro) e **licença ativa** —
nada disso existe em runner do GitHub Actions. O erro seria aceitar isso e não testar o `.mxd`: foi o
que aconteceu no projeto anterior, onde `mapa.mxd` ficou como "somente quando ArcMap estiver
configurado" e nunca teve teste ([handoff](../../NexoGeo-Ambiental/docs/NEXOMAP_AGENT_HANDOFF.md)).
Sem teste automatizado, o `.mxd` volta a ser opcional na prática. Solução em três anéis, o mesmo
código dividido por marcador de pytest:

| Anel | Onde roda | O que cobre | Gate |
|---|---|---|---|
| **Público** (`-m "not arcpy and not net"`) | GitHub Actions (ubuntu, windows) | tudo que não precisa de `arcpy` nem de rede externa: `MapSpec`, API, fila, `fsguard`, frontend | bloqueia merge |
| **Contrato** (`-m contract`) | qualquer lugar, inclusive a máquina do dev | schemas de `shared/` × fixtures canônicas × fakes dos três lados; garante que web, backend e agente concordam sobre o mesmo contrato | bloqueia merge |
| **MXD** (`-m arcpy`) | runner self-hosted Windows com ArcMap licenciado | geração real de `.mxd`/`.pdf`, regressão visual, fontes de dados | bloqueia release; roda em `main` e em tag |

O anel de contrato é o substituto honesto do que não roda na nuvem: prova que o **acordo** está
correto; o anel MXD prova que a **execução** está correta.

**Runner self-hosted.** Máquina Windows (VM ou desktop dedicado) com ArcMap, Python 2.7 do ArcGIS,
templates reais e runner registrado com label `windows-arcmap`. Não é exposto a PR de fork; roda em
push para `main`, em tag e por `workflow_dispatch`; usa pasta temporária apagada no fim. Runner
offline faz o job **falhar visivelmente**, nunca ficar "skipped" — release não passa por ausência de
teste. Descartados: emular `arcpy` (não existe; `arcpy.mapping` é proprietário e o `.mxd` é binário
fechado); ArcGIS Server em container (licença proibitiva, [`00`](00-visao-e-escopo.md)); testar à mão.

## Pirâmide adaptada

```
topo    manual (checklist de release)
        E2E Playwright com fakes  |  suíte MXD no runner Windows
        integração de API  |  integração do agente (subprocess e fs reais)
        unitários do backend | unitários do agente | componentes do frontend
base    contrato (schemas + fixtures)
```

A base larga é deliberadamente a **validação do `MapSpec`**: é o contrato central, é puro (entra JSON,
sai veredito) e é onde um bug custa mais — spec inválido aceito vira mapa errado no PC do cliente.

## Backend

Stack: `pytest`, `pytest-asyncio`, `httpx.AsyncClient` sobre ASGI, `factory-boy`.

### Validação do `MapSpec`

Um teste por invariante de [`01`](01-arquitetura.md#mapspec-v1--o-contrato-central), em par (válido /
violado); a mensagem de erro faz parte do contrato testado.

| Invariante | Caso válido | Casos inválidos |
|---|---|---|
| `mxd_template` no manifesto | `Dinamica_2026.mxd` | nome inexistente; caminho com `..`; vazio; `null` |
| `fonte` resolvível | `local.lotes` na listagem; id do catálogo | `local.inexistente`; id fora do catálogo; ausente |
| `escala` bonita; `saidas` ⊆ conjunto; `crs` projetado e compatível com a UF | `22000`, `"auto"`; `["mxd","pdf"]`; `EPSG:31982` para MT | `21750`, `0`, negativo; `["shp"]`, lista vazia; `EPSG:4674` (geográfico) e `EPSG:31984` (fuso errado) |
| `contract_version`; `area_base.fonte` polígono | igual à do agente; shapefile de lote | maior que a do agente → `agent_outdated`; camada de linha; fonte ausente |
| `tabela` coerente; limites de tamanho | colunas × linhas dentro do teto | número de colunas divergente; `total` sem coluna numérica; camadas acima do teto |

O validador **rejeita**, nunca corrige em silêncio, e há teste de que o spec de entrada não é mutado.

### API

Cliente async contra o app ASGI, sem servidor de rede, com cada teste numa transação com **rollback**
no teardown (`SAVEPOINT` sobre conexão única) contra Postgres real em container — nunca SQLite, porque
usamos `jsonb` e índices que ele não reproduz. Por rota: caminho feliz, `401`, `403` de outro
workspace, `404`, `422`, `429`; o isolamento cross-workspace é obrigatório em toda rota que receba id
([`09-seguranca-e-privacidade.md`](09-seguranca-e-privacidade.md)). O SSE de
`POST /v1/conversations/{id}/messages` tem teste de **ordem** (`message.start` → `text.delta`\* →
`tool.call`/`tool.result` → `mapspec.updated` → `job.created` → `message.end`) e de tolerância a
evento desconhecido; `cancel` interrompe o turno e emite `message.end`.

### Fake do provedor de IA

Nunca chamar o provedor real na CI: custa, é lento e é não determinístico.

```
tests/fixtures/llm/dinamica_2026_trevisol.json   # gravação: mensagens + tool_calls + respostas
tests/fixtures/llm/edicao_cor_atp.json           # edição sobre spec existente
tests/fixtures/llm/camada_inexistente.json       # alucinação -> validador rejeita
tests/fixtures/llm/loop_sem_convergir.json       # repete tool -> guarda de iteração
tests/fixtures/mapspec/, shp/, pdf_baseline/     # ver seção Fixtures
```

**Replay** é o padrão da CI: o fake devolve as mesmas `tool_calls` na mesma ordem, offline. **Gravação**
é manual, com a chave real, quando o system prompt muda, e o diff da fixture entra na revisão do PR. Há
também fakes feitos à mão para robustez — JSON malformado, argumento faltando, tool inexistente,
resposta vazia, timeout, `429` — e em todos o backend emite `event: error` conhecido e não cria job.

### Hub WebSocket

Cliente falso de agente falando o envelope de
[`01`](01-arquitetura.md#protocolo-websocket-agente--backend):

| Cenário | Esperado |
|---|---|
| `hello` com `contract_version` suportada / antiga demais | agente online com `pastas_autorizadas` gravadas / job recusado com `agent_outdated` e UI pedindo atualização |
| RPC `fs.list`, `fs.inspect`, `doctor.run`; RPC sem resposta | `rpc.result` com `reply_to` correto; timeout de 5 s e degradação graciosa (a IA segue sem a listagem) |
| Duas conexões com o mesmo `agent_id`; token revogado; mensagem fora de schema; `heartbeat` ausente | a nova derruba a antiga; conexão fechada sem `job.dispatch`; mensagem descartada com log sem matar a conexão; agente vira offline após a janela |

### Fila e ciclo de vida do job

Testes do diagrama de [`01`](01-arquitetura.md#ciclo-de-vida-do-job) com clock controlado:

- `queued` sem agente online permanece `queued` (UI mostra "aguardando seu PC"), nunca `failed`.
- `dispatched` sem `job.accepted` em 30 s volta a `queued` e redespacha; após 3 tentativas, `failed`.
- `running` com queda do WebSocket: ao reconectar o agente reporta e o job segue `running`, sem
  reinício nem duplicação; mensagem não entregue fica na fila 24 h.
- `job.cancel` durante `running` leva a `cancelled`, e `job.done` posterior é ignorado (idempotência).
- `job_events` é append-only e permite replay do SSE; edição gera job com `parent_job_id` e `versao`
  incrementada, deixando o anterior intacto.

## Agente local

Roda em `windows-latest` (público) para tudo que não é `arcpy`.

### `fsguard` — a suíte mais importante do repositório

Parametrizada, um caso por técnica de escape. Todos devem **negar**:

```python
NEGAR = [
    r"C:\Autorizado\..\Windows\Temp\x.mxd",    # travessia (simples e composta)
    r"C:\Autorizado2\x.mxd",                   # prefixo de string não é fronteira de diretório
    r"\\servidor\share\x.mxd",                 # UNC; idem \\?\C:\Windows e C:/Windows/x.mxd
    r"C:\Autorizado\junction_windows\x.mxd",   # junction/symlink que sai do escopo
    r"C:\Autorizado\x.mxd:oculto",             # ADS; idem CON, NUL, byte nulo, case+travessia
]
PERMITIR = [r"C:\Autorizado\job_01H\mapa.mxd",
            r"C:\autorizado\Sub Pasta\Fazenda São João\mapa.pdf"]  # case, espaço, acento
```

O caso de junction exige criar o link de verdade (`mklink /J`), o que pode requerer privilégio — sem
ele o teste **falha com mensagem clara**, não é pulado em silêncio. Complementos: valida o caminho
**resolvido**, não o recebido; a allowlist só muda por confirmação local; a saída vai sempre para
`<pasta_destino>/<job_id>/` e nunca sobrescreve arquivo existente.

### `doctor`

Registro do Windows e sistema de arquivos mockados, para cobrir o que não temos em máquina:

| Cenário mockado | Diagnóstico esperado |
|---|---|
| ArcMap 10.6, 10.8, ou ambos | escolhe a maior versão e reporta as duas |
| ArcGIS Pro 3.x sem ArcMap; nenhum dos dois | usa `arcpy.mp` avisando da diferença; `.mxd` indisponível com fallback PDF nativo ([`05`](05-motor-mxd-pdf.md)) |
| ArcMap presente com licença indisponível; Python 2.7 do ArcGIS ausente ou corrompido | erro **distinto** de "não instalado"; erro específico com o caminho procurado |
| Templates com hash divergente; registro apontando para pasta inexistente | lista quais; trata como não instalado |

O `doctor` nunca lança exceção não tratada: sempre devolve relatório, porque é o que o usuário vê
quando nada funciona.

### Resolvedor de camadas e parser do ArcPy

Com shapefiles fixture minúsculos: resolve `local.lotes`, aplica `filtro`, devolve CRS, contagem,
campos e bbox. Erros cobertos: `.shp` sem `.dbf`/`.shx`; `.prj` ausente; `.dbf` cp1252 com acento;
shapefile vazio; campo do `filtro` inexistente; `filtro` com aspas e caractere especial (reescrito da
árvore validada, nunca concatenado); `.zip` com travessia (zip slip). WFS com respostas gravadas:
cache por bbox, `500`, XML truncado, timeout, camada renomeada — contra a SEMA de verdade só no
marcador `net`. O parser da saída do subprocess Python 2.7 (JSON UTF-8 em arquivo) é testado com
saídas gravadas: sucesso; sucesso com aviso; traceback de `arcpy` (`ExecuteError`) mapeado para código
nosso; `print` de terceiro poluindo o stream (motivo de usar arquivo, não stdout); JSON truncado por
processo morto; cp1252 vindo do ArcMap; exit code não-zero sem JSON algum.

## Motor MXD (anel `arcpy`)

Roda no runner `windows-arcmap` e é o critério de aceite de todo milestone de mapa. **Integração:** um
teste por template do manifesto — abre o template, repõe as fontes para as fixtures, aplica
extent/escala/legenda/metadados/tabela, salva `.mxd`, exporta `.pdf` a 300 dpi e gera `preview.png`,
cronometrando, porque o critério da v1 é o mapa completo em menos de 3 minutos
([`00`](00-visao-e-escopo.md)). **Check de fontes quebradas (bloqueante, sem tolerância):** para cada
layer do `.mxd` salvo, checar `isBroken` e falhar se alguma estiver quebrada ou se algum `dataSource`
apontar para fora da pasta do job ou da pasta de dados do usuário — é a verificação por código do
critério "abre no ArcMap sem nenhum `!` vermelho".

**Regressão visual do PDF** em dois níveis, porque pixel puro é frágil demais para ser critério único:

1. **Diferença de pixels com tolerância.** Renderizar o PDF para PNG em DPI fixo, comparar com o
   baseline e falhar se a fração de pixels divergentes passar do limite (ordem de 0,5%), com limiar
   por canal para absorver antialiasing. O diff vira artefato do job de CI.
2. **Comparação estrutural por região.** A página é dividida em regiões nomeadas (título, mapa
   principal, legenda, tabela, metadados da imagem, minimapa, norte, logo), comparadas isoladamente
   com métrica de "tem conteúdo / está vazia / mudou muito". Dá diagnóstico útil ("a legenda mudou, o
   mapa não") e resiste a deslocamento de poucos pixels que quebraria a comparação global.

Complemento barato e estável: extrair o texto do PDF e afirmar que título, matrícula, datum,
satélite/sensor e os totais da tabela aparecem. Atualizar baseline é ação explícita — comando
dedicado, PNG commitado, revisor obrigado a olhar a imagem; nunca automático. Os checks *hard* de
[`06-padrao-imap.md`](06-padrao-imap.md) rodam sobre o PDF e viram `validacao.json`, com um teste por
check (um caso que passa, um que falha por spec adulterado) mais o teste de que check *hard* falhando
impede o job de virar `succeeded`.

## Frontend

| Nível | Ferramenta | Cobertura |
|---|---|---|
| Componente | Vitest + Testing Library | sidebar de conversas, bolha com tool call expansível, painel do `MapSpec`, seletor de agente (online/offline), preview do PDF, estados de erro |
| Streaming | servidor SSE falso | ordem dos eventos, `text.delta` incremental, tool call resolvendo, `mapspec.updated` atualizando o painel, reconexão, evento desconhecido ignorado |
| E2E | Playwright | fluxo completo contra backend e agente **fakes** |
| Acessibilidade | `axe-core` no Playwright | zero violação crítica; teclado no chat; foco visível; contraste |

Consultas usam papel e texto acessível (`getByRole`, `getByLabelText`), não `data-testid` — se não dá
para consultar por papel, provavelmente há problema de acessibilidade. Fluxo E2E mínimo, obrigatório
antes de qualquer release do site:

```
1. login por magic link (token de teste) e pareamento de agente fake por código de 8 caracteres
2. conversa nova: "Dinâmica 2026 da Fazenda Trevisol, lote 65, com AVN, AC e AUAS"
3. tool calls aparecendo, painel do MapSpec preenchendo, 9 etapas, preview.png e validação
4. edição ("deixa a ATP amarela"): surge versão 2 e a 1 continua acessível
5. recarregar no meio do job (progresso retomado por replay de job_events) e derrubar o agente
   fake (mensagem "aguardando seu PC", não erro)
```

## Fixtures

Versionadas em `tests/fixtures/`, com README de origem e como regerar.

| Fixture | Conteúdo | Tamanho alvo |
|---|---|---|
| `shp/lote_minimo/` e `shp/avn_ac_auas/` | 1 polígono retangular em EPSG:31982 com campos `NOME`, `LOTE`, `MATRICULA`, mais 3 polígonos dentro dele para legenda e tabela | poucos KB |
| `shp/quebrados/` e `shp/zip_slip.zip` | sem `.dbf`; sem `.prj`; `.dbf` cp1252 com acento; vazio; zip com travessia | poucos KB |
| `mapspec/*.json` e `mapspec/invalidos/*.json` | um canônico por tipo da série (Dinâmica 2008, Dinâmica 2019/2026, Uso Consolidado, Tipologia Vegetal, Embargos IBAMA, Alertas MapBiomas) e um por invariante violada, com o erro esperado ao lado | KB |
| `pdf_baseline/*.png`; `wfs/*.json|xml`; `llm/*.json`; `arcpy_out/*.json` | PNG de referência; respostas WFS/WMS gravadas (SEMA BBOX, SEMA INTERSECTS truncado, paginação 400, PAMGIA GeoJSON, INCRA GML, WMS XML-com-HTTP-200, GetCapabilities); `tool_calls`; saídas Python 2.7 | KB–centenas de KB |

Casos WFS obrigatórios nas fixtures (receitas do [13](13-wfs-e-servicos-geo.md) / GeoForest):

1. BBOX retorna N feições; INTERSECTS retorna M < N → clip local deve usar BBOX
2. `startIndex` → 400 `Cannot do natural order` → fallback single-page + `resultado_parcial`
3. WMS `Content-Type: text/xml` com HTTP 200 → rejeitar (não tratar como PNG)
4. Layer `Geoportal:TIPOLOGIA` ausente; `SIMCAR_D_TIPOLOGIA_VEGETAL` presente
5. Authkey ausente → warning `segredo_ausente`, job continua sem a camada

Nenhuma fixture contém dado real de cliente: geometrias sintéticas, nomes fictícios — requisito de
[`09`](09-seguranca-e-privacidade.md). O repositório é público e não usa LFS na v1; se os baselines
passarem de alguns MB, reduzir DPI ou adotar LFS.

## Suíte de avaliação da IA (evals)

Testes tradicionais não medem se o modelo **entendeu** o pedido em português. A suíte de evals mede.

```yaml
- id: dinamica_completa
  prompt: "faz a Dinâmica 2026 da Fazenda Trevisol com AVN, AC e AUAS"
  camadas_disponiveis: [local.lotes, local.avn, local.ac, local.auas]
  tools_esperadas: [estado_atual, listar_camadas_locais, criar_mapa, adicionar_camada x3,
                    editar_tabela, validar_mapspec, finalizar]
  mapspec_esperado: fixtures/mapspec/dinamica_2026.json
  campos_criticos: [mxd_template, crs, escala, camadas[].fonte, elementos_layout]
```

| Métrica | Definição | Meta v1 |
|---|---|---|
| Acerto de tool; acerto de campo crítico | tools chamadas contêm as esperadas, sem tool proibida; campos críticos idênticos ao esperado | ≥ 95%; ≥ 98% |
| Conformidade IMAP | `MapSpec` passando 100% dos checks *hard* | 100% |
| Rejeição correta | prompt impossível (camada inexistente, template inventado) em que a IA pede esclarecimento em vez de alucinar | ≥ 90% |
| Turnos até convergir; custo por mapa | mediana de idas e voltas; tokens × preço | ≤ 2; acompanhado |

Comparação por campo, não por igualdade de JSON — ordem de camadas e campos irrelevantes não devem
reprovar. Cada caso tem um par de **edição** ("agora deixa a ATP amarela"), porque o modo de falha mais
comum é a edição regredir algo que já estava certo. Roda quando muda o system prompt, as tools, o
catálogo ou o modelo, com tabela e diff no corpo do PR. Eval **não** bloqueia merge (é medição com
ruído), mas queda sem justificativa é motivo para não aprovar.

## Testes manuais

Checklist executado antes de cada release do agente, em VM com snapshot para repetir do zero.

| # | Cenário | O que observar |
|---|---|---|
| M1 | Instalação em Windows 11 virgem, sem Python e sem ArcMap | instalador conclui, tray abre, doctor explica a ausência sem travar |
| M2 | ArcMap instalado **sem licença** | mensagem distinta de "não instalado"; fallback PDF oferecido |
| M3 | Sem internet, e internet caindo no meio de um job | tray offline sem consumir CPU no backoff; job sobrevive, reporta ao reconectar, UI retoma |
| M4 | Caminho com acento e espaço (`C:\Projetos\Fazenda São João - Lote 65\`) | `.mxd` e `.pdf` corretos; nada de `UnicodeDecodeError` do Python 2.7 |
| M5 | Pasta dentro do OneDrive sincronizando; monitor com escala 150% e 4K | arquivo travado tratado com retry e mensagem clara, não erro cru; tray, confirmação de allowlist e diálogos legíveis, sem corte |
| M7 | Proxy corporativo com inspeção TLS; antivírus ativo | WSS funciona ou falha com mensagem acionável; instalador não é bloqueado em silêncio |
| M8 | Atualização do ArcMap (10.6 → 10.8); dois usuários do Windows na máquina; desinstalação | doctor detecta o novo caminho sem reinstalar; token não vaza entre perfis; desinstalação revoga o token, remove a configuração e preserva `.mxd`/`.pdf` |
| M10 | Primeiro mapa por um técnico que nunca viu o sistema | tempo total < 15 min (critério 3 de [`00`](00-visao-e-escopo.md)); hesitação conta como bug de UX |

## Definition of Done

| Tipo de mudança | Obrigatório antes do merge |
|---|---|
| Validação de `MapSpec` / schema em `shared/` | teste por invariante nova (válido + inválido); anel de contrato verde nos três lados; bump de `contract_version` se quebrar compatibilidade |
| Rota nova do backend | caminho feliz, `401`, `403` cross-workspace, `422`, `429`; `audit_log` se for ação sensível; documentada em [`01`](01-arquitetura.md) |
| Loop de IA / tools / system prompt; fila e ciclo de vida do job | fixture de replay nova e rodada de evals com tabela no PR; teste com clock controlado e idempotência de mensagem duplicada |
| `fsguard` / allowlist / auth; motor MXD / template / layout | caso de negação novo na suíte parametrizada e segundo par de olhos ([`09`](09-seguranca-e-privacidade.md)); teste `arcpy` no runner Windows, baseline visual revisado, `isBroken` verde |
| Componente de frontend | teste de componente; `axe` sem violação crítica; E2E atualizado se o fluxo muda |
| Dependência; migração de banco | lockfile atualizado, `pip-audit`/`npm audit` limpos, supply chain revisada se for do `agent/`; migração compatível para trás testada sobre dump de staging ([`12`](12-deploy-e-distribuicao.md)) |
| Correção de bug; documentação | teste que falha antes e passa depois, com o issue; coerência com [`01`](01-arquitetura.md) |

Cobertura não é meta numérica. Exigidos com cobertura de ramo alta e revisada: `MapSpec`, `fsguard`,
fila e autorização. O resto, o que fizer sentido.

## Bug bar e critérios de release

| Bloqueante (não sai release) | Exemplo |
|---|---|
| Escrita fora da allowlist | qualquer caminho negado que passe; sobrescrita de arquivo do usuário |
| Vazamento de dado do cliente; segredo exposto | geometria ou conteúdo de arquivo saindo para a nuvem ou para a IA; chave em repositório, log, bundle ou SSE |
| Falha de autorização | acesso ou despacho cruzando workspace |
| Mapa fora do padrão IMAP; camada quebrada no `.mxd` | check *hard* de [`06`](06-padrao-imap.md) falhando num template da série; `isBroken` verdadeiro em qualquer layer entregue |
| Perda de conversa ou de versão | mensagem, `MapSpec` ou job desaparecendo; `map_specs`/`job_events` deixando de ser append-only |
| Corrupção de saída; job travado; regressão de tempo | `.mxd` que não abre; job sem estado terminal nem erro; mapa da série passando de 3 min no runner de referência |

| Não bloqueante | Tratamento |
|---|---|
| Diferença estética dentro da tolerância visual | atualizar baseline com revisão |
| Check IMAP *soft* falhando; erro de WFS com fallback | aviso na UI e job entrega; documentar e monitorar |
| Ausência de ArcMap/licença com fallback; eval na margem; texto de UI, ordenação, atalho | comportamento esperado, não bug; monitorar; próxima release |
| Fora do escopo de [`00`](00-visao-e-escopo.md) (Linux, QGIS, multiusuário no mesmo agente) | fechar como fora de escopo |

Portão de release: `web` exige público e contrato verdes, E2E verde e `axe` sem violação crítica; `api`
exige público e contrato verdes com migração testada em dump de staging; `agent` exige público,
contrato e suíte MXD verdes, mais o checklist manual M1 a M9; qualquer release público exige o
checklist de segurança de [`09`](09-seguranca-e-privacidade.md) completo e os evals arquivados.

## Pendências e decisões abertas

| # | Questão | Opções | Quando decidir |
|---|---|---|---|
| T1 | Máquina do runner `windows-arcmap` e licença de CI | VM Windows com licença própria vs desktop físico do autor vs runner efêmero; licença adicional vs uso concorrente com a estação de trabalho | antes de M2 — sem isso o `.mxd` não tem teste |
| T2 | Tolerância exata da regressão visual e DPI do baseline | calibrar com o primeiro template real; frouxo não pega nada, rígido reprova sempre | M2/M4 |
| T3 | Baselines no Git ou em Git LFS; testar ArcGIS Pro (`arcpy.mp`) além do ArcMap | tamanho total dos PNGs em repositório público; dobrar a matriz de teste só se houver usuário real de Pro | quando passar de poucos MB; conforme demanda |
| T5 | Eval como gate de merge | hoje é medição; virar gate exige variância baixa e baseline estável | após ~10 rodadas |
| T6 | Teste de carga do hub WebSocket | quantos agentes por réplica antes de degradar (ver a limitação de 1 réplica em [`12`](12-deploy-e-distribuicao.md)) | antes do primeiro cliente com muitas máquinas |
| T7 | Suíte `net` diária contra SEMA/IBGE; mutation testing no validador | detecta mudança de layer antes do usuário, mas gera alerta ruidoso; mede a qualidade dos testes onde mais importa | pós-v1 |
