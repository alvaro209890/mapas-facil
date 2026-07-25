# 13 — WFS, WMS e serviços geoespaciais

Receitas e contratos de consumo de geoserviços para o Mapas Fácil. Destilado do que
já funciona em produção no [GeoForest-IA](https://github.com/alvaro209890) (`backend/wfs-intersection.ts`,
`simcar-clip.ts`) e no catálogo do Cerebro-Geo-IA (conferido ao vivo em 2026-07-08/10).

Este documento é a **fonte operacional** de como o agente baixa dado externo. O catálogo
machine-readable vive em [`shared/catalog/`](../shared/catalog/). Os nomes de campo do
`MapSpec` continuam sendo os de [`01-arquitetura.md`](01-arquitetura.md).

## Princípios (aprendidos a custo)

1. **Quem baixa é o agente, no PC do usuário.** `sema.mt.gov.br` bloqueia IP fora do Brasil
   (`UND_ERR_CONNECT_TIMEOUT` em Render/Vercel). Backend na nuvem **não** faz GetFeature.
2. **BBOX primeiro, clip fino local.** O `INTERSECTS` do GeoServer da SEMA perde feições em
   imóveis grandes (bug real 2026-07-10: 27 de 75 features de Área Consolidada). Ver seção
   [BBOX vs INTERSECTS](#bbox-vs-intersects-regra-de-ouro).
3. **Nunca paginar com `startIndex` na SEMA sem fallback.** `PagingIsTransactionSafe=FALSE`
   → timeout ou `Cannot do natural order without a primary key`. Uma chamada sem `startIndex`
   + marcar parcial.
4. **Falha de uma camada não aborta o mapa.** Warning no job, camada ausente, checks SOFT.
5. **Segredo nunca no código.** `authkey` só em env/keyring do agente. Dívida técnica do
   GeoForest (default hardcodado) **não se replica** aqui.

## Catálogo versionado

| Arquivo | Conteúdo |
|---|---|
| [`shared/catalog/camadas.json`](../shared/catalog/camadas.json) | 32 camadas com `id` estável, endpoint, layer, auth, tema |
| [`shared/catalog/servicos_geo.json`](../shared/catalog/servicos_geo.json) | Provedores (SEMA, INCRA, IBAMA, MapBiomas, FUNAI, Planet…) |

O `id` do catálogo é o que entra no `MapSpec` (`fonte: "embargos_siga"`). Se o GeoServer
renomear o layer, muda só o campo `layer` — o `id` permanece (caso real:
`Geoportal:TIPOLOGIA` → `Geoportal:SIMCAR_D_TIPOLOGIA_VEGETAL` em 2026-07-08).

## Endpoints por provedor

| Provedor | Endpoint | Tipo | Auth | Uso no mapa IMAP |
|---|---|---|---|---|
| **SEMA-MT GeoServer** | `https://geo.sema.mt.gov.br/geoserver/ows` | WMS+WFS 2.0 | `authkey` | CAR, SIMCAR, embargos SIGA, UC, tipologia, mosaicos |
| SEMA WFS (SFB hidro) | `https://geo.sema.mt.gov.br/geoserver/wfs` | WFS | `authkey` | hidrografia (opcional) |
| **IBAMA PAMGIA** | `…/adm_embargos_ibama_a/MapServer/0/query` | ArcGIS REST→GeoJSON | — | embargos federais (fonte primária) |
| IBAMA SISCOM | `https://siscom.ibama.gov.br/geoserver/publica/wms` | WMS | — | fallback imagem (Cloudflare) |
| **MapBiomas Alerta** | `https://production.alerta.mapbiomas.org/geoserver/ows` | WMS+WFS | — | alertas de desmate |
| **INPE PRODES** | `https://terrabrasilis.dpi.inpe.br/geoserver/prodes-legal-amz/ows` | WMS/WFS | — | desmate consolidado |
| **FUNAI** | `https://geoserver.funai.gov.br/geoserver/ows` | WMS+WFS 1.0 | — | terras indígenas |
| **INCRA Acervo** | `https://acervofundiario.incra.gov.br/i3geo/ogc.php?tema=<tema>` | WFS 1.0 GML | — | SIGEF / SNCI (só GML) |
| **Planet Basemaps** | `https://tiles.planet.com/basemaps/v1/planet-tiles/{mosaic}/gmap/{z}/{x}/{y}.png` | XYZ | `api_key` | basemap dos PDFs-modelo IMAP |
| Esri World Imagery | tiles Esri | XYZ | — | basemap default sem Planet |
| Google Satellite | `http://mt0.google.com/vt/lyrs=s&x={x}&y={y}&z={z}` | XYZ | — | fallback |
| IBGE Malhas v3 | API malhas | GeoJSON | — | minimapa de municípios |
| WMS local GeoForest (ref.) | `https://wms.cursar.space/geoserver/cbers/wms` | WMS | — | CBERS/Landsat próprios — **fora da v1** do Mapas Fácil |
| SCCON AUAS (ref.) | `https://geoserver-dashboard-mt.sccon.com.br/.../wfs` | WFS | Bearer | alertas AUAS — **fora da v1** |

## Camadas SEMA prioritárias para a série IMAP

### CAR validado (`Geoportal:CAR_*`)

| Layer | Uso no mapa |
|---|---|
| `CAR_ATP` | perímetro oficial do imóvel |
| `CAR_APP` / `CAR_APPD` | APP / APP degradada |
| `CAR_ARL` | reserva legal |
| `CAR_AVN` | vegetação nativa (contexto; preferir shapefile local) |
| `CAR_AUAS` | uso antropizado |
| `CAR_NASCENTE` | nascentes (pontos) |

### SIMCAR declarado (`Geoportal:SIMCAR_D_*`)

| Layer | Uso |
|---|---|
| `SIMCAR_D_AVN` / `_APP` / `_ARL` / `_AUAS` / `_NASCENTE` | declaração do produtor |
| `SIMCAR_D_AREA_CONSOLIDADA` | AC declarada |
| `SIMCAR_D_TIPOLOGIA_VEGETAL` | tipologia (substitui `TIPOLOGIA`, morto) |

### Fiscalização e contexto

| Layer | Preferência |
|---|---|
| `AREA_EMBARGADA_SIGA_POLIGONO` | **preferir** para embargos recentes |
| `AREAS_EMBARGADAS_SEMA` | histórico |
| `AREAS_DESEMBARGADAS_SEMA` | desembargos |
| `AUTOS_DE_INFRACAO_SIGA_POLIGONO` | autos |
| `UNIDADES_CONSERVACAO` | UCs |
| `USO_CONSOLIDADO` / `AREAS_USO_RESTRITO` | uso do solo |
| `LIM_MUNICIPIOS_MT` | município por ponto (`MUNICIPIO`, `COD_IBGE`, geom `SHAPE`) |
| `MVW_REQUERIMENTO_ATP` | consulta CAR por número |

### Mosaicos WMS (fundo histórico)

| Layer | Uso |
|---|---|
| `Mosaicos:MOSAICO_SPOT_SEPLAN` | SPOT 2008 (marco Código Florestal) |
| `Mosaicos:LANDSAT_5_<ano>` / `LANDSAT_8_<ano>` / `SENTINEL_2_<ano>` | mosaicos anuais |

## Autenticação

### SEMA `authkey`

Passa na **query string** de toda chamada OWS (`GetCapabilities`, `GetFeature`, `GetMap`,
`DescribeFeatureType`):

```
…&authkey=<uuid>
```

No agente Mapas Fácil:

| Item | Valor |
|---|---|
| Nome do segredo no catálogo | `sema_authkey` |
| Onde vive | Windows Credential Manager / env do agente (`SEMA_WFS_AUTHKEY`) |
| Default no código | **vazio** — sem fallback hardcodado |
| Quem configura | o usuário, na UI do agente |

### Outros

| Segredo | Serviço | Como passa |
|---|---|---|
| `planet_api_key` | Planet tiles | `api_key` na URL do tile |
| (nenhum) | PAMGIA, MapBiomas, FUNAI, INCRA, PRODES | público |
| Bearer SCCON | dashboard MT | fora da v1 |

## Receitas de request

### WFS GetFeature JSON (padrão SEMA)

```
GET {ows}?service=WFS&version=2.0.0&request=GetFeature
    &typeNames=Geoportal:CAR_ATP
    &outputFormat=application/json
    &srsName=EPSG:4674
    &bbox=minx,miny,maxx,maxy,EPSG:4674
    &count=2000
    &authkey=<uuid>
```

Regras:

- Expandir o bbox ~25% (mín. 0,002°) antes de buscar — pega vizinhos na moldura.
- **Não** misturar `bbox` e `CQL_FILTER` na mesma chamada.
- Teto no Mapas Fácil (mapa): **500–2000** feições/camada. GeoForest usa até 50.000
  (análise) — escala diferente; não copiar o teto cego.
- CRS oficial dos vetores SEMA: **EPSG:4674**. Turf/área geodésica: 4326. Cálculo de
  hectare no ArcMap: UTM SIRGAS 2000 (21S/22S derivados do centroide — **nunca hardcodar**).

### Fallback WFS 1.0.0 (FUNAI e servidores antigos)

Se 2.0.0 falhar:

```
version=1.0.0&typeName=<layer>&maxFeatures=<n>
```

(singular `typeName`, `maxFeatures` no lugar de `count`).

### CAR por número (entrada alternativa)

Camada: `Geoportal:MVW_REQUERIMENTO_ATP`, WFS 1.0.0, `maxFeatures=1`, `srsName=EPSG:4674`.

Ordem de tentativa no CQL (receita GeoForest):

1. `NUMEROESTADUAL='MT319367/2025'`
2. `CODIGO_CAR_FEDERAL='…'`
3. `PROTOCOLO='…'`

Se JSON falhar → GML. Se houver vários requerimentos do mesmo número → ordenar por
`REQUERIMENTO_ID` desc e pegar o mais recente.

### DescribeFeatureType (campo de geometria)

```
request=DescribeFeatureType&typeNames=<layer>&authkey=…
```

Procurar elemento `gml:*PropertyType`. Preferir `GEOMETRY`; não assumir `the_geom`.
Cache 30 min. Sem isso, `INTERSECTS`/`CQL` quebram em silêncio.

### Hits antes de baixar (opcional)

```
request=GetFeature&resultType=hits&CQL_FILTER=INTERSECTS(<geom>,<WKT>)
```

Ler `numberMatched`. Se 0, pular o download. No Mapas Fácil, hits são opcionais porque
o caminho primário é BBOX (abaixo).

### BBOX vs INTERSECTS (regra de ouro)

Pipeline obrigatório do agente (copiado do fix GeoForest 2026-07-10):

```
1. GetFeature com BBOX (expandido) + count
2. Clip fino local (shapely/turf) pelo polígono do imóvel
3. Se BBOX retornar vazio → tentar INTERSECTS como complemento
4. Se paginação com startIndex falhar (400 ou timeout) →
   uma chamada sem startIndex, marcar resultado_parcial=true
```

Não inverter essa ordem. INTERSECTS "parece funcionar" e devolve menos feições sem erro.

### ArcGIS REST — IBAMA PAMGIA

```
GET …/MapServer/0/query
  ?f=geojson&where=1=1&outFields=*&returnGeometry=true
  &geometry={"xmin":…,"ymin":…,"xmax":…,"ymax":…,"spatialReference":{"wkid":4674}}
  &geometryType=esriGeometryEnvelope
  &inSR=4674&outSR=4674
  &spatialRel=esriSpatialRelIntersects
  &resultRecordCount=500
```

Fonte primária de embargos federais. SISCOM WMS fica como fallback de imagem.

### INCRA — WFS 1.0 GML

```
GET ogc.php?tema=<tema>&service=WFS&version=1.0.0&request=GetFeature
    &typeName=<tema>&bbox=…&maxFeatures=500
```

- Sem JSON. Parser GML próprio (`featureMember`/`member`, `coordinates` ou `posList`).
- Geometria em **EPSG:4326** lon/lat.
- Timeout **120 s+** (notoriamente lento).

### WMS GetMap (fundo / mosaico)

```
GET {ows}?service=WMS&version=1.1.1&request=GetMap
    &layers=<layer>&styles=
    &bbox=minx,miny,maxx,maxy&srs=EPSG:4674
    &width=1200&height=<proporcional_ao_bbox>
    &format=image/png&transparent=true
    &authkey=<uuid>
```

Validação obrigatória da resposta (HTTP 200 mente):

1. `Content-Type` começa com `image/`
2. Magic bytes `\x89PNG` ou `\xFF\xD8\xFF`
3. Se for XML de erro → retry com backoff (2×, ~1,2 s)

Para desenhar no layout UTM: reprojetar o bbox **antes** do GetMap e pedir `srs` UTM —
o extent casa com o data frame.

### Planet / Esri (basemap)

- Planet: `global_monthly_AAAA_MM_mosaic` + `api_key` — idêntico ao PDF-modelo IMAP.
- Esri World Imagery: default quando não há chave Planet.
- No `.mxd`, preferir layer de serviço que o ArcMap persista; se XYZ não persistir bem,
  o PDF leva o basemap e o `.mxd` fica com aviso (pendência do [05](05-motor-mxd-pdf.md)).

## Cache no agente

| Item | TTL | Chave |
|---|---|---|
| GetCapabilities | 10 min | por endpoint |
| DescribeFeatureType (campo geom) | 30 min | por layer |
| Vetor recortado (CAR/SIMCAR) | 7 dias | `id + bbox~100m + epsg` |
| Embargos | 24 h | idem |
| Alertas MapBiomas | 6 h | idem |
| Malha IBGE UF | 180 dias | `municipios_<UF>` |
| Tiles basemap | 30 dias | `z/x/y` |

Local sugerido: `%LOCALAPPDATA%\MapasFacil\cache\`. Offline: usar cache expirado com aviso
de idade; camada sem cache → vazia + warning, job continua com locais.

## Cliente HTTP

| Regra | Motivo |
|---|---|
| User-Agent de navegador | alguns WAF gov. bloqueiam clientes "bot" |
| TLS verify relaxado **só** para domínios do catálogo | cadeias incompletas em geosserviços BR |
| Timeout 60 s (120 s INCRA) | serviços públicos lentos |
| Retry 2× com backoff | queda intermitente |
| Concorrência limitada entre camadas | não derrubar a SEMA; falha isolada |

## Módulo do agente (estrutura)

```
agent/mapasfacil_agent/layers/
  catalog.py          # lê shared/catalog/*.json
  wfs_client.py       # buildWfsUrl, GetFeature, DescribeFeatureType, hits
  wms_client.py       # GetMap + validação mágica
  rest_arcgis.py      # PAMGIA
  gml_incra.py        # parser GML 1.0
  clip.py             # BBOX fetch + clip fino local
  cache.py            # TTL por tema
  secrets.py          # keyring / env — sem default de authkey
```

Interface mínima (contrato interno):

```python
def resolve_layer(fonte: str, bbox, crs_mapa) -> Path:
    """Retorna shapefile/GeoJSON pronto para o ArcPy, dentro da allowlist/temp."""
```

`fonte` é `local.<id>` ou id do catálogo. Nunca URL livre vinda do backend (anti-SSRF /
anti-RCE por caminho).

## Tabela WFS vs WMS (resumo operacional)

| Precisa de… | Use |
|---|---|
| Área / tabela / estilo IMAP / layer editável no `.mxd` | **WFS** (ou REST GeoJSON) |
| Só fundo visual (satélite, mosaico, tipologia como pano) | **WMS** |
| Serviço só oferece WMS | WMS + documentar `tipo: wms_raster` |

## Gotchas (checklist de implementação)

Copiados de Cerebro `08-gotchas.md` + changelog GeoForest — cada um precisa de teste:

1. Geo-block SEMA fora do Brasil → agente local
2. Paginação `startIndex` → fallback single-page
3. INTERSECTS perde feições → BBOX + clip local
4. WMS HTTP 200 com XML de erro → magic bytes
5. `Geoportal:TIPOLOGIA` morto → `SIMCAR_D_TIPOLOGIA_VEGETAL`
6. FUNAI só WFS 1.0; INCRA só GML
7. SISCOM atrás de Cloudflare → PAMGIA primeiro
8. CAR com múltiplos requerimentos → `REQUERIMENTO_ID` desc
9. Nunca hardcodar zona UTM (MT = 21S/22S)
10. Mojibake `.dbf` → latin-1 primeiro
11. Anéis GeoJSON abertos → fechar antes do WKT
12. IBGE malhas gzip → descomprimir
13. `maxFeatures`/`count` sempre presentes
14. Authkey hardcoded → proibido (CI gitleaks)

## O que o Mapas Fácil NÃO copia do GeoForest

| GeoForest faz | Mapas Fácil |
|---|---|
| Análise Gemini sobre clip SIMCAR | fora de escopo (só mapa) |
| ZIP de shapefiles para download web | o `.mxd` já aponta para arquivos locais |
| WMS CBERS próprio em `wms.cursar.space` | fora da v1 (basemap Planet/Esri) |
| Proxy WMS no backend Node | agente baixa direto |
| Default de authkey no código | **nunca** |

## Pendências e decisões abertas

| # | Pendência |
|---|---|
| P1 | Basemap Planet persistido no `.mxd` vs só no PDF |
| P2 | GeoPackage vs shapefile temporário após o clip WFS (ArcMap lê os dois; Pro prefere GPKG) |
| P3 | Incluir mosaicos SPOT 2008 como opção de basemap na série Dinâmica 2008 |
| P4 | Tool `buscar_car_por_numero` no loop de IA (entrada sem shapefile local) — candidato a M3.5 |
| P5 | Job diário de GetCapabilities que atualiza `data_verificacao` no catálogo |
| P6 | SCCON / AUAS e WMS CBERS: v2, se houver demanda |
