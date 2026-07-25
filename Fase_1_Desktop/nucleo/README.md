# nucleo/

Sidecar Python da Fase 1 — geo, `MapSpec`, motores de `.mxd`/PDF, agente e `fsguard`.
Comunica com o Electron por NDJSON (stdio). Empacotado junto do app (PyInstaller onedir).

**Status:** M1 **bloco A fechado** (auditoria 2026-07-25); **bloco B parcial** (sem ArcMap). v0.3.1.

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
      nativo.py           # PDF mínimo (matplotlib)
    scripts/
      arcpy_job.py        # py2.7 — NUNCA importado pelo núcleo 3.12
    validacao/relatorio.py
    mapspec/
      validar.py          # schema JSON + regras (NU-210, NU-220…)
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

### Métodos implementados (v0.3.1)

| Método | Descrição |
|---|---|
| `ping` | smoke test |
| `doctor.rodar` | diagnóstico (stub em Linux; ArcMap/chave/rede no Windows) |
| `mapspec.validar` | schema + catálogo + invariantes (CRS, pasta, minimapa, metadados) |
| `workspace.abrir` | indexa pasta + lê recibo do CAR (`id_local` = stem do `.shp`) |
| `workspace.reindexar` | atualiza índice |
| `workspace.inspecionar` | metadados de `.shp` ou PDF |
| `car.ler_recibo` | parser do recibo (sem CPF) |
| `mapa.gerar` | materializa SHP/, cópia/patch `.mxd`, PDF nativo |
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
- `ogr2ogr` na materialização; patch de textos (slots UTF-16LE)
- Comparar PDF com baseline Harmonia (`Mapas/01`)
