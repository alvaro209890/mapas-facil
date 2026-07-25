# F2-01 — Arquitetura

> **LEGADO (2026-07-25).** Este texto ainda descreve o modelo antigo **nuvem (Vercel/Render) +
> agente WebSocket no PC**. A decisão vigente é **D7**: backend neste PC + Cloudflare Tunnel;
> o `.mxd` nasce na Fase 1. Use como referência histórica até a reescrita. Índice e direção
> nova: [`README.md`](README.md) e [`00-visao-e-escopo.md`](00-visao-e-escopo.md).
>
> A **fonte da verdade** da Fase 1 é [`../../Fase_1_Desktop/planos/01-arquitetura.md`](../../Fase_1_Desktop/planos/01-arquitetura.md).
> O `MapSpec` e o padrão visual vivem em [`../../planos/`](../../planos/README.md).

Este documento (legado) descrevia endpoints, protocolo do agente, estados de job e um `MapSpec`
embutido. **Não use como fonte da verdade** até ser reescrito.

## Os três componentes

```
┌─────────────────────────────── NUVEM ────────────────────────────────┐
│                                                                       │
│   web/  (Vercel)                    backend/  (Render)                │
│  ┌──────────────────┐              ┌────────────────────────────┐    │
│  │ Next.js 16       │  HTTPS       │ FastAPI 3.11               │    │
│  │ • sidebar convs  │─────────────▶│ • auth / conversas         │    │
│  │ • chat streaming │  SSE         │ • loop IA ↔ tools          │    │
│  │ • painel MapSpec │◀─────────────│ • validação do MapSpec     │    │
│  │ • preview PDF/PNG│              │ • fila e despacho de jobs  │    │
│  └──────────────────┘              │ • hub WebSocket de agentes │    │
│                                     └───────────┬────────────────┘    │
│                                     Postgres ───┘                     │
└─────────────────────────────────────────────────┼─────────────────────┘
                                                  │ WSS (agente inicia,
                                                  │ outbound only)
┌─────────────────────────────────────────────────▼─────────────────────┐
│  PC DO USUÁRIO — Windows 10/11                     agent/             │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │ Host Python 3.11 (serviço/tray)                                 │  │
│  │  • cliente WSS + heartbeat        • doctor do ambiente          │  │
│  │  • resolve camadas locais/WFS     • escreve saídas em disco     │  │
│  │  └── subprocess ──▶ Python 2.7 (ArcMap) rodando arcpy_export.py │  │
│  │                      • abre template .mxd  • repõe fontes       │  │
│  │                      • extent/escala       • exporta PDF        │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│  Saídas: C:\MapasFacil\<projeto>\<job_id>\{mapa.mxd, mapa.pdf, ...}   │
└───────────────────────────────────────────────────────────────────────┘
```

### Regras de fronteira (invioláveis)

1. O agente **sempre inicia** a conexão (WebSocket outbound). O backend nunca abre porta na
   máquina do usuário — funciona atrás de NAT, firewall corporativo e VPN sem configuração.
2. **Nenhum dado geoespacial do cliente sobe para a nuvem.** O que trafega é: `MapSpec` (JSON),
   metadados de job, listagens de nome de arquivo dentro das pastas autorizadas, `preview.png`
   (opt-in, com aviso explícito) e logs.
3. O agente só lê e escreve dentro das **pastas autorizadas** pelo usuário no pareamento. Todo
   caminho recebido do backend é validado contra essa allowlist antes de qualquer I/O.
4. O backend **nunca** manda código para o agente executar. Manda `MapSpec` declarativo. O
   agente traduz para chamadas `arcpy` que ele mesmo implementa.
5. `web/`, `backend/`, `agent/` e `shared/` são deployados independentemente. A compatibilidade
   entre eles é garantida por versão de contrato (`contract_version`), não por deploy sincronizado.

## Fluxo completo de um mapa

```
1. Usuário abre o site, faz login, escolhe/cria conversa.
2. Site mostra agentes pareados e online. Usuário escolhe o PC de trabalho.
3. Usuário: "Dinâmica 2026 da Fazenda Trevisol, lote 65, com AVN, AC e AUAS"
4. Backend inicia o loop IA↔tools:
     estado_atual → listar_camadas_locais (pergunta ao agente!) → criar_mapa
     → adicionar_camada ×4 → editar_tabela → validar_mapspec → finalizar
5. Backend valida o MapSpec contra shared/schemas + catálogo. Rejeita o que não existe.
6. Backend cria job (status=queued) e despacha para o agente via WS.
7. Agente: aceita → resolve camadas (shapefile local; WFS recortado por bbox, com cache)
     → chama Python 2.7 + arcpy → abre template .mxd → repõe data sources
     → aplica estilos, extent, escala "bonita", legenda, metadados, tabela
     → salva mapa.mxd → exporta mapa.pdf (300 dpi) → renderiza preview.png
8. Agente roda validação de conformidade IMAP local e envia o relatório.
9. Agente sobe preview.png + validacao.json; site atualiza em tempo real via SSE.
10. Usuário: "deixa a ATP amarela e tira a barra de escala"
      → nova versão do job (parent_job_id + versao), MXD e PDF novos, o anterior intacto.
```

