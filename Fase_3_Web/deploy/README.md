# `deploy/` — operação no server-desktop

Tudo aqui é para o **server-desktop** (`ssh sd`, tailnet `100.65.138.58`). Nada nesta pasta roda no
Windows nem no acer.

| Arquivo | Para quê | Marco |
|---|---|---|
| `scripts/preflight.sh` | diz o que falta no server antes de subir o app (somente leitura) | **W0** |
| `mapasfacil-app.service` | unit `systemd --user` do backend (`127.0.0.1:3130`) | W12 |
| `mapasfacil-app-tunnel.service` + `mapasfacil-app-tunnel.yml.example` | túnel próprio da Cloudflare | W12 |
| `scripts/checar_hd.sh` | `ExecStartPre` que espera o HD montar | W12 |
| `scripts/atualizar.sh`, `rollback.sh`, `backup.sh` | deploy por tag, volta e backup do SQLite | W12 |

## Regras que não se negociam

- Porta **3130 só em `127.0.0.1`**; quem fala com o backend é o túnel (AW-06).
- Nenhum `.yml` de túnel existente é editado: o app tem túnel próprio (`mapasfacil-app`).
- Serviço roda a partir de `/home/server/mapasfacil` (symlink para o HD), nunca do SSD nem de
  `~/Downloads`.
- Sem `git pull` por timer: atualização é por **tag**, com `atualizar.sh`.
- Nada aqui religa ou mexe em serviço mascarado no incidente de 15–16/10.

## Preflight

```bash
ssh sd
git -C ~/mapasfacil/codigo pull --ff-only      # ou copie este script para o server
bash ~/mapasfacil/codigo/Fase_3_Web/deploy/scripts/preflight.sh
```

Sai `0` quando está tudo pronto e `1` quando falta algo obrigatório. `--sem-rede` pula as sondas de
9Router/SEMA/WMS. A saída **não** contém segredo: das chaves ele só diz se existem.

## O que exige o Álvaro (o agente não tem `sudo` nem login na Cloudflare)

```bash
sudo apt install -y gdal-bin fonts-liberation python3.12 python3.12-venv
sudo loginctl enable-linger server
cloudflared tunnel create mapasfacil-app
cloudflared tunnel route dns mapasfacil-app mapasfacil-app.cursar.space
# e montar /home/server/mapasfacil/segredos/servidor.env (0600) com a chave
# dedicada do Mapas Fácil no 9Router da VPS
```
