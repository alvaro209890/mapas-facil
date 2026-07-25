# F1-13 — Checklist de implementação (kickoff)

Lista operacional da Fase 1. Complementa o [roadmap](12-roadmap.md).

Estado em 2026-07-25: **M0 fechado** · **bloco A fechado** · **bloco B parcial** (v0.3.5) — B1
automatizado parcialmente via arcpy (`ferramentas/normalizar_mxd_arcpy.py`); faltam 4
elementos de layout que só a GUI do ArcMap cria.

## Pré-voo

- [x] Repositório em duas fases + planos comuns
- [x] Acervo `Mapas/01` (Harmonia), `02` (Trevisol), `03` (SIMCAR + L5)
- [x] Schema MapSpec + MANIFEST stub + fixture canônica
- [x] Chaves fora dos `.mxd` versionados
- [x] Núcleo Python com CI anel 1

---

## Bloco A — Fundação do núcleo (M1)

| # | Tarefa | Feito | Nota |
|---|---|---|---|
| A1 | Scaffold + NDJSON | [x] | |
| A2 | `fsguard` 100% cobertura | [x] | |
| A3 | Schema + validador + invariantes | [x] | CRS geo, pasta, minimapa, metadados, operadores `<>` |
| A4 | workspace abrir/reindexar/inspecionar | [x] | `id_local` = stem (sem colisão ARL_*) |
| A5 | Parser recibo CAR (sem CPF) | [x] | |
| A6 | CLI `doctor` | [x] | stub Linux; ArcMap/rede só no Windows |
| A7 | PDF nativo + `validacao.json` | [x] | ordem de desenho: menor `ordem` por cima |
| A8 | pytest + CI | [x] | 129 testes anel 1 (jul/2026) |

## Bloco A+ — Quantitativos e validação visual (anel 1, sem ArcMap)

| # | Tarefa | Feito | Nota |
|---|---|---|---|
| Q1 | `quantitativos.calcular` a partir das camadas locais | [x] | áreas em ha, `TOTAL GERAL`, conferência com `MapSpec.tabela` |
| Q2 | Export `.xlsx` (F1-08) | [x] | abas Quantitativos, Detalhamento, Conferência, Avisos, Fontes |
| Q3 | `mapspec.diff` entre versões | [x] | diff por `id` de camada; NDJSON `mapspec.diff` |
| Q4 | PNG da tabela ≥ 600 dpi (F1-08) | [x] | `recursos/tabela_quantitativos.png`; NDJSON `quantitativos.renderizar_png` |
| Q5 | Aba Conferência recibo × calculado | [x] | `quantitativos/conferencia.py`; diferença ha e % |
| V1 | `validacao.comparar_pdf` (diff raster B9) | [x] | PyMuPDF + numpy; tolerância 0,3% padrão |
| V2 | Integração em `mapa.gerar` (`comparar_baseline`) | [x] | usa `baseline_pdf` do MANIFEST quando pedido |
| V3 | Smoke Harmonia vs `Mapas/01` | [ ] | infra pronta; baseline real ainda não passa (PDF nativo estrutural) |

## Bloco B — Motor `.mxd` (M2)

Detalhe: [`../nucleo/docs/bloco-b-sem-arcmap.md`](../nucleo/docs/bloco-b-sem-arcmap.md).

| # | Tarefa | Feito |
|---|---|---|
| B1 | Preparar template Dinâmica 2026 no ArcMap | [~] automatizado via `normalizar_mxd_arcpy.py` (data frames, camadas, metadados, norte, logo, legenda); faltam `TITULO`, `ROTULO_IMOVEL` (texto) e `MINIMAPA_RETANGULO`/`MINIMAPA_GUIA` (gráficos) — só GUI cria elemento novo |
| B2 | MANIFEST sha256 + offsets | [~] `dinamica_retrato` com sha256 registrado, `status: parcial`; offsets ainda pendem de B1 terminar (senão invalidam) |
| B3 | `arcpy_job.py` + ponte | [x] esqueleto |
| B4 | Materializar SHP/ | [~] cópia + ogr2ogr opcional |
| B5 | Extent bbox `.shp` | [~] via metadados |
| B6 | Textos / definition query | [~] infra UTF-16LE; falta MANIFEST |
| B7 | Minimapa retângulo + guia | [ ] aguarda B1 |
| B8 | Patch T2 sem ArcMap | [~] cópia do template preparado (`resolver_caminho_preparado`) |
| B9 | Diff raster vs `Mapas/01` | [~] | `validacao/comparar_pdf.py` + testes; smoke Harmonia manual pendente |

## Regras de ouro

1. Nunca `Describe` / `replaceDataSource` / cursores no ArcPy desta família.
2. Geometria → `ogr2ogr`. Extent → header do `.shp`. Fonte → homônimo + `findAndReplaceWorkspacePaths`.
3. Baseline visual = `Mapas/01/`, nunca `02/`.
4. `chaves_mxd.py limpar` antes de commit que toque `.mxd`.
5. IA não gera código — só MapSpec validado.

## Leitura

1. [`01-arquitetura.md`](01-arquitetura.md)  
2. [`04-motor-mxd.md`](04-motor-mxd.md)  
3. [`DOCUMENTACAO_MXD_HARMONIA.md`](../../Referencias_IMAP/MXD/DOCUMENTACAO_MXD_HARMONIA.md)  
4. Este checklist  
