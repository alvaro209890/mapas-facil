# shared/

Contratos versionados compartilhados por `web/`, `backend/` e `agent/`.

**Status:** esqueleto. Schemas e catálogo entram no primeiro PR de código (antes de M1).

## O que vai viver aqui

```
shared/
  schemas/
    mapspec.schema.json
  catalog/
    camadas.json          # WFS/WMS permitidos
    templates.json        # manifesto dos .mxd
  templates/              # cópias canônicas dos .mxd IMAP (ou refs)
    MANIFEST.json
  styles/                 # .lyr oficiais (ATP, AVN, AC, AUAS…)
  contract_version.json   # versão do contrato (int)
```

Qualquer mudança de schema ou catálogo incrementa `contract_version` e atualiza
[01-arquitetura.md](../planos/01-arquitetura.md) no mesmo PR.

Os gabaritos visuais (PDFs e MXDs modelo) ficam em
[`../Referencias_IMAP/`](../Referencias_IMAP/README.md) — não misturar com os templates
operacionais que o agente copia para o PC do usuário.
