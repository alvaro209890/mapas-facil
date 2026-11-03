#!/bin/bash
# Smoke ponta a ponta do app no server (anel 3), sem SPA.
#
# Percorre o caminho do usuário real por HTTP: cadastro -> login -> projeto -> upload do
# `.zip` sintético -> importação -> "faz a dinâmica" no chat -> PDF gerado e baixado.
# Não imprime segredo nem valor de senha; o CSRF só aparece truncado.
#
# Uso:  smoke_e2e.sh [http://127.0.0.1:3130] [caminho/do/zip]
#
# Pré-requisitos (no server): app de pé, `$B` respondendo, o zip sintético gerado por
# `Fase_3_Web/fixtures/gerar_zip_sintetico.py --destino <zip>`.
set -u

B="${1:-http://127.0.0.1:3130}/api/v1"
ZIP="${2:-/tmp/e2e.zip}"
J="$(mktemp)"; trap 'rm -f "$J"' EXIT
umask 077

falhou() { echo "FALHOU: $*" >&2; exit 1; }
campo() { python3 -c "import json,sys;d=json.load(open('$1'));print($2)" 2>/dev/null; }

EMAIL="smoke$(date +%s)@teste.local"; SENHA='Forte#2026abc'

echo "== 1. cadastro"
codigo=$(curl -s -o /tmp/mf_r1.json -w '%{http_code}' -X POST "$B/auth/cadastrar" \
  -H 'Content-Type: application/json' \
  -d "{\"nome\":\"Smoke\",\"email\":\"$EMAIL\",\"senha\":\"$SENHA\"}")
echo "   http $codigo"
[ "$codigo" = "201" ] || { cat /tmp/mf_r1.json; falhou "cadastro"; }

echo "== 2. login"
codigo=$(curl -s -c "$J" -o /tmp/mf_r2.json -w '%{http_code}' -X POST "$B/auth/entrar" \
  -H 'Content-Type: application/json' -d "{\"email\":\"$EMAIL\",\"senha\":\"$SENHA\"}")
CSRF=$(campo /tmp/mf_r2.json "d['csrf']")
echo "   http $codigo · csrf ${CSRF:0:6}… (${#CSRF} chars) · cookie $(grep -c mf_sessao "$J") linha"
[ "$codigo" = "200" ] && [ -n "$CSRF" ] || { cat /tmp/mf_r2.json; falhou "login"; }

echo "== 3. projeto"
codigo=$(curl -s -b "$J" -o /tmp/mf_r3.json -w '%{http_code}' -X POST "$B/projetos" \
  -H 'Content-Type: application/json' -H "X-MF-CSRF: $CSRF" \
  -d '{"nome":"Smoke E2E","folha":{"formato":"A4","orientacao":"retrato"}}')
PROJ=$(campo /tmp/mf_r3.json "d['projeto']['id']")
echo "   http $codigo · projeto $PROJ"
[ "$codigo" = "201" ] && [ -n "$PROJ" ] || { cat /tmp/mf_r3.json; falhou "projeto"; }

echo "== 4. upload ($(stat -c%s "$ZIP") bytes)"
TAM=$(stat -c%s "$ZIP")
codigo=$(curl -s -b "$J" -o /tmp/mf_r4.json -w '%{http_code}' -X POST "$B/uploads" \
  -H 'Content-Type: application/json' -H "X-MF-CSRF: $CSRF" \
  -d "{\"nome\":\"imovel_ficticio.zip\",\"tamanho\":$TAM}")
UP=$(campo /tmp/mf_r4.json "d['upload_id']")
echo "   criar http $codigo · upload $UP"
[ "$codigo" = "201" ] && [ -n "$UP" ] || { cat /tmp/mf_r4.json; falhou "criar upload"; }

# As partes são numeradas a partir de 0 (o `/estado` devolve `faltam: [0]`).
COD_PARTE=$(curl -s -b "$J" -o /dev/null -w '%{http_code}' -X PUT "$B/uploads/$UP/partes/0" \
  -H 'Content-Type: application/octet-stream' -H "X-MF-CSRF: $CSRF" \
  -H "X-Parte-SHA256: $(sha256sum "$ZIP" | cut -d' ' -f1)" --data-binary @"$ZIP")
