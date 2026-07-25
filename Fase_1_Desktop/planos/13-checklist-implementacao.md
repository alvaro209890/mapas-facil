# F1-13 — Checklist de implementação (kickoff)

Lista operacional da Fase 1. Complementa o [roadmap](12-roadmap.md).

Estado em 2026-07-25: **M0 fechado** · **bloco A fechado** (com correções de auditoria) ·
**bloco B parcial** (sem ArcMap). Próximo bloqueante: B1 no Windows.

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
| A8 | pytest + CI | [x] | |

## Bloco B — Motor `.mxd` (M2)

Detalhe: [`../nucleo/docs/bloco-b-sem-arcmap.md`](../nucleo/docs/bloco-b-sem-arcmap.md).

| # | Tarefa | Feito |
|---|---|---|
| B1 | Preparar template Dinâmica 2026 no ArcMap | [ ] bloqueado (manual) |
| B2 | MANIFEST sha256 + offsets | [~] leitor + `template.verificar`; hash ainda null |
| B3 | `arcpy_job.py` + ponte | [x] esqueleto |
| B4 | Materializar SHP/ | [~] cópia canônica (sem ogr2ogr) |
| B5 | Extent bbox `.shp` | [~] via metadados |
| B6 | Textos / definition query | [ ] |
| B7 | Minimapa retângulo + guia | [ ] |
| B8 | Patch T2 sem ArcMap | [~] cópia template |
| B9 | Diff raster vs `Mapas/01` | [ ] |

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
