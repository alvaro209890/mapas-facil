# nucleo/

Sidecar Python da Fase 1 — geo, `MapSpec`, motores de `.mxd`/PDF, agente e `fsguard`.
Comunica com o Electron por NDJSON (stdio). Empacotado junto do app (PyInstaller onedir).

**Status:** esqueleto. Implementação começa no milestone **M1**
([`../planos/12-roadmap.md`](../planos/12-roadmap.md)).

Planos: [`03-nucleo-python.md`](../planos/03-nucleo-python.md),
[`04-motor-mxd.md`](../planos/04-motor-mxd.md),
[`01-arquitetura.md`](../planos/01-arquitetura.md).

## Quando existir código

```
nucleo/
  mapasfacil_nucleo/
    __main__.py           # loop NDJSON
    workspace/
    camadas/
    mapspec/
    motores/              # mxd, pdf nativo, xlsx
    agente/
    cofre/
    doctor/
    fsguard.py
    scripts/
      arcpy_job.py        # Python 2.7 (ArcMap), payload em arquivo JSON
  tests/
  pyproject.toml
```

Distribuição: dentro do instalador Electron — ver
[`11-empacotamento-instalador.md`](../planos/11-empacotamento-instalador.md).
