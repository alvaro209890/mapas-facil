# F2-06 — Deploy e tunnel neste PC

> **LEGADO (2026-07-25).** Corpo ainda descreve Vercel/Render e distribuição do agente Windows.
> Destino D7: Cloudflare Tunnel dedicado neste PC (`mapasfacil-api.cursar.space` +
> `mapasfacil.cursar.space`), **sem** tocar nos tunnels existentes. Ver [`README.md`](README.md).

Como cada um dos três artefatos de [`01-arquitetura.md`](01-arquitetura.md) sai do repositório e chega
ao seu destino, e como eles continuam compatíveis apesar de serem liberados em ritmos diferentes.

## Visão geral

| Artefato | Onde roda | Como chega lá | Ritmo | Quem decide atualizar |
|---|---|---|---|---|
| `web/` | Vercel | push na branch de produção | várias vezes por semana | nós |
| `backend/` | Render (Docker) | tag `api-vX.Y.Z` | semanal | nós |
| `agent/` | PC do usuário (Windows) | instalador `.exe`, ou atualização opt-in | mensal | **o usuário** |
| `shared/` | dentro dos três | versionado junto, referenciado por `contract_version` | com o contrato | nós |

A diferença que organiza este documento: **site e backend nós atualizamos; o agente, não.** Existe um
parque instalado que só muda quando o usuário quiser, o que torna deploy sincronizado impossível — por
isso [`01`](01-arquitetura.md#regras-de-fronteira-invioláveis) já decidiu que a compatibilidade vem de
`contract_version`.

### Regra de compatibilidade

```
contract_version é um inteiro. Muda apenas quando o contrato quebra de forma incompatível
(campo obrigatório novo no MapSpec, semântica alterada de mensagem, remoção de campo).

O backend suporta as DUAS ÚLTIMAS versões de contrato do agente.
  backend em contract_version 5 -> aceita agentes 5 e 4; agente 3 ou anterior: agent_outdated
```

1. O agente manda `contract_version` no `hello`
   ([`01`](01-arquitetura.md#protocolo-websocket-agente--backend)); o backend grava e a UI mostra o
   estado da versão em `GET /v1/agents`.
2. Dentro da janela, o backend emite `MapSpec` **no nível daquele agente**: campos introduzidos depois
   são omitidos e a UI avisa que o recurso exige atualizar.
3. Fora da janela, `POST /v1/jobs` falha com
   `{"erro": {"codigo": "agent_outdated", ...}}`; o mesmo código viaja como `event: error` no SSE e a
   UI mostra o download com a versão mínima. Não há degradação: mapa errado é pior que mapa não gerado.
4. Adição compatível (campo opcional, tipo de mensagem ignorável) **não** incrementa
   `contract_version` — o agente ignora campo e mensagem desconhecidos, como o frontend faz com SSE.
5. A janela é de duas versões para dar um ciclo de folga ao usuário, e não é ilimitada porque manter
   tradução para N versões antigas do `MapSpec` é onde nascem os bugs de layout silencioso.

`GET /v1/catalog/version` expõe `contract_version` e o hash do catálogo, e é o que o agente consulta
para saber se seu catálogo local está velho.

## Frontend na Vercel

| Item | Configuração |
|---|---|
| Projeto e produção | um projeto Vercel com root directory `web/`; branch `main` em produção |
| Preview | um deploy por PR, URL efêmera, apontando para o backend de **staging** |
| Variáveis | `NEXT_PUBLIC_API_URL`, a única pública. Nenhum segredo ([`09`](../../planos/05-seguranca-e-segredos.md)) |
| Domínio | `mapasfacil.app` (apex) + redirect de `www`; DNS na Vercel |
| Headers | HSTS, CSP, `nosniff`, `Referrer-Policy`, `X-Frame-Options: DENY`, `Permissions-Policy` — no `next.config` e conferidos por teste na CI |
| Rollback | promover o deploy anterior no painel, instantâneo e sem rebuild |

ISR, cache de CDN e edge caching **não se aplicam**: toda página útil é autenticada e mostra estado por
usuário (conversas, jobs em andamento, agentes online). Só a landing e os assets são cacheáveis, e disso
o Next.js já cuida. O frontend também não fala com o agente nem tem rota de API com segredo — é cliente
do backend, o que mantém a Vercel fora do escopo de dado sensível.

## Backend no Render

| Item | Configuração |
|---|---|
| Tipo | Web Service com Dockerfile próprio (controle da versão do Python e das libs geo) |
| Start | `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health check | rota leve, sem tocar o banco a cada checagem |
| Réplicas | **1 (uma)** na v1; escala é vertical |
| Banco | Postgres gerenciado do Render, mesma região |
| Auto deploy e rollback | desligado no branch, deploy por tag via CI; rollback é redeploy do build anterior |

### A limitação de uma réplica

Repetindo o que [`01`](01-arquitetura.md) estabelece, porque é a restrição operacional mais importante
deste documento: **o hub WebSocket de agentes é em memória**. A conexão de um agente vive no processo
que a aceitou; com duas réplicas, o processo que recebe `POST /v1/jobs` pode não ser o que detém o
WebSocket daquele agente, e o `job.dispatch` não chega.

- Uma réplica, escala vertical. Todo deploy **derruba as conexões dos agentes**, o que é aceitável
  porque o agente reconecta com backoff exponencial (1 s → 60 s com jitter) e jobs em execução
  sobrevivem e reportam ao reconectar; mesmo assim, deploy é feito fora do horário de pico.
- Reinício não perde job: `jobs` e `job_events` estão no Postgres e mensagem não entregue fica 24 h na
  fila. Ponto único de falha assumido: backend fora significa "nenhum mapa novo", não "mapa
  corrompido" — o usuário segue com o ArcMap e os arquivos já gerados.

Quando isso deixar de servir, a saída é um barramento externo (Redis pub/sub ou `LISTEN/NOTIFY` no
Postgres) roteando o dispatch para a réplica que detém a conexão. Fora da v1 de propósito: custa
dinheiro e complexidade para resolver um problema que só aparece com muitos agentes simultâneos.

```
DATABASE_URL              # gerenciada pelo Render      JWT_SECRET   # janela de dois segredos
AI_PROVIDER  AI_MODEL     # provedor trocável           AI_API_KEY   # segredo
EMAIL_PROVIDER_API_KEY    # envio do magic link
PUBLIC_WEB_ORIGIN         # allowlist de CORS
ARTIFACT_STORAGE_URL / ARTIFACT_STORAGE_KEY   # bucket dos preview.png opt-in
SENTRY_DSN   LOG_LEVEL    ENV (dev|staging|prod)
CONTRACT_VERSION_MIN      # menor contract_version de agente aceita
```

`.env.example` no repositório com estes nomes e **valores vazios**. Nenhuma delas existe no frontend.

Backup automático diário do plano gerenciado, retenção de 7 dias no início (avaliar 30 dias com cliente
pagante), dump manual antes de migração de risco guardado fora do provedor, e **restore testado
trimestralmente** em banco de staging com a suíte de API rodando contra ele — backup não testado não é
backup. O resultado fica registrado, e o item está no checklist de [`11`](../../Fase_1_Desktop/planos/10-testes-e-qa.md).

## Migrações de banco

Alembic, uma migração por PR quando houver mudança de esquema. Como `alembic upgrade head` roda no start
e há uma réplica, a janela em que código novo e esquema novo coexistem é curta — mas a regra vale igual,
porque rollback do código sem rollback do banco tem que funcionar.

| Permitido na mesma release | Proibido na mesma release |
|---|---|
| Adicionar coluna **nullable** ou com default | Adicionar coluna `NOT NULL` sem default |
| Adicionar tabela ou índice (`CONCURRENTLY` quando possível) | Dropar ou renomear coluna/tabela em uso |
| Ampliar tipo (`varchar(50)` → `text`); adicionar valor a enum | Estreitar tipo; remover valor de enum |
| Backfill em lote, fora do caminho de request | Backfill longo dentro da migração (bloqueia o start) |

Remoção é sempre em **três releases**: (1) para de escrever na coluna; (2) para de ler; (3) dropa.
Nunca (1) e (3) juntos — se o deploy for revertido no passo 1, o código antigo ainda precisa da coluna.

```
Rollback
1. Reverter o código (redeploy do build anterior no Render).
2. Se a migração era compatível, o esquema novo funciona com o código antigo: não fazer downgrade.
3. Downgrade só como último recurso, com dump antes, e nunca em migração que apagou dado.
4. Registrar no incidente qual migração ficou aplicada à frente do código.
```

Toda migração é aplicada antes em staging, sobre dump recente de produção, com o tempo de execução
medido — migração que trave tabela grande por muito tempo precisa ser reescrita.

## Distribuição do agente

O componente mais delicado: instala software com permissão de escrita no PC de um terceiro, num Windows
corporativo, sem que ninguém nos conheça.

```
runner: windows-latest (build)  +  windows-arcmap (suíte MXD)
1. pip install -r agent/requirements.txt   (lockfile com hash)     4. iscc installer/mapasfacil.iss
2. pytest -m "not arcpy"                                           5. assinatura de código do .exe
3. pyinstaller agent/mapasfacil.spec                               6. sha256sum publicado junto
```

**PyInstaller em modo pasta** (`onedir`), não `onefile`: `onefile` extrai para `%TEMP%` a cada execução,
o que é lento, atrai antivírus e complica o caminho do subprocess ArcPy. O Python 2.7 do ArcMap **não**
é empacotado — o agente o localiza pelo registro do Windows, conforme a defesa 4 de
[`09`](../../planos/05-seguranca-e-segredos.md). Templates `.mxd` e catálogo de `shared/` vão embutidos, com hash
verificado na inicialização, e o build é reprodutível na medida do possível (lockfile com hash, versão
de Python fixa, runner limpo).

| Instalador (Inno Setup) | Decisão |
|---|---|
| Escopo | instalação por usuário em `%LOCALAPPDATA%\MapasFacil`, **sem exigir administrador** |
| Por quê | Windows corporativo raramente dá admin ao técnico; pedir elevação é o maior ponto de abandono e aumentaria o privilégio do agente sem necessidade |
| Autostart, firewall e pareamento | atalho opcional em `HKCU\...\Run`; nenhuma regra de firewall, porque o agente só faz conexão de saída; ao final, abre a tela local pedindo o código de 8 caracteres e as pastas autorizadas |
| Desinstalação | remove binários, configuração, atalho e o token do Credential Manager; **não** toca em `.mxd`/`.pdf`/projetos do usuário |

### Versionamento, canais e download

`MAJOR.MINOR.PATCH`, com `contract_version` **independente** da versão do agente e anunciada no `hello`.
Canal `estavel` (tag `agent-vX.Y.Z`) para todos; canal `beta` (tag `agent-vX.Y.Z-beta.N`, instalador com
sufixo `-beta`) para o autor e voluntários. Beta e estável instalam em pastas distintas e coexistem na
mesma máquina — aparecem como dois agentes em `GET /v1/agents`, o que permite validar versão nova sem
perder a que funciona.

Página pública em `mapasfacil.app/download` com, por canal: versão, data, changelog em português,
requisitos, link e **SHA-256 impresso na página** (também na release do GitHub), mais a instrução de
como conferir:

```powershell
Get-FileHash .\MapasFacilAgent-Setup-1.2.0.exe -Algorithm SHA256
```

### Assinatura de código e SmartScreen

Sem assinatura, o Windows mostra "Editor desconhecido" e alguns antivírus corporativos bloqueiam. É
obstáculo real de adoção, não detalhe cosmético.

| Opção | Custo anual (ordem de grandeza) | Efeito |
|---|---|---|
| Sem certificado | zero | SmartScreen alerta sempre; o usuário precisa clicar "Mais informações → Executar assim mesmo"; alguns ambientes bloqueiam de vez |
| Certificado OV | ordem de US$ 100 a 300 | remove "editor desconhecido", mas a reputação SmartScreen é construída por volume de downloads — o alerta pode persistir por semanas |
| Certificado EV | ordem de US$ 300 a 700, com token de hardware ou HSM | reputação praticamente imediata; exige pessoa jurídica e validação mais rigorosa |

Decisão da v1: começar sem certificado, com instrução honesta na página de download e o SHA-256 como
verificação, e comprar OV assim que houver usuário externo; EV entra se aparecer cliente com política de
bloqueio de binário não assinado. **Enquanto não houver assinatura, a atualização automática fica
desligada** — auto-update sem verificação criptográfica é exatamente o vetor de RCE que
[`09`](../../planos/05-seguranca-e-segredos.md) se propõe a fechar.

```
Atualização automática (opt-in): backend -> agent.update {versao, url, sha256}
1. url tem que ser https no domínio de distribuição fixado no binário (pinning)
2. baixa em pasta temporária no próprio escopo e confere o sha256 anunciado
3. verifica a assinatura de código contra o certificado esperado
4. mostra versão atual, nova e changelog; só com clique encerra jobs, instala, reinicia, reconecta
falha em qualquer passo -> descarta, registra no log local e no audit_log, mantém a versão atual
```

Nunca silenciosa, nunca obrigatória. O usuário é dono da máquina; forçar atualização em software com
permissão de escrita é abuso de confiança e risco de disponibilidade no meio de uma entrega.

## CI/CD

| Workflow | Dispara em | Passos | Bloqueia merge |
|---|---|---|---|
| `ci-backend` | PR/push em `backend/` ou `shared/` | ruff + mypy, `pytest -m "not arcpy and not net"` com Postgres de serviço, `pip-audit` | sim |
| `ci-web` e `ci-agent` | PR/push em `web/`, `agent/` ou `shared/` | eslint + `tsc --noEmit`, vitest, `next build`, Playwright com fakes, `axe`, `npm audit`, checagem de headers; e em `windows-latest`, ruff + `pytest -m "not arcpy"` (fsguard, doctor, parser, resolvedor) | sim |
| `ci-contract` e `ci-secrets` | qualquer PR | schemas de `shared/` × fixtures nos três lados; `gitleaks detect` no diff e varredura de `NEXT_PUBLIC_*` suspeito | sim |
| `mxd-suite` | push em `main`, tag `agent-*`, manual | runner `windows-arcmap`: `pytest -m arcpy`, regressão visual, check de `isBroken` | bloqueia release |
| `release-api` | tag `api-v*` | build da imagem, deploy no Render, smoke do health e de `/v1/catalog/version` | — |
| `release-agent` | tag `agent-v*` | PyInstaller + Inno Setup, assinatura, SHA-256, release no GitHub com changelog | — |
| `evals` | manual, e obrigatório em PR de prompt/tools/modelo | roda os evals e publica a tabela no PR | não (medição) |

`shared/` dispara os três CIs de propósito: mudar contrato sem rodar os três lados é a forma mais fácil
de quebrar a compatibilidade.

```
Proteção da branch main
[x] PR obrigatório (sem push direto), inclusive para o mantenedor; sem force push
[x] Checks obrigatórios: ci-backend, ci-web, ci-agent, ci-contract, ci-secrets
[x] Branch atualizada com main e conversas de revisão resolvidas
[x] Segundo par de olhos em diff que toque fsguard, auth ou allowlist

Commits em Conventional Commits com escopo, e tags por artefato (versões independentes)
feat(agent): repontar data sources no arcpy_export     chore(shared): bump contract_version para 5
web-v1.2.0    api-v1.2.0    agent-v1.2.0    agent-v1.3.0-beta.1
```

## Ambientes e promoção

| Item | dev | staging | prod |
|---|---|---|---|
| web e backend | `localhost:3000` e `localhost:8000` | preview da Vercel e serviço Render staging | `mapasfacil.app` e `api.mapasfacil.app` |
| banco | Postgres em Docker | Postgres staging (dump anonimizado) | Postgres prod |
| agente | na mão, apontando para localhost | build `-beta` | instalador do canal estável |
| IA e e-mail | fake de replay; magic link no console | chave real com modelo barato; provedor em modo teste | modelo de produção; provedor real |
| Sentry e dados | desligado; fixtures de [`11`](../../Fase_1_Desktop/planos/10-testes-e-qa.md) | ambiente `staging`; dump anonimizado | ambiente `prod`; dados reais |

Promoção: merge em `main` → preview e staging automáticos → tag `api-v*`/`web-v*` para produção. O agente
tem cadência própria: beta primeiro, na máquina do autor, com a suíte MXD verde, e só depois tag estável.
Dados de staging são **anonimizados** (e-mails substituídos, rótulos com nome de cliente trocados, nenhum
caminho real de pasta): staging é ambiente de teste com credencial de teste, não cópia de produção.

## Observabilidade em produção

Logs em JSON estruturado, uma linha por evento, com `request_id`, `job_id`, `agent_id` e `workspace_id`
como campos. Nunca no log: token, segredo, geometria, conteúdo de mensagem do chat; caminho de pasta do
usuário aparece **apenas** no log local do agente. Sentry no frontend (`tracesSampleRate` baixo, sem
replay de sessão na v1, que capturaria tela com nome de cliente), no backend (integração ASGI) e no
agente (envio **opt-in**, com o mesmo aviso do `preview.png`; erro de `arcpy` é o que mais precisamos
ver), com scrubbing obrigatório testado com evento real ([`11`](../../Fase_1_Desktop/planos/10-testes-e-qa.md)):

```
C:\Projetos\Fazenda São João - Lote 65\Shapes\avn.shp -> <pasta_usuario>\...\avn.shp
Bearer eyJ..., sk-..., authkey=...  -> [redigido]      rotulo_texto, tabela.linhas -> removidos
```

Métricas de negócio extraídas do próprio Postgres (`jobs`, `job_events`), num painel simples, sem stack
de métricas dedicada na v1:

| Métrica | Por que importa |
|---|---|
| Mapas gerados por dia, por workspace e por template; taxa de sucesso (`succeeded` / total) | uso real e quais templates da série valem manter; saúde do produto, com meta acima de 95% |
| Tempo médio e p95 por etapa (as 9 de [`01`](01-arquitetura.md#ciclo-de-vida-do-job)); tempo total prompt → `.mxd` | onde está o gargalo (WFS, `arcpy` ou export do PDF) e o critério de < 3 min da v1 |
| Jobs `queued` por falta de agente online; redespachos por timeout de accept | atrito de "meu PC estava desligado"; instabilidade de conexão |
| Distribuição de `agent_version` e `contract_version` | quando é seguro sair da janela de compatibilidade |
| Erros por código e top erros de `arcpy`; checks IMAP *hard* por template; custo de IA por mapa | fila de bugs priorizada pela realidade; qualidade cartográfica; sustentabilidade |

Alertas, poucos e todos acionáveis (alerta que ninguém atende treina a ignorar os reais): backend fora
do ar (health falhando por 2 ciclos); nenhum agente online por mais de 15 min em horário comercial; erro
de job acima de 20% em 1 h; provedor de IA com `5xx`/`429` acima do limiar em 15 min; banco em 80% do
disco; jobs `queued` com agente online há mais de 10 min; falha de migração no start (e-mail imediato).

## Runbook de incidentes

| Sintoma | Diagnóstico | Ação |
|---|---|---|
| Todos os agentes offline ao mesmo tempo | quase sempre é o backend, não os PCs: deploy recente, health, log de start, migração falhando; confirmar em `agents.ultimo_hello_em` que todos pararam no mesmo minuto | se foi deploy, rollback para o build anterior; se foi migração, ver a linha própria abaixo; os agentes reconectam sozinhos, sem ação do usuário |
| Um agente offline, os outros ok | é o PC do usuário: desligado, sem rede, proxy novo, token revogado, antivírus | pedir print do tray e do log local; conferir `audit_log` por `agente.revogado`; se for TLS corporativo, orientar allowlist do domínio |
| `arcpy` falhando em todos os jobs após atualização do ArcMap | mudou o caminho do Python 2.7 e/ou a versão do `arcpy` | rodar `GET /v1/agents/{id}/doctor` e ver o caminho detectado; se o doctor não achou, publicar patch com a nova chave de registro; enquanto isso, `strict_mxd=false` entrega PDF |
| `arcpy` falhando em um job só | template, dado ou spec específico: ler `log_tail` de `job.error` e a etapa | reproduzir na suíte MXD com o `MapSpec` do job; se for dado do usuário (shapefile corrompido, CRS estranho), devolver erro claro em vez de consertar |
| Provedor de IA fora do ar | `5xx`/timeout no log; SSE emitindo `event: error` | avisar na UI que o chat está indisponível; gerar mapa a partir de `MapSpec` existente **continua funcionando** (é o caminho de degradação); se durar, trocar `AI_PROVIDER`/`AI_MODEL` por env var |
| Banco cheio | disco em 80–90%; suspeitos são `job_events` e log de aplicação | rodar a retenção (90 dias de `job_events`, 30 de log), `VACUUM`, subir plano se o crescimento é legítimo; ver se algum agente está inundando `job.log` |
| Fila travada (jobs `queued` com agente online) | conectado mas não aceita: subprocess ArcPy pendurado, licença presa, disco cheio no PC | `POST /v1/jobs/{id}/cancel`; pedir reinício do agente; se `job.accepted` nunca chega, o redespacho (3×) já deveria ter agido — investigar o hub |
| Job preso em `running` | agente caiu no meio sem reconectar, ou `arcpy` travou | cancelar após o timeout; conferir se sobrou `.mxd` parcial na pasta do job (o usuário precisa saber que aquele arquivo não presta) |
| Deploy com migração falhando no start; muitos `agent_outdated` | serviço não sobe e o log mostra o erro do Alembic; saímos da janela de duas versões e há parque antigo | corrigir a migração e refazer o deploy, nunca rodar migração à mão em produção sem dump (se urgente, rollback do código, que a migração compatível permite); comunicar na UI e por e-mail com link de download, e se a base for grande considerar reabrir a compatibilidade num patch |
| Suspeita de token de agente vazado | `hostname` divergente no `hello`; `audit_log` com pareamento inesperado | revogar (`DELETE /v1/agents/{id}`), o que derruba o WebSocket na hora; reparear na máquina certa; auditar os jobs criados naquele agente |
| Segredo vazado; site fora com backend ok | `gitleaks` ou aviso externo; build da Vercel ou DNS | rotacionar primeiro e limpar histórico depois ([`09`](../../planos/05-seguranca-e-segredos.md)); promover o deploy anterior ou checar o registro do apex |

Todo incidente rende três coisas: registro com linha do tempo, um teste que o pegaria antes
([`11`](../../Fase_1_Desktop/planos/10-testes-e-qa.md)) e uma linha nova nesta tabela quando o sintoma for novo.

## Custos estimados

Estimativas de **ordem de grandeza** para a fase inicial (poucos usuários, dezenas de mapas por dia),
não cotação. Servem para dimensionar decisão e devem ser reconferidas na contratação.

| Serviço | Custo mensal (ordem de grandeza) | Observação |
|---|---|---|
| Vercel (Hobby → Pro) | US$ 0 a ~20 | Hobby atende a validação; Pro com uso comercial |
| Render — web service e Postgres | ~US$ 14 a 45 | o plano gratuito hiberna, inaceitável com WebSocket de agente; o banco inclui backup diário |
| Provedor de IA (por uso) | ~US$ 5 a 50 | dominado pelo tamanho do system prompt e do catálogo; a escolha do modelo muda a conta em ordem de grandeza |
| Armazenamento de artefatos; e-mail transacional | < US$ 5; US$ 0 a ~15 | só `preview.png` opt-in, porque `.mxd`/`.pdf` não sobem; magic link tem volume baixo |
| Sentry (Developer → Team); domínio; certificado de assinatura | US$ 0 a ~26; ~US$ 15 a 25/ano; OV ~US$ 100 a 300/ano, EV ~US$ 300 a 700/ano | gratuito atende no início; ver a seção de assinatura |
| Runner `windows-arcmap` | US$ 0 (desktop existente) a ~100 | **maior incerteza**; licença ArcGIS não contabilizada |
| **Total de nuvem** | **ordem de US$ 30 a 150 por mês** | sem certificado e sem VM dedicada |

Duas observações mudam a leitura desses números. O custo por mapa é dominado pela **IA**, não pela
infraestrutura, porque o trabalho pesado (`arcpy`, WFS, PDF) roda na máquina do usuário, de graça para
nós — consequência direta da decisão D1 de [`00`](00-visao-e-escopo.md). E o item mais caro do projeto
não aparece na tabela: a **licença ArcGIS** do usuário (e a do runner de CI, se for separada), que é
premissa do produto e a razão de a arquitetura existir para não comprar licença de servidor.

## Pendências e decisões abertas

| # | Questão | Opções | Quando decidir |
|---|---|---|---|
| D1 | Runner `windows-arcmap` e licença de CI | desktop do autor (barato, indisponível às vezes) vs VM Windows dedicada (custo + licença) | antes de M2 — é o gargalo de [`11`](../../Fase_1_Desktop/planos/10-testes-e-qa.md) |
| D2 | Quando sair de 1 réplica | Redis pub/sub vs `LISTEN/NOTIFY` no Postgres vs manter vertical | quando o teste de carga do hub mostrar o limite |
| D3 | Certificado de assinatura de código | nenhum na v1; OV ao primeiro usuário externo; EV se houver política corporativa | ao primeiro usuário fora da casa |
| D4 | Provedor de e-mail transacional; armazenamento do `preview.png` | Resend, Postmark, SES; bucket próprio (S3/R2) vs disco do Render (não persistente) | antes de M1; antes de M3 |
| D5 | Render vs alternativa (Fly.io, VPS); deploy automático em merge de `main` | Render é simples e traz Postgres gerenciado, VPS é mais barato e dá controle do WebSocket; hoje o deploy é por tag, com mais controle e mais atrito | reavaliar acima de ~US$ 100/mês; quando a suíte de API amadurecer |
| D6 | Telemetria de uso do agente além de erro | opt-in ajuda a priorizar, mas contradiz o discurso de privacidade se for silenciosa | antes do release público |
| D7 | Canal para comunicar atualização necessária | e-mail, banner na UI, notificação no tray | quando o parque passar de uma dezena de máquinas |
| D8 | Winget/Chocolatey como canal alternativo; status page pública | reduzem atrito e dão confiança, mas custam empacotamento e manutenção | pós-v1; quando houver cliente pagante |
