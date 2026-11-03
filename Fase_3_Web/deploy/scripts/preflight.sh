#!/usr/bin/env bash
# Preflight do Mapas Fácil — Fase 3 (W-12 §Preflight, tarefa W0-20).
#
# Somente leitura, exceto o symlink MF_RAIZ (criado se faltar — sem sudo).
# Imprime uma tabela OK/FALTA/AVISO e termina != 0 se faltar algo obrigatório.
# NUNCA imprime valor de segredo: das chaves só diz se existem.
#
# Uso:  bash Fase_3_Web/deploy/scripts/preflight.sh
#       bash preflight.sh --sem-rede     # pula as sondas de rede (9Router, geo)
#
# Roda no server-desktop como o usuário `server`. Não usa sudo em nada.

set -uo pipefail

MF_RAIZ_ESPERADA="${MF_RAIZ:-/home/server/mapasfacil}"
HD="/media/server/HD Backup"
IP_SERVER="100.65.138.58"
PORTA="${MF_PORTA:-3130}"
SOMA_REDE=1
for arg in "$@"; do
  case "$arg" in
    --sem-rede) SOMA_REDE=0 ;;
    -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
    *) echo "argumento desconhecido: $arg" >&2; exit 64 ;;
  esac
done

FALHAS=0
AVISOS=0
LINHAS=()

registrar() { # $1=estado  $2=item  $3=observação
  LINHAS+=("$(printf '%-6s %-28s %s' "$1" "$2" "${3:-}")")
  case "$1" in
    FALTA) FALHAS=$((FALHAS + 1)) ;;
    AVISO) AVISOS=$((AVISOS + 1)) ;;
  esac
}

# 1. Está no server-desktop? ------------------------------------------------
HOSTNAME_CURTO="$(hostname 2>/dev/null || echo '?')"
IP_TAIL="$(tailscale ip -4 2>/dev/null | head -1)"
if [ "$IP_TAIL" = "$IP_SERVER" ]; then
  registrar OK "host" "$HOSTNAME_CURTO · $IP_TAIL"
else
  registrar FALTA "host" "tailnet=$IP_TAIL (esperado $IP_SERVER) — este não é o server-desktop"
fi

# 2. HD montado? ------------------------------------------------------------
if mountpoint -q "$HD" 2>/dev/null; then
  registrar OK "HD de backup" "montado em $HD"
else
  registrar FALTA "HD de backup" "NÃO montado em $HD — pedir ao Álvaro"
fi

# 3. Espaço no HD (aviso abaixo de 200 GB) ----------------------------------
if mountpoint -q "$HD" 2>/dev/null; then
  LIVRE_GB="$(df -BG --output=avail "$HD" 2>/dev/null | tail -1 | tr -dc '0-9')"
  if [ -n "${LIVRE_GB:-}" ] && [ "$LIVRE_GB" -ge 200 ]; then
    registrar OK "espaço no HD" "${LIVRE_GB} GB livres"
  else
    registrar AVISO "espaço no HD" "${LIVRE_GB:-?} GB livres (alvo: ≥ 200 GB)"
  fi
fi

