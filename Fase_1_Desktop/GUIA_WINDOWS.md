# Guia Windows — o que fazer agora (M2 → M9 → M10 → M11)

**Para quem:** você neste PC **Windows com ArcMap 10.6–10.8**.  
**Por quê:** no Linux (Acer) o backlog desktop **sem** ArcMap já fechou. O que falta na
Fase 1 **só roda aqui**.

> Snapshot vivo: [`../AGENT_BRIEF.md`](../AGENT_BRIEF.md#snapshot--o-que-falta-2026-07-26).  
> Planos longos: [F1-04](planos/04-motor-mxd.md) · [F1-09](planos/09-validacao-conformidade.md) ·
> [F1-11](planos/11-empacotamento-instalador.md) · [F1-12](planos/12-roadmap.md) ·
> [checklist B/I](planos/13-checklist-implementacao.md).  
> Progresso sem ArcMap já feito: [`nucleo/docs/bloco-b-sem-arcmap.md`](nucleo/docs/bloco-b-sem-arcmap.md).

**Ordem fixa (não pule):**

```
0. Preparar máquina
   ↓
1. M2 — Motor .mxd (B1 → B2 → T1/T2)
   ↓
2. M9 — Conformidade Harmonia
   ↓
3. M10 — Instalador
   ↓
4. M11 — Piloto
```

Fase 2 (site) **não** entra neste guia — só depois do M11.

---

## 0) Preparar a máquina Windows

### 0.1 Software

| Item | Versão / nota |
|---|---|
| Windows | 10 ou 11 |
| ArcMap | **10.6–10.8** (Python 2.7 tipicamente em `C:\Python27\ArcGIS10.8\python.exe`) |
| Git | clone de `https://github.com/alvaro209890/mapas-facil.git` · branch `main` |
| Node.js + pnpm | para o app Electron (`Fase_1_Desktop/app/`) |
| Python 3.12 | venv do núcleo (`Fase_1_Desktop/nucleo/.venv`) — **não** misturar com o 2.7 do ArcMap |
| GDAL / `ogr2ogr` | opcional mas útil para materializar camadas |

### 0.2 Clone e atualize

```powershell
git clone https://github.com/alvaro209890/mapas-facil.git
cd mapas-facil
git checkout main
git pull origin main
```

Leia de novo o snapshot no `AGENT_BRIEF.md` (pode ter mudado desde o último `pull`).

### 0.3 Núcleo (Python 3)

```powershell
cd Fase_1_Desktop\nucleo
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest -q
python -m mapasfacil_nucleo doctor
```

Doctor tem de reportar ArcMap encontrado quando `--completo` / sondagem Windows.

### 0.4 App Electron

```powershell
cd Fase_1_Desktop\app
pnpm install
pnpm typecheck
pnpm test
pnpm build
pnpm run dev:electron
```

### 0.5 Segredos (nunca no git)

- Copie `secrets.example.json` → `secrets.local.json` na raiz (gitignored).
- Preencha `deepseek_api_key` se for usar o chat.
- Em produção/piloto: chave no **Credential Manager** via Preferências do app (A11).
- Antes de qualquer commit que toque `.mxd`:

```powershell
python ferramentas\chaves_mxd.py limpar
python ferramentas\chaves_mxd.py verificar
```

Tem de dizer **"Seguro para commit"**.

### 0.6 Pasta de teste (Harmonia)

Use o acervo versionado:

- MXDs: `Referencias_IMAP\MXD\` e/ou `Referencias_IMAP\Mapas\01\`
- PDFs-modelo (baseline): `Referencias_IMAP\Mapas\01\`
- Documentação da adaptação manual:  
  `Referencias_IMAP\MXD\DOCUMENTACAO_MXD_HARMONIA.md`

Ideal: uma pasta de projeto local (fora do git) com shapefiles ATP/AVN/AC/AUAS + recibo CAR,
como o usuário real usaria — conecte pelo app (`Ctrl+O`).

### 0.7 Anti-padrões neste PC (resumo)

| Não faça | Por quê |
|---|---|
| Commitar `secrets.local.json` / authkey / CPF | AP-03 / AP-09 |
| Editar `.mxd` do acervo **no lugar** | sempre trabalhar em **cópia** → `shared/templates/` |
| Deixar a IA gerar script `arcpy` livre | AP-02 — só `MapSpec` |
| Marcar B1/M2 feito sem atualizar checklist + `AGENT_BRIEF` | AP-15 |
| Empacotar (M10) antes da Harmonia passar (M9) | roadmap: M9 bloqueia M10 |

---

## 1) M2 — Motor `.mxd` (o coração)

**Objetivo:** `.mxd` que abre noutro PC sem `!` vermelho + PDF; template `dinamica_retrato`
sai de `parcial` → `pronto` no MANIFEST.

**Planos:** [F1-04](planos/04-motor-mxd.md) · checklist Bloco B ·
[`nucleo/docs/bloco-b-sem-arcmap.md`](nucleo/docs/bloco-b-sem-arcmap.md).

### Passo 1.1 — Inspecionar o que o ArcMap vê

```powershell
C:\Python27\ArcGIS10.8\python.exe ferramentas\inspecionar_mxd_arcpy.py `
  Referencias_IMAP\MXD\Dinamica_2026.mxd
```

(Ajuste o caminho do Python 2.7 se a instalação for 10.6/10.7.)

Anote data frames, layers e elementos de layout. Compare com a tabela de nomes canônicos em
F1-04 (`PERIMETRO`, `AVN`, `AC`, `AUAS`, `MUNICIPIOS`, `UF`, `TITULO`, `ROTULO_IMOVEL`, …).

### Passo 1.2 — B1: normalizar o template (script + o que sobrar na GUI)

**Sempre em cópia** — o script já escreve em `shared/templates/`:

```powershell
C:\Python27\ArcGIS10.8\python.exe ferramentas\normalizar_mxd_arcpy.py `
  Referencias_IMAP\MXD\Dinamica_2026.mxd `
  shared\templates\Dinamica_retrato.mxd `
  --logo
```

Leia o relatório `aplicados` / `pendencias` no stdout.

**O que o script já tenta (Linux não rodou — confirme aqui):**

- `relativePaths = True`
- Data frames `MAPA` / `MINIMAPA`
- Renomear camadas e elementos conhecidos
- Reaproveitar caixa "Ano: NNNN" → `TITULO`
- Rótulo solto → `ROTULO_IMOVEL`
- Heurística `MINIMAPA_RETANGULO` / `MINIMAPA_GUIA`
- Apontar `LOGO` para PNG em `Referencias_IMAP\Logos IMAP\` (se `sourceImage` gravável)

**Se sobrar pendência:** abra **só a cópia** no ArcMap e feche na GUI (não invente layout do
zero — F1-04). Depois **rode de novo** a normalização e siga para 1.3 — offsets mudam quando a
estrutura do `.mxd` muda.

Checklist visual mínimo no ArcMap:

- [ ] File → Map Document Properties → **Store relative pathnames** ligado
- [ ] Camadas canônicas apontando para `.\SHP\<nome>.shp` (pasta ao lado do template ou da
      entrega)
- [ ] Elementos `TITULO`, `ROTULO_IMOVEL`, `METADADOS`, `LEGENDA`, `NORTE`, `LOGO`,
      `MINIMAPA_RETANGULO`, `MINIMAPA_GUIA` nomeados
- [ ] Sem textos herdados de outra análise (`Querência`, `Área concolidada`, …) — prep para S11
- [ ] Salvar em versão **mínima 10.6** (abre em 10.6+; 10.8-only não)

### Passo 1.3 — B2: registrar `sha256` + offsets no MANIFEST

```powershell
# Com venv Python 3 do núcleo ativo:
python ferramentas\registrar_template.py shared\templates\Dinamica_retrato.mxd
```

(Use `--dry-run` primeiro se quiser só ver números — dry-run **não** pode sobrescrever o
template real.)

Confirme em `shared/templates/MANIFEST.json`:

- [ ] entrada `dinamica_retrato` (ou id do manifesto) com `sha256` novo
- [ ] `status` caminhando para **`pronto`** quando offsets + smoke passarem
- [ ] offsets / sentinelas coerentes com F1-04 §T2

Se existir `preparar_sentinelas_arcpy.py` / `inspecionar_mxd_offsets.py`, use-os conforme o
README em `ferramentas/README.md` para calibrar patch T2.

### Passo 1.4 — Materializar `SHP/` e gerar (T2 + T1)

1. Monte um `MapSpec` da galeria (`dinamica_2026_retrato`) pela UI **ou** via
   `galeria.montar_mapspec` / ferramenta de teste.
2. `mapa.gerar` com saídas `mxd` + `pdf` (usuário autenticado — conta local M5).
3. Confira a pasta de entrega:

```
Entrega/
├─ *.mxd          ← caminhos relativos → SHP\ e recursos\
├─ *.pdf
├─ Quantitativos.xlsx   (se pedido)
├─ SHP\           ← ATP, AVN, …
└─ recursos\
```

4. **T2 (sem depender do patch arcpy no job):** `.mxd` estrutural (extent/textos se offsets
   existirem).
5. **T1 (ArcPy):** job via `scripts/arcpy_job.py` + `motores/arcpy_ponte.py` — payload **só**
   em JSON UTF-8 (`MAPASFACIL_JOB_JSON`), **nunca** acento em `argv`.

### Passo 1.5 — Critério de saída do M2 (marque só quando for verdade)

- [ ] Com ArcMap 10.8: `Dinamica_2026.mxd` (ou o gerado) da pasta Harmonia abre **sem** `!`
- [ ] Sem ArcMap no path do job: T2 ainda gera `.mxd` estruturalmente útil
- [ ] PDF ArcMap e PDF nativo existem; diferença **documentada** (não finja paridade)
- [ ] Timeout mata subprocesso travado (`AG-020`)
- [ ] `dinamica_retrato` no MANIFEST: `status: pronto` + offsets calibrados
- [ ] Nenhum texto de análise anterior no mapa gerado (base do S11)
- [ ] Checklist B1–B8 atualizado + linha no `AGENT_BRIEF` (AP-15)
- [ ] `chaves_mxd.py verificar` limpo + commit/push em `main`

---

## 2) M9 — Conformidade Harmonia

**Só depois do M2 fechado.**  
**Planos:** [F1-09](planos/09-validacao-conformidade.md) · checklist Bloco I (I1–I3) ·
padrão visual [`planos/01-padrao-imap-harmonia.md`](../planos/01-padrao-imap-harmonia.md).

### Passo 2.1 — Série completa

- [ ] Gerar a série IMAP da Harmonia (meta: **19 mapas** em &lt; 10 min com ArcMap, ou tempo
      documentado se diferente)
- [ ] Cada mapa: 14 checks **HARD** verdes
- [ ] `validacao.json` com `confianca: "arcpy"` ou `"estrutural"` **honesto**

### Passo 2.2 — Paridade visual

- [ ] Diff raster &lt; **0,3%** contra PDFs em `Referencias_IMAP/Mapas/01/`
      (`validacao.comparar_pdf` / flag `comparar_baseline` em `mapa.gerar`)
- [ ] Smoke V3 do checklist (A+) deixa de ser “infra pronta, baseline não passa”

### Passo 2.3 — Portabilidade e edição

- [ ] `.mxd` abre no ArcMap de **outro PC** (pasta autocontida)
- [ ] “Muda a cor da AVN” (ou edição equivalente) gera `_v2` **sem** apagar v1
- [ ] Check **S11** (texto herdado) verde em todos

### Passo 2.4 — Fechar M9 na doc

Atualize F1-13 Bloco I (I1–I3), roadmap M9, gap R22–R24 no `AGENT_BRIEF`, push `main`.

---

## 3) M10 — Instalador

**Infra no repositório** (2026-07-27): siga [`EMPACOTAMENTO.md`](EMPACOTAMENTO.md) — tag
`desktop-v*` dispara o build no GitHub Actions. No Windows local: `pnpm run dist:win`.

**Só anuncie qualidade Harmonia depois do M9.** Não empacote como “mapa perfeito” se o baseline
ainda falha.  
**Plano:** [F1-11](planos/11-empacotamento-instalador.md).

### Passo 3.1 — Build

- [x] PyInstaller **onedir** do núcleo → `resources/nucleo/` (sem `arcpy` no bundle)
- [x] `arcpy_job.py` copiado ao lado (invocado pelo Python 2.7 do ArcMap do usuário)
- [x] `electron-builder` → NSIS `MapasFacil-Setup-<semver>.exe`
- [x] `shared/` (catálogo, schema, templates) dentro do bundle
- [x] **Não** embutir `Referencias_IMAP/` inteiro nem `secrets.*`
- [ ] Smoke: instala limpo e sobe `doctor.rodar` (validar no Windows)

### Passo 3.2 — Assinatura e update

- [ ] Authenticode (OV/EV) + `sha256.txt` na release (`sha256.txt` já sai do CI)
- [x] `electron-updater` + `latest.yml` (canal stable)
- [ ] Instalador &lt; **250 MB** ou desvio justificado no plano (medir no primeiro build CI)

### Passo 3.3 — Critério de saída

- [ ] Instala limpo em Windows 11 **sem** Python pré-instalado
- [ ] T2 completo após instalação (máquina **sem** ArcMap ainda gera pelo caminho template)
- [ ] Login local funciona na build instalada
- [ ] Auto-update N → N+1
- [ ] Desinstalação limpa; `%APPDATA%\MapasFacil\` conforme escolha do usuário
- [x] Doc + checklist I4 parcial + push
- [x] `download-manifest.json` para o site (`shared/releases/`)

---

## 4) M11 — Piloto

**Depende do M10.**  
**Plano:** [F1-12 §M11](planos/12-roadmap.md).

- [ ] Piloto instala **e faz login** sozinho em &lt; 15 min
- [ ] Primeiro mapa válido **sem** ajuda do desenvolvedor
- [ ] Análise completa em imóvel **novo** (não só Harmonia)
- [ ] Zero bugs S1/S2 abertos
- [ ] Feedback registrado (incorporado ou pendência pós-v1)
- [ ] Critérios de aceite de [F1-00](planos/00-visao-e-escopo.md) verificados um a um
- [ ] Checklist I8 + `AGENT_BRIEF` + push

**Depois do M11:** aí sim a [Fase 2](../Fase_2_Site/README.md) (site/backend).

---

## 5) Comandos úteis (cola rápida)

```powershell
# Raiz do repo
git pull origin main

# Núcleo
cd Fase_1_Desktop\nucleo
.\.venv\Scripts\Activate.ps1
pytest -q
python -m mapasfacil_nucleo doctor

# App
cd ..\app
pnpm test
pnpm run dev:electron

# ArcMap / template (Python 2.7 do ArcGIS)
C:\Python27\ArcGIS10.8\python.exe ..\..\ferramentas\normalizar_mxd_arcpy.py `
  ..\..\Referencias_IMAP\MXD\Dinamica_2026.mxd `
  ..\..\shared\templates\Dinamica_retrato.mxd --logo

# MANIFEST (Python 3 do núcleo)
python ..\..\ferramentas\registrar_template.py ..\..\shared\templates\Dinamica_retrato.mxd

# Segurança antes de commit
python ..\..\ferramentas\chaves_mxd.py limpar
python ..\..\ferramentas\chaves_mxd.py verificar

git add -A
git status   # confira: nada de secrets / recibo CPF
git commit -m "M2: …"
git push origin main
```

---

## 6) O que já está pronto (não refaça no Windows)

Isto **já fechou no Linux** — no Windows você só valida/empacota, não reimplementa:

| Área | Estado |
|---|---|
| Shell Electron, galeria, login local, chats, agente 27/27 tools | feito |
| Motion / preview / `mapspec.atualizado` / menus / tray / offline | feito |
| WFS/REST/GML/WMS — 41/41 camadas | feito |
| Visão determinística (print/PDF/zip/mxd strings) | feito |
| API DeepSeek V4 **sem** imagem (P1 negativa) | documentado — print LLM → `IA-060` |
| Infra de diff PDF / quantitativos / fsguard / VCR | feito |

---

## 7) Ao fechar cada marco

1. Critérios de saída do [roadmap](planos/12-roadmap.md) todos `[x]`  
2. [Checklist F1-13](planos/13-checklist-implementacao.md) Bloco B ou I  
3. Gap analysis no [`AGENT_BRIEF.md`](../AGENT_BRIEF.md)  
4. `chaves_mxd.py verificar` se tocou `.mxd`  
5. `git push origin main` (convenção do repo: commits diretos em `main`)

**Comece pelo Passo 0 e 1.2 (normalizar template).** É o caminho crítico do M2.
