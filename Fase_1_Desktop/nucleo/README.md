# nucleo/

Sidecar Python da Fase 1 — geo, `MapSpec`, motores de `.mxd`/PDF, quantitativos e `fsguard`.
Comunica com o Electron por NDJSON (stdio), quando a UI existir. Empacotamento previsto:
PyInstaller onedir junto do app.

**Status:** M1 **bloco A fechado**; **bloco B parcial** (sem ArcMap). **v0.3.6**.

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
    bloco-b-sem-arcmap.md
  mapasfacil_nucleo/
    __main__.py             # loop NDJSON + CLI doctor
    protocolo.py
    config.py
    erros.py
    fsguard.py
    doctor.py
    geo/                    # area, crs, bbox_shp, ogr2ogr
    camadas/materializar.py
    workspace/              # indice, shapefile, zip_simcar, recibo_car, servico, papeis
    motores/
      manifesto.py
      gerar.py
      patch_mxd.py
      arcpy_ponte.py
      nativo.py             # PDF matplotlib + overlay tabela PNG
    scripts/arcpy_job.py    # py2.7 — NUNCA importado pelo núcleo 3.12
    validacao/
      relatorio.py
      comparar_pdf.py
    quantitativos/
      calcular.py
      xlsx.py
      png_tabela.py
      conferencia.py
    mapspec/
      validar.py
      diff.py
  tests/                    # anel 1 — CI Linux (133 testes coletados)
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

Registrados em `criar_roteador()` — 17 métodos:

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
| `mapa.gerar` | SHP/, cópia/patch `.mxd`, PDF nativo com overlay da tabela, quantitativos, `.xlsx`, PNG; `comparar_baseline` opcional |
| `quantitativos.calcular` | áreas a partir das camadas locais |
| `quantitativos.exportar_xlsx` | `*_Quantitativos.xlsx` (inclui aba Conferência) |
| `quantitativos.renderizar_png` | `recursos/tabela_quantitativos.png` (≥ 600 dpi) |
| `validacao.comparar_pdf` | diff raster entre PDFs (tolerância 0,3%) |
| `zip.listar` / `zip.extrair` | ZIP SIMCAR (anti zip-slip) |
| `template.listar` / `template.verificar` | MANIFEST; `sha256_ok` se hash registrado |

**Não implementado neste sidecar:** agente IA, chat, tools DeepSeek, cliente WFS/SEMA em runtime, UI Electron.

### Limites conhecidos (honestos)

- Doctor não detecta ArcMap/GDAL versão/rede fora do Windows.
- `dinamica_retrato` está `parcial` (sha256 ok; offsets `{}`). Os outros 4 templates estão `a_preparar` (`sha256: null`). `pronto_para_mxd` exige **todos** com sha256 e (patch `pronto` ou ArcMap sondado) — hoje fica `false`.
- PDF nativo é estrutural (não paridade visual Harmonia); já sobrepõe a tabela PNG quando `elementos_layout.tabela` (ou equivalente). Ordem de camadas: menor `ordem` por cima.
- Materialização B4: cópia + **ogr2ogr opcional** (fallback cópia se GDAL ausente).
- Sem agente: o núcleo só executa MapSpec / workspace / motores — não gera MapSpec por linguagem natural.

## CI

Workflow [`.github/workflows/nucleo.yml`](../../.github/workflows/nucleo.yml) — `pytest` anel 1 no Ubuntu,
cobertura 100% em `fsguard`, validação do MapSpec canônico em `shared/fixtures/mapspecs/`.

## Próximos passos (realidade)

- B1 manual no ArcMap: `TITULO`, `ROTULO_IMOVEL`, minimapa, logo → depois calibrar offsets (B2)
- Smoke Harmonia: PDF nativo vs `Mapas/01` ainda não passa (motor estrutural)
- Evoluir PDF nativo (F1-05): grade DMS, rosa, metadados, minimapa, logo
- UI Electron (M3) — pasta `app/` ainda não existe
- Agente (M4) — não iniciado
