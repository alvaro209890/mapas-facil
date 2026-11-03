# W-12 — Deploy no server-desktop e operação

## Objetivo

Colocar o app web no ar no **server-desktop** (Linux, `/home/server`, tailnet `100.65.138.58`)
de um jeito que sobe no boot, não depende do SSD quase cheio, não mexe em túnel nem porta de
outro serviço da frota, tem backup, rollback e um `preflight` que diz o que falta antes de
qualquer coisa.

## Estado atual vs alvo

| Item | Hoje (vault, 2026-11-03) | Alvo |
|---|---|---|
| Landing `mapasfacil.cursar.space` | no **acer** (`mapas-facil-site` :3080, `mapas-facil-tunnel`) | continua lá, intocada |
| `analises.cursar.space` | no acer (:3081), sem senha | **desligado** (P6 — não é usado; tarefa W12-08) |
| App web | — | server-desktop, `127.0.0.1:3130`, túnel próprio `mapasfacil-app` |
| Disco do server | SSD `/` 82% (19 GB livres); HD backup 1,9 TB em `/media/server/HD Backup/Servidores_NAO_MEXA/` (39%) | código e dados no HD |
| Recursos | 4 núcleos, 15 GB RAM, Python 3.12, Node 22, Docker | suficiente para `MF_MAX_WORKERS=6`, `MF_MAX_JOBS=2` |

Fontes do estado: vault `01-infra/servidor.md`, `01-infra/portas.md`, `01-infra/dominios-e-tunnels.md`,
`01-infra/incidente-invasao-frota-2026-10-15.md`. **Reler antes de executar** — o estado da frota muda.

## Dependências

Tudo do MVP (W0–W9). O preflight (W0-20) roda **no começo** da Fase 3, para o agente saber cedo
o que falta no server.

## Contratos

### Pastas no server

```
/media/server/HD Backup/Servidores_NAO_MEXA/mapasfacil/      ← tudo no HD (nome com espaço!)
/home/server/mapasfacil  →  symlink para a pasta acima         ← MF_RAIZ (sem espaço; usar sempre este)
  ├── codigo/            git clone do repositório (somente leitura no dia a dia; atualizar por script)
  ├── venv/              Python 3.12 com núcleo + servidor instalados (pip com hashes)
  ├── dados/
  │   ├── mapasfacil.sqlite (+ -wal, -shm)
  │   ├── projetos/<id>/  ← W-02
  │   ├── uploads/        ← partes temporárias
  │   ├── cache/          ← MAPASFACIL_CACHE_DIR (camadas WFS/WMS)
  │   ├── acervo_rasters/ ← MAPASFACIL_ACERVO_RASTERS
  │   ├── templates/      ← variantes .mxd da fábrica (W-08)
  │   └── vagas/          ← locks de geração
  ├── segredos/servidor.env  (0600)
  ├── logs/servidor.log, logs/workers/<id>.log  (rotação)
  ├── backups/           sqlite diário (14 dias)
  └── releases/<tag>/web-dist/   build do SPA por versão (rollback instantâneo)
```

### Preflight — `Fase_3_Web/deploy/scripts/preflight.sh`

Somente leitura; imprime uma tabela OK/FALTA e termina ≠ 0 se faltar algo obrigatório.

| Item | Como checa | Se faltar |
|---|---|---|
| Está no server-desktop | `hostname` / `tailscale ip -4` = `100.65.138.58` | aborta |
| HD montado | `mountpoint -q "/media/server/HD Backup"` | aborta — pedir ao Álvaro |
| Espaço no HD | `df` ≥ 200 GB livres | aviso |
| Symlink `MF_RAIZ` | `readlink -f /home/server/mapasfacil` aponta para o HD | cria (sem sudo) |
| Porta 3130 livre | `ss -tlnp | grep ':3130 '` vazio | escolher outra e atualizar o vault `01-infra/portas.md` |
| Python 3.12 + venv | `python3 --version`, `python3 -m venv --help` | pedir `apt install python3.12-venv` ao Álvaro (sudo) |
| GDAL (`ogr2ogr`) | `ogr2ogr --version` | pedir `apt install gdal-bin` (sudo) |
| Fontes | `fc-list | grep -i "Liberation Sans"` | pedir `apt install fonts-liberation` (sudo) |
| Node 22 + pnpm/npm | `node --version` | — (já há Node 22) |
| `loginctl show-user server -p Linger` | `Linger=yes` (units `--user` sobem sem login) | pedir `loginctl enable-linger server` |
| `cloudflared` | `cloudflared --version` | pedir instalação |
| Segredos | `segredos/servidor.env` existe, `0600`, tem as 3 chaves | o Álvaro cria (o agente nunca vê o valor) |
| 9Router (IA) | `curl -sS http://100.104.255.35:20128/v1/models -H "Authorization: Bearer $(grep ^MAPASFACIL_PROVEDOR_CHAVE= segredos/servidor.env | cut -d= -f2-)"` lista `ag/gemini-3.8-flash-high` — o script **nunca** imprime a chave, só o resultado | VPS fora do ar ou chave errada: avisar o Álvaro (o 9Router central não tem reserva) |
| Saída para APIs geo | `curl` de status no SEMA WFS (`planos/03-wfs-e-servicos-geo.md`), Planet e GeoServer da IMAP (`wms.cursar.space`, serviço virtual de uma camada) | investigar rede/DNS (o `/etc/hosts` do server tem bloqueios pós-incidente) |

