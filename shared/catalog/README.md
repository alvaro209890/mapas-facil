# Catálogo compartilhado

Arquivos machine-readable consumidos por `backend/`, `agent/` e (somente metadados) `web/`.

| Arquivo | Origem | Conteúdo |
|---|---|---|
| [`camadas.json`](camadas.json) | Cerebro-Geo-IA / NexoGeo (GetCapabilities SEMA 2026-07-08) | 32 camadas com `id` estável |
| [`servicos_geo.json`](servicos_geo.json) | Cerebro-Geo-IA | provedores WFS/WMS/REST/XYZ |

**Não contém credenciais.** O campo `auth` é o *nome* do segredo (`sema_authkey`), nunca o valor.
Segredos vivem no agente local (Credential Manager / env).

Documentação operacional: [`../planos/13-wfs-e-servicos-geo.md`](../planos/13-wfs-e-servicos-geo.md).

Ao alterar layer ou endpoint: bump de `contract_version`, atualizar `data_verificacao`, e PR com
prova de `GetCapabilities`/`DescribeFeatureType`.
