-- F1-17 §Esquema SQLite — estado consolidado do banco de conversas.
--
-- Este arquivo é a FORMA ALVO, para leitura humana e para o teste de deriva
-- (`test_esquema_consolidado_igual_ao_das_migracoes`): quem cria o banco de
-- verdade é `banco.py`, aplicando `migracoes/00N_*.sql` em ordem. Mudou o
-- esquema? escreva a migração nova **e** atualize este arquivo no mesmo commit,
-- senão o teste falha.
--
-- `PRAGMA journal_mode`/`foreign_keys` não moram aqui: pragma de conexão é
-- responsabilidade de `banco.conectar`, não de DDL versionada.

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
  tokens_saida           INTEGER NOT NULL DEFAULT 0,
  title_manual           INTEGER NOT NULL DEFAULT 0 -- 1 = renomeado pelo usuário; a IA não sobrescreve
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

CREATE TABLE schema_versao (versao INTEGER NOT NULL);

CREATE INDEX idx_conversas_updated  ON conversas(arquivada, updated_at DESC);
CREATE INDEX idx_conversas_ws       ON conversas(workspace_fingerprint, updated_at DESC);
CREATE INDEX idx_mensagens_conv_seq ON mensagens(conversation_id, seq DESC);
CREATE INDEX idx_traces_conv        ON tool_traces(conversation_id, criado_em);

CREATE VIRTUAL TABLE mensagens_fts USING fts5(
  conteudo, content='mensagens', content_rowid='rowid', tokenize='unicode61 remove_diacritics 2'
);

-- Sincronia do índice externo. Sem estes três a busca mente: o FTS fica com o
-- texto antigo e `chat.buscar` devolve mensagem que não existe mais.
CREATE TRIGGER mensagens_fts_ai AFTER INSERT ON mensagens BEGIN
  INSERT INTO mensagens_fts(rowid, conteudo) VALUES (new.rowid, new.conteudo);
END;

CREATE TRIGGER mensagens_fts_ad AFTER DELETE ON mensagens BEGIN
  INSERT INTO mensagens_fts(mensagens_fts, rowid, conteudo) VALUES ('delete', old.rowid, old.conteudo);
END;

CREATE TRIGGER mensagens_fts_au AFTER UPDATE ON mensagens BEGIN
  INSERT INTO mensagens_fts(mensagens_fts, rowid, conteudo) VALUES ('delete', old.rowid, old.conteudo);
  INSERT INTO mensagens_fts(rowid, conteudo) VALUES (new.rowid, new.conteudo);
END;
