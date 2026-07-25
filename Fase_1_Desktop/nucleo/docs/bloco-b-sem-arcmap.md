# Bloco B — o que dá para fazer sem ArcMap

Documentação do progresso do **motor `.mxd`** quando o desenvolvimento roda em Linux/CI
(sem ArcMap nem Python 2.7 do ArcGIS).

Plano de referência: [`../planos/04-motor-mxd.md`](../planos/04-motor-mxd.md)  
Checklist: [`../planos/13-checklist-implementacao.md`](../planos/13-checklist-implementacao.md)

## Resumo (v0.3.2)

| Item | Status | Onde |
|---|---|---|
| B1 — Preparar template no ArcMap | **Desbloqueado** (manual, Windows + ArcMap) | `ferramentas/inspecionar_mxd_arcpy.py` |
| B2 — `sha256` + offsets no MANIFEST | Parcial — `registrar_template.py` + leitor | `motores/manifesto.py`, `ferramentas/` |
| B3 — `arcpy_job.py` + ponte | **Esqueleto** pronto; só roda com ArcMap | `scripts/arcpy_job.py`, `motores/arcpy_ponte.py` |
| B4 — Materializar homônimos em `SHP/` | **Cópia** canônica (sem `ogr2ogr` ainda) | `camadas/materializar.py` |
| B5 — Extent / escala | Bbox via metadados do shapefile + conversão CRS | `motores/gerar.py` |
| B6–B7 — Textos, minimapa | Aguardam offsets/slots no MANIFEST | `motores/patch_mxd.py` |
| B8 — Patch T2 sem ArcMap | **Cópia do template** + patch quando offsets existirem | `motores/patch_mxd.py` |
| B9 — Comparar PDF com Harmonia | Não iniciado | — |

## Fluxo atual de `mapa.gerar`

```
MapSpec válido
    │
    ├─ materializar_camadas_em (ex.: SHP/)  →  ATP.shp, AVN.shp, AREA_CONSOLIDADA.shp …
    │
    ├─ saidas contém "mxd"
    │     └─ copia Referencias_IMAP/MXD/*.mxd → MXD/<nome_base>.mxd
    │        └─ patch de extent/escala SE o MANIFEST tiver offsets + sentinelas
    │
    └─ saidas contém "pdf"
          └─ renderizador nativo (matplotlib) + validacao.json
```

**Modo T3 implícito:** sem offsets no manifesto, o `.mxd` é cópia fiel do acervo (caminhos
relativos ainda apontam para o template original). O PDF nativo continua sendo a saída confiável
no Linux.

## Módulos novos

```
mapasfacil_nucleo/
  camadas/materializar.py    # nomes canônicos em SHP/
  geo/bbox_shp.py            # bbox do cabeçalho .shp (struct)
  motores/gerar.py           # orquestra materialização + MXD + PDF
  motores/patch_mxd.py       # cópia template + patch float64 LE
  motores/arcpy_ponte.py     # subprocesso py2.7, payload em MAPASFACIL_JOB_JSON
  scripts/arcpy_job.py       # NUNCA importado pelo núcleo 3.12
  workspace/zip_simcar.py    # listar/extrair ZIP SIMCAR (anti zip-slip)
```

## Métodos NDJSON adicionais

| Método | Descrição |
|---|---|
| `zip.listar` | Lista entradas e `.shp` dentro de um ZIP no workspace |
| `zip.extrair` | Extrai em `_extraido/<nome>/` com proteção zip-slip |
| `template.listar` | Templates do `shared/templates/MANIFEST.json` |
| `template.verificar` | `sha256` do `.mxd` de acervo vs manifesto |

## Preparação manual (B1/B2) — uma vez por template

Ferramentas em [`ferramentas/`](../../../ferramentas/README.md#preparação-de-template-b1b2--requer-arcmap).

1. `inspecionar_mxd_arcpy.py` — diagnóstico do que falta normalizar.
2. Trabalho no ArcMap: caminhos relativos, nomes canônicos, elementos de layout.
3. `preparar_sentinelas_arcpy.py` — extent/escala sentinela para offsets.
4. `registrar_template.py dinamica_retrato` — sha256 + offsets no MANIFEST.
5. Smoke: `doctor --json` + `mapa.gerar` no Windows com ArcMap.

## `doctor` no Windows

O comando `doctor` detecta ArcMap 10.x, licença via arcpy e define `motor_preferido`
(`arcpy` > `patch` > `nativo`). `pronto_para_mxd` exige template com sha256 e (patch pronto
ou ArcMap disponível).

## ArcPy — o que o usuário final **não** precisa fazer

- O caminho **T2** (patch) + PDF nativo cobre desenvolvimento e CI sem licença ArcGIS.
- **T1** (ArcPy) é referência para paridade máxima com a Harmonia; exige preparação B1 e máquina
  Windows com ArcMap 10.x.
- Exit code **124** após `save()` pode ser normal (trava no cleanup); validar pelo `ExportToPDF`
  seguinte — ver F1-04 §T1.

## Próximos passos técnicos

1. `ogr2ogr` na materialização (reprojeção para CRS do data frame).
2. Slots UTF-16LE para textos no T2.
3. Teste raster B9 contra `Referencias_IMAP/Mapas/01/Dinamica_2026.pdf`.
4. Integrar escolha T1 vs T2 em `doctor` — **feito** (`motor_preferido`).
