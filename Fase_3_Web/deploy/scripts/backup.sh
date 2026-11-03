#!/usr/bin/env bash
# Backup diário: `mapasfacil.sqlite` + o `chats.sqlite` de cada projeto ativo.
#
# Usa `sqlite3 .backup` (cópia consistente com o WAL, sem parar o app). Retenção de 14 dias.
# Decisão P7 (03/11/2026): as pastas de projeto ficam SÓ no HD do server — o backup do banco
# mora no mesmo HD, então isto protege contra corrupção/erro de operador, não contra falha física.
set -uo pipefail

BASE="${MF_RAIZ:-/home/server/mapasfacil}"
DADOS="$BASE/dados"
BACKUPS="${MF_BACKUPS:-$BASE/backups}"
DIAS="${MF_BACKUP_DIAS:-14}"
SILENCIOSO=0
[ "${1:-}" = "--silencioso" ] && SILENCIOSO=1

log() { [ "$SILENCIOSO" = "1" ] || echo "$@"; }
erro() { echo "$@" >&2; }

mkdir -p "$BACKUPS" || { erro "não consegui criar $BACKUPS"; exit 1; }
STAMP="$(date +%Y%m%d-%H%M%S)"
FALHAS=0

_backup_sqlite() {
  local origem="$1" rotulo="$2"
  [ -f "$origem" ] || return 0
  local destino="$BACKUPS/${rotulo}-${STAMP}.sqlite"
  if sqlite3 "$origem" ".backup '$destino'" 2>/dev/null; then
    log "ok   $rotulo -> $(basename "$destino") ($(du -h "$destino" | cut -f1))"
  else
    erro "FALHA $rotulo ($origem)"
    FALHAS=$((FALHAS + 1))
  fi
}

# Banco central (contas, projetos, versões, eventos).
_backup_sqlite "$DADOS/mapasfacil.sqlite" "mapasfacil"

# Um chat por projeto: projetos/<id>/chats.sqlite
if [ -d "$DADOS/projetos" ]; then
  for chat in "$DADOS/projetos"/*/chats.sqlite; do
    [ -f "$chat" ] || continue
    projeto="$(basename "$(dirname "$chat")")"
    _backup_sqlite "$chat" "chat-${projeto}"
  done
fi

# Retenção por idade — só nos arquivos que este script cria.
find "$BACKUPS" -maxdepth 1 -name 'mapasfacil-*.sqlite' -mtime "+$DIAS" -delete 2>/dev/null
find "$BACKUPS" -maxdepth 1 -name 'chat-*.sqlite' -mtime "+$DIAS" -delete 2>/dev/null

if [ "$FALHAS" -gt 0 ]; then
  erro "backup terminou com $FALHAS falha(s)"
  exit 1
fi
log "backup ok em $BACKUPS (retenção ${DIAS} dias)"
