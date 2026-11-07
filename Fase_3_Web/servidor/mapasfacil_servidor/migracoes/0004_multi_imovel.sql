-- 0004_multi_imovel.sql — suporte aditivo a múltiplos imóveis por projeto (multi-imóvel)
-- Preserva integralmente contas, projetos e versões anteriores.

CREATE TABLE IF NOT EXISTS imoveis_projeto (
  id            TEXT PRIMARY KEY,
  projeto_id    TEXT NOT NULL REFERENCES projetos(id) ON DELETE CASCADE,
  imovel_id     TEXT NOT NULL,
  nome          TEXT NOT NULL,
  car           TEXT,
  matricula     TEXT,
  area_ha       REAL,
  atp_fonte     TEXT,
  principal     INTEGER NOT NULL DEFAULT 0,
  criado_em     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_imoveis_projeto_proj ON imoveis_projeto(projeto_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_imoveis_projeto_unique ON imoveis_projeto(projeto_id, imovel_id);

-- Backfill aditivo: projetos existentes com dados de imóvel ganham 1 registro em imoveis_projeto
-- sem inventar matrículas, áreas ou ATP não documentados.
INSERT OR IGNORE INTO imoveis_projeto (
  id,
  projeto_id,
  imovel_id,
  nome,
  car,
  matricula,
  area_ha,
  atp_fonte,
  principal,
  criado_em
)
SELECT
  p.id || '_principal',
  p.id,
  'imovel_principal',
  COALESCE(NULLIF(p.imovel_nome, ''), p.nome),
  p.imovel_car,
  NULL,
  NULL,
  NULL,
  1,
  p.criado_em
FROM projetos p
WHERE (p.imovel_nome IS NOT NULL AND p.imovel_nome != '')
   OR (p.imovel_car IS NOT NULL AND p.imovel_car != '');
