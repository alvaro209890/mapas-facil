# shared/

Contratos versionados compartilhados pela **Fase 1** (desktop) e pela **Fase 2** (site/backend).

**Status (jul/2026):** catálogo geo versionado; schema `MapSpec` e `contract_version` **2**;
manifesto de templates com `dinamica_retrato` **parcial** (sha256 registrado, offsets vazios);
demais templates `a_preparar`; núcleo **v0.3.6**.

## Conteúdo atual

```
shared/
  catalog/
    README.md
    camadas.json              # 41 camadas
    servicos_geo.json         # provedores WFS/WMS/REST/XYZ
    sema_layers_live.json     # GetCapabilities SEMA (live)
    mosaicos_sema.json
    simcar_template_map.json
  schemas/
    mapspec.schema.json       # contract_version 2
    README.md
  templates/
    MANIFEST.json             # dinamica_retrato parcial; 4 a_preparar
    Dinamica_retrato.mxd      # template preparado (B1 parcial)
    README.md
  fixtures/
    mapspecs/
      dinamica_2026_canonico.json   # único MapSpec de fixture (válido)
    README.md
  contract_version.json       # 2 — alinhado ao schema MapSpec
```

O padrão visual Harmonia (geometria, cores, checks) **não** vive em `shared/` — está em
[`../planos/01-padrao-imap-harmonia.md`](../planos/01-padrao-imap-harmonia.md).
Não há pasta `shared/styles/` no repositório.

Documentação operacional do catálogo:
[`../planos/03-wfs-e-servicos-geo.md`](../planos/03-wfs-e-servicos-geo.md).

Contrato do `MapSpec`:
[`../planos/02-mapspec-contrato.md`](../planos/02-mapspec-contrato.md).

Qualquer mudança de schema ou catálogo incrementa `contract_version` e atualiza o plano
comum afetado **no mesmo PR** — nunca só num plano de fase.

Os gabaritos visuais (PDFs e MXDs modelo) ficam em
[`../Referencias_IMAP/`](../Referencias_IMAP/README.md) — não misturar com os templates
operacionais em `shared/templates/`.
