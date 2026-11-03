#!/usr/bin/env bash
# Deploy do Mapas Fácil por TAG: nada de auto-pull de `main` (lição do incidente do GeoForest).
#
#   ./atualizar.sh web-v0.1.0
#
# Ordem: preflight → tag → dependências → backup do banco → migrações → SPA → symlink `atual`
# → restart → smoke. Qualquer passo que falhe ABORTA antes do restart (o app antigo continua no ar).
set -euo pipefail

TAG="${1:-}"
BASE="${MF_RAIZ:-/home/server/mapasfacil}"
CODIGO="$BASE/codigo"
VENV="$BASE/venv"
DEPLOY="$CODIGO/Fase_3_Web/deploy"

if [ -z "$TAG" ]; then
  echo "uso: $0 <tag>   (ex.: $0 web-v0.1.0)" >&2
  exit 2
fi

echo "== 1/8 preflight"
bash "$DEPLOY/scripts/preflight.sh" || {
  echo "preflight reprovou — corrija antes de publicar" >&2
  exit 1
}

echo "== 2/8 tag $TAG"
git -C "$CODIGO" fetch --tags --prune
if ! git -C "$CODIGO" rev-parse --verify --quiet "refs/tags/$TAG" >/dev/null; then
  echo "tag $TAG não existe no repositório" >&2
  exit 1
fi
git -C "$CODIGO" checkout --detach "$TAG"

echo "== 3/8 dependências"
"$VENV/bin/pip" install --quiet --require-hashes -r "$CODIGO/Fase_3_Web/servidor/requirements.lock"
"$VENV/bin/pip" install --quiet --no-deps -e "$CODIGO/Fase_1_Desktop/nucleo" -e "$CODIGO/Fase_3_Web/servidor"

echo "== 4/8 backup do banco antes da migração"
bash "$DEPLOY/scripts/backup.sh" --silencioso

echo "== 5/8 migrações"
"$VENV/bin/python" -m mapasfacil_servidor migrar

echo "== 6/8 build do SPA"
(
  cd "$CODIGO/Fase_3_Web/web"
  # O repo versiona pnpm-lock.yaml (não package-lock.json): o gerenciador tem de ser o pnpm,
  # senão o `npm ci` recusa ou instala árvore diferente da conferida.
  if [ -f pnpm-lock.yaml ] && command -v pnpm >/dev/null 2>&1; then
    pnpm install --frozen-lockfile --silent
    pnpm run build --silent
  elif [ -f package-lock.json ]; then
    npm ci --silent
    npm run build --silent
  else
    echo "sem lockfile em $PWD — recusando build não reprodutível" >&2
    exit 1
  fi
)
DEST="$BASE/releases/$TAG/web-dist"
mkdir -p "$DEST"
rm -rf "$DEST"/*
cp -a "$CODIGO/Fase_3_Web/web/dist/." "$DEST/"

echo "== 7/8 symlink e restart"
ln -sfn "$DEST" "$BASE/releases/atual"
systemctl --user restart mapasfacil-app
sleep 3

echo "== 8/8 smoke"
saude="$(curl -fsS --max-time 10 http://127.0.0.1:3130/api/v1/saude)"
echo "$saude" | head -c 400; echo
if ! printf '%s' "$saude" | grep -q "\"versao\": *\"$TAG\""; then
  echo "smoke falhou: /saude não reporta versao=$TAG — rode o rollback" >&2
  exit 1
fi
printf '%s' "$saude" | grep -q '"spa": *true' || {
  echo "aviso: /saude não confirma a SPA — conferir dist/" >&2
}

echo "OK: $TAG no ar em 127.0.0.1:3130 (releases/atual -> $DEST)"
echo "Registre no vault (02-projetos/mapas-facil.md) e no 06-changelog.md."
