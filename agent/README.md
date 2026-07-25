# agent/

Agente local Windows — conecta ao backend por WebSocket, resolve camadas no PC e gera
`.mxd` + `.pdf` com ArcMap (`arcpy`) ou ArcGIS Pro (`arcpy.mp`).

**Status:** esqueleto. Implementação começa no milestone M2 ([planos/10-roadmap.md](../planos/10-roadmap.md)).

Planos: [04-agente-local.md](../planos/04-agente-local.md), [05-motor-mxd-pdf.md](../planos/05-motor-mxd-pdf.md).

## Requisitos no PC do usuário

- Windows 10/11
- ArcMap 10.6+ **ou** ArcGIS Pro 3.x
- Pastas autorizadas configuradas no pareamento

## Quando existir código

```
agent/
  mapasfacil_agent/
    main.py               # tray / serviço
    ws_client.py
    jobs.py
    doctor.py
    fsguard.py
    layers/
    arcpy_runner.py
    scripts/
      arcpy_export.py     # Python 2.7 (ArcMap)
      arcpy_pro_export.py # Python 3 (Pro)
  installer/              # Inno Setup
  tests/
```

Distribuição: instalador `.exe` assinado (ver [12-deploy-e-distribuicao.md](../planos/12-deploy-e-distribuicao.md)).
