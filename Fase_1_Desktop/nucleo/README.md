# nucleo/

Sidecar Python da Fase 1 — geo, `MapSpec`, motores de `.mxd`/PDF, agente e `fsguard`.
Comunica com o Electron por NDJSON (stdio). Empacotado junto do app (PyInstaller onedir).

**Status:** M1 **bloco A fechado**; **bloco B parcial** (sem ArcMap). v0.3.6.

Acervo de calibração: [`Referencias_IMAP/Mapas/03/`](../../Referencias_IMAP/Mapas/03/README.md).

Documentação do bloco B: [`docs/bloco-b-sem-arcmap.md`](docs/bloco-b-sem-arcmap.md).
Checklist: [`../planos/13-checklist-implementacao.md`](../planos/13-checklist-implementacao.md).

Planos: [`../planos/03-nucleo-python.md`](../planos/03-nucleo-python.md),
[`../planos/04-motor-mxd.md`](../planos/04-motor-mxd.md),
[`../planos/01-arquitetura.md`](../planos/01-arquitetura.md).

## Estrutura

```
nucleo/
  pyproject.toml
  docs/
    bloco-b-sem-arcmap.md   # progresso B1–B9 sem ArcMap
  mapasfacil_nucleo/
    __main__.py           # loop NDJSON + CLI doctor
    protocolo.py          # envelope req/res/evt
    config.py             # caminhos shared/, escalas permitidas
    erros.py              # ErroNucleo, CaminhoNaoAutorizado
    fsguard.py            # allowlist de disco (100% cobertura)
    doctor.py             # diagnóstico do ambiente
    geo/                  # zona UTM, área, bbox do .shp
    camadas/              # materialização SHP/ canônico
    workspace/            # índice, shapefile, ZIP SIMCAR, recibo CAR
    motores/
      manifesto.py        # MANIFEST.json + sha256
      gerar.py            # orquestra MXD + PDF
      patch_mxd.py        # cópia template + patch T2
      arcpy_ponte.py      # subprocesso ArcPy (Windows)
      nativo.py           # PDF mínimo (matplotlib) + overlay tabela PNG
    scripts/
      arcpy_job.py        # py2.7 — NUNCA importado pelo núcleo 3.12
    validacao/
      relatorio.py
      comparar_pdf.py   # diff raster B9 (anel 1)
    quantitativos/
      calcular.py       # áreas por camada local (F1-08)
      xlsx.py           # export .xlsx estilizado (F1-08)
      png_tabela.py     # PNG ≥ 600 dpi para o mapa (F1-08)
      conferencia.py    # recibo CAR × áreas calculadas
    mapspec/
      validar.py
      diff.py           # diff entre versões do MapSpec
  tests/                  # anel 1 — roda no CI Linux
```

## Desenvolvimento

Requisitos: **Python 3.12+**.

```bash
cd Fase_1_Desktop/nucleo
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

### CLI

```bash
# Diagnóstico (humano ou JSON)
python -m mapasfacil_nucleo doctor
python -m mapasfacil_nucleo doctor --json

# Loop NDJSON (como o Electron vai usar)
python -m mapasfacil_nucleo stdio
```

Exemplo de requisição NDJSON:

```json
{"v":1,"id":"01J8X","tipo":"req","metodo":"mapspec.validar","params":{"mapspec":{…}}}
```

### Métodos implementados (v0.3.6)

| Método | Descrição |
|---|---|
| `ping` | smoke test |
| `doctor.rodar` | diagnóstico (stub em Linux; ArcMap/chave/rede no Windows) |
| `mapspec.validar` | schema + catálogo + invariantes (CRS, pasta, minimapa, metadados) |
| `mapspec.diff` | lista operações entre duas versões do MapSpec |
| `workspace.abrir` | indexa pasta + lê recibo do CAR (`id_local` = stem do `.shp`) |
| `workspace.reindexar` | atualiza índice |
| `workspace.inspecionar` | metadados de `.shp` ou PDF |
| `car.ler_recibo` | parser do recibo (sem CPF) |
| `mapa.gerar` | materializa SHP/, cópia/patch `.mxd`, PDF nativo **com overlay da tabela**, quantitativos, `.xlsx`, PNG tabela; `comparar_baseline` opcional |
| `quantitativos.calcular` | tabela de áreas a partir das camadas locais |
| `quantitativos.exportar_xlsx` | grava `*_Quantitativos.xlsx` (inclui aba Conferência com recibo) |
| `quantitativos.renderizar_png` | grava `recursos/tabela_quantitativos.png` (≥ 600 dpi) |
| `validacao.comparar_pdf` | diff raster entre dois PDFs (B9, tolerância 0,3%) |
| `zip.listar` / `zip.extrair` | ZIP SIMCAR (anti zip-slip) |
| `template.listar` / `template.verificar` | MANIFEST; `sha256_ok` só se hash registrado |

### Limites conhecidos (honestos)

- Doctor não detecta ArcMap/GDAL versão/rede fora do Windows.
- Templates do MANIFEST ainda `a_preparar` (`sha256: null`) → aviso `AG-030`, `pronto_para_mxd: false`.
- PDF nativo é estrutural (não Harmonia visual); ordem de camadas: menor `ordem` por cima.
- Materialização B4 ainda é cópia, sem `ogr2ogr`.

## CI

Workflow [`.github/workflows/nucleo.yml`](../../.github/workflows/nucleo.yml) — `pytest` anel 1 no Ubuntu,
cobertura 100% em `fsguard`, validação do MapSpec canônico em `shared/fixtures/mapspecs/`.

## Próximos passos (bloco B)

- B1 manual: preparar template Dinâmica 2026 no ArcMap + offsets no MANIFEST
- `ogr2ogr` na materialização — feito (opcional); patch de textos aguarda offsets
- Smoke Harmonia: comparar PDF nativo com `Mapas/01` via `validacao.comparar_pdf` ou `mapa.gerar` com `comparar_baseline: true`
- Export `.xlsx` (com Conferência) e PNG da tabela — feitos; overlay no PDF nativo feito
- Evoluir PDF nativo (F1-05): grade DMS, rosa, metadados, minimapa, logo
