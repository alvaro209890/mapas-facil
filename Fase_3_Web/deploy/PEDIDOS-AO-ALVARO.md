# Pedidos ao Álvaro — o que só ele pode fazer no server

*(autor: Hermes-windows/default | 2026-11-03 — W12-05)*

Tudo aqui exige **sudo** no `server-desktop`, **login na Cloudflare** ou **um valor de segredo**.
O agente não tem nenhum dos três. Cada bloco é para copiar e colar; nada aqui imprime segredo.

Medido no server em 2026-11-03 pelo `deploy/scripts/preflight.sh`:

| Item | Estado |
|---|---|
| `fonts-liberation` | ✅ instalada (o check antigo dava falso negativo — corrigido) |
| `loginctl enable-linger server` | ✅ `Linger=yes` |
| `cloudflared` | ✅ 2026.1.1 |
| Python 3.12.3 / GDAL 3.8.4 / node v22.23.1 | ✅ |
| `segredos/servidor.env` | ✅ existe, `0600` (symlink → ext4) |
| 9Router `ag/gemini-3.8-flash-high` | ✅ responde |
| WMS da IMAP | ✅ `GetCapabilities` 200 |
| **Chaves `MAPASFACIL_SEMA_AUTHKEY` e `MAPASFACIL_PLANET_API_KEY`** | ❌ **faltam** |

## 1. As duas chaves geo (bloqueia camada autenticada da SEMA e mosaico Planet)

Não existem em nenhum cofre da frota — nem no do server, nem no deste Windows. Sem elas o app
**sobe** e gera mapa com as camadas locais; ficam de fora o WFS autenticado da SEMA e o WMTS da
Planet.

Me manda os dois valores por um canal que você preferir; eu escrevo direto em
`/home/server/segredos-mapasfacil/servidor.env` (600, fora do git) **sem imprimir** em terminal,
log, relatório, commit ou chat. Se preferir fazer você mesmo:

```bash
# como usuário `server`, no server
umask 077
printf 'MAPASFACIL_SEMA_AUTHKEY=%s\n' 'COLE_AQUI' >> /home/server/segredos-mapasfacil/servidor.env
printf 'MAPASFACIL_PLANET_API_KEY=%s\n' 'COLE_AQUI' >> /home/server/segredos-mapasfacil/servidor.env
chmod 600 /home/server/segredos-mapasfacil/servidor.env
```

## 2. Túnel e DNS do `mapasfacil-app` (bloqueia o site no ar)

O túnel é **novo e só deste app** — não reaproveita nem edita túnel de outro serviço da frota.

```bash
# como usuário `server`, no server — pede login na Cloudflare pelo navegador
cloudflared tunnel create mapasfacil-app
# anote o UUID que ele imprime (vai no yml e no nome do JSON de credencial)

cloudflared tunnel route dns mapasfacil-app mapasfacil-app.cursar.space
```

Depois, com o UUID em mãos:

```bash
cp /home/server/mapasfacil/codigo/Fase_3_Web/deploy/mapasfacil-app-tunnel.yml.example \
   /home/server/.cloudflared/mapasfacil-app.yml
# edite o yml e troque os DOIS <UUID-do-tunel-mapasfacil-app> pelo id acima
chmod 600 /home/server/.cloudflared/mapasfacil-app.yml
```

O `mapasfacil-app-tunnel.service` do repo já sobe com esse yml.

## 3. `analises.cursar.space` (W12-08) — decisão sua de quando

Você já decidiu que não usa mais. O desligamento é em duas partes:

```bash
# no ACER (o túnel da landing mora lá): tira só a entrada `analises` do ingress
# e reinicia o túnel; conferir depois que a landing continua de pé:
curl -s -o /dev/null -w '%{http_code}\n' https://mapasfacil.cursar.space
```

E na Cloudflare: apagar o registro DNS `analises`. **As análises publicadas lá não são apagadas**
sem você dizer onde guardar — isso eu não toco.

## 4. Ordem sugerida

1. As duas chaves (item 1) — libera o preflight por inteiro.
2. Túnel + DNS (item 2) — libera o `mapasfacil-app.cursar.space`.
3. Eu faço o primeiro deploy por tag (`atualizar.sh web-v0.1.0`), o smoke e o registro no vault.
4. Piloto com 3 pessoas do escritório (item depois do deploy).
5. `analises` (item 3), quando você quiser — não bloqueia nada.
