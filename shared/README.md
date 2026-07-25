# shared/

Contratos versionados compartilhados pela **Fase 1** (desktop) e pela **Fase 2** (site/backend).

**Status:** catálogo geo já versionado; schema do `MapSpec` e manifesto de templates entram
ainda no M0 / início do M1.

## Conteúdo atual

```
shared/
  catalog/
    README.md
    camadas.json          # 32 camadas (Cerebro/NexoGeo, GetCapabilities SEMA 2026-07-08)
    servicos_geo.json     # provedores WFS/WMS/REST/XYZ
  schemas/                # mapspec.schema.json (a criar / completar no M0)
  templates/              # (a criar) manifesto dos .mxd operacionais
  styles/                 # (a criar) .lyr oficiais ATP/AVN/AC/AUAS
  contract_version.json   # (a criar)
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
