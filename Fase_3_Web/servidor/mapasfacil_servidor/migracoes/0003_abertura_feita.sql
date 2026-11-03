-- 0003_abertura_feita.sql (W5-22 / D41)
-- Marca se o turno de abertura automática já foi disparado para esta importação.
ALTER TABLE importacoes ADD COLUMN abertura_feita INTEGER NOT NULL DEFAULT 0;
