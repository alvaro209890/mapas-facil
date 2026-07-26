# F1-17 — Persistência local de conversas

## Objetivo

Toda conversa do app é salva localmente e reabrível a qualquer momento, como o histórico do
Cursor: sidebar com a lista, busca por texto, renomear, arquivar, apagar, ramificar. Reabrir uma
conversa restaura as mensagens, os traços de tool, o resumo comprimido e o ponteiro para o
`MapSpec` que ela produziu. Nada disso sai do PC na v1 (D20).

## Estado atual vs alvo

| Item | Atual | Alvo |
|---|---|---|
| Armazenamento de conversa | **feito** — `MAPASFACIL_DADOS/chats/chats.sqlite` (Electron: `userData`) | `%APPDATA%\MapasFacil\chats\chats.sqlite` |
| Métodos `chat.*` de histórico | **feitos** (9 + `chat.gravar_mensagem`) | 9 métodos NDJSON abaixo |
| Sidebar de chats | **feita** — `BarraChats` com busca, filtro pasta, novo, apagar | `barra-chats` ([F1-16](16-design-system-dark.md)) |
| Local declarado na arquitetura antiga | `projetos\<hash>\conversas.sqlite` | **revogado por D13** — banco único global |

### D13 — por que um banco global e não um por projeto

O desenho anterior ([F1-01](01-arquitetura.md)) colocava `conversas.sqlite` dentro de
`projetos\<hash>\`. Isso impede a sidebar de listar chats de todos os workspaces, que é o
comportamento esperado por quem vem do Cursor. Decisão: **um banco em
`%APPDATA%\MapasFacil\chats\chats.sqlite`**, com `workspace_fingerprint` por conversa. Apagar um
projeto continua fácil (`DELETE ... WHERE workspace_fingerprint = ?`), e a busca global sai de
graça. A F1-01 foi reescrita para refletir isso.

## Dependências

| Precisa de | Estado |
|---|---|
| M3 — shell da UI | **feito** |
| `workspace.abrir` (para o fingerprint) | existe |
| Agente (para produzir mensagens) | ausente — mas o histórico **não** depende dele: `chat.gravar_mensagem` cobre galeria/modo determinístico |

## Contratos

### Layout em disco

```
%APPDATA%\MapasFacil\chats\
├─ chats.sqlite            conversas, mensagens, traços de tool, resumos, FTS
├─ chats.sqlite-wal        (WAL — journal_mode=WAL)
└─ anexos\<conversation_id>\<message_id>-<n>.<ext>
                           cópia local de print/PDF/zip arrastado para o chat