# `hash_partes` = sha256 da concatenação dos hex das partes — o mesmo cálculo do navegador.
HP=$(python3 -c "import hashlib;print(hashlib.sha256(hashlib.sha256(open('$ZIP','rb').read()).hexdigest().encode('ascii')).hexdigest())")
COD_CONC=$(curl -s -b "$J" -o /tmp/mf_r5.json -w '%{http_code}' -X POST "$B/uploads/$UP/concluir" \
  -H 'Content-Type: application/json' -H "X-MF-CSRF: $CSRF" -d "{\"hash_partes\":\"$HP\"}")
echo "   parte http $COD_PARTE · concluir http $COD_CONC"
[ "$COD_PARTE" = "204" ] && [ "$COD_CONC" = "200" ] || { cat /tmp/mf_r5.json; falhou "upload"; }

echo "== 5. importação"
codigo=$(curl -s -b "$J" -o /tmp/mf_r6.json -w '%{http_code}' -X POST "$B/projetos/$PROJ/importacao" \
  -H 'Content-Type: application/json' -H "X-MF-CSRF: $CSRF" -d "{\"upload_id\":\"$UP\"}")
IMP=$(campo /tmp/mf_r6.json "d['importacao_id']")
echo "   http $codigo · importação $IMP"
[ "$codigo" = "202" ] && [ -n "$IMP" ] || { cat /tmp/mf_r6.json; falhou "importação"; }

for i in $(seq 1 40); do
  sleep 3
  curl -s -b "$J" -o /tmp/mf_r7.json "$B/importacoes/$IMP"
  EST=$(campo /tmp/mf_r7.json "d.get('estado','')")
  printf '   [%3ss] %s\n' "$((i * 3))" "$EST"
  case "$EST" in
    pronto|pronta|falhou|erro) break ;;
  esac
done
case "$EST" in
  pronto|pronta) echo "   resumo: $(campo /tmp/mf_r7.json "json.dumps(d.get('resumo'),ensure_ascii=False)[:300]")" ;;
  *) cat /tmp/mf_r7.json; falhou "importação terminou em '$EST'" ;;
esac

echo "== 6. chat: faz a dinâmica"
codigo=$(curl -s -b "$J" -o /tmp/mf_r8.json -w '%{http_code}' -X POST "$B/projetos/$PROJ/mensagens" \
  -H 'Content-Type: application/json' -H "X-MF-CSRF: $CSRF" \
  -d '{"texto":"Gera agora a dinâmica do imóvel para 2020 em A4 retrato. Não faça perguntas: gere o mapa."}')
echo "   http $codigo · $(head -c 200 /tmp/mf_r8.json)"
[ "$codigo" = "202" ] || falhou "chat"

echo "== 7. espera o PDF"
# A importação também deixa o projeto em `pronto`: o critério de fim do job é
# `versao_atual >= 1`, não o estado.
for i in $(seq 1 80); do
  sleep 3
  curl -s -b "$J" -o /tmp/mf_r9.json "$B/projetos/$PROJ"
  EST=$(campo /tmp/mf_r9.json "d['projeto']['estado']")
  VA=$(campo /tmp/mf_r9.json "d['projeto']['versao_atual']")
  printf '   [%3ss] estado=%s versao=%s
' "$((i * 3))" "$EST" "$VA"
  if [ "${VA:-0}" -ge 1 ]; then break; fi
  if [ "$EST" = "erro" ]; then cat /tmp/mf_r9.json; falhou "job terminou em erro"; fi
done
[ "${VA:-0}" -ge 1 ] || { cat /tmp/mf_r9.json; falhou "timeout esperando a versão 1"; }

echo "== 8. baixa o PDF"
CAMINHO=$(curl -s -b "$J" "$B/projetos/$PROJ/versoes" | python3 -c "
import json,sys
d=json.load(sys.stdin)
vs=d.get('versoes') or d.get('itens') or []
pdf=[v for v in vs if str(v.get('pdf','')).endswith('.pdf')] or vs
print(pdf[0].get('pdf') or pdf[0].get('caminho') or '')")
echo "   caminho: $CAMINHO"
[ -n "$CAMINHO" ] || falhou "não achei o PDF nas versões"
COD_PDF=$(curl -s -b "$J" -o /tmp/mf_smoke.pdf -w '%{http_code}' "$B/projetos/$PROJ/arquivos/$CAMINHO")
echo "   http $COD_PDF · $(stat -c%s /tmp/mf_smoke.pdf) bytes · $(head -c 5 /tmp/mf_smoke.pdf)"
[ "$COD_PDF" = "200" ] || falhou "download do PDF"

echo
echo "OK — projeto $PROJ, versão $VA, PDF em /tmp/mf_smoke.pdf"
