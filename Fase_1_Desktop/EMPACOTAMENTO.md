# Empacotamento desktop (M10 / F1-11)

Como gerar o `.exe` instalável, publicar no GitHub e ligar o site na página de download.

## O que este marco entrega

| Artefato | Onde |
|---|---|
| PyInstaller **onedir** do núcleo | `nucleo/packaging/` → `resources/nucleo/` |
| NSIS `MapasFacil-Setup-<semver>.exe` | `electron-builder` + `app/electron-builder.yml` |
| Auto-update | `electron-updater` + `latest.yml` na Release |
| CI | [`.github/workflows/release-desktop.yml`](../.github/workflows/release-desktop.yml) |
| Contrato do site | [`shared/releases/`](../shared/releases/) |

**Honestidade de escopo:** M2 (motor ArcPy) e M9 (paridade Harmonia) ainda dependem do
Windows+ArcMap. O instalador empacota o produto atual (T2/PDF nativo + UI completa). Não finja
paridade visual Harmonia na página de download até o M9 fechar.

Assinatura Authenticode: **dívida aceita no beta** (F1-11) — SmartScreen pede “Executar mesmo
assim”; `sha256.txt` na release.

## Publicar uma versão (recomendado)

No PC com git (Linux ou Windows), com `package.json` já na versão certa:

```bash
# 1. Bump (mantenha VERSAO_NUCLEO_ESPERADA em sync com nucleo __version__)
#    app/package.json → "version": "0.5.0"
#    app/electron/nucleo/versao.ts → VERSAO_APP / VERSAO_NUCLEO_ESPERADA

git add -A
git commit -m "release: desktop 0.5.0"
git push origin main

git tag desktop-v0.5.0
git push origin desktop-v0.5.0
```

O workflow **Release — desktop Windows** sobe num runner `windows-latest`, gera o instalador e
cria a GitHub Release com:

- `MapasFacil-Setup-0.5.0.exe`
- `MapasFacil-0.5.0-win-x64.zip` (portátil)
- `latest.yml` + `.blockmap`
- `sha256.txt`
- `download-manifest.json` ← **o site lê isto**

Também dá para rodar **Actions → Release — desktop Windows → Run workflow**.

## Build local no Windows (sem esperar o CI)

```powershell
cd mapas-facil
git pull origin main

# Núcleo
cd Fase_1_Desktop\nucleo
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pip install "pyinstaller>=6.3,<7"
python packaging\empacotar.py

# App
cd ..\app
pnpm install
pnpm typecheck
pnpm test
pnpm run dist:win
# → app\release\MapasFacil-Setup-*.exe

pnpm run dist:manifest -- --dir release --versao 0.5.0 --tag desktop-v0.5.0
```

## Ligar o site (`/download`)

URL estável:

```
https://github.com/alvaro209890/mapas-facil/releases/latest/download/download-manifest.json
```

Detalhe e snippet TypeScript: [`shared/releases/README.md`](../shared/releases/README.md).

Checklist na página:

1. Botão **Baixar Mapas Fácil** → `instalador.url`
2. Mostrar versão + data (`versao`, `publicado_em`)
3. Exibir SHA-256 (`instalador.sha256`) + link para `sha256.txt`
4. Texto do SmartScreen a partir de `notas` (enquanto não houver certificado)

## Estrutura pós-instalação

```
%LOCALAPPDATA%\Programs\Mapas Facil\     (per-user, padrão NSIS do builder)
├─ Mapas Facil.exe
├─ resources\
│  └─ nucleo\
│     ├─ nucleo.exe
│     ├─ _internal\
│     └─ shared\
├─ arcpy_job.py
└─ …

%APPDATA%\MapasFacil\                   ← config, chats, contas
```

## Comandos úteis

| Objetivo | Comando |
|---|---|
| Só o sidecar | `python Fase_1_Desktop/nucleo/packaging/empacotar.py` |
| Staging para o builder | `pnpm run pack:prepare` (em `app/`) |
| Instalador Windows | `pnpm run dist:win` |
| Manifesto | `pnpm run dist:manifest -- --dir release --versao X.Y.Z` |

## Critérios M10 (infra)

- [x] PyInstaller onedir + `shared/` + `arcpy_job.py` fora do blob
- [x] `electron-builder` NSIS + zip
- [x] `electron-updater` no boot (quando empacotado)
- [x] `UI-010` se `doctor.nucleo` ≠ versão esperada
- [x] Workflow GitHub Actions em tag `desktop-v*`
- [x] `download-manifest.json` + schema para o site
- [ ] Assinatura Authenticode (quando houver certificado OV/EV)
- [ ] Smoke instalado em Windows limpo sem Python (CI gera; validação manual / M11)
- [ ] T2 completo pós-instalação sem ArcMap (depende template `pronto` — M2)
