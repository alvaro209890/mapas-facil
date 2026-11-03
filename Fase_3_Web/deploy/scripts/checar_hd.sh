#!/usr/bin/env bash
# Pré-requisito da unit do app: o HD Backup precisa estar montado antes de subir.
# Depois de um reboot o HD pode montar *depois* do login — por isso a unit tenta de novo
# em 30 s (RestartSec) em vez de subir com o diretório vazio e "perder" os projetos.
set -uo pipefail

MF_RAIZ="${MF_RAIZ:-/home/server/mapasfacil}"
HD="/media/server/HD Backup"

if ! mountpoint -q "$HD"; then
  echo "checar_hd: $HD não está montado — abortando para a unit tentar de novo em 30 s" >&2
  exit 1
fi

if [ ! -d "$MF_RAIZ/dados" ]; then
  echo "checar_hd: $MF_RAIZ/dados não existe (symlink quebrado?) — abortando" >&2
  exit 1
fi

# O fuseblk aceita tudo como 777; o teste que vale é escrita real no diretório de trabalho.
teste="$MF_RAIZ/dados/.checar_hd.$$"
if ! : >"$teste" 2>/dev/null; then
  echo "checar_hd: $MF_RAIZ/dados não aceita escrita (HD read-only?) — abortando" >&2
  exit 1
fi
rm -f "$teste"
exit 0