Tudo que precisa de `sudo` vira **pedido ao Álvaro** com o comando exato — o agente não tem e
não pede a senha.

### Units systemd `--user`

`Fase_3_Web/deploy/mapasfacil-app.service`:

```ini
[Unit]
Description=Mapas Fácil — app web (API + SPA)
After=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/server/mapasfacil/codigo/Fase_3_Web/servidor
EnvironmentFile=/home/server/mapasfacil/segredos/servidor.env
Environment=MF_RAIZ=/home/server/mapasfacil
Environment=MF_HOST=127.0.0.1
Environment=MF_PORTA=3130
ExecStartPre=/home/server/mapasfacil/codigo/Fase_3_Web/deploy/scripts/checar_hd.sh
ExecStart=/home/server/mapasfacil/venv/bin/python -m mapasfacil_servidor serve
Restart=on-failure
RestartSec=30
TimeoutStopSec=60
KillMode=mixed

[Install]
WantedBy=default.target
```

`checar_hd.sh`: `mountpoint -q "/media/server/HD Backup"` e `test -d "$MF_RAIZ/dados"`; falha ⇒
a unit tenta de novo em 30 s (o HD pode montar depois do login). Unit de usuário não consegue
depender de mount de sistema — por isso o script.

`mapasfacil-app-tunnel.service`: `cloudflared tunnel --config ~/.cloudflared/mapasfacil-app.yml run`,
`Restart=always`. Config (`mapasfacil-app-tunnel.yml.example` no repo, sem credencial):

```yaml
tunnel: <UUID criado pelo Álvaro>
credentials-file: /home/server/.cloudflared/<UUID>.json
ingress:
  - hostname: mapasfacil-app.cursar.space
    service: http://127.0.0.1:3130
    originRequest:
      noTLSVerify: false
      disableChunkedEncoding: false
  - service: http_status:404
```

Criar túnel e DNS exige login na Cloudflare (navegador) — **passo do Álvaro**:

```bash
cloudflared tunnel create mapasfacil-app
cloudflared tunnel route dns mapasfacil-app mapasfacil-app.cursar.space
```

Nada de editar `.yml` de túnel de outro serviço (regra do vault: "sem tocar tunnels existentes").

### Instalação e atualização — `deploy/scripts/atualizar.sh <tag>`

1. `preflight.sh` (aborta se faltar algo).
2. `git -C codigo fetch --tags && git -C codigo checkout <tag>` — **tag** assinada/conferida,
   nunca `main` solto; nada de auto-pull por timer (lição do incidente do GeoForest).
3. `venv/bin/pip install --require-hashes -r Fase_3_Web/servidor/requirements.lock` +
   `pip install --no-deps -e Fase_1_Desktop/nucleo -e Fase_3_Web/servidor`.
4. `python -m mapasfacil_servidor migrar` (migrações SQL numeradas, transacionais; backup do
   sqlite antes).
5. Build do SPA: `npm ci` (ou `pnpm install --frozen-lockfile`) e `build` em `Fase_3_Web/web`;
   copiar `dist/` para `releases/<tag>/web-dist/`; o servidor serve o diretório apontado por
   `releases/atual` (symlink).
6. `systemctl --user restart mapasfacil-app` (workers ociosos morrem; jobs em curso recebem
   aviso — rodar fora do horário de uso).
7. Smoke: `curl -fsS http://127.0.0.1:3130/api/v1/saude` com `versao == <tag>`; login com a conta
   de teste `teste@mapasfacil.local` (criada pelo próprio script, senha em
   `segredos/teste.env`), criar projeto, importar `imovel_ficticio.zip`, `GET /resumo` ok,
   apagar projeto de teste.
8. Registrar no vault (abaixo).

`rollback.sh <tag_anterior>`: `checkout`, `pip install` (cache), **não** desfaz migração
(migrações são só aditivas na Fase 3 — regra), aponta `releases/atual` para a anterior, restart, smoke.

### Backup

| O quê | Como | Retenção |
|---|---|---|
| `mapasfacil.sqlite` | `sqlite3 .backup` diário (timer `--user` 02:30) para `backups/` | 14 dias |
| `chats.sqlite` de cada projeto | idem, junto (loop por projeto ativo) | 14 dias |
| Pastas de projeto | ficam só no HD do server — **sem cópia externa** (decisão P7 de 2026-11-03) | enquanto o projeto existir (lixeira 30 dias) |

Risco aceito: se o HD do server falhar, os projetos se perdem (o banco tem cópia diária, mas no
mesmo HD). O `/admin/saude` mostra o espaço livre e o timer de saúde registra erro de E/S do HD.

### Observabilidade

