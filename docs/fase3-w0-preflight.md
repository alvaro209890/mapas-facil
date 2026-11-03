# Fase 3 — W0 — preflight do server-desktop

**Rodado em:** 2026-11-03 10:36 (America/Sao_Paulo) · `server-desktop` (`100.65.138.58`)
**Script:** `Fase_3_Web/deploy/scripts/preflight.sh` (copiado para `/tmp/mf-preflight/` e executado
lá; o código ainda não tem clone no server — isso chega no W12)
**Saída sem segredo:** o script só diz se uma chave existe, nunca o valor.

```
servidor: server-desktop · MF_RAIZ=/home/server/mapasfacil · porta=3130
--------------------------------------------------------------------------
OK     host                         server-desktop · 100.65.138.58
OK     HD de backup                 montado em /media/server/HD Backup
OK     espaço no HD                 1039 GB livres
OK     MF_RAIZ                      symlink criado → /media/server/HD Backup/Servidores_NAO_MEXA/mapasfacil
OK     porta 3130                   livre
OK     python3.12                   Python 3.12.3
OK     venv                         disponível
OK     ogr2ogr                      GDAL 3.8.4, released 2024/02/08
FALTA  fonte Liberation             pedir: sudo apt install fonts-liberation
OK     node                         v22.23.1
OK     loginctl linger              Linger=yes
OK     cloudflared                  cloudflared version 2026.1.1 (built 2026-01-20-11:14 UTC)
FALTA  servidor.env                 não existe em /home/server/mapasfacil/segredos/servidor.env — pedir ao Álvaro
AVISO  9Router (IA)                 sem chave para sonda (servidor.env)
OK     WMS da IMAP                  GetCapabilities 200
OK     SEMA GeoServer               responde (HTTP 200; chave só no WFS autenticado)
--------------------------------------------------------------------------
falhas: 2 · avisos: 1
```

## O que já está pronto no server

- HD de backup montado, **1039 GB livres** (o plano exige ≥ 200 GB).
- `/home/server/mapasfacil` criado como symlink para
  `/media/server/HD Backup/Servidores_NAO_MEXA/mapasfacil` (o preflight criou; era a única escrita
  prevista).
- Porta **3130 livre** — coerente com o vault `01-infra/portas.md`.
- Python 3.12.3 + `venv`, GDAL 3.8.4 (`ogr2ogr`), Node 22.23.1, `cloudflared` 2026.1.1,
  `Linger=yes` (units `--user` sobem sem login).
- WMS da IMAP e GeoServer da SEMA respondem de dentro do server.

## O que falta — e é pedido ao Álvaro

| Item | Comando exato |
|---|---|
| `fonts-liberation` (o núcleo cai para Liberation Sans quando não há Arial) | `sudo apt install -y fonts-liberation` |
| Arquivo de segredos do app (0600) com a **chave dedicada do Mapas Fácil** no 9Router da VPS | criar `/home/server/mapasfacil/segredos/servidor.env` com `MAPASFACIL_PROVEDOR_CHAVE`, `MAPASFACIL_SEMA_AUTHKEY`, `MAPASFACIL_PLANET_API_KEY` + `MF_ADMIN_EMAIL`; depois `chmod 600` |

Nada disso bloqueia o desenvolvimento no Windows: o CI e os anéis 1–2 rodam com `fake_nucleo` e
segredos fictícios. Bloqueia o **deploy** (W12) e o smoke ao vivo (anel 3).

## Observação para o W12

O preflight precisa existir no server a partir do clone (`codigo/Fase_3_Web/deploy/scripts/`). Hoje
ele rodou de `/tmp/mf-preflight/`, o suficiente para o diagnóstico do W0.
