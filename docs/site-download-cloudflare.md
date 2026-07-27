# Site público + download + dados locais (Acer / Cloudflare)

Estado operacional neste PC (2026-07-27).

## URLs

| O quê | Onde |
|---|---|
| Site (Cloudflare Tunnel) | https://mapasfacil.cursar.space |
| Download do instalador | https://mapasfacil.cursar.space/download |
| Instalador `.exe` (GitHub Releases) | https://github.com/alvaro209890/mapas-facil/releases/download/desktop-v0.5.0/MapasFacil-Setup-0.5.0.exe |
| Manifesto JSON | https://github.com/alvaro209890/mapas-facil/releases/latest/download/download-manifest.json |
| Release | `desktop-v0.5.0` — tag no repositório `alvaro209890/mapas-facil` |

O site **não** hospeda o `.exe`. O botão em `/download` aponta para o asset da release no GitHub.

## Como o site sobe neste PC

1. **vinext** em `127.0.0.1:3080` — unidade `mapas-facil-site.service`
2. **cloudflared** tunnel dedicado `mapasfacil` — unidade `mapas-facil-tunnel.service`
3. DNS: `mapasfacil.cursar.space` → tunnel

Detalhe de instalação/operação: [`Fase_2_Site/deploy/README.md`](../Fase_2_Site/deploy/README.md).

Após mudar o front:

```bash
cd ~/Documentos/Mapas_Facil/Fase_2_Site/web
npm run build
systemctl --user restart mapas-facil-site.service
curl -I https://mapasfacil.cursar.space/download
```

Variáveis públicas do instalador: `Fase_2_Site/web/.env.production` (URL, versão, SHA-256).  
Código: `Fase_2_Site/web/lib/download.ts` + `app/download/page.tsx`.

## O que quem instala já tem

| Capacidade | Estado |
|---|---|
| Criar conta (e-mail + senha local) | Sim — no app, não no site |
| DeepSeek no chat | Sim — chave do projeto ativada **no login** (cofre). Não precisa colar chave |
| MXD / PDF / chats por usuário | Sim — ver árvore abaixo |
| ArcMap / paridade Harmonia | Ainda no Windows (M9) — fora deste pacote de site |

A chave **não** vai no git. Neste Acer ela está em `secrets.local.json` e é espelhada para `Documentos/database/MapasFacil/provisao.local.json`.  
No `.exe` Windows: incluir `provisao.local.json` em `resources/` — ver [`provisao-deepseek-instalador.md`](provisao-deepseek-instalador.md).

## Árvore de dados neste PC

```
Documentos/database/MapasFacil/
  contas/contas.sqlite
  provisao.local.json          # gitignored
  <email_slug>/
    chats/                     # chats.sqlite, anexos, mapspecs
    mxd/  pdf/  xlsx/  artefatos/
    Mapas/  MXD/  SHP/
    cache/
    workspace/                 # pasta padrão aberta após login
```

Código: `Fase_1_Desktop/nucleo/mapasfacil_nucleo/dados.py`, `agente/provisao.py`, `contas/servico.py`, `app/electron/main.ts`.

## Checklist rápido “está no ar?”

```bash
systemctl --user is-active mapas-facil-site.service mapas-facil-tunnel.service
curl -sI https://mapasfacil.cursar.space/download | head -5
curl -s https://mapasfacil.cursar.space/download | grep -o 'MapasFacil-Setup[^"]*'
```

Esperado: serviços `active`, HTTP 200, link `MapasFacil-Setup-0.5.0.exe`.

## SmartScreen

O instalador beta ainda **não** tem Authenticode. No Windows: *Mais informações → Executar mesmo assim* e conferir o SHA-256 da página `/download` / `sha256.txt` da release.
