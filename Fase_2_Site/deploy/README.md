# Deploy do site Mapas Fácil neste PC

Produção local + Cloudflare Tunnel dedicado → `https://mapasfacil.cursar.space`.

## Serviços systemd (user)

| Unidade | Função |
|---|---|
| `mapas-facil-site.service` | vinext em `127.0.0.1:3080` — site de download |
| `mapas-facil-analises.service` | entrega das análises em `127.0.0.1:3081` — `servidor_analises.py` |
| `mapas-facil-tunnel.service` | tunnel dedicado `mapasfacil` (serve os dois hostnames) |

| Hostname | Aponta para | Doc |
|---|---|---|
| `mapasfacil.cursar.space` | site de download (3080) | [`../../docs/site-download-cloudflare.md`](../../docs/site-download-cloudflare.md) |
| `analises.cursar.space` | PDFs das análises (3081) — **sem senha** | [`../../docs/analise-entrega-cloudflare.md`](../../docs/analise-entrega-cloudflare.md) |

`Linger=yes` no usuário faz os serviços subirem no boot sem login gráfico.

## Instalação rápida (já aplicada neste PC)

```bash
cd ~/Documentos/Mapas_Facil/Fase_2_Site/web
npm install
npm run build

install -m 0755 ../deploy/run-mapas-facil-site.sh ~/.config/systemd/user/
install -m 0644 ../deploy/mapas-facil-site.service ~/.config/systemd/user/
install -m 0644 ../deploy/mapas-facil-tunnel.service ~/.config/systemd/user/
install -m 0644 ../deploy/mapas-facil-analises.service ~/.config/systemd/user/

# tunnel dedicado (uma vez):
# cloudflared tunnel create mapasfacil
# cloudflared tunnel route dns -f <UUID> mapasfacil.cursar.space
# copiar mapasfacil-config.yml.example → ~/.cloudflared/mapasfacil-config.yml

systemctl --user daemon-reload
systemctl --user enable --now mapas-facil-site.service mapas-facil-tunnel.service
```

## Operação

```bash
systemctl --user status mapas-facil-site.service mapas-facil-tunnel.service
systemctl --user restart mapas-facil-site.service
curl -I http://127.0.0.1:3080/
curl -I https://mapasfacil.cursar.space/
```

Após `git pull` com mudanças no front: `npm run build` em `web/` e `systemctl --user restart mapas-facil-site.service`.

Download do instalador: ver [`docs/site-download-cloudflare.md`](../../docs/site-download-cloudflare.md).

Regra F2-06: **não** editar tunnels de outros sistemas.
