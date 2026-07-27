# M2 — entrega real Harmonia (2026-07-27)

Rodada neste PC (Windows + ArcMap 10.8). **M2 fechado** em 2026-07-27 via script automatizado.

## Script de fechamento (use daqui pra frente)

ArcMap **fechado**:

```powershell
cd C:\GIS\mapas-facil
powershell -ExecutionPolicy Bypass -File ferramentas\fechar_m2_windows.ps1
```

O que o script faz, em ordem:

1. `fechar_m2_template_arcpy.py` — materializa `shared/templates/SHP/`, corrige `AC` (recria fora do grupo `BASEMAP` quebrado), reconecta IBGE/LOGO/PERIMETRO
2. `preparar_sentinelas_arcpy.py` + `registrar_template.py` — recalibra B2 no MANIFEST
3. `chaves_mxd.py limpar` + `verificar`
4. `inspecionar_mxd_arcpy.py` — confirma `broken: []`
5. `smoke_m2_harmonia.py` — T1 (ArcPy) e T2 (patch)
6. `pytest` do núcleo

Relatório consolidado: `output/m2_fechamento_relatorio.json` (gitignored).

## Pasta do projeto de teste

`C:\Users\Usuario\Downloads\Analise_de_area\Analise_de_área-Julio Barbosa_ 4_Harmonia`

## Artefatos gerados (T1)

Em `Mapas/` do projeto Harmonia:

| Arquivo | O quê |
|---|---|
| `Dinamica_2026_MapasFacil_M2.mxd` | Motor **arcpy** (T1), minimapa IBGE |
| `Dinamica_2026_MapasFacil_M2_arcmap.pdf` | Export ArcMap 300 dpi |
| `Dinamica_2026_MapasFacil_M2.pdf` | PDF **nativo** (ReportLab + overlay tabela) |
| `*_validacao.json` / `*_relatorio_m2.json` | checks + metadados |

T2: `MXD/Dinamica_2026_MapasFacil_M2_T2.mxd` com `motor: patch`.

## Critérios GUIA §1.5 (2026-07-27)

| Critério | Estado |
|---|---|
| `.mxd` abre sem `!` vermelho | **ok** — `broken: []` no template e no T1 (`relatorio_arcpy.quebradas: []`) |
| T2 gera `.mxd` útil | **ok** (`motor: patch`) |
| PDF ArcMap + PDF nativo | **ok** |
| Timeout `AG-020` | **ok** |
| `dinamica_retrato` `status: pronto` | **ok** — sha256 recalibrado após fix AC |
| Sem texto de análise anterior | **parcial** — `ROTULO_IMOVEL` genérico no montar; METADADOS do template |
| Checklist + AGENT_BRIEF | **ok** |

## Correção técnica da camada AC

A `AC` estava aninhada em `BASEMAP\AC` com datasource nulo — `replaceDataSource` não funciona nesse tipo de layer. O script:

- recria `AC` na raiz do data frame `MAPA` a partir de `shared/templates/SHP/AREA_CONSOLIDADA.shp`
- remove o grupo `BASEMAP` (só continha a AC fantasma)

## Diferença PDF ArcMap vs nativo

| | ArcMap (`*_arcmap.pdf`) | Nativo (`*.pdf`) |
|---|---|---|
| Conteúdo | Layout do `.mxd` | Estrutural A4 + geometrias + tabela PNG |
| Paridade Harmonia | referência T1 | **não** é paridade &lt; 0,3% (isso é **M9**) |

## Próximo marco

**M9** — série Harmonia, diff raster &lt; 0,3%, portabilidade para outro PC.