# 4. Symlink MF_RAIZ ---------------------------------------------------------
DESTINO_ESPERADO="$HD/Servidores_NAO_MEXA/mapasfacil"
if [ -L "$MF_RAIZ_ESPERADA" ]; then
  ALVO="$(readlink -f "$MF_RAIZ_ESPERADA")"
  case "$ALVO" in
    "$HD"/*) registrar OK "MF_RAIZ" "$MF_RAIZ_ESPERADA → $ALVO" ;;
    *) registrar FALTA "MF_RAIZ" "aponta para $ALVO (deveria estar no HD)" ;;
  esac
elif [ -e "$MF_RAIZ_ESPERADA" ]; then
  registrar FALTA "MF_RAIZ" "existe como pasta, não como symlink — mover para o HD"
elif mountpoint -q "$HD" 2>/dev/null; then
  mkdir -p "$DESTINO_ESPERADO" 2>/dev/null &&
    ln -sfn "$DESTINO_ESPERADO" "$MF_RAIZ_ESPERADA" 2>/dev/null &&
    registrar OK "MF_RAIZ" "symlink criado → $DESTINO_ESPERADO" ||
    registrar FALTA "MF_RAIZ" "não consegui criar o symlink $MF_RAIZ_ESPERADA"
else
  registrar FALTA "MF_RAIZ" "nem pasta nem symlink (o HD não está montado)"
fi

# 5. Porta 3130 livre --------------------------------------------------------
if ss -tln 2>/dev/null | awk '{print $4}' | grep -q ":$PORTA\$"; then
  DONO="$(ss -tlnp 2>/dev/null | awk -v p=":$PORTA" '$4 ~ p {print $6; exit}')"
  registrar FALTA "porta $PORTA" "ocupada ${DONO:-(sem permissão de ver o dono)} — escolher outra e atualizar o vault"
else
  registrar OK "porta $PORTA" "livre"
fi

# 6. Python 3.12 + venv ------------------------------------------------------
if command -v python3.12 >/dev/null 2>&1; then
  registrar OK "python3.12" "$(python3.12 -V 2>&1)"
else
  registrar FALTA "python3.12" "pedir: sudo apt install python3.12 python3.12-venv"
fi
if python3 -m venv --help >/dev/null 2>&1; then
  registrar OK "venv" "disponível"
else
  registrar FALTA "venv" "pedir: sudo apt install python3.12-venv"
fi

# 7. GDAL (ogr2ogr) ----------------------------------------------------------
if command -v ogr2ogr >/dev/null 2>&1; then
  registrar OK "ogr2ogr" "$(ogr2ogr --version 2>&1 | head -1)"
else
  registrar FALTA "ogr2ogr" "pedir: sudo apt install gdal-bin"
fi

# 8. Fontes ------------------------------------------------------------------
# ⚠️ `fc-list | grep -q` mente sob `pipefail`: o `grep -q` sai no primeiro acerto, o `fc-list`
# morre com SIGPIPE (141) e a pipeline inteira é "falha". Já deu falso negativo com as fontes
# instaladas. `fc-match` imprime uma linha só e não tem esse problema.
if fc-match "Liberation Sans" 2>/dev/null | grep -qi "^Liberation"; then
  registrar OK "fonte Liberation" "instalada ($(fc-match -f '%{family}' 'Liberation Sans'))"
else
  registrar FALTA "fonte Liberation" "pedir: sudo apt install fonts-liberation"
fi

# 9. Node 22 -----------------------------------------------------------------
if command -v node >/dev/null 2>&1; then
  NODE_V="$(node --version 2>&1)"
  case "$NODE_V" in
    v2[2-9]*) registrar OK "node" "$NODE_V" ;;
    *) registrar AVISO "node" "$NODE_V (alvo: ≥ 22)" ;;
  esac
else
  registrar AVISO "node" "ausente — necessário só para buildar o SPA"
fi

# 10. linger (units --user sobem sem login) ---------------------------------
LINGER="$(loginctl show-user "$(id -un)" -p Linger --value 2>/dev/null)"
if [ "$LINGER" = "yes" ]; then
  registrar OK "loginctl linger" "Linger=yes"
else
  registrar FALTA "loginctl linger" "pedir: sudo loginctl enable-linger $(id -un)"
fi

# 11. cloudflared ------------------------------------------------------------
if command -v cloudflared >/dev/null 2>&1; then
  registrar OK "cloudflared" "$(cloudflared --version 2>&1 | head -1)"
else
  registrar FALTA "cloudflared" "pedir instalação (túnel mapasfacil-app)"
fi

# 12. Segredos (só nomes, nunca valores) ------------------------------------
SEGREDOS="${MF_SEGREDOS:-$MF_RAIZ_ESPERADA/segredos/servidor.env}"
if [ -f "$SEGREDOS" ]; then
  # `-L` porque, quando o `MF_RAIZ` é NTFS (`fuseblk`), o arquivo real mora no ext4 e o caminho
  # dentro do projeto é symlink: `stat` sem `-L` lê 777 do link, não o 600 do destino.
  MODO="$(stat -Lc '%a' "$SEGREDOS" 2>/dev/null)"
  if [ "$MODO" = "600" ]; then
    registrar OK "servidor.env" "$SEGREDOS (0600)"
  else
    registrar FALTA "servidor.env" "modo $MODO (precisa 600) — pedir ao Álvaro: chmod 600"
  fi
  FALTANDO=""
  for chave in MAPASFACIL_PROVEDOR_CHAVE MAPASFACIL_SEMA_AUTHKEY MAPASFACIL_PLANET_API_KEY; do
    grep -q "^${chave}=" "$SEGREDOS" || FALTANDO="$FALTANDO $chave"
  done
  if [ -n "$FALTANDO" ]; then
    registrar FALTA "chaves do servidor.env" "faltam:$FALTANDO (pedir ao Álvaro)"
  else
    registrar OK "chaves do servidor.env" "as 3 presentes"
  fi
else
  registrar FALTA "servidor.env" "não existe em $SEGREDOS — pedir ao Álvaro"
fi

# 13/14. Sondas de rede ------------------------------------------------------
if [ "$SOMA_REDE" -eq 1 ]; then
  CHAVE=""
  if [ -f "$SEGREDOS" ]; then
    CHAVE="$(grep -m1 '^MAPASFACIL_PROVEDOR_CHAVE=' "$SEGREDOS" 2>/dev/null | cut -d= -f2-)"
  fi
  if [ -n "$CHAVE" ]; then
    MODS="$(curl -sS -m 15 -H "Authorization: Bearer $CHAVE" \
      "${MAPASFACIL_PROVEDOR_URL:-http://100.104.255.35:20128/v1}/models" 2>/dev/null)"
    if printf '%s' "$MODS" | grep -q 'ag/gemini-3.8-flash-high'; then
      registrar OK "9Router (IA)" "ag/gemini-3.8-flash-high disponível"
    else
      registrar FALTA "9Router (IA)" "não listou ag/gemini-3.8-flash-high — VPS fora ou chave errada"
    fi
    unset CHAVE MODS
  else
    registrar AVISO "9Router (IA)" "sem chave para sonda (servidor.env)"
  fi

  COD_WMS="$(curl -s -o /dev/null -m 15 -w '%{http_code}' \
    'https://wms.cursar.space/geoserver/cbers/wms?service=WMS&request=GetCapabilities' 2>/dev/null)"
  case "$COD_WMS" in
    200) registrar OK "WMS da IMAP" "GetCapabilities 200" ;;
    *) registrar AVISO "WMS da IMAP" "HTTP ${COD_WMS:-sem resposta}" ;;
  esac

  COD_SEMA="$(curl -s -o /dev/null -m 15 -w '%{http_code}' \
    'https://geo.sema.mt.gov.br/geoserver/ows?service=WFS&request=GetCapabilities' 2>/dev/null)"
  case "$COD_SEMA" in
    200|401|403) registrar OK "SEMA GeoServer" "responde (HTTP $COD_SEMA; chave só no WFS autenticado)" ;;
    000|"") registrar AVISO "SEMA GeoServer" "sem resposta — conferir DNS/bloqueio de IP (planos/03)" ;;
    *) registrar AVISO "SEMA GeoServer" "HTTP $COD_SEMA" ;;
  esac
fi

# 12. Peças de deploy (W12) ---------------------------------------------------
# Onde está o código: no server ele mora em `$MF_RAIZ/codigo`; rodando do clone local, ao lado
# do script. O preflight roda nos dois lugares e não pode confundir "não publicado ainda" com
# "arquivo faltando".
CODIGO_DIR="${MF_CODIGO:-}"
if [ -z "$CODIGO_DIR" ] || [ ! -d "$CODIGO_DIR" ]; then
  if [ -d "${MF_RAIZ:-$MF_RAIZ_ESPERADA}/codigo/Fase_3_Web" ]; then
    CODIGO_DIR="${MF_RAIZ:-$MF_RAIZ_ESPERADA}/codigo"
  else
    VIZINHO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." 2>/dev/null && pwd)"
    if [ -d "$VIZINHO/servidor" ]; then
      CODIGO_DIR="$VIZINHO"
    else
      CODIGO_DIR=""
    fi
  fi
fi
LOCK="$CODIGO_DIR/servidor/requirements.lock"
if [ -z "$CODIGO_DIR" ] || [ ! -d "$CODIGO_DIR/servidor" ]; then
  registrar AVISO "código publicado" "não achei o código nesta máquina (esperado em ${MF_RAIZ:-$MF_RAIZ_ESPERADA}/codigo) — primeiro deploy ainda não aconteceu"
fi
if [ -z "$CODIGO_DIR" ] || [ ! -d "$CODIGO_DIR/servidor" ]; then
  : # já avisado acima; não cobra o lock de um código que não está aqui
elif [ -f "$LOCK" ]; then
  # Toda linha `pacote==versao` precisa de ao menos um `--hash=sha256:` depois dela.
  FALTA_HASH="$(awk '/^[A-Za-z0-9_.-]+==/ {if (anterior != "" && !tem) print anterior; anterior=$1; tem=0; next} /--hash=sha256:/ {tem=1} END {if (anterior != "" && !tem) print anterior}' "$LOCK")"
  if [ -n "$FALTA_HASH" ]; then
    registrar FALTA "requirements.lock" "sem hash em: $(echo "$FALTA_HASH" | tr '
' ' ')"
  else
    registrar OK "requirements.lock" "$(grep -cE '^[A-Za-z0-9_.-]+==' "$LOCK") pacotes, todos com hash"
  fi
else
  registrar FALTA "requirements.lock" "ausente — sem ele o deploy não é reprodutível"
fi

WEB_DIR="${CODIGO_DIR%/}/web"
# `CODIGO_DIR` é a raiz do código (`<mf>/codigo`), com `servidor/` e `web/` dentro.
if [ -d "$WEB_DIR" ]; then
  if [ -f "$WEB_DIR/pnpm-lock.yaml" ] && ! command -v pnpm >/dev/null 2>&1; then
    registrar AVISO "gerenciador do SPA" "o repo usa pnpm-lock.yaml e o pnpm não está no PATH (corepack enable resolve)"
  elif [ -f "$WEB_DIR/pnpm-lock.yaml" ] || [ -f "$WEB_DIR/package-lock.json" ]; then
    registrar OK "gerenciador do SPA" "lockfile presente"
  else
    registrar FALTA "gerenciador do SPA" "sem lockfile em web/ — build não reprodutível"
  fi
fi

RELEASES="${MF_RAIZ:-$MF_RAIZ_ESPERADA}/releases/atual"
if [ -e "$RELEASES" ]; then
  registrar OK "releases/atual" "-> $(readlink -f "$RELEASES" 2>/dev/null | sed "s|${MF_RAIZ:-$MF_RAIZ_ESPERADA}/releases/||")"
else
  registrar AVISO "releases/atual" "ainda não existe (primeiro deploy cria)"
fi

# Saída ----------------------------------------------------------------------
echo
echo "Mapas Fácil — preflight da Fase 3 ($(date '+%Y-%m-%d %H:%M %Z'))"
echo "servidor: $HOSTNAME_CURTO · MF_RAIZ=$MF_RAIZ_ESPERADA · porta=$PORTA"
echo "--------------------------------------------------------------------------"
printf '%s\n' "${LINHAS[@]}"
echo "--------------------------------------------------------------------------"
echo "falhas: $FALHAS · avisos: $AVISOS"

if [ "$FALHAS" -gt 0 ]; then
  echo "RESULTADO: FALTA algo obrigatório — resolver antes de subir o app."
  exit 1
fi
echo "RESULTADO: OK para seguir."
exit 0
