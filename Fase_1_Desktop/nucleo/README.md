# nucleo/

Sidecar Python da Fase 1 — geo, `MapSpec`, motores de `.mxd`/PDF, agente e `fsguard`.
Comunica com o Electron por NDJSON (stdio). Empacotado junto do app (PyInstaller onedir).

**Status:** M1 em andamento — bloco A (fundação) iniciado.

Planos: [`../planos/03-nucleo-python.md`](../planos/03-nucleo-python.md),
[`../planos/04-motor-mxd.md`](../planos/04-motor-mxd.md),
[`../planos/01-arquitetura.md`](../planos/01-arquitetura.md).

## Estrutura

```
nucleo/
  pyproject.toml
  mapasfacil_nucleo/
    __main__.py           # loop NDJSON + CLI doctor
    protocolo.py          # envelope req/res/evt
    config.py             # caminhos shared/, escalas permitidas
    erros.py              # ErroNucleo, CaminhoNaoAutorizado
    fsguard.py            # allowlist de disco (100% cobertura)
    doctor.py             # diagnóstico do ambiente
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

### Métodos implementados (v0.1.0)

| Método | Descrição |
|---|---|
| `ping` | smoke test |
| `doctor.rodar` | diagnóstico do ambiente |
| `mapspec.validar` | schema + catálogo + invariantes |

## CI

Workflow [`.github/workflows/nucleo.yml`](../../.github/workflows/nucleo.yml) — `pytest` anel 1 no Ubuntu,
cobertura 100% em `fsguard`, validação do MapSpec canônico em `shared/fixtures/mapspecs/`.

## Próximos passos (bloco A)

- `workspace.abrir` / `reindexar` / `inspecionar`
- Parser do recibo do CAR
- PDF nativo mínimo + `validacao.json`
