# Handoff Windows — Fase 1 (o que falta de você)

Atualizado: **2026-07-27** (Acer Aspire + ArcMap 10.8).  
Quem continua: você, amanhã, em **outro PC Windows** (com ArcMap 10.6–10.8).

Leia junto: [`Fase_1_Desktop/GUIA_WINDOWS.md`](../Fase_1_Desktop/GUIA_WINDOWS.md) ·
[`AGENT_BRIEF.md`](../AGENT_BRIEF.md).

---

## O que já foi feito neste PC (não refaça)

| Item | Estado |
|---|---|
| Planet removido + GUI save nos MXDs do acervo | feito (PR #13) |
| Base IBGE no repo + minimapa conectado (62 MXDs) | feito (PR #14) |
| IA detecta minimapa + `gerar_mapa` T1/T2 | feito (PR #15 + fix CI) |
| **B1 parcial** em `shared/templates/Dinamica_retrato.mxd` | **feito por script** |
| **B2** — `status: pronto` + offsets extent/escala no MANIFEST | **feito** |
| Logo embutido em `shared/templates/recursos/logo_imap_tom_escuro.png` | feito |
| `chaves_mxd.py verificar` | Seguro para commit |
| pytest anel 1 (local) | verde |

### Template `dinamica_retrato` agora tem

- Camadas canônicas: `PERIMETRO`, `AC`, `MUNICIPIOS`, `UF`, `BASEMAP`
- Textos: `TITULO`, `METADADOS`, `ROTULO_MUNICIPIO`, `UF_SELO`
- Layout: `LEGENDA`, `NORTE`, `LOGO` (com PNG), `MINIMAPA_RETANGULO`, `MINIMAPA_GUIA`
- Data frames: `MAPA`, `MINIMAPA`, `UF_INSET`
- MANIFEST: `status: "pronto"`, sha256 + offsets de extent/escala (T2 patch)
- Extent do template = **sentinelas** (valores artificiais). Na geração, T2/T1 substituem pelo bbox real.

### Scripts novos / melhorados

| Script | Uso |
|---|---|
| `ferramentas/corrigir_template_b1_arcpy.py` | Reaplica LOGO + nomes do minimapa |
| `ferramentas/preparar_sentinelas_arcpy.py` | Agora grava `.mxd.sentinelas.json` com extent **real** pós-aspecto |
| `ferramentas/registrar_template.py` | Lê o sidecar para achar offsets (BOM UTF-8 ok) |
| `ferramentas/normalizar_mxd_arcpy.py` | Não sobrescreve mais nomes canônicos do minimapa |

---

## O que **só você** precisa fazer (GUI ArcMap) — ~15–30 min

### 1. Criar `ROTULO_IMOVEL` (única pendência B1 automática)

`arcpy.mapping` **não cria** TextElement novo. Falta no diagnóstico (`pronto_b1: false` só por isto).

1. `git pull origin main`
2. Abra **só a cópia** `shared/templates/Dinamica_retrato.mxd` no ArcMap  
   (extents vão parecer “estranhos” — são sentinelas; ignore)
3. Insert → Text → digite `Fazenda Harmonia` (ou `{imovel}`)
4. Properties → **Element Name** = `ROTULO_IMOVEL`
5. Posicione perto do perímetro (como no PDF `Referencias_IMAP/Mapas/01/Dinamica_2026.pdf`)
6. File → Save (versão mínima **10.6**)
7. Feche o ArcMap

### 2. Confirmar visualmente a `LEGENDA`

Há 2 legendas no layout; o script nomeou a **maior** como `LEGENDA`.  
Confirme que é a do `MAPA` (não a do minimapa). Se estiver invertido, troque os nomes na GUI.

### 3. Recalibrar B2 (obrigatório depois de editar o .mxd)

Qualquer save na GUI **move** offsets binários:

```powershell
cd C:\caminho\mapas-facil
git pull origin main

# Backup
copy shared\templates\Dinamica_retrato.mxd shared\templates\Dinamica_retrato.pre_b2.bak

# Sentinelas + sidecar
C:\Python27\ArcGIS10.8\python.exe ferramentas\preparar_sentinelas_arcpy.py shared\templates\Dinamica_retrato.mxd

# MANIFEST
Fase_1_Desktop\nucleo\.venv\Scripts\python.exe ferramentas\registrar_template.py dinamica_retrato shared\templates\Dinamica_retrato.mxd

# Segurança
Fase_1_Desktop\nucleo\.venv\Scripts\python.exe ferramentas\chaves_mxd.py limpar
Fase_1_Desktop\nucleo\.venv\Scripts\python.exe ferramentas\chaves_mxd.py verificar

# Inspecionar
C:\Python27\ArcGIS10.8\python.exe ferramentas\inspecionar_mxd_arcpy.py shared\templates\Dinamica_retrato.mxd -o inspecao_template.json
```

Esperado: `pronto_b1: true` e MANIFEST `status: pronto` com extent+escala.

### 4. Smoke de geração (este PC ou o de amanhã)

```powershell
cd Fase_1_Desktop\nucleo
.\.venv\Scripts\Activate.ps1
pytest tests/test_bloco_b.py::test_gerar_mapa_com_mxd_e_pdf -q
python -m mapasfacil_nucleo doctor --json
```

No app: abrir pasta Harmonia → galeria Dinâmica 2026 → gerar `mxd`+`pdf`.  
Com ArcMap: motor `arcpy` (T1) + minimapa IBGE. Sem ArcMap no PATH do job: T2 patch.

---

## Depois disso (ordem fixa — não pule)

| Marco | O quê | Exige você? |
|---|---|---|
| **M2 fechar** | Critérios do `GUIA_WINDOWS.md` §1.5 + checklist B + `AGENT_BRIEF` | sim (após passo 1–4) |
| **M9** | Série Harmonia, diff &lt; 0,3%, S11 | sim (ArcMap + tempo) |
| **M10** | Instalador NSIS / PyInstaller | sim (Windows) |
| **M11** | Piloto com usuário real | sim |

M9–M11 **não** foram iniciados de propósito — o roadmap exige M2 completo antes.

---

## Setup no outro PC (cola)

```powershell
git clone https://github.com/alvaro209890/mapas-facil.git
cd mapas-facil
git checkout main
git pull

cd Fase_1_Desktop\nucleo
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest -q

cd ..\app
pnpm install
pnpm test
```

Python do ArcMap (não misturar com o 3.12):

`C:\Python27\ArcGIS10.8\python.exe` (ajuste 10.6/10.7 se for o caso).

---

## App Electron neste Acer

`pnpm`/`vitest`: o teste de CDN em `tema-default` foi reescrito sem `grep` (Windows).
Rode `pnpm test` no outro PC após `pnpm install`.


- `*.mxd.bak`, `*.pre_sentinela.bak`, `*.sentinelas.json`
- `inspecao_*.json`, `normalizacao_relatorio.json`, `relatorio_planet_falhas.json`
- `secrets.local.json`

Se o logo no ArcMap apontar para caminho absoluto de outra máquina: rode

```powershell
C:\Python27\ArcGIS10.8\python.exe ferramentas\corrigir_template_b1_arcpy.py `
  shared\templates\Dinamica_retrato.mxd `
  --logo shared\templates\recursos\logo_imap_tom_escuro.png
```

e **recalibre B2** (passo 3).