- `GET /api/v1/saude` (público, sem dado) e `/admin/saude`.
- Logs: `logs/servidor.log` (JSON por linha: `ts`, `nivel`, `codigo`, `projeto_id`, `req_id`,
  `ms`), rotação 10 × 20 MB; workers à parte. Nunca corpo de requisição, nunca CPF/chave.
- Timer `mapasfacil-app-saude.timer` (5 min): chama `/saude`; 3 falhas seguidas ⇒ grava alerta em
  `logs/alertas.log`. Integração com WhatsApp do Álvaro **fora** do escopo inicial (se for feita:
  pelo chip do Hermes para o pessoal do Álvaro, regra do CLAUDE.md global).
- Limpeza diária: `python -m mapasfacil_servidor limpar-lixeira` (lixeira > 30 dias, uploads
  expirados, `.preview` > 7 dias).

### Registro no Segundo Cérebro (obrigatório ao subir)

Protocolo do vault (`AGENTS.md` na raiz do vault): `ssh sd`, `VAULT_AUTOR=<agente>
./ferramentas/lock.sh <arquivo>`, patch cirúrgico, unlock, `lock.sh commit "msg"`. Atualizar:

| Arquivo do vault | O que entra |
|---|---|
| `02-projetos/mapas-facil.md` | seção "Fase 3 — web" com URL, porta, pastas, estado dos marcos |
| `01-infra/portas.md` | linha `3130 · 127.0.0.1 · python3 · mapasfacil-app · mapasfacil-app.cursar.space` |
| `01-infra/dominios-e-tunnels.md` | hostname e túnel `mapasfacil-app` (no server) |
| `01-infra/servicos.md` | as 2 units + timers |
| `01-infra/onde-vivem-os-segredos.md` | **ponteiro** para `segredos/servidor.env` (sem valor) |
| `06-changelog.md` | entrada no topo |

## Tarefas agentáveis

- [ ] **W0-20** `deploy/scripts/preflight.sh` + rodar no server e anexar a saída (sem segredos) ao relatório do W0.
- [ ] **W12-01** `deploy/mapasfacil-app.service`, `mapasfacil-app-tunnel.service`, `mapasfacil-app-tunnel.yml.example`, `scripts/checar_hd.sh`.
- [ ] **W12-02** `scripts/atualizar.sh`, `scripts/rollback.sh`, `scripts/backup.sh` + timers.
- [ ] **W12-03** `servidor/requirements.lock` com hashes (gerado por `pip-compile --generate-hashes`).
- [ ] **W12-04** CLI `migrar`, `limpar-lixeira`, `amostras-mxd`, `varrer-pii`.
- [ ] **W12-05** Pedidos ao Álvaro (lista com comandos exatos): sudo apt, linger, túnel/DNS, `servidor.env`, **chave dedicada do Mapas Fácil no 9Router** (D33).
- [ ] **W12-06** Primeiro deploy por tag `web-v0.1.0`, smoke, registro no vault.
- [ ] **W12-07** Piloto interno: 3 usuários do escritório, 5 imóveis reais cada (dado fica no server, nunca no git); coletar problemas em `docs/piloto-fase3.md` (sem dado de cliente).
- [ ] **W12-08** Desligar `analises.cursar.space` (P6: "não usamos, pode apagar"). No **acer**: `systemctl --user disable --now mapas-facil-analises.service`; tirar só a entrada `analises` do ingress de `mapasfacil-config.yml` (o mesmo túnel serve a landing `mapasfacil` — reiniciar o túnel e conferir que `https://mapasfacil.cursar.space` continua 200); pedir ao Álvaro para remover o DNS `analises` na Cloudflare. No repo: marcar `Fase_2_Site/deploy/servidor_analises.py`, `ferramentas/publicar_analise.py` e `docs/analise-entrega-cloudflare.md` como legado (não apagar o histórico). Vault: `01-infra/portas-acer.md`, `01-infra/dominios-e-tunnels.md`, `02-projetos/mapas-facil.md`. As análises publicadas lá **não** são apagadas sem perguntar onde guardá-las.

## Critérios de aceite

- [ ] `preflight.sh` verde no server.
- [ ] Reboot do server ⇒ app volta sozinho (com o HD montando depois do login, a unit espera e sobe).
- [ ] `https://mapasfacil-app.cursar.space/api/v1/saude` responde 200 de fora da tailnet.
- [ ] `ss -tlnp` mostra 3130 só em `127.0.0.1`.
- [ ] `rollback.sh` para a tag anterior funciona e o smoke passa.
- [ ] Vault atualizado nos 6 arquivos, com autor e data.

## Fora de escopo

- Alta disponibilidade, segundo servidor, balanceador.
- Mover a landing do acer para o server.

## Anti-padrões

- Rodar o serviço a partir do SSD ou de `~/Downloads`.
- Usar `0.0.0.0` "para testar pela tailnet" (use `ssh -L 3130:127.0.0.1:3130 sd`).
- Editar config de túnel de outro projeto para "aproveitar".
- Auto-update por `git pull` em timer.