```

`anexos/` guarda **cópia**, não referência: o usuário pode mover a pasta do projeto e o histórico
continua legível. Limite de 20 MB por anexo; acima disso guarda só o caminho original e o hash.

### Esquema SQLite

```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE conversas (
  conversation_id        TEXT PRIMARY KEY,          -- ULID
  title                  TEXT NOT NULL,
  created_at             TEXT NOT NULL,             -- ISO-8601 UTC, sufixo Z
  updated_at             TEXT NOT NULL,
  workspace_path         TEXT,                      -- absoluto; NUNCA enviado ao LLM
  workspace_fingerprint  TEXT NOT NULL,             -- sha256(realpath normalizado minúsculo)
  workspace_nome         TEXT,                      -- só o nome da pasta, para a sidebar
  conta_id               TEXT,                      -- dono; NULL em chats criados antes do login
  arquivada              INTEGER NOT NULL DEFAULT 0,
  parent_conversation_id TEXT REFERENCES conversas(conversation_id) ON DELETE SET NULL,
  parent_message_seq     INTEGER,                   -- ponto da ramificação
  compact_summary        TEXT,                      -- resumo do trecho antigo (ver F1-06)
  compact_ate_seq        INTEGER,                   -- o resumo cobre mensagens seq <= este
  modelo                 TEXT,                      -- ex.: deepseek-v4-pro
  tokens_entrada         INTEGER NOT NULL DEFAULT 0,
  tokens_saida           INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE mensagens (
  message_id      TEXT PRIMARY KEY,                 -- ULID
  conversation_id TEXT NOT NULL REFERENCES conversas(conversation_id) ON DELETE CASCADE,
  seq             INTEGER NOT NULL,                 -- 1..N, monotônico por conversa
  papel           TEXT NOT NULL CHECK (papel IN ('usuario','assistente','sistema','tool')),
  conteudo        TEXT NOT NULL,
  criado_em       TEXT NOT NULL,
  mapspec_id      TEXT,
  mapspec_versao  INTEGER,
  cancelada       INTEGER NOT NULL DEFAULT 0,
  UNIQUE (conversation_id, seq)
);

CREATE TABLE tool_traces (
  trace_id         TEXT PRIMARY KEY,
  conversation_id  TEXT NOT NULL REFERENCES conversas(conversation_id) ON DELETE CASCADE,
  message_id       TEXT REFERENCES mensagens(message_id) ON DELETE CASCADE,
  tool             TEXT NOT NULL,
  args_resumo      TEXT,                            -- <= 500 caracteres, já resumido
  resultado_resumo TEXT,                            -- <= 1000 caracteres, já resumido
  ms               INTEGER,
  ok               INTEGER NOT NULL DEFAULT 1,
  erro_codigo      TEXT,
  criado_em        TEXT NOT NULL
);

CREATE TABLE conversa_mapspecs (
  conversation_id TEXT NOT NULL REFERENCES conversas(conversation_id) ON DELETE CASCADE,
  mapspec_id      TEXT NOT NULL,
  versao          INTEGER NOT NULL,
  criado_em       TEXT NOT NULL,
  PRIMARY KEY (conversation_id, mapspec_id, versao)
);

CREATE TABLE anexos (
  anexo_id        TEXT PRIMARY KEY,
  conversation_id TEXT NOT NULL REFERENCES conversas(conversation_id) ON DELETE CASCADE,
  message_id      TEXT REFERENCES mensagens(message_id) ON DELETE CASCADE,
  caminho_local   TEXT NOT NULL,                    -- relativo a chats/anexos/
  nome_original   TEXT NOT NULL,
  bytes           INTEGER NOT NULL,
  sha256          TEXT NOT NULL
);

CREATE INDEX idx_conversas_updated  ON conversas(arquivada, updated_at DESC);
CREATE INDEX idx_conversas_ws       ON conversas(workspace_fingerprint, updated_at DESC);
CREATE INDEX idx_mensagens_conv_seq ON mensagens(conversation_id, seq DESC);
CREATE INDEX idx_traces_conv        ON tool_traces(conversation_id, criado_em);

CREATE VIRTUAL TABLE mensagens_fts USING fts5(
  conteudo, content='mensagens', content_rowid='rowid', tokenize='unicode61 remove_diacritics 2'
);
-- triggers de sincronia INSERT/UPDATE/DELETE obrigatórios; sem eles a busca mente
```

Migrações: tabela `schema_versao (versao INTEGER)` com valor inicial `1`. Toda mudança de esquema
é um script `nucleo/mapasfacil_nucleo/conversas/migracoes/00N_*.sql` aplicado no boot, dentro de
transação. **Nunca** `DROP TABLE` sem cópia de segurança do arquivo ao lado (`chats.sqlite.bak`).

### Métodos NDJSON

| Método | Params | Retorno |
|---|---|---|
| `chat.criar_conversa` | `{workspace?, title?}` | `{conversation_id, title, created_at}` |
| `chat.listar_conversas` | `{workspace?, incluir_arquivadas?:false, limite?:50, antes_de?}` | `{conversas:[{conversation_id, title, updated_at, workspace_nome, mensagens_total, ultimo_trecho}], tem_mais}` |
| `chat.abrir_conversa` | `{conversation_id, limite?:30}` | `{conversa, mensagens:[…últimas N…], compact_summary, total, mapspecs:[]}` |
| `chat.carregar_anteriores` | `{conversation_id, antes_de_seq, limite?:50}` | `{mensagens:[], tem_mais}` |
| `chat.renomear` | `{conversation_id, title}` | `{ok:true}` |
| `chat.arquivar` | `{conversation_id, arquivada:true\|false}` | `{ok:true}` |
| `chat.apagar` | `{conversation_id}` | `{ok:true, anexos_removidos:N}` |
| `chat.ramificar` | `{conversation_id, a_partir_do_seq, title?}` | `{conversation_id}` — copia mensagens `seq <= a_partir_do_seq` |
| `chat.buscar` | `{termo, workspace?, limite?:30}` | `{resultados:[{conversation_id, message_id, seq, trecho_destacado, updated_at}]}` |

Nenhum destes tem gate de sessão ([F1-14](14-auth-e-conta.md)): ler o próprio histórico offline e
com sessão expirada é permitido. `chat.enviar` (que grava mensagem nova de IA) **tem** gate.

### Título automático

1. Ao criar, `title` = `"Conversa sem título"`.
2. Depois da **primeira** resposta do agente, o título é gerado por `deepseek-v4-flash` (tarefa
   trivial e barata) com teto de 48 caracteres, e gravado.
3. Sem chave de IA, o título vem do modelo da galeria usado (`"Dinâmica de uso do solo · Harmonia"`)
   ou dos 48 primeiros caracteres da primeira mensagem do usuário.
4. Renomear manualmente marca `title_manual` implicitamente: uma vez renomeado pelo usuário, o
   título **nunca** é sobrescrito pela IA. (Coluna: reaproveite `title` + `parent_message_seq`
   não serve — acrescente `title_manual INTEGER NOT NULL DEFAULT 0` na migração 001.)

### Privacidade

| Regra | Como se cumpre |
|---|---|
| Sem CPF, nunca | redator aplicado **antes do INSERT**, não na leitura: regex `\d{3}\.?\d{3}\.?\d{3}-?\d{2}` → `[CPF removido]`. Testado |
| Sem chave de API no conteúdo | o mesmo redator cobre `api_key=`, `authkey=`, `Bearer `, `PLAK…` |
| Sem sincronização para nuvem na v1 | D20. Não existe código de upload; o espelho é Fase 2 e opt-in |
| `workspace_path` não vai para o LLM | o montador de contexto usa `workspace_nome` e caminhos relativos ([F1-06](06-agente-eng-florestal.md)) |
| Logout preserva o histórico | D14. "Sair" só revoga sessão. "Sair e esquecer este PC" apaga `chats.sqlite`, `anexos/` e `config.json`, com confirmação por texto digitado |
| Apagar conversa apaga anexos | `chat.apagar` remove os arquivos de `anexos/<conversation_id>/` e devolve a contagem |

## Comportamento na interface (`barra-chats`)

| Elemento | Comportamento |
|---|---|
| Botão "novo chat" | `chat.criar_conversa` com o workspace aberto; foco vai para `campo-entrada` |
| Lista | agrupada por "Hoje", "Ontem", "7 dias", "Antes"; cada item mostra título e nome da pasta quando difere do workspace aberto |
| Filtro por pasta | alterna entre "todos os chats" e "só desta pasta" (`workspace_fingerprint`) |
| Busca (`Ctrl+F`) | `chat.buscar`, com trecho destacado; Enter abre a conversa **na mensagem encontrada** |
| Menu de contexto | renomear · arquivar · ramificar daqui · apagar (com confirmação) |
| Reabrir | `chat.abrir_conversa` traz as últimas 30; rolar para cima dispara `chat.carregar_anteriores`; o `compact_summary` aparece como um bloco recolhido no topo ("resumo de 84 mensagens anteriores") |
| Conversa de outro workspace | abrir mostra faixa: "esta conversa é da pasta X — abrir a pasta?" e **não** troca o workspace sozinho |

## Tarefas agentáveis

- [x] `nucleo/mapasfacil_nucleo/conversas/esquema.sql` — DDL acima + triggers do FTS
- [x] `nucleo/mapasfacil_nucleo/conversas/migracoes/001_inicial.sql`
- [x] `nucleo/mapasfacil_nucleo/conversas/repositorio.py` — CRUD, transações, WAL
- [x] `nucleo/mapasfacil_nucleo/conversas/redator.py` — CPF, chaves, tokens (compartilhado com o log)
- [x] `nucleo/mapasfacil_nucleo/conversas/titulo.py` — geração e regra de `title_manual`
- [x] `nucleo/mapasfacil_nucleo/conversas/fingerprint.py` — `sha256(realpath normalizado)`
- [x] `nucleo/mapasfacil_nucleo/__main__.py` — registrar os 9 métodos (+ `chat.gravar_mensagem`)
- [x] `app/src/paineis/BarraChats.tsx`, `app/src/estado/conversas.ts`
- [x] `nucleo/tests/test_conversas.py`, `nucleo/tests/test_conversas_redator.py`

## Critérios de aceite

- [x] `pytest nucleo/tests/test_conversas.py` verde
- [x] **Ciclo completo:** criar conversa → gravar 5 mensagens → fechar o processo do núcleo →
      reabrir → `chat.abrir_conversa` devolve as 5 na ordem correta, com os `tool_traces`
- [x] **Escala:** fixture com 1 conversa de 200 mensagens; `chat.abrir_conversa` responde em
      **< 300 ms** em máquina normal (teste usa teto 800 ms para CI/VM) e devolve exatamente 30
      mensagens + `total: 200`
- [x] `chat.buscar` com termo acentuado encontra a mensagem escrita sem acento e vice-versa
      (`remove_diacritics 2`)
- [x] Inserir mensagem com `"CPF 123.456.789-00"` → `SELECT conteudo` devolve `[CPF removido]`;
      o CPF **não** está no arquivo (`grep -a "123.456.789" chats.sqlite` vazio)
- [x] `chat.ramificar` a partir do `seq` 3 de uma conversa de 10 cria uma conversa com 3
      mensagens e `parent_conversation_id` preenchido
- [x] `chat.apagar` remove as linhas em cascata (mensagens, traces, anexos) e os arquivos do disco
- [ ] Logout (`auth:sair` sem `esquecer_este_pc`) mantém `chats.sqlite` intacto — teste de integração (espera M5)
- [x] `grep` por cliente HTTP em `nucleo/mapasfacil_nucleo/conversas/` vazio — nenhum caminho de rede
- [x] Abrir a mesma conversa em duas conexões não corrompe o banco (WAL + transações; teste de
      escrita concorrente)

## Fora de escopo

- Sincronizar conversas entre máquinas (Fase 2, opt-in — D20).
- Exportar conversa para PDF/Markdown (candidato a v1.1).
- Compartilhar link de conversa.
- Criptografar `chats.sqlite` em repouso (o disco do usuário é a fronteira de confiança na v1;
  registre como pendência se um piloto pedir).
- Editar mensagem já enviada (ramificar cobre o caso).

## Anti-padrões

| Não faça | Por quê |
|---|---|
| Gravar conversa dentro da pasta do projeto do cliente | polui a entrega e vaza histórico junto com o `.zip` do mapa |
| Carregar as 200 mensagens de uma vez ao abrir | trava a UI; existe paginação |
| Redigir CPF só na exibição | o dado fica no arquivo; a redação é **na entrada** |
| Apagar histórico no logout | D14; o usuário perde trabalho por trocar de conta |
| Guardar resultado bruto de tool no `tool_traces` | o campo é resumo; blob bruto infla o banco e volta para o LLM depois |
| JSON solto por conversa "porque é mais simples" | busca e paginação viram código manual e lento |
| Usar `updated_at` local sem UTC | ordena errado ao virar o horário de verão |
