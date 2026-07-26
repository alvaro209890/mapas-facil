-- DDL canônico das conversas (F1-17). Aplicado pela migração 001.
-- Não execute este arquivo sozinho em produção — use migracoes/001_inicial.sql.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_versao (
  versao INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS conversas (
  conversation_id        TEXT PRIMARY KEY,
  title                  TEXT NOT NULL,
  title_manual           INTEGER NOT NULL DEFAULT 0,
  created_at             TEXT NOT NULL,
  updated_at             TEXT NOT NULL,
  workspace_path         TEXT,
  workspace_fingerprint  TEXT NOT NULL,
  workspace_nome         TEXT,
  conta_id               TEXT,
  arquivada              INTEGER NOT NULL DEFAULT 0,
  parent_conversation_id TEXT REFERENCES conversas(conversation_id) ON DELETE SET NULL,
  parent_message_seq     INTEGER,
  compact_summary        TEXT,
  compact_ate_seq        INTEGER,
  modelo                 TEXT,
  tokens_entrada         INTEGER NOT NULL DEFAULT 0,
  tokens_saida           INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS mensagens (
  message_id      TEXT PRIMARY KEY,
  conversation_id TEXT NOT NULL REFERENCES conversas(conversation_id) ON DELETE CASCADE,
  seq             INTEGER NOT NULL,
  papel           TEXT NOT NULL CHECK (papel IN ('usuario','assistente','sistema','tool')),
  conteudo        TEXT NOT NULL,
  criado_em       TEXT NOT NULL,
  mapspec_id      TEXT,
  mapspec_versao  INTEGER,
  cancelada       INTEGER NOT NULL DEFAULT 0,
  UNIQUE (conversation_id, seq)
);

CREATE TABLE IF NOT EXISTS tool_traces (
  trace_id         TEXT PRIMARY KEY,
  conversation_id  TEXT NOT NULL REFERENCES conversas(conversation_id) ON DELETE CASCADE,
  message_id       TEXT REFERENCES mensagens(message_id) ON DELETE CASCADE,
  tool             TEXT NOT NULL,
  args_resumo      TEXT,
  resultado_resumo TEXT,
  ms               INTEGER,
  ok               INTEGER NOT NULL DEFAULT 1,
  erro_codigo      TEXT,
  criado_em        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversa_mapspecs (
  conversation_id TEXT NOT NULL REFERENCES conversas(conversation_id) ON DELETE CASCADE,
  mapspec_id      TEXT NOT NULL,
  versao          INTEGER NOT NULL,
  criado_em       TEXT NOT NULL,
  PRIMARY KEY (conversation_id, mapspec_id, versao)
);

CREATE TABLE IF NOT EXISTS anexos (
  anexo_id        TEXT PRIMARY KEY,
  conversation_id TEXT NOT NULL REFERENCES conversas(conversation_id) ON DELETE CASCADE,
  message_id      TEXT REFERENCES mensagens(message_id) ON DELETE CASCADE,
  caminho_local   TEXT NOT NULL,
  nome_original   TEXT NOT NULL,
  bytes           INTEGER NOT NULL,
  sha256          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_conversas_updated  ON conversas(arquivada, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversas_ws       ON conversas(workspace_fingerprint, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_mensagens_conv_seq ON mensagens(conversation_id, seq DESC);
CREATE INDEX IF NOT EXISTS idx_traces_conv        ON tool_traces(conversation_id, criado_em);

CREATE VIRTUAL TABLE IF NOT EXISTS mensagens_fts USING fts5(
  conteudo,
  content='mensagens',
  content_rowid='rowid',
  tokenize='unicode61 remove_diacritics 2'
);

CREATE TRIGGER IF NOT EXISTS mensagens_ai AFTER INSERT ON mensagens BEGIN
  INSERT INTO mensagens_fts(rowid, conteudo) VALUES (new.rowid, new.conteudo);
END;

CREATE TRIGGER IF NOT EXISTS mensagens_ad AFTER DELETE ON mensagens BEGIN
  INSERT INTO mensagens_fts(mensagens_fts, rowid, conteudo) VALUES ('delete', old.rowid, old.conteudo);
END;

CREATE TRIGGER IF NOT EXISTS mensagens_au AFTER UPDATE ON mensagens BEGIN
  INSERT INTO mensagens_fts(mensagens_fts, rowid, conteudo) VALUES ('delete', old.rowid, old.conteudo);
  INSERT INTO mensagens_fts(rowid, conteudo) VALUES (new.rowid, new.conteudo);
END;
