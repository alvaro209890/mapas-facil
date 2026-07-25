# 09 — Segurança e privacidade

Este documento parte dos contratos de [`01-arquitetura.md`](01-arquitetura.md) e responde a uma
pergunta: **o que acontece se cada peça do sistema for comprometida?** Ela pesa mais aqui do que num
SaaS comum, porque o Mapas Fácil instala software com permissão de escrita no PC do usuário e esse
software aceita instruções de um servidor na internet — a decisão que compra todo o valor do produto
(`arcpy` local, dados que não sobem) é também onde se concentra quase todo o risco.

Ativos em ordem de gravidade do pior caso, não de probabilidade:

| # | Ativo | Pior caso |
|---|---|---|
| A1 | Escrita/execução no PC do usuário (via agente) | execução remota de código em todos os PCs pareados, ao mesmo tempo |
| A2 | Dados do cliente (shapefile, matrícula, CAR, CPF) | vazamento de dado pessoal de terceiro |
| A3 | Segredos do backend (chave de IA, authkey SEMA, `JWT_SECRET`, `DATABASE_URL`) | conta de terceiro esgotada; forja de sessão |
| A4 | Histórico de conversas e `MapSpec` | vazamento comercial (quais clientes, quais imóveis) |
| A5 | Disponibilidade | usuário volta a fazer mapa à mão; irritante, não grave |

A1 é uma ordem de grandeza mais grave que os outros: onde houver conflito com conveniência, A1 ganha.

## Modelo de ameaças

| Ator | O que pode tentar | Impacto | Mitigação |
|---|---|---|---|
| Usuário legítimo | pedir mapa de pasta não autorizada; sobrescrever projeto por acidente | baixo | allowlist explícita; saída sempre em `<pasta_destino>/<job_id>/`, nunca sobrescreve |
| Usuário malicioso do próprio workspace | usar o agente de um colega para ler/escrever no PC dele | médio | dono da máquina vê e revoga; papéis `owner`/`membro`; `audit_log` de todo job por ator |
| Usuário de outro workspace | forjar `agent_id`/`job_id` para direcionar escrita a PC alheio | alto | toda rota filtra por `workspace_id`; despacho valida que job e agente são do mesmo workspace |
| Atacante externo sem credencial | força bruta no código de pareamento; enumerar `job_id`; SSRF; roubo de sessão | alto | código de 8 caracteres com TTL 10 min, uso único e rate limit; IDs opacos; allowlist de saída; cookie `httpOnly` e access token de 15 min |
| Atacante com controle do backend | mandar comando arbitrário para todos os agentes | **crítico** | o protocolo não tem mensagem capaz de expressar "execute isto" — seção seguinte |
| Provedor de IA | ver o chat; treinar com ele; devolver `MapSpec` malicioso | médio | nunca recebe geometria nem arquivo; opt-out de treinamento; saída passa pelo validador antes de virar job |
| Dependência comprometida (PyPI, npm) | exfiltrar segredos; injetar código no instalador | alto | lockfile com hash, Dependabot, build em runner limpo, SHA-256 publicado, revisão de bump em `agent/` |
| Rede hostil / proxy corporativo | MITM no WebSocket | médio | só WSS com validação de certificado; sem opção de desabilitar TLS, nem em dev |

Risco residual aceito: administrador na máquina do usuário e comprometimento da Vercel ou do Render.

## A1: por que "backend comprometido" não pode virar RCE

O agente roda com o usuário do Windows, tem `arcpy` disponível e obedece a mensagens de
`api.mapasfacil.app`. Se a única barreira fosse "o backend só manda coisa boa", comprometê-lo
significaria RCE em todo o parque instalado. A barreira precisa ser **estrutural**: mesmo com
controle total do backend, o atacante não deve conseguir expressar "execute este programa".

