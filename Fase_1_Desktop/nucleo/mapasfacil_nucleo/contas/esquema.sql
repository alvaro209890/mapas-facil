-- Esquema canônico de contas locais (F1-14 / M5). A fonte aplicada
-- no boot é migracoes/001_inicial.sql.

CREATE TABLE IF NOT EXISTS schema_versao (
  versao INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS contas (
  id              TEXT PRIMARY KEY,
  email           TEXT NOT NULL COLLATE NOCASE UNIQUE,
  nome            TEXT,
  senha_hash      TEXT NOT NULL,
  criado_em       TEXT NOT NULL,
  ultimo_login_em TEXT,
  ativa           INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS sessoes_locais (
  id                 TEXT PRIMARY KEY,
  conta_id           TEXT NOT NULL REFERENCES contas(id) ON DELETE CASCADE,
  criada_em          TEXT NOT NULL,
  expira_em          TEXT,
  lembrar_neste_pc   INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_sessoes_conta ON sessoes_locais(conta_id);
