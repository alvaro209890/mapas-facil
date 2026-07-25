# shared/

Contratos versionados compartilhados por `web/`, `backend/` e `agent/`.

**Status:** catálogo geo já versionado; schemas JSON entram no primeiro PR de código (M1).

## Conteúdo atual

```
shared/
  catalog/
    README.md
    camadas.json          # 32 camadas (Cerebro/NexoGeo, GetCapabilities SEMA 2026-07-08)
    servicos_geo.json     # provedores WFS/WMS/REST/XYZ
  schemas/                # (a criar) mapspec.schema.json
  templates/              # (a criar) manifesto dos .mxd operacionais
  styles/                 # (a criar) .lyr oficiais ATP/AVN/AC/AUAS
  contract_version.json   # (a criar)
```

Documentação operacional do catálogo: [`../planos/13-wfs-e-servicos-geo.md`](../planos/13-wfs-e-servicos-geo.md).

Qualquer mudança de schema ou catálogo incrementa `contract_version` e atualiza
[01-arquitetura.md](../planos/01-arquitetura.md) no mesmo PR.

Os gabaritos visuais (PDFs e MXDs modelo) ficam em
[`../Referencias_IMAP/`](../Referencias_IMAP/README.md) — não misturar com os templates
operacionais que o agente copia para o PC do usuário.
