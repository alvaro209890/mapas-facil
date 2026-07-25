# shared/

Contratos versionados compartilhados pela **Fase 1** (desktop) e pela **Fase 2** (site/backend).

**Status:** catálogo geo versionado; schema `MapSpec` (contract_version 2); manifesto de templates
com `dinamica_retrato` parcial; núcleo v0.3.3.

## Conteúdo atual

```
shared/
  catalog/
    README.md
    camadas.json          # 32 camadas (Cerebro/NexoGeo, GetCapabilities SEMA 2026-07-08)
    servicos_geo.json     # provedores WFS/WMS/REST/XYZ
  schemas/                # mapspec.schema.json (contract_version 2)
  templates/              # MANIFEST.json (dinamica_retrato parcial; demais a_preparar)
  fixtures/mapspecs/      # dinamica_2026_canonico.json
  contract_version.json   # 2 — alinhado ao schema MapSpec
```

Documentação operacional do catálogo:
[`../planos/03-wfs-e-servicos-geo.md`](../planos/03-wfs-e-servicos-geo.md).

Contrato do `MapSpec`:
[`../planos/02-mapspec-contrato.md`](../planos/02-mapspec-contrato.md).

Qualquer mudança de schema ou catálogo incrementa `contract_version` e atualiza o plano
comum afetado **no mesmo PR** — nunca só num plano de fase.

Os gabaritos visuais (PDFs e MXDs modelo) ficam em
[`../Referencias_IMAP/`](../Referencias_IMAP/README.md) — não misturar com os templates
operacionais que o app copia para o PC do usuário.
