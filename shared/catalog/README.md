# Catálogo compartilhado

Arquivos machine-readable consumidos pelo **núcleo da Fase 1** e pelo **backend da Fase 2**.

| Arquivo | Conteúdo |
|---|---|
| [`camadas.json`](camadas.json) | **41** camadas com `id` estável para o MapSpec (atualizado 2026-07-25) |
| [`servicos_geo.json`](servicos_geo.json) | Provedores WFS/WMS/REST/API (SEMA, SIMCAR, SCCON, PRODES…) |
| [`sema_layers_live.json`](sema_layers_live.json) | **135** FeatureTypes do GetCapabilities SEMA (server-desktop, IP BR) |
| [`mosaicos_sema.json`](mosaicos_sema.json) | Mosaicos WMS SPOT/Landsat/Sentinel curados no GeoForest |
| [`simcar_template_map.json`](simcar_template_map.json) | Template curto → candidatos `Geoportal:SIMCAR_D_*` |
| [`wms_sondagem_2026-07-26.json`](wms_sondagem_2026-07-26.json) | Sonda GetCapabilities/GetMap no Windows **sem senha** |

**Não contém credenciais.** O campo `auth` é o *nome* do segredo (`sema_authkey`), nunca o valor.
Segredos vivem no Credential Manager do desktop (Fase 1) ou no cofre deste PC (Fase 2).

Documentação operacional: [`../../planos/03-wfs-e-servicos-geo.md`](../../planos/03-wfs-e-servicos-geo.md)
(seção **Sondagem WMS no Windows**).

### WMS que funcionam sem senha (2026-07-26)

| OK GetMap | Bloqueado / exige chave |
|---|---|
| FUNAI `Funai:tis_poligonais` | SEMA inteiro (`sema_authkey`) — mosaicos inclusos |
| MapBiomas alertas + simplificados | SISCOM IBAMA — HTTP 403 |
| PRODES raster + yearly | CBERS `wms.cursar.space` — fora da v1 |

Fonte das descobertas: backend GeoForest em `server-desktop` (`wfs-intersection.ts`,
`simcar-clip.ts`, `Automacao_AUAS/ENDPOINTS.md`, Oráculo `11-endpoints-sema-descobertos.md`).

Ao alterar layer ou endpoint: bump de `contract_version`, atualizar `data_verificacao`, e PR com
prova de `GetCapabilities`/`DescribeFeatureType`.
