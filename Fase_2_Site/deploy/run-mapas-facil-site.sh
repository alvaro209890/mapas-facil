#!/usr/bin/env bash
set -euo pipefail

export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
# shellcheck disable=SC1091
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
nvm use 22 >/dev/null

SITE_DIR="$HOME/Documentos/Mapas_Facil/Fase_2_Site/web"
cd "$SITE_DIR"

export PORT=3080
export HOSTNAME=127.0.0.1

NODE_BIN="$(command -v node)"
VINEXT_BIN="$SITE_DIR/node_modules/.bin/vinext"

if [[ ! -x "$VINEXT_BIN" ]]; then
  echo "vinext não encontrado em $VINEXT_BIN — rode npm install em $SITE_DIR" >&2
  exit 1
fi

if [[ ! -d "$SITE_DIR/dist" ]]; then
  echo "Build ausente; executando npm run build..." >&2
  npm run build
fi

exec "$NODE_BIN" "$VINEXT_BIN" start -p 3080 -H 127.0.0.1
