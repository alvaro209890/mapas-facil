# MXD — templates da série Análise de área (Fase W, 2026-07-29)

Rodada no **Windows + ArcMap 10.8** que fecha a preparação dos **20 templates `.mxd`**
da série Análise de área e registra todos no `MANIFEST.json` com `status: pronto`.

Complementa a entrega em PDF nativo documentada em
[`analise-de-area-serie.md`](analise-de-area-serie.md) e a integração desktop em
[`f28791c`](https://github.com/alvaro209890/mapas-facil/commit/f28791c).

## O que foi feito nesta rodada

### Templates versionados (`shared/templates/`)

| Grupo | Quantidade | Estado no MANIFEST |
|---|---|---|
| Série Análise de área (20 mapas) | 20 `.mxd` | `pronto` + `sha256` + offsets extent/escala |
| Galeria (`dinamica_retrato` + 4 modelos) | 5 `.mxd` | `pronto` |
| **Total** | **25 templates** | **25/25 `pronto`** — nenhum `a_preparar` |

Cada template da série tem campo `serie` no MANIFEST (ordem, `mapa_id`, baseline PDF).
Os binários foram derivados dos MXD-modelo do acervo Julio (`Testes/01_analise_04_Julio/Modelo/MXD/`)
via clonagem e normalização — **sem criar elementos de layout novos** (herdar, não inventar).

`python ferramentas/chaves_mxd.py verificar` → **Seguro para commit** (placeholders, zero chave real).

### Núcleo

| Módulo | Mudança |
|---|---|
| `analise/executar.py` | Aceita `saidas=("mxd", "pdf")`; reporta `mxd`, `pdf` e `pdf_arcmap` por mapa |
| `analise/serie.py` | Template id por receita alinhado ao MANIFEST |
| `galeria/estado.py` | Card `analise_de_area` com `mxd` valida **todos** os templates `serie` |
| `motores/minimapa_job.py` | Minimapa IBGE: retângulo, linha-guia e município por template da série |
| `motores/arcpy_ponte.py` | Ponte T1 para templates da série |
| `scripts/arcpy_job.py` | Job ArcPy generalizado para os 20 layouts (extent, escala, textos, SHP/) |
| `__main__.py` | `analise.executar` com `saidas` no payload NDJSON |

### App

| Arquivo | Mudança |
|---|---|
| `estado/galeria.ts` | `saidas_pedidas: ["mxd", "pdf"]` na listagem do card Análise de área |
| `shared/galeria/modelos.json` | `analise_de_area.saidas_padrao` → `["mxd", "pdf"]` |

### Ferramentas novas

| Script | Função |
|---|---|
| `detectar_arcmap.ps1` | W0 — ArcMap, ArcPy, licença → `output/w0_ambiente.json` |
| `clonar_elementos_layout_arcobjects.py` | Clona layout de MXD-modelo sem GUI manual |
| `preparar_templates_serie_mxd.ps1` | W3–W4 — normaliza, sentinelas, `registrar_template.py` |
| `auditar_templates_mxd.ps1` | Inspeciona todos os `.mxd` em `shared/templates/` |
| `analise_area_windows.ps1` | Orquestrador W1–W8 (pytest, smoke, commit opcional) |
| `smoke_serie_mxd.py` | Smoke W5 — série com `saidas=("mxd", "pdf")` + relatório JSON |

Ferramentas existentes ampliadas: `normalizar_mxd_arcpy.py`, `inspecionar_mxd_arcpy.py`,
`registrar_template.py`, `chaves_mxd.py` (cobre `shared/templates/`).

### Testes

- `test_galeria.py` — gate `analise_de_area` com 20 templates `pronto`
- `test_manifesto.py` — 25 templates, todos `pronto`
- `test_analise_serie.py` / `test_analise_progresso.py` — saídas `mxd`
- `test_bloco_b.py`, `test_minimapa.py` — minimapa por template da série

## Como rodar no Windows

```powershell
# Auditoria rápida dos templates
.\ferramentas\auditar_templates_mxd.ps1

# Smoke da série (MXD + PDF) num workspace com ATP
python Fase_1_Desktop\nucleo\.venv\Scripts\python.exe ferramentas\smoke_serie_mxd.py `
  --workspace C:\caminho\do\job `
  --atp-rel SHP\analise\ATP.shp

# Orquestrador completo (sem commit)
.\ferramentas\analise_area_windows.ps1 -SemCommit
```

Handoff anterior (não refazer B1/B2 da Harmonia):
[`handoff-windows-fase1.md`](handoff-windows-fase1.md).

## O que ainda falta (não bloqueado por esta rodada)

| Item | Nota |
|---|---|
| **W5/W6/W7** | Smoke MXD+PDF na Aruanã com relatório `output/w5_serie_mxd.json` e paridade |
| **M9** | Diff raster T1 × modelo &lt; 0,3% na Harmonia (última medição ~81%) |
| **M10** | Authenticode no instalador |
| **M11** | Piloto em PC limpo com técnico real |
| **Groq Vision** | Opcional — sem `groq_api_key` no cofre |
| **TCR** | Dado do escritório — anatomia 19/20 na Aruanã |

## Commits relacionados

| Commit | Conteúdo |
|---|---|
| `f28791c` | Galeria + progresso série + acervo raster + golden CI |
| `18f39ee` | CI Node 24 |
| *(este)* | Templates `.mxd` da série + MANIFEST 25/25 + ferramentas W3–W5 |
