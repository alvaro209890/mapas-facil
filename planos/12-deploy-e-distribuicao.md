# 12 — Deploy e distribuição

Como cada um dos três artefatos de [`01-arquitetura.md`](01-arquitetura.md) sai do repositório e chega
ao seu destino, e como eles continuam compatíveis apesar de serem liberados em ritmos diferentes.

## Visão geral

| Artefato | Onde roda | Como chega lá | Ritmo típico | Quem decide atualizar |
|---|---|---|---|---|
| `web/` | Vercel | push na branch de produção | várias vezes por semana | nós |
| `backend/` | Render (Docker) | tag `api-vX.Y.Z` | semanal | nós |
| `agent/` | PC do usuário (Windows) | instalador `.exe`, ou atualização opt-in | mensal | **o usuário** |
| `shared/` | dentro dos três | versionado junto, referenciado por `contract_version` | com o contrato | nós |

A diferença que organiza este documento: **site e backend nós atualizamos; o agente, não.** Existe um
parque instalado que só muda quando o usuário quiser. Deploy sincronizado é impossível, e por isso
[`01`](01-arquitetura.md#regras-de-fronteira-invioláveis) já decidiu que a compatibilidade vem de
`contract_version`.

### Regra de compatibilidade

```
contract_version é um inteiro. Muda apenas quando o contrato quebra de forma incompatível
(campo obrigatório novo no MapSpec, semântica alterada de mensagem, remoção de campo).

O backend suporta as DUAS ÚLTIMAS versões de contrato do agente.

  backend em contract_version 5  ->  aceita agentes 5 e 4
                                 ->  agente 3 ou anterior: erro agent_outdated
```

1. O agente manda `contract_version` no `hello`
   ([`01`](01-arquitetura.md#protocolo-websocket-agente--backend)); o backend grava e a UI mostra o
   estado da versão em `GET /v1/agents`.
2. Dentro da janela, o backend emite `MapSpec` **no nível daquele agente** — campos introduzidos
   depois são omitidos e a UI avisa que o recurso exige atualizar.
3. Fora da janela, `POST /v1/jobs` falha com
   `{"erro": {"codigo": "agent_outdated", "mensagem": "...", "detalhes": {...}}}`; o mesmo código
   viaja como `event: error` no SSE e a UI mostra o download com a versão mínima exigida. Não há
   tentativa de degradar: mapa errado é pior que mapa não gerado.
4. Adição compatível (campo opcional, tipo de mensagem que o agente pode ignorar) **não** incrementa
   `contract_version`. O agente é obrigado a ignorar campo e mensagem desconhecidos, o mesmo princípio
   já adotado no frontend para eventos SSE.
5. A janela é de duas versões, não uma: dá um ciclo inteiro de folga ao usuário. Não é ilimitada
   porque manter tradução para N versões antigas do `MapSpec` é onde nascem os bugs de layout
   silencioso.

`GET /v1/catalog/version` expõe `contract_version` e o hash do catálogo, e é o que o agente consulta
para saber se seu catálogo local está velho.

## Frontend na Vercel

| Item | Configuração |
|---|---|
| Projeto | um projeto Vercel, root directory `web/` |
| Produção | branch `main` |
| Preview | um deploy por PR, URL efêmera, apontando para o backend de **staging** |
| Variáveis | `NEXT_PUBLIC_API_URL`, a única pública. Nenhum segredo aqui ([`09`](09-seguranca-e-privacidade.md)) |
| Domínio | `mapasfacil.app` (apex) + redirect de `www`; DNS na Vercel |
| Headers | HSTS, CSP, `nosniff`, `Referrer-Policy`, `X-Frame-Options: DENY`, `Permissions-Policy` — no `next.config` e conferidos por teste na CI |
| Rollback | promover o deploy anterior no painel, instantâneo e sem rebuild |

ISR, cache de CDN e edge caching **não se aplicam**: toda página útil é autenticada e mostra estado
por usuário (conversas, jobs em andamento, agentes online). Só a landing pública e os assets são
cacheáveis, e disso o Next.js já cuida. Perseguir edge aqui seria complexidade sem ganho. O frontend
também não fala com o agente e não tem rota de API própria com segredo — é cliente do backend, o que
mantém a Vercel fora do escopo de dado sensível.

## Backend no Render

| Item | Configuração |
|---|---|
| Tipo | Web Service com Dockerfile próprio (controle da versão do Python e das libs geo) |
| Start | `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health check | rota leve, sem tocar o banco a cada checagem |
| Réplicas | **1 (uma)** na v1; escala é vertical |
| Banco | Postgres gerenciado do Render, mesma região |
| Auto deploy | desligado no branch; deploy disparado por tag via CI |
| Rollback | redeploy do build anterior (o Render mantém o histórico) |

### A limitação de uma réplica

Repetindo o que [`01`](01-arquitetura.md) estabelece, porque é a restrição operacional mais importante
deste documento: **o hub WebSocket de agentes é em memória**. A conexão de um agente vive no processo
que a aceitou. Com duas réplicas, o processo que recebe `POST /v1/jobs` pode não ser o que detém o
WebSocket daquele agente, e o `job.dispatch` simplesmente não chega.

Consequências práticas:

- Uma réplica, escala vertical.
- Todo deploy **derruba as conexões dos agentes**. É aceitável porque o agente reconecta com backoff
  exponencial (1 s → 60 s com jitter) e jobs em execução sobrevivem e reportam ao reconectar. Mesmo
  assim, deploy é feito fora do horário de pico.
- Reinício não perde job: `jobs` e `job_events` estão no Postgres e mensagem não entregue fica na
  fila por 24 h.
- Ponto único de falha assumido: backend fora significa "nenhum mapa novo", não "mapa corrompido" — o
  usuário segue com o ArcMap e os arquivos já gerados.

Quando isso deixar de servir, a saída é um barramento externo (Redis pub/sub ou `LISTEN/NOTIFY` no
Postgres) roteando o dispatch para a réplica que detém a conexão. Fora da v1 de propósito: custa
dinheiro e complexidade para resolver um problema que só aparece com muitos agentes simultâneos.

### Variáveis de ambiente

```
DATABASE_URL              # gerenciada pelo Render
JWT_SECRET                # rotação com janela de dois segredos aceitos
AI_PROVIDER               # nome do provedor (trocável)
AI_API_KEY                # segredo
AI_MODEL
EMAIL_PROVIDER_API_KEY    # envio do magic link
PUBLIC_WEB_ORIGIN         # allowlist de CORS
ARTIFACT_STORAGE_URL      # bucket dos preview.png opt-in
ARTIFACT_STORAGE_KEY      # segredo
SENTRY_DSN
CONTRACT_VERSION_MIN      # menor contract_version de agente aceita
LOG_LEVEL
ENV                       # dev | staging | prod
```

`.env.example` no repositório com estes nomes e **valores vazios**. Nenhuma delas existe no frontend.

### Backup e restore

Backup automático diário do plano gerenciado, com retenção de 7 dias no plano inicial (avaliar 30 dias
quando houver cliente pagante). Dump manual antes de qualquer migração de risco, guardado fora do
provedor. **Restore testado trimestralmente**, restaurando em banco de staging e rodando a suíte de API
contra ele: backup não testado não é backup. O resultado (data, duração, problemas) fica registrado, e
o item está no checklist de release de [`11`](11-testes-e-qa.md).

## Migrações de banco

Alembic, uma migração por PR quando houver mudança de esquema. Como `alembic upgrade head` roda no
start e há uma réplica, a janela em que código novo e esquema novo coexistem é curta — mas a regra
vale igual, porque rollback do código sem rollback do banco tem que funcionar.

| Permitido na mesma release | Proibido na mesma release |
|---|---|
| Adicionar coluna **nullable** ou com default | Adicionar coluna `NOT NULL` sem default |
| Adicionar tabela ou índice (`CONCURRENTLY` quando possível) | Dropar ou renomear coluna/tabela em uso |
| Ampliar tipo (`varchar(50)` → `text`) | Estreitar ou mudar tipo de forma incompatível |
| Adicionar valor a enum | Remover valor de enum |
| Backfill em lote, fora do caminho de request | Backfill longo dentro da migração (bloqueia o start) |

Remoção é sempre em **três releases**: (1) para de escrever na coluna; (2) para de ler; (3) dropa.
Nunca (1) e (3) juntos — se o deploy for revertido no passo 1, o código antigo ainda precisa da coluna.

```
Rollback:
1. Reverter o código (redeploy do build anterior no Render).
2. Se a migração era compatível, o esquema novo funciona com o código antigo. Não fazer downgrade.
3. Downgrade só como último recurso, com dump feito antes, e nunca em migração que apagou dado.
4. Registrar no incidente qual migração ficou aplicada à frente do código.
```

Toda migração é aplicada antes em staging, sobre um dump recente de produção, com o tempo de execução
medido — migração que trave tabela grande por muito tempo precisa ser reescrita.

## Distribuição do agente

O componente mais delicado: instala software com permissão de escrita no PC de um terceiro, num
Windows corporativo, sem que ninguém nos conheça.

```
runner: windows-latest (build)  +  windows-arcmap (suíte MXD)

1. pip install -r agent/requirements.txt   (lockfile com hash)
2. pytest -m "not arcpy"
3. pyinstaller agent/mapasfacil.spec       -> dist/MapasFacilAgent/
4. iscc installer/mapasfacil.iss           -> MapasFacilAgent-Setup-1.2.0.exe
5. assinatura de código do .exe            (quando houver certificado)
6. sha256sum do instalador                 -> publicado junto
```

**PyInstaller em modo pasta** (`onedir`), não `onefile`: `onefile` extrai para `%TEMP%` a cada
execução, o que é lento, atrai antivírus e complica o caminho do subprocess ArcPy. O Python 2.7 do
ArcMap **não** é empacotado — o agente o localiza pelo registro do Windows, conforme a defesa 4 de
[`09`](09-seguranca-e-privacidade.md). Os templates `.mxd` e o catálogo de `shared/` vão embutidos,
com hash verificado na inicialização. Build reprodutível na medida do possível: lockfile com hash,
versão de Python fixa, runner limpo.

### Instalador (Inno Setup)

| Aspecto | Decisão |
|---|---|
| Escopo | instalação por usuário em `%LOCALAPPDATA%\MapasFacil`, **sem exigir administrador** |
| Por quê | Windows corporativo raramente dá admin ao técnico; pedir elevação é o maior ponto de abandono e aumentaria o privilégio do agente sem necessidade |
| Autostart | atalho em `HKCU\...\Run`, opcional na instalação |
| Firewall | nenhuma regra necessária: o agente só faz conexão de saída |
| Pareamento | ao final, abre a tela local pedindo o código de 8 caracteres e a escolha das pastas autorizadas |
| Idioma | português do Brasil |
| Desinstalação | remove binários, configuração, atalho e o token do Credential Manager; **não** toca em `.mxd`/`.pdf`/projetos do usuário |

### Versionamento, canais e download

`MAJOR.MINOR.PATCH`, com `contract_version` **independente** da versão do agente e anunciada no
`hello`. Canal `estavel` (tag `agent-vX.Y.Z`) para todos; canal `beta` (tag `agent-vX.Y.Z-beta.N`,
instalador com sufixo `-beta`) para o autor e voluntários. Beta e estável instalam em pastas distintas
e podem coexistir na mesma máquina — aparecem como dois agentes em `GET /v1/agents`, o que permite
validar versão nova sem perder a que funciona.

Página pública em `mapasfacil.app/download` com, por canal: versão, data, changelog em português,
requisitos, link e **SHA-256 impresso na página** (também na release do GitHub), mais a instrução de
como conferir:

```powershell
Get-FileHash .\MapasFacilAgent-Setup-1.2.0.exe -Algorithm SHA256
```

### Assinatura de código e SmartScreen

Sem assinatura, o Windows mostra "Editor desconhecido" e alguns antivírus corporativos bloqueiam.
É obstáculo real de adoção, não detalhe cosmético.

| Opção | Custo anual (ordem de grandeza) | Efeito |
|---|---|---|
| Sem certificado | zero | SmartScreen alerta sempre; usuário precisa clicar "Mais informações → Executar assim mesmo"; alguns ambientes bloqueiam de vez |
| Certificado OV | ordem de US$ 100 a 300 | remove "editor desconhecido", mas a reputação SmartScreen é construída por volume de downloads — o alerta pode persistir por semanas |
| Certificado EV | ordem de US$ 300 a 700, com token de hardware ou HSM | reputação praticamente imediata; exige pessoa jurídica e validação mais rigorosa |

Decisão da v1: começar sem certificado, com instrução honesta na página de download e o SHA-256 como
verificação, e comprar OV assim que houver usuário externo. EV entra se aparecer cliente com política
de bloqueio de binário não assinado. **Enquanto não houver assinatura, a atualização automática fica
desligada** — um canal de auto-update sem verificação criptográfica é exatamente o vetor de RCE que
[`09`](09-seguranca-e-privacidade.md) se propõe a fechar.

### Atualização automática (opt-in)

```
backend -> agent.update {versao, url, sha256}
agente:
  1. url tem que ser https no domínio de distribuição fixado no binário (pinning)
  2. baixa em pasta temporária dentro do próprio escopo
  3. confere o sha256 anunciado
  4. verifica a assinatura de código contra o certificado esperado
  5. mostra ao usuário: versão atual, nova, changelog, botão
  6. só com clique: encerra jobs com aviso, roda o instalador, reinicia, reconecta
falha em qualquer passo -> descarta, registra no log local e no audit_log, mantém a versão atual
```

Nunca silenciosa, nunca obrigatória. O usuário é dono da máquina; forçar atualização em software com
permissão de escrita é abuso de confiança e risco de disponibilidade no meio de uma entrega.

## CI/CD

| Workflow | Dispara em | Passos | Bloqueia merge |
|---|---|---|---|
| `ci-backend` | PR/push em `backend/` ou `shared/` | ruff + mypy, `pytest -m "not arcpy and not net"` com Postgres de serviço, `pip-audit` | sim |
| `ci-web` | PR/push em `web/` ou `shared/` | eslint + `tsc --noEmit`, vitest, `next build`, Playwright com fakes, `axe`, `npm audit`, checagem de headers | sim |
| `ci-agent` | PR/push em `agent/` ou `shared/` | `windows-latest`: ruff + `pytest -m "not arcpy"` (fsguard, doctor, parser, resolvedor) | sim |
| `ci-contract` | qualquer PR | anel de contrato: schemas de `shared/` × fixtures canônicas nos três lados | sim |
| `ci-secrets` | qualquer PR | `gitleaks detect` no diff; varredura de `NEXT_PUBLIC_*` suspeito | sim |
| `mxd-suite` | push em `main`, tag `agent-*`, manual | runner `windows-arcmap`: `pytest -m arcpy`, regressão visual, check de `isBroken` | bloqueia release |
| `release-api` | tag `api-v*` | build da imagem, deploy no Render, smoke do health e de `/v1/catalog/version` | — |
| `release-agent` | tag `agent-v*` | PyInstaller + Inno Setup, assinatura, SHA-256, release no GitHub com changelog | — |
| `evals` | manual, e obrigatório em PR de prompt/tools/modelo | roda os evals e publica a tabela no PR | não (medição) |

`shared/` dispara os três CIs de propósito: mudar contrato sem rodar os três lados é a forma mais
fácil de quebrar a compatibilidade.

```
Proteção da branch main:
[x] PR obrigatório (sem push direto), inclusive para o mantenedor
[x] Checks obrigatórios: ci-backend, ci-web, ci-agent, ci-contract, ci-secrets
[x] Branch atualizada com main antes do merge
[x] Conversas de revisão resolvidas
[x] Sem force push, sem exclusão da branch
[x] Segundo par de olhos em diff que toque fsguard, auth ou allowlist
```

Commits em Conventional Commits com escopo do componente, o que também alimenta o changelog, e tags
por artefato, porque as versões são independentes:

```
feat(agent): repontar data sources por workspace no arcpy_export
fix(api): validar workspace do job antes do dispatch
chore(shared): bump contract_version para 5

web-v1.2.0      api-v1.2.0      agent-v1.2.0      agent-v1.3.0-beta.1
```

## Ambientes e promoção

| Item | dev | staging | prod |
|---|---|---|---|
| web | `localhost:3000` | preview da Vercel | `mapasfacil.app` |
| backend | `localhost:8000` | serviço Render staging | `api.mapasfacil.app` |
| banco | Postgres em Docker | Postgres staging (dump anonimizado) | Postgres prod |
| agente | na mão, apontando para localhost | build `-beta` | instalador do canal estável |
| IA | fake de replay; chave real sob demanda | chave real, modelo barato | chave real, modelo de produção |
| E-mail | magic link impresso no console | provedor em modo teste | provedor real |
| Sentry | desligado | ambiente `staging` | ambiente `prod` |
| Dados | fixtures de [`11`](11-testes-e-qa.md) | dump anonimizado + fixtures | dados reais |

Promoção: merge em `main` → preview e staging automáticos → tag `api-v*`/`web-v*` para produção. O
agente tem cadência própria: beta primeiro, na máquina do autor, com a suíte MXD verde, e só depois
tag estável. Dados de staging são **anonimizados** (e-mails substituídos, rótulos com nome de cliente
trocados, nenhum caminho real de pasta de cliente): staging é ambiente de teste com credencial de
teste, não cópia de produção com dado de terceiro.

## Observabilidade em produção

Logs em JSON estruturado, uma linha por evento, com `request_id`, `job_id`, `agent_id` e
`workspace_id` como campos. Nunca no log: token, segredo, geometria, conteúdo de mensagem do chat.
Caminho de pasta do usuário aparece **apenas** no log local do agente, não no log da nuvem.

Sentry no frontend (`tracesSampleRate` baixo, sem replay de sessão na v1 — captura tela com nome de
cliente), no backend (integração ASGI, agrupamento por código de erro nosso) e no agente (envio
**opt-in**, com o mesmo aviso do `preview.png`; erro de `arcpy` é o que mais precisamos ver). Scrubbing
obrigatório antes do envio, testado com evento real ([`11`](11-testes-e-qa.md)):

```
C:\Projetos\Fazenda São João - Lote 65\Shapes\avn.shp
  -> <pasta_usuario>\...\avn.shp      (mantém a extensão, perde o nome de cliente)
Bearer eyJ..., sk-..., authkey=...    -> [redigido]
rotulo_texto, tabela.linhas           -> removidos do contexto
```

Métricas de negócio extraídas do próprio Postgres (`jobs`, `job_events`), num painel simples, sem
stack de métricas dedicada na v1:

| Métrica | Por que importa |
|---|---|
| Mapas gerados por dia, por workspace e por template | uso real, e quais templates da série valem manter |
| Taxa de sucesso (`succeeded` / total) | saúde do produto; meta acima de 95% |
| Tempo médio e p95 por etapa (as 9 de [`01`](01-arquitetura.md#ciclo-de-vida-do-job)) | onde está o gargalo: WFS, `arcpy` ou export do PDF |
| Tempo total prompt → `.mxd` | critério de sucesso da v1 (< 3 min) |
| Jobs `queued` por falta de agente online, e por quanto tempo | atrito de "meu PC estava desligado" |
| Redespachos por timeout de accept | instabilidade de conexão |
| Distribuição de `agent_version` e `contract_version` | quando é seguro sair da janela de compatibilidade |
| Erros por código, e top erros de `arcpy` | fila de bugs priorizada pela realidade |
| Custo de IA por mapa e por workspace | sustentabilidade |
| Checks IMAP *hard* falhando por template | qualidade cartográfica |

| Alerta | Condição |
|---|---|
| Backend fora do ar | health check falhando por 2 ciclos |
| Nenhum agente online | zero conexões por mais de 15 min em horário comercial |
| Taxa de erro de job | acima de 20% numa janela de 1 h |
| Provedor de IA falhando | `5xx`/`429` acima do limiar em 15 min |
| Banco em 80% do disco | uso de armazenamento |
| Fila crescendo | jobs `queued` com agente online há mais de 10 min |
| Falha de migração no start | log do deploy, e-mail imediato |

Poucos alertas, todos acionáveis: alerta que ninguém atende é ruído que treina a ignorar os reais.

## Runbook de incidentes

| Sintoma | Diagnóstico | Ação |
|---|---|---|
| Todos os agentes offline ao mesmo tempo | quase sempre é o backend, não os PCs: deploy recente, health, log de start, migração falhando; confirmar em `agents.ultimo_hello_em` que todos pararam no mesmo minuto | se foi deploy, rollback para o build anterior; se foi migração, ver linha própria abaixo; os agentes reconectam sozinhos, sem ação do usuário |
| Um agente offline, os outros ok | é o PC do usuário: desligado, sem rede, proxy novo, token revogado, antivírus | pedir print do tray e do log local; conferir `audit_log` por `agente.revogado`; se for TLS corporativo, orientar allowlist do domínio |
| `arcpy` falhando em todos os jobs após atualização do ArcMap | mudou o caminho do Python 2.7 e/ou a versão do `arcpy` | rodar `GET /v1/agents/{id}/doctor` e ver o caminho detectado; se o doctor não achou, publicar patch com a nova chave de registro; enquanto isso, `strict_mxd=false` entrega PDF |
| `arcpy` falhando em um job só | template, dado ou spec específico: ler `log_tail` de `job.error` e a etapa | reproduzir na suíte MXD com o `MapSpec` do job; se for dado do usuário (shapefile corrompido, CRS estranho), devolver erro claro em vez de tentar consertar |
| Provedor de IA fora do ar | `5xx`/timeout no log; SSE emitindo `event: error` | avisar na UI que o chat está indisponível; gerar mapa a partir de `MapSpec` existente **continua funcionando** (é o caminho de degradação); se durar, trocar `AI_PROVIDER`/`AI_MODEL` por env var |
| Banco cheio | disco em 80–90%; suspeitos são `job_events` e log de aplicação | rodar a retenção (90 dias de `job_events`, 30 de log), `VACUUM`, subir plano se o crescimento é legítimo; ver se algum agente está inundando `job.log` |
| Fila travada (jobs `queued` com agente online) | conectado mas não aceita: subprocess ArcPy pendurado, licença presa, disco cheio no PC | `POST /v1/jobs/{id}/cancel`; pedir reinício do agente; se `job.accepted` nunca chega, o redespacho (3×) já deveria ter agido — investigar o hub |
| Job preso em `running` | agente caiu no meio sem reconectar, ou `arcpy` travou | cancelar após o timeout; conferir se sobrou `.mxd` parcial na pasta do job (o usuário precisa saber que aquele arquivo não presta) |
| Deploy com migração falhando no start | serviço não sobe; log mostra o erro do Alembic | corrigir a migração e refazer o deploy; **não** rodar migração à mão em produção sem dump; se urgente, rollback do código (a migração compatível permite) |
| Muitos `agent_outdated` | saímos da janela de duas versões e há parque antigo | comunicar na UI e por e-mail com link de download; se a base for grande, considerar reabrir a compatibilidade num patch do backend |
| Suspeita de token de agente vazado | `hostname` divergente no `hello`; `audit_log` com pareamento inesperado | revogar (`DELETE /v1/agents/{id}`), o que derruba o WebSocket na hora; reparear na máquina certa; auditar os jobs criados naquele agente |
| Segredo vazado no repositório | `gitleaks` ou aviso externo | **rotacionar primeiro**, limpar histórico depois, seguindo [`09`](09-seguranca-e-privacidade.md) |
| Site fora, backend ok | build da Vercel ou DNS | promover o deploy anterior; se for DNS, checar o registro do apex |

Todo incidente rende três coisas: registro com linha do tempo, um teste que o pegaria antes
([`11`](11-testes-e-qa.md)) e uma linha nova nesta tabela quando o sintoma for novo.

## Custos estimados

Estimativas de **ordem de grandeza** para a fase inicial (poucos usuários, dezenas de mapas por dia),
não cotação. Servem para dimensionar decisão e devem ser reconferidas na contratação.

| Serviço | Plano | Custo mensal (ordem de grandeza) | Observação |
|---|---|---|---|
| Vercel | Hobby → Pro | US$ 0 a ~20 | Hobby atende a validação; Pro com uso comercial |
| Render — web service | plano pago inicial | ~US$ 7 a 25 | o gratuito hiberna, inaceitável com WebSocket de agente |
| Render — Postgres | plano pago inicial | ~US$ 7 a 20 | inclui backup diário |
| Provedor de IA | por uso | ~US$ 5 a 50 | dominado pelo tamanho do system prompt e do catálogo; a escolha do modelo muda a conta em ordem de grandeza |
| Armazenamento de artefatos | por GB | < US$ 5 | só `preview.png` opt-in; `.mxd`/`.pdf` não sobem |
| E-mail transacional | gratuito → pago | US$ 0 a ~15 | magic link tem volume baixo |
| Sentry | Developer → Team | US$ 0 a ~26 | gratuito atende no início |
| Domínio `mapasfacil.app` | anual | ~US$ 15 a 25 por ano | |
| Certificado de assinatura | anual | OV ~US$ 100 a 300; EV ~US$ 300 a 700 por ano | ver seção de assinatura |
| Runner `windows-arcmap` | VM ou máquina física | US$ 0 (desktop existente) a ~100 | **maior incerteza**; licença ArcGIS não contabilizada |
| **Total de nuvem** | | **ordem de US$ 30 a 150 por mês** | sem certificado e sem VM dedicada |

Duas observações que mudam a leitura desses números. O custo por mapa é dominado pela **IA**, não pela
infraestrutura, porque o trabalho pesado (`arcpy`, WFS, PDF) roda na máquina do usuário, de graça para
nós — consequência direta da decisão D1 de [`00`](00-visao-e-escopo.md). E o item mais caro do projeto
não aparece na tabela: a **licença ArcGIS** do usuário (e a do runner de CI, se for separada), que é
premissa do produto e a razão de a arquitetura existir para não comprar licença de servidor.

## Pendências e decisões abertas

| # | Questão | Opções | Quando decidir |
|---|---|---|---|
| D1 | Runner `windows-arcmap` e licença de CI | desktop do autor (barato, indisponível às vezes) vs VM Windows dedicada (custo + licença) | antes de M2 — é o gargalo de [`11`](11-testes-e-qa.md) |
| D2 | Quando sair de 1 réplica | Redis pub/sub vs `LISTEN/NOTIFY` no Postgres vs manter vertical | quando o teste de carga do hub mostrar o limite |
| D3 | Certificado de assinatura de código | nenhum na v1; OV ao primeiro usuário externo; EV se houver política corporativa | ao primeiro usuário fora da casa |
| D4 | Provedor de e-mail transacional | Resend, Postmark, SES | antes de M1 |
| D5 | Armazenamento do `preview.png` | bucket próprio (S3/R2) vs disco do Render (não persistente) | antes de M3 |
| D6 | Render vs alternativa (Fly.io, VPS) | Render é simples e traz Postgres gerenciado; VPS é mais barato e dá controle do WebSocket | reavaliar se o custo passar de ~US$ 100/mês |
| D7 | Deploy do backend automático em merge de `main` | hoje é por tag: mais controle, mais atrito | quando a suíte de API estiver madura |
| D8 | Telemetria de uso do agente além de erro | opt-in ajuda a priorizar, mas contradiz o discurso de privacidade se for silenciosa | antes do release público |
| D9 | Canal para comunicar atualização necessária | e-mail, banner na UI, notificação no tray | quando o parque passar de uma dezena de máquinas |
| D10 | Winget/Chocolatey como canal alternativo | reduz atrito para usuário técnico; exige empacotamento extra | pós-v1 |
| D11 | Status page pública | dá confiança ao cliente; custa manutenção | quando houver cliente pagante |
