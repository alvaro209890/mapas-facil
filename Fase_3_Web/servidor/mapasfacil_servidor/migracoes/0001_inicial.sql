-- 0001_inicial.sql — schema base do servidor (W-03 §Banco, W-11 §Contas)
-- Tudo em UTC ISO-8601 com 'Z' na aplicação; o banco guarda texto comparável.

CREATE TABLE IF NOT EXISTS usuarios (
  id            TEXT PRIMARY KEY,
  email         TEXT NOT NULL UNIQUE COLLATE NOCASE,
  nome          TEXT NOT NULL,
  papel         TEXT NOT NULL CHECK (papel IN ('usuario','admin')),
  senha_hash    TEXT NOT NULL,
  trocar_senha  INTEGER NOT NULL DEFAULT 1,
  ativo         INTEGER NOT NULL DEFAULT 1,
  criado_em     TEXT NOT NULL,
  ultimo_acesso TEXT
);

CREATE TABLE IF NOT EXISTS sessoes (
  id_hash     TEXT PRIMARY KEY,
  usuario_id  TEXT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
  csrf        TEXT NOT NULL,
  criada_em   TEXT NOT NULL,
  expira_em   TEXT NOT NULL,
  ip_prefixo  TEXT,
  agente      TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessoes_usuario ON sessoes(usuario_id);

CREATE TABLE IF NOT EXISTS auditoria (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  em         TEXT NOT NULL,
  usuario_id TEXT,
  acao       TEXT NOT NULL,
  alvo       TEXT,
  detalhe    TEXT
);
CREATE INDEX IF NOT EXISTS idx_auditoria_em ON auditoria(em DESC);

CREATE TABLE IF NOT EXISTS projetos (
  id             TEXT PRIMARY KEY,
  usuario_id     TEXT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
  nome           TEXT NOT NULL,
  estado         TEXT NOT NULL CHECK (estado IN (
                   'aguardando_zip','importando','indexando','pronto',
                   'gerando','erro','lixeira')),
  folha_formato    TEXT NOT NULL CHECK (folha_formato IN ('A4','A3','A2','A1','A0')),
  folha_orientacao TEXT NOT NULL CHECK (folha_orientacao IN ('retrato','paisagem')),
  imovel_nome      TEXT,
  imovel_car       TEXT,
  imovel_municipio TEXT,
  imovel_uf        TEXT,
  versao_atual   INTEGER NOT NULL DEFAULT 0,
  miniatura      TEXT,
  erro_codigo    TEXT,
  criado_em      TEXT NOT NULL,
  atualizado_em  TEXT NOT NULL,
  apagado_em     TEXT
);
CREATE INDEX IF NOT EXISTS idx_projetos_usuario ON projetos(usuario_id, atualizado_em DESC);
CREATE INDEX IF NOT EXISTS idx_projetos_estado ON projetos(estado);

CREATE TABLE IF NOT EXISTS versoes (
  projeto_id  TEXT NOT NULL REFERENCES projetos(id) ON DELETE CASCADE,
  numero      INTEGER NOT NULL,
  pasta       TEXT NOT NULL,
  conforme    INTEGER NOT NULL DEFAULT 0,
  miniatura   TEXT,
  artefatos   TEXT NOT NULL DEFAULT '{}',
  validacao   TEXT NOT NULL DEFAULT '{}',
  criada_em   TEXT NOT NULL,
  PRIMARY KEY (projeto_id, numero)
);

CREATE TABLE IF NOT EXISTS importacoes (
  id          TEXT PRIMARY KEY,
  projeto_id  TEXT NOT NULL REFERENCES projetos(id) ON DELETE CASCADE,
  upload_id   TEXT,
  estado      TEXT NOT NULL CHECK (estado IN ('na_fila','rodando','pronto','erro')),
  fase        TEXT,
  resumo      TEXT,
  erro_codigo TEXT,
  criada_em   TEXT NOT NULL,
  fim_em      TEXT
);
CREATE INDEX IF NOT EXISTS idx_importacoes_projeto ON importacoes(projeto_id, criada_em DESC);
