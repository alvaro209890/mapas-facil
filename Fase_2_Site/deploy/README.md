# Deploy do site Mapas Fácil neste PC

Produção local + Cloudflare Tunnel dedicado → `https://mapasfacil.cursar.space`.

## Serviços systemd (user)

| Unidade | Função |
|---|---|
| `mapas-facil-site.service` | vinext em `127.0.0.1:3080` |
| `mapas-facil-tunnel.service` | tunnel dedicado `mapasfacil` |

`Linger=yes` no usuário faz os serviços subirem no boot sem login gráfico.

## Instalação rápida (já aplicada neste PC)

```bash
cd ~/Documentos/Mapas_Facil/Fase_2_Site/web
npm install
npm run build

install -m 0755 ../deploy/run-mapas-facil-site.sh ~/.config/systemd/user/
install -m 0644 ../deploy/mapas-facil-site.service ~/.config/systemd/user/
install -m 0644 ../deploy/mapas-facil-tunnel.service ~/.config/systemd/user/

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

Regra F2-06: **não** editar tunnels de outros sistemas.