O passo 4 tem uma consequência arquitetural importante: **o loop de IA precisa consultar o
agente local em tempo real** (para listar shapefiles disponíveis). Isso é feito por RPC sobre o
mesmo WebSocket, com timeout curto (5 s) e degradação graciosa se o agente estiver offline.

## Contrato HTTP do backend (v1)

Prefixo `/v1`. Autenticação por `Authorization: Bearer <jwt>` (usuário) ou
`Authorization: Bearer <agent_token>` (agente). Respostas de erro seguem
`{"erro": {"codigo": "...", "mensagem": "...", "detalhes": {...}}}`.

### Autenticação e conta

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/v1/auth/magic-link` | envia link de login por e-mail |
| `POST` | `/v1/auth/callback` | troca token do link por sessão |
| `POST` | `/v1/auth/refresh` | renova o access token |
| `GET` | `/v1/me` | perfil, workspace e limites de uso |

### Conversas e mensagens

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/v1/conversations?cursor=&limit=` | lista paginada (mais recentes primeiro) |
| `POST` | `/v1/conversations` | cria conversa (título gerado depois pela IA) |
| `GET` | `/v1/conversations/{id}` | conversa + `MapSpec` ativo + jobs |
| `PATCH` | `/v1/conversations/{id}` | renomear, arquivar, fixar |
| `DELETE` | `/v1/conversations/{id}` | soft delete |
| `GET` | `/v1/conversations/{id}/messages?cursor=` | histórico paginado |
| `POST` | `/v1/conversations/{id}/messages` | **envia mensagem → responde SSE** |
| `POST` | `/v1/conversations/{id}/cancel` | cancela o turno em andamento |

### Jobs (geração de mapa)

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/v1/jobs` | cria job a partir de `{conversation_id, mapspec_id, agent_id, strict_mxd}` |
| `GET` | `/v1/jobs/{id}` | estado, versão, `parent_job_id`, artefatos |
| `GET` | `/v1/jobs/{id}/events` | **SSE** com progresso ao vivo |
| `POST` | `/v1/jobs/{id}/cancel` | pede cancelamento ao agente |
| `GET` | `/v1/jobs/{id}/artifacts` | lista artefatos + URLs assinadas |

### Agentes locais

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/v1/agents/pair-code` | usuário gera código de 8 caracteres (TTL 10 min) |
| `POST` | `/v1/agents/pair` | agente troca código por `agent_token` permanente |
| `GET` | `/v1/agents` | lista agentes do workspace: nome, SO, online, doctor, versão |
| `PATCH` | `/v1/agents/{id}` | renomear, alterar pastas autorizadas, revogar |
| `DELETE` | `/v1/agents/{id}` | revoga token |
| `GET` | `/v1/agents/{id}/doctor` | força novo diagnóstico (RPC) |
| `GET` | `/v1/agents/{id}/fs?path=` | lista shapefiles/pastas dentro da allowlist (RPC) |
| `WS` | `/v1/agents/ws` | canal do agente (ver protocolo abaixo) |

