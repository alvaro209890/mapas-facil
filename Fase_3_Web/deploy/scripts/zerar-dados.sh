#!/usr/bin/env bash
# Zera os dados do app web (contas, projetos, importações, versões e uploads), com backup
# consistente antes. O schema é recriado pelas migrações no boot seguinte.
#
# Uso (no server):  bash Fase_3_Web/deploy/scripts/zerar-dados.sh
#
# O que NÃO é apagado: `dados/logs/` (log de operação), o backup gerado e o código.
# O que é apagado: `dados/projetos/*`, `dados/uploads/*` e o SQLite do app.
#
# Restaurar um backup: parar o serviço, `tar xzf <backup> -C /home/server/mapasfacil`
# e subir de novo — o tar contém a pasta `dados/` inteira.
set -euo pipefail

BASE="${MF_RAIZ:-/home/server/mapasfacil}"
DADOS="$BASE/dados"
BACKUPS="$BASE/backups"
CARIMBO="$(date +%Y%m%d-%H%M%S)"
ALVO="$BACKUPS/zeragem-$CARIMBO.tar.gz"
SERVICO="mapasfacil-app.service"
SAUDE="http://127.0.0.1:3130/api/v1/saude"

subiu=0
subir() {
  if [ "$subiu" = "0" ]; then
    systemctl --user start "$SERVICO" || true
    subiu=1
  fi
}
trap subir EXIT

echo "== antes =="
sqlite3 "$DADOS/mapasfacil.sqlite" \
  "select 'usuarios='||count(*) from usuarios; select 'projetos='||count(*) from projetos;" 2>/dev/null || true

echo "== backup =="
mkdir -p "$BACKUPS"
systemctl --user stop "$SERVICO" || true
tar czf "$ALVO" -C "$BASE" dados
echo "   $ALVO ($(du -h "$ALVO" | cut -f1))"

echo "== zerando =="
rm -rf "$DADOS/projetos"/* "$DADOS/uploads"/*
rm -f "$DADOS/mapasfacil.sqlite" "$DADOS/mapasfacil.sqlite-wal" "$DADOS/mapasfacil.sqlite-shm"

echo "== subindo =="
subir
for _ in $(seq 1 30); do
  if curl -sf -m 2 "$SAUDE" >/dev/null; then break; fi
  sleep 1
done
curl -s -m 10 "$SAUDE"; echo

echo "== depois =="
sqlite3 "$DADOS/mapasfacil.sqlite" \
  "select 'usuarios='||count(*) from usuarios; select 'projetos='||count(*) from projetos; select 'schema='||max(versao) from schema_version;"
echo "   projetos em disco: $(find "$DADOS/projetos" -mindepth 1 -maxdepth 1 | wc -l)"
echo "   uploads em disco:  $(find "$DADOS/uploads" -mindepth 1 -maxdepth 1 | wc -l)"
echo "OK: banco virgem; backup em $ALVO"