**1. O canal só transporta dados declarativos.** As mensagens backend → agente são exatamente sete
([`01`](01-arquitetura.md#protocolo-websocket-agente--backend)): `job.dispatch`, `job.cancel`,
`fs.list`, `fs.inspect`, `doctor.run`, `agent.update`, `ping`. Nenhuma tem campo para código, linha
de comando, caminho de executável, script ou nome de módulo. O `job.dispatch` carrega um `MapSpec`,
que descreve *o mapa desejado*, nunca *como produzi-lo*. A tradução para chamadas `arcpy` vive
**dentro do agente**; o backend não conhece o nome de uma função `arcpy` e portanto não tem
vocabulário para pedir uma.

**2. Validação por schema na entrada, com enumerações fechadas.** O agente valida toda mensagem contra
o JSON Schema de `shared/schemas/` antes de qualquer I/O, com `additionalProperties: false` em todos
os níveis:

```yaml
mxd_template / layout_template: enum de shared/templates/MANIFEST.json (nome, nunca caminho)
crs:      "EPSG:\d{4,5}"            escala: inteiro da lista de escalas bonitas, ou "auto"
saidas:   subconjunto de {mxd, pdf, preview_png, geojson}     estilo.linha: "#RRGGBB"
fonte:    "local.<id>" resolvido pelo agente, ou id do catálogo
filtro:   where clause validada por parser próprio, reescrita a partir da árvore
```

`mxd_template` é um **nome de chave**, resolvido pelo agente para um caminho dentro da pasta de
templates que ele mesmo instalou. Um `"mxd_template": "..\\..\\Windows\\System32\\cmd.exe"` não está
na enumeração e é rejeitado antes de qualquer I/O.

**3. A allowlist de pastas é local e só o usuário a altera.** A lista vive em disco na máquina do
usuário. O backend tem uma cópia (`agents.pastas_autorizadas`) apenas para exibir na UI e para a IA
saber onde procurar; ela não é autoritativa, e alterá-la no banco não amplia permissão alguma.
`PATCH /v1/agents/{id}` faz o agente pedir **confirmação na interface local** (tray), mostrando quais
caminhos entram e quais saem. Sem clique, nada muda — ampliar escopo exige presença física. O módulo
`fsguard` ([`04-agente-local.md`](04-agente-local.md)) canonicaliza o caminho antes de comparar, e
estes casos devem ser negados (teste obrigatório em [`11-testes-e-qa.md`](11-testes-e-qa.md)):

```
C:\Autorizado\..\Windows\Temp\x         -> travessia
C:\Autorizado\junction_para_C_Windows\  -> symlink/junction que sai do escopo
\\servidor\share\x  e  \\?\C:\Windows\x -> UNC e prefixo estendido
C:\Autorizado2\x  (allowlist C:\Autorizado) -> prefixo de string não é fronteira de diretório
C:\AUTORIZADO\..\x                      -> case-insensitive, mas por caminho canônico
CON, NUL, C:\Autorizado\a.mxd:oculto    -> nome reservado e alternate data stream
```

**4. O agente nunca executa binário indicado remotamente.** O único executável externo lançado é o
Python 2.7 do ArcMap (ou o do ArcGIS Pro), e o caminho vem do **registro do Windows local**,
descoberto pelo `doctor`, ou de configuração feita na própria máquina. Não existe campo
`python_path`/`arcgis_python` em nenhum payload — diferente do projeto anterior, em que
`arcgis_python` era campo de configuração de projeto. O `arcpy_export.py` é versionado dentro do
agente, com integridade verificada por hash na inicialização, e recebe o `MapSpec` por arquivo JSON
UTF-8, nunca por `argv` (o que também resolve acento em Python 2.7).

**5. Atualização automática exige assinatura e confirmação.** Ao receber
`agent.update {versao, url, sha256}`, o agente recusa `url` fora do domínio de distribuição fixado no
binário (pinning), confere o SHA-256, **verifica a assinatura de código** e só então mostra versão,
changelog e botão ao usuário. Instalação silenciosa não existe; sem assinatura válida o download é
descartado e o evento vai para o `audit_log`. Enquanto não houver certificado
([`12`](12-deploy-e-distribuicao.md)), a atualização automática fica **desligada** — preferimos
atrito a um canal de update sem verificação criptográfica.

## Pareamento navegador ↔ agente

| Etapa | Regra |
|---|---|
| Geração | `POST /v1/agents/pair-code` autenticado; 8 caracteres de alfabeto sem ambiguidade (sem `O`/`0`, `I`/`1`/`l`), CSPRNG, ~41 bits |
| Validade | TTL de 10 minutos, uso único, invalidado ao ser usado ou ao gerar outro para o mesmo workspace |
| Rate limit | 5 tentativas de `POST /v1/agents/pair` por IP por minuto e 10 por código; ao esgotar, o código é queimado e o evento auditado |
| Troca | agente envia código + `hostname`, `os`, `agent_version`, `contract_version` e recebe `agent_token` opaco (≥256 bits) |
| Armazenamento | no banco, apenas `token_hash` (hash lento com sal), nunca o token em claro; no agente, Windows Credential Manager via `keyring`, nunca em `.json`, `.ini`, env var ou linha de comando |
| Escopo | vale para um `workspace_id` e um `agent_id`; não serve para rotas de usuário |
| Revogação | `DELETE /v1/agents/{id}` grava `revogado_em`, derruba o WebSocket na hora e cancela jobs pendentes |
| Rotação | sob demanda, e obrigatória ao detectar `hostname` diferente do registrado (sinal de token copiado) |

Descartados: QR code (o usuário está no mesmo PC, sem ganho); OAuth device flow (servidor de
autorização sem benefício, já que o agente não age em nome de terceiros); mTLS por agente (melhor
tecnicamente, mas emissão e renovação em máquina de usuário final custam mais suporte do que valem na
v1 — reavaliar na v2).

## Autenticação de usuário

Magic link por e-mail, sem senha.

| Item | Decisão |
|---|---|
| Início | `POST /v1/auth/magic-link`; resposta idêntica exista ou não a conta (não enumera usuários). Token do link aleatório, TTL de 15 min, uso único, ligado ao e-mail, guardado como hash |
| Troca | `POST /v1/auth/callback` devolve access token JWT de **15 minutos** e grava o refresh em cookie |
| Cookie de refresh | `HttpOnly`, `Secure`, `SameSite=Lax`, path restrito à rota de refresh, TTL de 30 dias |
| Rotação | cada `POST /v1/auth/refresh` emite novo refresh e invalida o anterior; reuso de token já usado invalida a família inteira e audita (detecção de roubo) |
| JWT | `sub`, `workspace_id`, `papel`, `exp`, `iat`, `jti`, assinado com `JWT_SECRET` |
| Rate limit | por e-mail (3 links/10 min) e por IP |

Por que não senha: exigiria recuperação, política de complexidade, hashing, risco de vazamento de
base e suporte — e o e-mail seria o fator de recuperação de qualquer jeito. Por que não OAuth de
terceiros na v1: coloca dependência externa no caminho crítico do login e exige configurar OAuth app
por ambiente, sem resolver nenhum problema atual; entra na v2 se houver demanda de SSO, e o modelo
`users` + `workspace_members` já suporta. MFA não está na v1 — o passo seguinte natural é passkey,
não TOTP.

## Autorização

| Papel | Pode |
|---|---|
| `owner` | tudo do workspace: convidar/remover membros, parear e revogar agentes, alterar pastas autorizadas, excluir dados |
| `membro` | criar conversas, gerar jobs nos agentes do workspace, ver artefatos e histórico |

Regras verificadas em toda rota e no despacho:

1. Todo acesso a `conversations`, `messages`, `map_specs`, `jobs`, `artifacts` e `agents` filtra por
   `workspace_id` do token. Não existe consulta por id sem esse filtro.
2. Um agente pertence a exatamente um workspace (`agents.workspace_id`); seu token só autentica
   mensagens sobre jobs daquele workspace.
3. Antes de `job.dispatch`, o backend confirma que `jobs.agent_id` é o agente conectado **e** que
   `jobs.conversation_id` é do mesmo `workspace_id`. Divergência é `403` mais `audit_log`.
4. `POST /v1/jobs/{id}/artifacts` só aceita upload do agente dono do job. IDs são ULID/UUID opacos,
   mas a autorização não depende de imprevisibilidade de id.

Multiusuário no mesmo agente está fora da v1 ([`00`](00-visao-e-escopo.md)), o que evita a pergunta
difícil de "qual membro escreve no PC de quem": quem pareia a máquina é quem a usa.

## Segredos

| Segredo | Onde vive | Quem acessa | Rotação |
|---|---|---|---|
| Chave do provedor de IA | env var no backend (Render) | processo do backend; 1 mantenedor no painel | trimestral e a cada saída de pessoa; limite de gasto no provedor |
| `authkey` SEMA (WFS) e chave Planet | **somente no agente** (Credential Manager / env `SEMA_WFS_AUTHKEY`, `PLANET_API_KEY`) — nunca no backend nem no frontend | usuário do PC | quando a SEMA reemitir; Planet, trimestral |
| `JWT_SECRET` | env var no backend | backend | com janela de dois segredos (novo assina, antigo valida) |
| `DATABASE_URL` | env var gerenciada pelo Render | backend | ao rotacionar credencial do Postgres |
| `agent_token` | Credential Manager no PC; `token_hash` no banco | agente local | sob demanda ou por mudança de host |
| Chave de assinatura de código | cofre do mantenedor / HSM do provedor | só o pipeline de release | conforme validade do certificado |

Nota sobre a `authkey` SEMA: quem baixa WFS é o **agente**, na rede do usuário (a SEMA
bloqueia IP fora do Brasil — lição do GeoForest/Cerebro). A chave **não** passa pelo backend
nem pelo frontend: o usuário cola a authkey dele na UI do agente, que guarda no Credential
Manager. O catálogo só declara `auth: "sema_authkey"` (o *nome*). Proxyar WFS pelo backend
é proibido (geodado na nuvem + geobloqueio). Default no código = string vazia — a dívida de
authkey hardcoded do GeoForest **não se replica** (CI com gitleaks).

Receitas e gotchas: [`13-wfs-e-servicos-geo.md`](13-wfs-e-servicos-geo.md).

Regras sem exceção: nunca no repositório (`.env.example` lista **nomes** com valor vazio); nunca no
frontend (só `NEXT_PUBLIC_API_URL` é público, e segredo em `NEXT_PUBLIC_*` é bug bloqueante); nunca em
log, `job.log`, SSE ou `audit_log` (o logger redige `Bearer `, `sk-`, `authkey=`); default de código é
**string vazia**, nunca chave real como fallback.

O projeto anterior falhou exatamente aqui: houve chave DeepSeek hardcoded em `core/llm/deepseek.py`,
em repositório público, e o handoff precisou registrar por escrito que ela "não deve voltar a ter
chave hardcoded" ([handoff](../../NexoGeo-Ambiental/docs/NEXOMAP_AGENT_HANDOFF.md)). Disciplina não
bastou; aqui o controle é mecânico:

| Camada | Controle |
|---|---|
| Máquina do dev | hook `pre-commit` com `gitleaks protect --staged`; o commit falha localmente |
| CI | `gitleaks detect` no diff do PR — **falha bloqueia merge**, não é aviso |
| CI | varredura de `NEXT_PUBLIC_*` com valor parecido com chave |
| Revisão | diff que toque `.env.example`, auth ou `fsguard` exige segundo par de olhos |
| Reação | procedimento escrito: rotacionar primeiro, limpar histórico depois (o que vazou, vazou) |

## Privacidade dos dados do cliente

O diferencial do produto é uma promessa que precisa ser verificável: **shapefile de cliente não sobe
para a nuvem**.

| Trafega para a nuvem | Nunca trafega |
|---|---|
| `MapSpec` (JSON declarativo) | shapefiles, `.zip` deles, geodatabases |
| Nomes de arquivo e pasta dentro da allowlist | conteúdo de arquivo |
| Metadados de `fs.inspect`: geometria, CRS, contagem, campos, **bbox** | geometrias completas, tabela de atributos |
| Texto do chat digitado pelo usuário | rasters e imagens de satélite baixadas |
| `preview.png` — **opt-in por job**, com aviso do que a imagem revela | `mapa.mxd` e `mapa.pdf` (ficam no PC; `artifacts.storage_key` nulo) |
| `validacao.json` (checks IMAP, sem geometria) | matrícula, CPF, CAR — salvo o que o usuário digitar no chat ou num rótulo |

Duas ressalvas honestas que a UI precisa comunicar: **bbox e escala localizam o imóvel** com boa
precisão e contam como dado do cliente, mesmo sendo metadado necessário à validação; e rótulos como
`"Fazenda Trevisol (Lote 65)\nMatrícula 13.533"` vão dentro do `MapSpec`, logo para o banco e para a
IA — é inerente, porque o texto tem que aparecer no mapa.

| Dado | Retenção |
|---|---|
| `conversations`, `messages`, `map_specs` | enquanto o workspace existir; `DELETE /v1/conversations/{id}` é soft delete, purga física em 30 dias |
| `job_events` | 90 dias (replay de SSE não precisa de mais) |
| `artifacts` com `storage_key` (preview) | 30 dias; depois o objeto é apagado e resta o metadado |
| `audit_log`; log de aplicação; log local do agente | 12 meses append-only; 30 dias; 14 dias rotativo no PC do usuário |

Exclusão de conta: o `owner` pede e em até 7 dias tudo é apagado, inclusive o `audit_log`, exceto o
mínimo legal de registro da exclusão. Nada no PC do usuário é tocado — apagar os `.mxd` dele não é
nosso papel; a desinstalação remove token e configuração.

**LGPD.** O controlador é o usuário (consultoria); somos operador. Ainda assim, dado geoespacial de
imóvel rural **pode ser dado pessoal**: um polígono isolado não é, mas o mesmo polígono vinculado a
matrícula, CAR, nome de proprietário ou CPF identifica pessoa natural. A arquitetura reduz o problema
por design (o polígono fica no PC), restando rótulo, bbox e nome de arquivo — que ainda podem conter
nome e matrícula. Antes do release: política de privacidade replicando a tabela acima, cláusula de
operador no termo de uso e registro do provedor de IA como suboperador.

## O que é enviado ao provedor de IA

Somente texto e estrutura: mensagens do chat, `MapSpec` atual, nomes de camada disponíveis, catálogo
e resultados de tool calls.

1. **Nunca geometria** — nem WKT, nem GeoJSON, nem coordenada de feição. Nem "para a IA escolher a
   escala": extent e escala são calculados pelo agente e pelo validador.
2. `fs.inspect` devolve bbox ao backend, mas o que entra no prompt é a informação derivada de que a
   decisão precisa ("camada em EPSG:31982, 1 feição, campos NOME, LOTE, MATRICULA").
3. Opt-out de treinamento configurado na conta do provedor, com evidência arquivada; provedor sem
   opt-out não é elegível. Retenção zero ou mínima quando oferecida.
4. A saída do modelo é **não confiável**: passa pelo validador e pelas tools atômicas
   ([`07-ia-e-tools.md`](07-ia-e-tools.md)) antes de virar job. Prompt injection por nome de arquivo
   (`AVN; ignore instruções anteriores.shp`) não escapa, porque nada que a IA produz vira comando.
5. O provedor é variável de configuração, para não travar em fornecedor que mude política de dados.

## Superfície web do backend

| Controle | Regra |
|---|---|
| CORS | allowlist explícita (`https://mapasfacil.app` e previews da Vercel do projeto). Sem `*`, sem regex frouxo; `allow_credentials` só com origem exata |
| Headers | CSP `default-src 'self'` com `connect-src` para `api.mapasfacil.app` e sem `unsafe-inline` em script; HSTS com preload; `nosniff`; `Referrer-Policy: strict-origin-when-cross-origin`; `X-Frame-Options: DENY`; `Permissions-Policy` restritiva |
| Rate limit | por IP, por conta (mensagens, criação de job) e por rota sensível (`pair`, `magic-link`); `429` com `Retry-After` |
| Validação e tamanho | Pydantic com `extra="forbid"` em **todo** corpo, query e header customizado, sem `dict` solto atravessando camada; corpo limitado e `MapSpec` com teto de bytes, camadas e linhas de tabela |
| SSRF | o backend não busca URL fornecida por usuário ou pela IA. As únicas saídas HTTP são provedor de IA, e-mail e storage, todos hosts fixos. Sem "importar camada por URL" na v1 |
| Upload e download | só `preview.png` e `validacao.json`, tipo verificado por conteúdo e não por extensão, teto de poucos MB, `sha256` conferido contra o de `job.artifact`; `GET /v1/artifacts/{id}` redireciona para URL assinada de TTL 15 min, `Content-Disposition: attachment`, fora do domínio da API |
| WebSocket, dependências e banco | auth no handshake, timeout de idle, limite de tamanho de mensagem, uma conexão ativa por `agent_id` (a nova derruba a antiga); `pip-audit`/`npm audit` na CI; ORM com parâmetros ligados; usuário do banco sem `SUPERUSER`; TLS obrigatório |

## Auditoria

`audit_log` é **append-only** (sem `UPDATE`, sem `DELETE` fora da retenção) e usa as colunas de
[`01`](01-arquitetura.md#modelo-de-dados-postgres): `(id, workspace_id, ator, acao, alvo, ip,
payload, criado_em)`.

| `acao` | `payload` contém |
|---|---|
| `login.magic_link_enviado`, `login.sucesso`, `login.falha` | e-mail mascarado, IP, motivo da falha |
| `login.refresh_reuso` | família de tokens invalidada (suspeita de roubo) |
| `agente.pair_code_gerado`, `agente.pareado`, `agente.pair_falhou` | usuário, hostname, SO, versão, pastas iniciais, tentativas |
| `agente.allowlist_alterada`; `agente.revogado`; `agente.token_rotacionado` | diff de pastas antes e depois; quem revogou; motivo da rotação (manual / host divergente) |
| `job.criado`, `job.cancelado` | ator, `agent_id`, `mapspec_id`, `pasta_destino` |
| `autorizacao.negada`, `artefato.upload_rejeitado` | rota e ids envolvidos; motivo (tipo, tamanho, hash) |
| `conta.exclusao_solicitada` | prazo |

Nunca vai para o `audit_log`: token, segredo, conteúdo de mensagem, geometria. Caminho de pasta vai
(é o objeto do controle de acesso), e por isso o próprio `audit_log` é dado sensível. No agente há log
local espelhando o que ele aceitou e negou — a evidência que sustenta o critério de sucesso 5 de
[`00`](00-visao-e-escopo.md) ("zero shapefile trafegando, auditável no log do agente").

## Checklist de segurança pré-release

Cada item é verificável e tem teste associado em [`11-testes-e-qa.md`](11-testes-e-qa.md).

```
[ ] gitleaks passa no histórico completo, não apenas no último diff
[ ] .env.example sem valor real; nenhum segredo em NEXT_PUBLIC_*
[ ] Suíte do fsguard verde: travessia, symlink, UNC, case, prefixo, nome reservado, ADS
[ ] Nenhum payload do protocolo tem campo de executável, código ou comando
[ ] Schema do agente com additionalProperties:false em todo nível; teste de payload hostil
[ ] mxd_template resolvido por enum local; valor de travessia rejeitado em teste
[ ] Alteração de allowlist exige confirmação na UI local (teste manual documentado)
[ ] Atualização automática desligada enquanto não houver assinatura de código válida
[ ] agent_token só no Credential Manager; revogação derruba o WebSocket em menos de 5 s
[ ] Pareamento: TTL, uso único e rate limit cobertos por teste
[ ] Access token de 15 min; refresh rotativo com detecção de reuso testada
[ ] Isolamento cross-workspace em toda rota com id; job de outro workspace não despacha
[ ] CORS sem curinga; headers de segurança conferidos na resposta de produção
[ ] Rate limit em magic-link, pair e mensagens; Pydantic com extra="forbid" em toda entrada
[ ] Nenhuma saída HTTP com host derivado de entrada de usuário ou da IA
[ ] Upload valida tipo por conteúdo, tamanho e sha256; URL assinada com TTL de 15 min
[ ] Logger redige Bearer/sk-/authkey em log, SSE e job.log; audit_log sem token nem geometria
[ ] Política de privacidade igual à tabela "trafega / não trafega"; opt-out de treinamento
    confirmado no provedor, com evidência arquivada
[ ] Restore do backup do Postgres testado de verdade (ver 12)
[ ] pip-audit e npm audit sem vulnerabilidade alta; scrubbing do Sentry testado com evento real
```

## Pendências e decisões abertas

| # | Questão | Opções | Quando decidir |
|---|---|---|---|
| S1 | `authkey` SEMA no agente | usuário cola a chave própria no agente (decisão alinhada ao [13](13-wfs-e-servicos-geo.md)); alternativas descartadas: só camadas públicas / proxy no backend | fechado na v1 — validar UX no M2 |
| S2 | Assinatura de código do instalador | OV (barato, SmartScreen reclama até ganhar reputação) vs EV (caro, reputação imediata) | antes do primeiro release público |
| S3 | MFA / passkey | só magic link na v1; WebAuthn depois | ao primeiro cliente com exigência de compliance |
| S4 | Agente como serviço do Windows ou app de tray | serviço roda sem sessão, mas `arcpy` e licença podem exigir sessão interativa; tray é mais simples e menos privilegiado | durante M2, em máquina real |
| S5 | Cifrar `pastas_autorizadas` e rótulos no banco | claro (simples, buscável) vs cifrado em coluna (protege dump vazado) | ao primeiro cliente com dado de terceiro sensível |
| S6 | Sandbox do subprocess ArcPy (Job Object, limite de CPU/memória, sem rede) | `arcpy` é código de terceiro rodando junto do nosso | M2 ou M4 |
| S7 | Modo totalmente offline (agente sem nuvem); pentest externo | pedido provável de cliente conservador, mas muda o modelo de auth; contratar vs revisão interna com checklist | pós-v1; quando houver receita |