### Catálogo e artefatos

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/v1/catalog/layers` | camadas que a IA pode usar (de `shared/catalog/camadas.json`) |
| `GET` | `/v1/catalog/services` | provedores WFS/WMS/REST (de `shared/catalog/servicos_geo.json`) |
| `GET` | `/v1/catalog/templates` | templates `.mxd` permitidos |
| `GET` | `/v1/catalog/version` | `contract_version` + hash do catálogo |

O backend **não** baixa geodado. Quem resolve WFS/WMS é o agente local — a SEMA bloqueia IP
fora do Brasil. Receitas: [`13-wfs-e-servicos-geo.md`](../../planos/03-wfs-e-servicos-geo.md).
| `POST` | `/v1/jobs/{id}/artifacts` | **agente** sobe `preview.png` / `validacao.json` |
| `GET` | `/v1/artifacts/{id}` | redireciona para URL assinada (TTL 15 min) |

### Eventos SSE do chat

Um turno de conversa emite, na ordem:

```
event: message.start      {"message_id": "...", "role": "assistant"}
event: text.delta         {"delta": "Vou montar a Dinâmica..."}
event: tool.call          {"id":"c1","tool":"adicionar_camada","args":{...}}
event: tool.result        {"id":"c1","ok":true,"resultado":"camada AVN adicionada"}
event: mapspec.updated    {"mapspec_id":"...","versao":3,"diff":[...]}
event: job.created        {"job_id":"..."}
event: message.end        {"finish_reason":"stop","usage":{...}}
event: error              {"codigo":"agent_offline","mensagem":"..."}
```

O frontend deve tolerar eventos desconhecidos (ignorar) — isso permite evoluir o protocolo sem
quebrar clientes antigos.

## Protocolo WebSocket agente ↔ backend

Envelope único para as duas direções:

```json
{
  "v": 1,
  "id": "msg_01H...",
  "tipo": "job.dispatch",
  "ts": "2026-07-24T23:41:02Z",
  "reply_to": null,
  "payload": {}
}
```

`id` é ULID; `reply_to` referencia o `id` da mensagem que originou a resposta (RPC).

### Backend → agente

| Tipo | Payload | Semântica |
|---|---|---|
| `job.dispatch` | `{job_id, mapspec, saidas, pasta_destino, strict_mxd}` | gera o mapa |
| `job.cancel` | `{job_id}` | aborta (mata o subprocess ArcPy) |
| `fs.list` | `{path, tipos:["shp","zip"]}` | RPC: lista conteúdo dentro da allowlist |
| `fs.inspect` | `{path}` | RPC: geometria, CRS, contagem, campos, bbox de um shapefile |
| `doctor.run` | `{}` | RPC: diagnóstico completo do ambiente |
| `agent.update` | `{versao, url, sha256}` | oferece atualização (usuário confirma) |
| `ping` | `{}` | keep-alive |

### Agente → backend

| Tipo | Payload | Semântica |
|---|---|---|
| `hello` | `{agent_version, contract_version, os, hostname, doctor, pastas_autorizadas}` | primeira mensagem após conectar |
| `heartbeat` | `{uptime_s, jobs_ativos}` | a cada 20 s |
| `job.accepted` | `{job_id}` | aceitou e vai executar |
| `job.progress` | `{job_id, etapa, pct, mensagem}` | etapas em [`04`](../../Fase_1_Desktop/planos/03-nucleo-python.md) |
| `job.log` | `{job_id, nivel, linha}` | log técnico (útil no painel de debug) |
| `job.artifact` | `{job_id, tipo, nome, caminho_local, bytes, sha256, upload:bool}` | artefato pronto |
| `job.done` | `{job_id, artefatos, validacao, duracao_ms}` | sucesso |
| `job.error` | `{job_id, codigo, mensagem, etapa, log_tail}` | falha |
| `rpc.result` | resposta de `fs.*`/`doctor.run` | com `reply_to` |
| `pong` | `{}` | resposta ao `ping` |

Regras: reconexão com backoff exponencial (1 s → 60 s, com jitter); jobs em execução sobrevivem à
queda do WebSocket e reportam ao reconectar; mensagens não entregues ficam na fila do backend por
24 h.

## Ciclo de vida do job

```
queued ──▶ dispatched ──▶ running ──┬──▶ succeeded
   │            │            │       ├──▶ failed
   │            │            │       └──▶ cancelled
   │            │            └── (agente cai) ──▶ running (retomado ao reconectar)
   │            └── (timeout 30 s sem accept) ──▶ queued (redespacha, até 3×)
   └── (nenhum agente online) ──▶ queued, UI mostra "aguardando seu PC"
```

Etapas dentro de `running`, reportadas em `job.progress`:

| # | Etapa | Peso |
|---|---|---|
| 1 | `validando_spec` | 5% |
| 2 | `resolvendo_camadas_locais` | 10% |
| 3 | `baixando_wfs` | 20% |
| 4 | `abrindo_template` | 5% |
| 5 | `repontando_fontes` | 15% |
| 6 | `aplicando_layout` | 15% |
| 7 | `salvando_mxd` | 5% |
| 8 | `exportando_pdf` | 15% |
| 9 | `validando_saida` | 10% |

## Modelo de dados (Postgres)

```
users(id, email, nome, criado_em, ultimo_login_em)
workspaces(id, nome, owner_id, plano)
workspace_members(workspace_id, user_id, papel)

agents(id, workspace_id, nome, hostname, os, agent_version, token_hash,
       pastas_autorizadas jsonb, doctor jsonb, ultimo_hello_em, online bool,
       revogado_em)

conversations(id, workspace_id, user_id, titulo, agent_id, arquivada, fixada,
              criada_em, atualizada_em)
messages(id, conversation_id, role, conteudo, tool_calls jsonb, usage jsonb,
         mapspec_id, criada_em)

map_specs(id, conversation_id, versao, parent_id, spec jsonb, valido bool,
          erros_validacao jsonb, criada_em)

