# F2-02 — Backend (API e orquestração)

> **LEGADO (2026-07-25).** Corpo ainda assume Render + hub WebSocket de agentes. Destino D7:
> FastAPI neste PC, tunnel `mapasfacil-api.cursar.space`, consultas geo locais. Ver
> [`README.md`](README.md).

Implementação do `backend/`. Os contratos — endpoints, protocolo WebSocket, estados de job, tabelas e
`MapSpec` — são os de [01-arquitetura.md](01-arquitetura.md) e não são renegociados aqui. O que este
documento precisa e não existe no 01 está marcado como proposta em
[Pendências](#pendências-e-decisões-abertas).

## Stack e justificativa

| Componente | Escolha | Por quê | Alternativa descartada |
|---|---|---|---|
| Linguagem | Python 3.11 | reuso do ecossistema geo do autor; mesma linguagem do agente | Node/Express (decisão D3 do [00](00-visao-e-escopo.md)) |
| Framework | FastAPI | async nativo — WebSocket do agente e SSE do chat no mesmo processo; OpenAPI de graça | Django (ORM síncrono atrapalha o WS); Starlette puro (reinventar validação) |
| Validação | Pydantic v2 | rápido, discriminated union para o envelope WS, JSON Schema exportável para `shared/` | dataclasses + jsonschema na mão |
| ORM | SQLAlchemy 2 async | precisamos de `FOR UPDATE SKIP LOCKED` e `jsonb` sem sair do ORM | SQLModel (camada extra, menos controle) |
| Migrações | Alembic | `map_specs` e `job_events` são append-only: mudança de schema tem de ser revisável | criar tabelas no boot (não auditável) |
| Banco | Postgres 15+ | `jsonb`, `SKIP LOCKED` para a fila, `LISTEN/NOTIFY` como saída futura | SQLite (sem concorrência real) |
| Driver | asyncpg | todo o request path é async | psycopg2 síncrono |
| Servidor | uvicorn, 1 worker, uvloop | WebSocket + registry em memória exigem processo único na v1 | gunicorn com N workers (quebraria o registry) |

### Redis: não na v1

O reflexo seria Redis para fila e pub/sub. Não entra agora: a fila é a tabela `jobs` consumida com
`FOR UPDATE SKIP LOCKED`, o que na escala inicial (dezenas de jobs por dia, um agente por usuário) é
folgado e mantém uma única fonte da verdade — o estado do job não pode divergir entre Redis e Postgres.
O despacho também não precisa de broker: o backend já tem a conexão WebSocket na memória do processo.
Redis passa a ser necessário quando houver **duas ou mais réplicas**, porque aí o roteamento
réplica→conexão deixa de ser local (ver [múltiplas réplicas](#o-problema-das-múltiplas-réplicas)).
O custo dessa decisão é processo único como ponto único de falha, com deploy derrubando WebSockets —
aceitável porque o agente reconecta com backoff e jobs em execução sobrevivem à queda do WS (regra do
01), então um deploy custa segundos de latência, não um job perdido.

## Estrutura de pastas

```
backend/
├── app/
│   ├── main.py                  # FastAPI, routers, lifespan (pool, hub, worker)
│   ├── config.py                # Settings (pydantic-settings): único leitor de env
│   ├── deps.py                  # sessão, usuário atual, agente atual, workspace
│   ├── api/v1/
│   │   ├── auth.py              # /v1/auth/*, /v1/me
│   │   ├── conversations.py     # /v1/conversations*
│   │   ├── messages.py          # /v1/conversations/{id}/messages (SSE), /cancel
│   │   ├── jobs.py              # /v1/jobs*, /v1/jobs/{id}/events (SSE)
│   │   ├── agents.py            # /v1/agents*, /v1/agents/ws
│   │   ├── catalog.py           # /v1/catalog/*
│   │   └── artifacts.py         # /v1/jobs/{id}/artifacts, /v1/artifacts/{id}
│   ├── domain/                  # mapspec.py (MapSpec v1), job.py (estados, 9 etapas, pesos,
│   │                            # transições), errors.py — sem SQLAlchemy, sem FastAPI
│   ├── db/                      # models.py (tabelas do 01, 1:1), session.py, migrations/
│   ├── llm/                     # base.py (ChatProvider), deepseek.py, openai_compat.py,
│   │                            # tools.py (ver 07), loop.py (único produtor do SSE do chat)
│   ├── agentctl/                # hub.py (registry), connection.py (envelope, heartbeat),
│   │                            # rpc.py (futures por reply_to), protocol.py (union por "tipo")
│   ├── mapspec/                 # validate.py (invariantes do 01), diff.py (mapspec.updated)
│   ├── services/                # conversations, jobs, agents, catalog, events
│   ├── worker/dispatcher.py     # laço in-process que puxa jobs queued
│   └── obs/                     # logging.py (JSON + request_id), metrics.py
├── tests/                       # unit/ (MapSpec, transições, RPC), integration/ (PG + WS fake)
├── pyproject.toml
├── alembic.ini
├── Dockerfile
└── .env.example
```

Regra de dependência: `api/` → `services/` → `db/` + `domain/`. `domain/` não importa framework
nenhum, o que mantém as invariantes do `MapSpec` testáveis sem banco nem HTTP.

## Hub WebSocket de agentes

### Registry em memória

`WS /v1/agents/ws` autentica pelo `Authorization: Bearer <agent_token>` (comparado contra
`agents.token_hash`), exige `hello` como primeira mensagem e só então registra a conexão:

```python
class AgentHub:
    _conns: dict[UUID, AgentConnection] = {}

    async def register(self, agent_id: UUID, conn: AgentConnection) -> None:
        if (antiga := self._conns.get(agent_id)) is not None:
            await antiga.close(motivo="substituida")   # última conexão ganha
        self._conns[agent_id] = conn
```

"Última conexão ganha" evita agente zumbi depois de reconexão por rede caída — o socket antigo pode
levar minutos para o TCP declarar morto. Liveness: `heartbeat` a cada 20 s (01) atualiza
`agents.ultimo_hello_em`; `agents.online` é escrito no `hello` e no `close`, mas `GET /v1/agents` deve
considerar online só quem está no registry **ou** tem `ultimo_hello_em` mais recente que 60 s — a coluna
sozinha mente depois de um crash do processo.

### RPC com futures

`fs.list`, `fs.inspect` e `doctor.run` são RPC: o backend manda o envelope com `id` ULID e espera um
`rpc.result` cujo `reply_to` é aquele `id`.

```python
async def call(self, tipo: str, payload: dict, timeout: float = 5.0) -> dict:
    msg_id = ulid()
    fut = asyncio.get_running_loop().create_future()
    self._pendentes[msg_id] = fut          # resolvido pelo rpc.result com reply_to=msg_id
    try:
        await self._send({"v": 1, "id": msg_id, "tipo": tipo, "ts": agora(),
                          "reply_to": None, "payload": payload})
        return await asyncio.wait_for(fut, timeout)
    except asyncio.TimeoutError:
        raise ErroDominio("agent_offline", "o agente não respondeu em 5 s")
    finally:
        self._pendentes.pop(msg_id, None)
```

O timeout de 5 s é o do 01 e existe porque essas chamadas acontecem **dentro do loop de IA**, com o
usuário olhando o cursor piscar. Estourado o prazo, a tool devolve erro à IA em vez de travar o
turno, e a IA passa a pedir o caminho ao usuário — a degradação graciosa prevista no 01. Se o
WebSocket cair com futures pendentes, todas são resolvidas com `agent_offline` na hora.

### O problema das múltiplas réplicas

Com duas réplicas, o agente mantém o WebSocket com a réplica A e o `POST /v1/jobs` do usuário pode cair
na réplica B; B consulta o registry, não acha nada e conclui erroneamente `agent_offline`. Na v1:
**uma réplica**, escala vertical, e um guard explícito — se houver mais de um worker, o boot falha com
mensagem clara em vez de produzir bug intermitente. Na v2, duas saídas:

| Solução | Como funciona | Prós | Contras |
|---|---|---|---|
| Postgres `LISTEN/NOTIFY` | `agents` ganha a réplica dona da conexão; B grava o comando e notifica `agent_cmd_<replica>`; A entrega | zero infra nova | payload de 8 kB (notifica só o id, o `mapspec` vai pelo banco); `NOTIFY` não é durável |
| Redis pub/sub | canal por `agent_id`, réplica dona assina | payload maior, menor latência, escala para muitas réplicas | serviço novo para operar e pagar |

As duas mantêm o RPC com futures: muda só o transporte da ida e da volta.

## Fila e despacho de jobs

`jobs` é a fila — sem tabela paralela, o estado que a UI lê é o mesmo que o worker consome.

```sql
UPDATE jobs SET status = 'dispatched'
WHERE id = (
  SELECT id FROM jobs
   WHERE status = 'queued' AND agent_id = ANY(:agentes_online)
   ORDER BY criado_em
   FOR UPDATE SKIP LOCKED
   LIMIT 1
) RETURNING *;
```

`SKIP LOCKED` é o que permite mais de um consumidor sem duplo despacho no futuro; hoje já protege do caso
real de dois laços concorrentes (worker e retry de reconexão) tocando o mesmo job. O filtro por
`agentes_online` implementa a regra do 01: sem agente online o job **fica em `queued`** e a UI mostra
"aguardando seu PC" — não é erro. Quando um agente manda `hello`, o worker acorda e reavalia a fila dele.

| Situação | Regra | Estado resultante |
|---|---|---|
| `job.dispatch` enviado | grava `dispatched`, arma timer de 30 s | `dispatched` |
| `job.accepted` chega | cancela o timer | `running` |
| 30 s sem `job.accepted` | incrementa tentativas | `queued` (até 3 redespachos) |
| 4ª tentativa falha | erro `job_timeout` | `failed` |
| WS cai com job `running` | nada é feito; o agente reporta ao reconectar | `running` |
| `job.done` / `job.error` | grava `validacao`/`erro`, `duracao_ms`, `finalizado_em` | `succeeded` / `failed` |
| `POST /v1/jobs/{id}/cancel` | envia `job.cancel`; se offline, cancela local | `cancelled` |

Guarda de sanidade: job `running` sem `job.progress` por 15 min vira `failed` com `job_timeout`. Sem isso,
um travamento do ArcPy deixa a UI girando para sempre; o número é generoso porque `baixando_wfs` e
`exportando_pdf` de verdade demoram. Todo evento recebido do agente vira linha em `job_events` **antes**
de qualquer efeito colateral — é isso que torna o replay do SSE possível e o debug pós-mortem viável.

## SSE

Dois streams de natureza diferente: o turno de conversa (`POST /v1/conversations/{id}/messages`) e o
progresso de job (`GET /v1/jobs/{id}/events`).

```python
@router.get("/jobs/{job_id}/events")
async def job_events(job_id: UUID, request: Request, last_event_id: str | None = Header(None)):
    async def gen():
        fila = events.subscribe(job_id)                        # assina antes de ler o replay
        try:
            async for ev in events.replay(job_id, depois_de=last_event_id):
                yield sse(ev)                                  # vem de job_events
            while not await request.is_disconnected():
                try:
                    yield sse(await asyncio.wait_for(fila.get(), timeout=15))
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"     # comentário SSE: mantém proxy e cliente vivos
        finally:
            events.unsubscribe(job_id, fila)
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
```

Três detalhes que só se aprende quebrando:

- **Heartbeat de 15 s.** A linha `: keepalive` é comentário SSE, o cliente ignora, e proxies (Render,
  Cloudflare, nginx) param de cortar a conexão por inatividade. Sem isso, um job em `baixando_wfs` de
  40 s aparece como stream morto.
- **`X-Accel-Buffering: no`.** Sem esse header, proxy com buffer entrega tudo no fim e o streaming vira
  uma resposta única.
- **`Last-Event-ID`.** Cada evento sai com `id: <job_events.id>`; ao recarregar a página o cliente
  reenvia o último id e o backend faz replay a partir de `job_events`, que é append-only e ordenado por
  `(job_id, criado_em)` — nenhuma estrutura nova. O gap entre replay e assinatura se fecha assinando
  antes de ler o replay e descartando duplicatas por id.

O stream do chat é a resposta do `POST` e emite exatamente os eventos do 01, em ordem garantida por
haver um único produtor (o loop de IA). Se o cliente desconectar no meio, o turno segue até o fim e é
persistido em `messages` — não se joga fora trabalho de LLM já pago. Cancelamento explícito é
`POST /v1/conversations/{id}/cancel`, que dispara um `asyncio.Event` observado pelo loop entre passos
de tool.

## Camada LLM

```python
class ChatProvider(Protocol):
    nome: str
    async def complete(self, messages: list[Mensagem], tools: list[ToolDef],
                       *, stream: bool = True) -> RespostaLLM: ...
```

`RespostaLLM` traz `texto`, `tool_calls` e `usage` (tokens de entrada e saída). Duas implementações,
`deepseek.py` e `openai_compat.py`, com o mesmo wire format de chat completions e URL e modelo por env
— foi o que provou funcionar no projeto anterior, onde ambos compartilhavam o mesmo caminho de código.

Regras não negociáveis:

- **Chave só em env var.** No repositório anterior houve chave DeepSeek hardcoded em código; isso não
  se repete aqui. `config.py` é o único lugar que lê ambiente, a chave nunca aparece em log (o logger
  redige `sk-*` e `Authorization`) e o CI roda scanner de segredo que reprova o build.
- **Timeout e retry.** 90 s por chamada; backoff exponencial (1 s, 2 s, 4 s, com jitter) apenas em
  429, 5xx e timeout de rede. Nunca em 400 — pedido malformado repetido só queima cota.
- **Sem fallback silencioso.** O projeto anterior caía num parser local por regras quando a IA
  falhava. Aqui, falha de LLM emite `event: error` e a conversa fica sem resposta: um MapSpec
  heurístico passaria pela validação e produziria um mapa errado com aparência de certo, que é o pior
  resultado possível.
- **Contabilidade.** `messages.usage` guarda tokens por mensagem; o custo por conversa é a soma, com
  preço por 1k tokens vindo de configuração (muda com frequência). É a base do limite por workspace.

O loop IA ↔ tools, a lista de tools e os prompts estão em [07-ia-e-tools.md](../../Fase_1_Desktop/planos/06-agente-eng-florestal.md). Aqui
só importa que o loop é o único produtor do SSE e que cada tool que altera o mapa grava nova linha em
`map_specs` (append-only, `parent_id` apontando para a anterior).

## Validação do MapSpec antes de criar job

`POST /v1/jobs` valida antes de gravar. As invariantes são as do 01, na íntegra e sem acréscimo:

| Invariante | Falha vira |
|---|---|
| `mxd_template` existe no manifesto de `shared/templates/` | `template_not_found` |
| toda `fonte` é `local.<id>` presente na listagem do agente **ou** id do catálogo | `layer_not_allowed` |
| `escala` está na lista de escalas "bonitas" ou é `"auto"` | `mapspec_invalid` |
| `saidas` ⊆ `{mxd, pdf, preview_png, geojson}` | `mapspec_invalid` |
| `crs` é EPSG projetado compatível com a UF do imóvel | `mapspec_invalid` |
| `contract_version` compatível com a do agente | `agent_outdated` |

Rejeição, nunca correção silenciosa (regra do 01). A checagem de `local.<id>` exige o agente online no
momento da criação: se estiver offline, a criação falha com `agent_offline` em vez de enfileirar um job
condenado. A validação roda em dois lugares — aqui e no agente, na etapa `validando_spec` — porque
catálogo e templates do agente podem estar em versão diferente.

## Códigos de erro

Formato `{"erro": {"codigo": "...", "mensagem": "...", "detalhes": {...}}}` do 01. A UI escolhe o
texto pelo `codigo`; `mensagem` é para humano e log, nunca para lógica.

| Código | HTTP | Quando | O que a UI mostra |
|---|---|---|---|
| `agent_offline` | 409 | agente fora do registry ou sem responder RPC | "Seu PC não está conectado" + abrir agente e link do instalador |
| `agent_outdated` | 409 | `contract_version` incompatível | "Atualize o agente" + botão que dispara `agent.update` |
| `mapspec_invalid` | 422 | invariante violada | erros por campo no painel MapSpec, sem jargão de schema |
| `template_not_found` | 422 | `mxd_template` fora do manifesto | "Modelo indisponível" + templates válidos |
| `layer_not_allowed` | 422 | `fonte` fora do catálogo e da listagem local | "Camada não encontrada" + o que existe na pasta |
| `arcpy_failed` | 502 | subprocess Python 2.7 falhou | erro amigável + `log_tail` no painel "Log do job" |
| `license_unavailable` | 502 | ArcMap sem licença na hora da execução | "ArcMap sem licença" + como liberar, com retry |
| `path_not_allowed` | 403 | caminho fora da allowlist do agente | "Pasta não autorizada" + link para configurar pastas |
| `job_timeout` | 504 | sem accept após 3 redespachos, ou `running` parado 15 min | "Demorou demais" + tentar novamente |
| `rate_limited` | 429 | limite do workspace excedido | "Limite atingido" + `Retry-After` e o limite específico |

`arcpy_failed`, `license_unavailable` e `path_not_allowed` nascem no agente e chegam por `job.error`;
aparecem como HTTP apenas quando consultados via `GET /v1/jobs/{id}`.

## Observabilidade

- **Log estruturado JSON**, uma linha por evento, campos fixos: `ts`, `nivel`, `msg`, `request_id`,
  `workspace_id`, `user_id`, `agent_id`, `job_id`, `conversation_id`, `latencia_ms`. Um middleware gera
  `request_id` (ou aceita o `X-Request-ID` recebido) e o propaga por `contextvars` — inclusive dentro do
  loop de IA e do hub WS, senão o rastro se perde no async.
- **Métricas essenciais**: duração de job por etapa (histograma rotulado pelas 9 etapas do 01); taxa de
  falha por `codigo`, com `arcpy_failed` em destaque; tokens e custo por conversa e por workspace;
  latência do RPC ao agente (o p99 diz se 5 s é folgado ou apertado); agentes online; profundidade da
  fila `queued`.
- **Health checks**: `/healthz` responde 200 sem tocar em nada (liveness); `/readyz` faz `SELECT 1` e lê
  o catálogo, devolvendo 503 se faltar algo, para não receber tráfego antes de estar pronto.
- Correlação com o agente pelo `job_id`, que viaja em todos os eventos WS e junta o log do backend ao do
  agente ([04-agente-local.md](../../Fase_1_Desktop/planos/03-nucleo-python.md)).

## Configuração por env var

| Nome | Exemplo | Obrigatório |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@host:5432/mapasfacil` | sim |
| `JWT_SECRET` | string aleatória de 64 bytes | sim |
| `JWT_ACCESS_TTL_MIN` / `JWT_REFRESH_TTL_DIAS` | `30` / `30` | não |
| `LLM_PROVIDER` | `deepseek` \| `openai_compat` | sim |
| `LLM_API_KEY` | `sk-...` | sim |
| `LLM_API_URL` | `https://api.deepseek.com/chat/completions` | sim |
| `LLM_MODEL` | `deepseek-v4-pro` | sim |
| `LLM_TIMEOUT_S` / `LLM_MAX_TOKENS` | `90` / `4096` | não |
| `SHARED_DIR` | `/app/shared` | sim |
| `CORS_ORIGINS` | `https://mapasfacil.app,http://localhost:3000` | sim |
| `SMTP_URL` | `smtp://user:pass@host:587` (magic link) | sim |
| `STORAGE_BUCKET_URL` | destino do `preview.png` opt-in | não |
| `AGENT_WS_HEARTBEAT_S` / `AGENT_RPC_TIMEOUT_S` | `20` / `5` | não |
| `JOB_ACCEPT_TIMEOUT_S` / `JOB_MAX_REDISPATCH` | `30` / `3` | não |
| `RATE_LIMIT_MSG_MIN` | `20` | não |
| `LOG_LEVEL` | `info` | não |
| `ENV` | `dev` \| `staging` \| `prod` | sim |

`config.py` valida tudo no boot e **falha imediatamente** se faltar obrigatório — melhor não subir do que
subir e quebrar no primeiro pedido do usuário. `.env.example` lista todas as chaves com valores falsos.

## Rate limiting e limites de uso por workspace

| Mecanismo | Escopo | Limite inicial | Resposta |
|---|---|---|---|
| Rate limit de requisição | por usuário, janela deslizante | 20 mensagens/min, 60 jobs/hora, 10 `pair-code`/hora | 429 `rate_limited` + `Retry-After` |
| Cota de uso | por workspace, mês corrente | teto de tokens e de jobs por `workspaces.plano` | 429 `rate_limited` com `detalhes.limite` |

Implementação na v1: contadores no Postgres, dentro da transação do pedido — mais lento que Redis e correto
sem infra nova; na escala atual custa um `INSERT` a mais. O `GET /v1/me` já devolve limites de uso (01),
então a UI mostra o consumo antes de o usuário bater no teto. Limites que valem independentemente de
plano: mensagem ≤ 32 kB, `MapSpec` ≤ 512 kB, `preview.png` ≤ 8 MB, no máximo 3 jobs simultâneos por
agente (um agente = uma máquina = um ArcMap; paralelizar só cria disputa por licença).

## Pendências e decisões abertas

0. **Backend não baixa geodado.** Confirmar em code review de todo PR: nenhum `httpx`/`requests`
   para `sema.mt.gov.br` ou outros endpoints do [`13`](../../planos/03-wfs-e-servicos-geo.md). Quem resolve
   WFS é o agente (geobloqueio SEMA + regra de fronteira). O backend só serve o catálogo JSON.

1. **`pasta_destino` do job.** O 01 tem `pasta_destino` em `jobs` e em `job.dispatch`, mas o corpo de
   `POST /v1/jobs` é `{conversation_id, mapspec_id, agent_id, strict_mxd}`. Proposta: derivar de
   `agents.pastas_autorizadas` (primeira pasta de escrita), com campo opcional no corpo para
   sobrescrever. Precisa entrar no 01.
2. **`saidas` duplicado** entre `MapSpec.saidas` e `job.dispatch.saidas`. Proposta: o `MapSpec` é a
   fonte e o payload é cópia derivada, para o agente não interpretar o spec antes de aceitar.
   Confirmar quem ganha em caso de divergência.
3. **Códigos de pareamento e sessões sem tabela.** `POST /v1/agents/pair-code` (TTL 10 min),
   `/v1/auth/magic-link` e `/v1/auth/refresh` não têm onde persistir no modelo do 01. Proposta:
   `agent_pair_codes(codigo_hash, workspace_id, user_id, expira_em, usado_em)` e
   `auth_tokens(token_hash, tipo, expira_em, revogado_em)`.
4. **Turno em andamento.** `POST /v1/conversations/{id}/cancel` precisa saber qual turno cancelar.
   Proposta: coluna `messages.status` (`streaming`/`completa`/`cancelada`/`erro`).
5. **Tenancy.** `jobs`, `map_specs` e `messages` não têm `workspace_id`; o isolamento depende de join
   com `conversations`. Decidir entre denormalizar `workspace_id` (mais fácil de indexar e auditar) ou
   usar RLS no Postgres.
6. **Lacunas de schema do `MapSpec`.** `escala` é número no exemplo e `"auto"` na invariante, o que exige
   união explícita no JSON Schema e a regra de cálculo de `"auto"` em
   [05-motor-mxd-pdf.md](../../Fase_1_Desktop/planos/04-motor-mxd.md); e `tabela.posicao` usa `in-map-bottom-right` sem enumerar
   valores — sem enumeração fechada, a IA inventa posição e o validador não pega.
7. **`GET /v1/agents/{id}/doctor` tem efeito colateral** (dispara RPC), o que quebra idempotência e pode
   ser refeito por retry de proxy. Proposta: `POST` para forçar, `GET` para ler o cache.
8. **`usage` de `message.end`** está como `{...}` no 01. Proposta: `{tokens_entrada, tokens_saida,
   custo_usd, provedor, modelo}`, espelhando `messages.usage`.
9. **Retenção.** `job_events` cresce rápido. Definir política (proposta: detalhe por 90 dias, resumo
   permanente) e o destino dos `preview.png` opt-in expirados.
10. **Fonte dos schemas.** Decidir se `shared/schemas/*.json` é gerado do Pydantic ou o contrário.
    Preferência: `shared/` é a fonte e o CI falha se o modelo Pydantic divergir — assim backend e agente
    não podem discordar em silêncio.
