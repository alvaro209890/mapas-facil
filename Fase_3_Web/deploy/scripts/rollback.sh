#!/usr/bin/env bash
# Volta para a tag anterior SEM desfazer migração.
#
# Regra da Fase 3: as migrações do banco são só aditivas, então código antigo roda sobre banco
# novo. Desfazer migração não existe aqui de propósito — o backup do deploy cobre o resto.
#
#   ./rollback.sh web-v0.0.9
set -euo pipefail

TAG="${1:-}"
BASE="${MF_RAIZ:-/home/server/mapasfacil}"
CODIGO="$BASE/codigo"
VENV="$BASE/venv"

if [ -z "$TAG" ]; then
  echo "uso: $0 <tag-anterior>" >&2
  exit 2
fi

if [ ! -d "$BASE/releases/$TAG/web-dist" ]; then
  echo "não existe build de $TAG em releases/$TAG/web-dist — rode o atualizar.sh dessa tag antes" >&2
  exit 1
fi

echo "== tag $TAG"
git -C "$CODIGO" checkout --detach "$TAG"
"$VENV/bin/pip" install --quiet --require-hashes -r "$CODIGO/Fase_3_Web/servidor/requirements.lock"
"$VENV/bin/pip" install --quiet --no-deps -e "$CODIGO/Fase_1_Desktop/nucleo" -e "$CODIGO/Fase_3_Web/servidor"

echo "== symlink e restart"
ln -sfn "$BASE/releases/$TAG/web-dist" "$BASE/releases/atual"
systemctl --user restart mapasfacil-app
sleep 3

saude="$(curl -fsS --max-time 10 http://127.0.0.1:3130/api/v1/saude)"
echo "$saude" | head -c 400; echo
printf '%s' "$saude" | grep -q "\"versao\": *\"$TAG\"" || {
  echo "rollback NÃO confirmou $TAG — investigar agora (logs/servidor.log)" >&2
  exit 1
}
echo "OK: de volta em $TAG"