jobs(id, conversation_id, mapspec_id, agent_id, parent_job_id, versao, status,
     strict_mxd, etapa, pct, pasta_destino, duracao_ms, erro jsonb,
     validacao jsonb, criado_em, finalizado_em)
job_events(id, job_id, tipo, payload jsonb, criado_em)      -- append-only
artifacts(id, job_id, tipo, nome, bytes, sha256, caminho_local,
          storage_key, criado_em)                            -- storage_key null = só local

audit_log(id, workspace_id, ator, acao, alvo, ip, payload jsonb, criado_em)
```

Índices que importam: `conversations(workspace_id, atualizada_em desc)`,
`messages(conversation_id, criada_em)`, `jobs(agent_id, status)`,
`job_events(job_id, criado_em)`.

Decisões: `map_specs` é **append-only** (edição = nova linha com `parent_id`), o que dá o
histórico de versões de graça; `job_events` também, para replay do SSE quando o usuário
recarrega a página.

## `MapSpec` v1 — o contrato central

JSON declarativo que descreve o mapa por completo. Schema em
`shared/schemas/mapspec.schema.json`. Formato canônico:

```json
{
  "contract_version": 1,
  "titulo": "DINÂMICA DE USO DO SOLO - 2026",
  "layout_template": "dinamica_a4_paisagem",
  "mxd_template": "Dinamica_2026.mxd",
  "crs": "EPSG:31982",
  "escala": 22000,
  "area_base": { "fonte": "local.lotes", "campo_rotulo": "NOME" },
  "camadas": [
    {
      "id": "lote_principal",
      "fonte": "local.lotes",
      "filtro": "LOTE = '65'",
      "estilo": { "preenchimento": "none", "linha": "#c00000", "largura": 2.8 },
      "rotulo_texto": "Fazenda Trevisol (Lote 65)\nMatrícula 13.533",
      "legenda": "Lote 65"
    },
    {
      "id": "avn",
      "fonte": "local.avn",
      "estilo": { "preenchimento": "none", "linha": "#00b050",
                  "hachura": "xxx", "largura": 0.7 },
      "legenda": "Área de Vegetação Nativa"
    }
  ],
  "elementos_layout": {
    "grade": true, "grade_linhas": false, "norte": true,
    "rosa_dos_ventos": false, "escala_grafica": false, "creditos": false,
    "minimapa": true, "titulo_caixa": true, "tabela": true,
    "metadados_imagem": true, "logo": true, "inset_tipologia": false
  },
  "tabela": {
    "posicao": "in-map-bottom-right",
    "colunas": ["Propriedade", "Área total (ha)", "AVN (ha)", "AC (ha)", "AUAS (ha)"],
    "linhas": [["Lote 65", "1.234,56", "800,12", "400,00", "34,44"]],
    "total": true
  },
  "metadados_imagem": {
    "satelite_sensor": "PLANET", "orbita_ponto": "Não se aplica",
    "data_aquisicao": "Maio/2026", "datum": "SIRGAS 2000 UTM 22S"
  },
  "basemap": { "tipo": "esri_world_imagery" },
  "saidas": ["mxd", "pdf", "preview_png"]
}
```

Invariantes validadas antes de qualquer job (rejeição, não correção silenciosa):

- `mxd_template` existe no manifesto de `shared/templates/`.
- toda `fonte` é `local.<id>` presente na listagem do agente **ou** id do catálogo de camadas.
- `escala` pertence à lista de escalas "bonitas" (ou é `"auto"`).
- `saidas` ⊆ `{mxd, pdf, preview_png, geojson}`.
- `crs` é EPSG projetado compatível com a UF do imóvel.
- `contract_version` compatível com a do agente (senão: pedir atualização do agente).

## Ambientes

| Ambiente | web | backend | banco | agente |
|---|---|---|---|---|
| dev | `localhost:3000` | `localhost:8000` | Postgres em Docker | rodando na mão, aponta para localhost |
| staging | preview Vercel | serviço staging | Postgres staging | build assinado `-beta` |
| prod | `mapasfacil.app` | `api.mapasfacil.app` | Postgres prod | instalador assinado |

Detalhes em [`12-deploy-e-distribuicao.md`F-deploy-tunnel-neste-pc.md).

## O que este desenho deliberadamente não faz

- **Não** usa WebRTC/túnel reverso para o navegador falar direto com o agente: o backend no meio
  simplifica auth, auditoria e histórico, e o custo (JSON pequeno) é irrelevante.
- **Não** guarda os artefatos na nuvem por padrão: `.mxd`/`.pdf` ficam no PC; a nuvem guarda
  metadados e, se o usuário permitir, o `preview.png`.
- **Não** tem microserviços: um backend monolítico FastAPI resolve tudo nessa escala.
