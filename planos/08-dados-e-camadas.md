# 08 — Dados e camadas

De onde vem a geometria que aparece no mapa. Este documento cobre as duas classes de dados, o
catálogo versionado, o recorte e a reprojeção, o cache, os segredos e os defeitos conhecidos dos
serviços públicos brasileiros. Os nomes de campo do `MapSpec` e o protocolo do agente são os de
[`01-arquitetura.md`](01-arquitetura.md).

**Receitas WFS/WMS detalhadas** (URLs, parâmetros, BBOX vs INTERSECTS, authkey, PAMGIA, INCRA):
[`13-wfs-e-servicos-geo.md`](13-wfs-e-servicos-geo.md). Catálogo machine-readable já versionado em
[`../shared/catalog/camadas.json`](../shared/catalog/camadas.json) (32 camadas) e
[`servicos_geo.json`](../shared/catalog/servicos_geo.json) — origem Cerebro-Geo-IA / NexoGeo,
conferido no GetCapabilities SEMA 2026-07-08; consumo em produção no GeoForest-IA.

## Duas classes de dados

| Classe | O que é | Onde vive | Papel no mapa IMAP |
|---|---|---|---|
| **LOCAIS** | shapefiles do imóvel no PC do usuário (lotes, AVN, AC, AUAS, tipologia, APP, ARL) | disco do usuário, nas pastas autorizadas | **a base dos mapas da série** — é isso que o cliente entrega e cobra |
| **EXTERNAS** | WFS/WMS/REST de serviços públicos (SEMA-MT, IBAMA, MapBiomas, IBGE) | internet | contexto e sobreposição (embargos, alertas, malha municipal, fundo de satélite) |

A hierarquia importa e está no system prompt: **camada local vence camada externa** sempre que as
duas representam a mesma coisa. O AVN do shapefile do imóvel é o que o técnico validou e vai
defender; o `Geoportal:CAR_AVN` do WFS é o que está no sistema da SEMA, que pode estar
desatualizado ou divergir da versão em análise. Mapa da série feito com dado de WFS no lugar do
shapefile do cliente é retrabalho garantido.

No `MapSpec`, a distinção aparece no campo `fonte` da camada: `local.<id>` para camada local, id do
catálogo para camada externa (invariante do [`01`](01-arquitetura.md)).

## Camadas locais

### Descoberta

O agente varre as pastas autorizadas e classifica cada shapefile por convenção de nome, comparando
sempre em minúsculas e sem acento:

| `id` sugerido | Padrões reconhecidos no nome do arquivo |
|---|---|
| `lotes` | `lote`, `lotes`, `atp`, `perimetro`, `imovel`, `matricula` |
| `avn` | `avn`, `veg_nativa`, `vegetacao_nativa`, `remanescente` |
| `ac` | `ac`, `area_consolidada`, `consolidada`, `uso_consolidado` |
| `auas` | `auas`, `antropizado`, `desmate`, `desmatamento` |
| `tipologia` | `tipologia`, `tipologia_vegetal`, `fitofisionomia` |
| `app` | `app`, `preservacao_permanente` |
| `arl` | `arl`, `reserva_legal`, `reserva` |

Regras da descoberta: ela é **sugestão, não verdade**. O resultado vai para `listar_camadas_locais`
com `estilo_sugerido` já preenchido conforme [`06-padrao-imap.md`](06-padrao-imap.md), e o modelo
pode ser corrigido pelo usuário. Arquivo que não casa com nenhum padrão entra na lista com
`tema: "desconhecido"` — nunca é descartado silenciosamente, porque o técnico às vezes nomeia por
número de matrícula.

### Validação de shapefile

Um "shapefile" é um conjunto de arquivos. O agente recusa a camada se faltar qualquer um dos
obrigatórios:

| Arquivo | Obrigatório | O que acontece se faltar |
|---|---|---|
| `.shp` | sim | geometria; sem ele não há camada |
| `.shx` | sim | índice; ArcMap se recusa a abrir |
| `.dbf` | sim | atributos; sem ele não há rótulo nem quantitativo |
| `.prj` | **sim** | sem CRS declarado, não há como reprojetar nem calcular área — erro `prj_ausente`, e o agente **pergunta** o CRS em vez de assumir |
| `.cpg` | não | declara o encoding do `.dbf`; quando existe, tem prioridade |
| `.sbn`/`.sbx`/`.qix` | não | índices espaciais opcionais |

Assumir CRS quando o `.prj` falta é tentador e errado: `EPSG:4674` e `EPSG:31982` produzem mapas
completamente diferentes, e o erro só aparece na conferência visual.

### Campos esperados

| Uso | Campos procurados (na ordem) | Fallback |
|---|---|---|
| Rótulo do lote | `NOME`, `PROPRIEDA`, `FAZENDA`, `IMOVEL`, `DENOMINAC` | primeiro campo texto com valores distintos |
| Matrícula | `MATRICULA`, `MATR`, `NUM_MATRIC` | não rotula matrícula |
| Identificação do lote | `LOTE`, `NUM_LOTE`, `COD_LOTE` | usado em `filtro` (ex.: `LOTE = '65'`) |
| Classe / tipologia | `CLASSE`, `TIPOLOGIA`, `DESCRICAO`, `USO` | agrupa tudo como classe única |
| Área declarada | `AREA_HA`, `AREA`, `HECTARES` | **ignorado** — a área é sempre recalculada |

Área declarada no `.dbf` nunca é usada no mapa. Ela costuma vir de outro CRS, de outra versão da
geometria, ou arredondada. O agente recalcula em CRS projetado
([`06-padrao-imap.md`](06-padrao-imap.md)) e, se a diferença com o campo declarado passar de 1%,
registra aviso no log do job — divergência grande normalmente indica shapefile trocado.

O nome real do campo é descoberto por `inspecionar_camada`
([`07-ia-e-tools.md`](07-ia-e-tools.md)), não adivinhado pelo modelo.

### `.zip`, encoding e geometria

- **`.zip`:** o usuário frequentemente tem os shapefiles zipados (é como o SIMCAR entrega). O agente
  extrai para uma pasta temporária **dentro da allowlist**, valida o conjunto e usa o extraído.
  Nunca extrai para fora das pastas autorizadas, e limpa o temporário no fim do job.
- **Encoding do `.dbf`:** este é um problema real, não teórico. Shapefile de órgão público
  brasileiro costuma estar em **cp1252/latin-1**, não UTF-8, e ler como UTF-8 produz mojibake em
  todo nome com acento (`Fazenda São José` → `Fazenda SÃ£o JosÃ©`) — que vai direto para o rótulo do
  mapa e para a tabela. A ordem de tentativa é: `.cpg` se existir → **cp1252/latin-1** → UTF-8 →
  UTF-8 com substituição e aviso. O projeto anterior errou a ordem (UTF-8 primeiro) e teve de
  corrigir.
- **Geometrias inválidas:** auto-interseção, anéis não fechados, polígono de área zero. O agente
  detecta, tenta reparo padrão (buffer zero / `RepairGeometry`) e registra o que foi reparado. Se o
  reparo mudar a área em mais de 0,1%, ele **não** aplica e falha com mensagem clara: reparo
  silencioso que altera hectare é inaceitável num mapa que vai para órgão ambiental.
- **Multipart:** normal e esperado — um lote pode ser dois polígonos separados. O rótulo vai no
  centroide da **maior parte**, não no centroide do conjunto (que pode cair fora do imóvel). Tabela
  de quantitativos agrega as partes.
- **Geometria fora do Brasil / coordenada absurda:** bbox que não intersecta a UF é erro de CRS
  disfarçado; falha com mensagem apontando o `.prj`.

## Camadas externas

### Catálogo versionado

Arquivo único, versionado em `shared/catalog/camadas.json`, no mesmo espírito do catálogo do projeto
anterior. Cada entrada:

| Campo | Significado |
|---|---|
| `id` | id estável usado no `MapSpec` (nunca muda, mesmo que o layer mude de nome) |
| `nome` | nome legível, aparece na legenda e na UI |
| `tema` | agrupador (`car`, `embargos`, `desmatamento`, `areas_protegidas`, `fundiario`, `uso_solo`, `tipologia`, `malhas`) |
| `tipo` | `wms_wfs`, `wfs_gml`, `wms_raster`, `arcgis_rest`, `xyz` |
| `endpoint` | URL base do serviço |
| `layer` | nome da camada no serviço |
| `auth` | nome do segredo exigido, ou `null` |
| `descricao` | para que serve e quando preferir esta em vez de outra |
| `data_verificacao` | data da última verificação por `GetCapabilities` — **campo obrigatório** |

### Fontes principais

| Fonte | Endpoint | Camadas / `layer` |
|---|---|---|
| **SEMA-MT (GeoServer)** | `https://geo.sema.mt.gov.br/geoserver/ows` | CAR validado: `Geoportal:CAR_ATP`, `Geoportal:CAR_APP`, `Geoportal:CAR_APPD`, `Geoportal:CAR_ARL`, `Geoportal:CAR_AVN`, `Geoportal:CAR_AUAS`, `Geoportal:CAR_NASCENTE` |
| SEMA-MT — SIMCAR declarado | idem | `Geoportal:SIMCAR_D_APP`, `_ARL`, `_AVN`, `_AUAS`, `_NASCENTE`, `Geoportal:SIMCAR_D_AREA_CONSOLIDADA`, `Geoportal:SIMCAR_D_TIPOLOGIA_VEGETAL` |
| SEMA-MT — requerimentos | idem | `Geoportal:MVW_REQUERIMENTO_ATP` (consulta por número de CAR) |
| SEMA-MT — fiscalização | idem | `Geoportal:AREA_EMBARGADA_SIGA_POLIGONO`, `Geoportal:AREAS_EMBARGADAS_SEMA`, `Geoportal:AREAS_DESEMBARGADAS_SEMA`, `Geoportal:AUTOS_DE_INFRACAO_SIGA_POLIGONO`, `Geoportal:UNIDADES_CONSERVACAO`, `Geoportal:USO_CONSOLIDADO`, `Geoportal:AREAS_USO_RESTRITO` |
| **IBAMA — PAMGIA** (embargos federais, fonte primária) | `https://pamgia.ibama.gov.br/server/rest/services/01_Publicacoes_Bases/adm_embargos_ibama_a/MapServer/0/query` | `adm_embargos_ibama_a`, ArcGIS REST com `f=geojson` |
| IBAMA — SISCOM (fallback, só imagem) | `https://siscom.ibama.gov.br/geoserver/publica/wms` | `publica:vw_brasil_adm_embargo_a` |
| **MapBiomas Alerta** | `https://production.alerta.mapbiomas.org/geoserver/ows` | `mapbiomas-alertas:v_alerts_last_status`; fallback mais leve `mapbiomas-alertas:crew_simplified-alerts` |
| **IBGE — malhas municipais** | API de malhas v3, `qualidade=minima&intrarregiao=municipio` | malha de municípios por UF, usada só no minimapa |
| INPE — PRODES | `https://terrabrasilis.dpi.inpe.br/geoserver/prodes-legal-amz/ows` | `accumulated_deforestation_2007` (tratado como raster/overlay) |
| FUNAI — Terras Indígenas | `https://geoserver.funai.gov.br/geoserver/ows` | `Funai:tis_poligonais` |
| **Basemap Esri World Imagery** | serviço de tiles da Esri | fundo satélite default |
| **Basemap Planet** (opcional, com chave) | `https://tiles.planet.com/basemaps/v1/planet-tiles/{mosaic}/gmap/{z}/{x}/{y}.png` | `mosaic = global_monthly_AAAA_MM_mosaic`; é o basemap dos PDFs-modelo |

A v1 entra com o subconjunto que a série IMAP realmente usa: CAR/SIMCAR da SEMA, embargos (SIGA +
IBAMA), alertas MapBiomas, tipologia vegetal, malhas do IBGE e os dois basemaps. O resto entra por
demanda, via o processo de governança abaixo.

## Recorte por bbox e reprojeção

Toda camada externa é pedida **recortada pelo bbox do imóvel** com uma folga de 5% do lado maior.
Nunca a camada inteira. Duas razões: uma camada estadual tem dezenas de milhares de feições
(carregar `Geoportal:CAR_ATP` de MT inteiro trava a chamada e o ArcMap), e a resposta recortada cabe
em cache e em disco.

Sequência do recorte, na ordem (regra de ouro do GeoForest, changelog 2026-07-10):

1. Calcular o bbox do `area_base` no CRS projetado do mapa (`EPSG:31981`/`31982`).
2. Reprojetar o bbox para o CRS que o serviço espera — normalmente `EPSG:4674` para a SEMA —
   e **expandir ~25%** (mín. 0,002°) para pegar vizinhos na moldura.
3. Montar a requisição:
   - **WFS:** `srsName` explícito, **`BBOX` como método primário** (não `INTERSECTS` — a SEMA
     perde feições em imóveis grandes sem erro aparente), `outputFormat=application/json` quando
     suportado, e **sempre** um teto de feições (`count`/`maxFeatures`). Sem teto, a chamada trava.
   - **ArcGIS REST (PAMGIA):** `geometry` como envelope JSON, `geometryType=esriGeometryEnvelope`,
     `inSR`/`outSR`, `spatialRel=esriSpatialRelIntersects`, `resultRecordCount`.
   - **WMS:** `GetMap` com bbox e `height` proporcional ao bbox — bbox e imagem com proporções
     diferentes geram fundo esticado; validar magic bytes (HTTP 200 mente).
4. **Clip fino local** pelo polígono do imóvel (shapely) — o servidor devolve feições que
   intersectam o bbox, inteiras.
5. Se BBOX vier vazio → tentar `INTERSECTS` como complemento (nunca o contrário).
6. Reprojetar o resultado para o CRS do mapa.

Detalhes de URL e parâmetros: [`13-wfs-e-servicos-geo.md`](13-wfs-e-servicos-geo.md).

Limites e paginação:

| Parâmetro | Valor de partida | Motivo |
|---|---|---|
| Teto de feições por camada | 5.000 | acima disso o mapa fica ilegível e o `.mxd` lento |
| Timeout por requisição | 60 s (120 s para INCRA) | serviços públicos são lentos; INCRA com filtro é notoriamente lento |
| Tentativas | 3, com backoff | queda intermitente é o modo de falha mais comum |
| Paginação | `startIndex`/`count` quando suportado | camadas sem chave primária respondem HTTP 400 `Cannot do natural order without a primary key`; nesse caso, refazer **uma** chamada sem paginação e marcar o resultado como parcial |

Camada externa que responde 0 feições no bbox não é erro: entra vazia e dispara o check `S09` de
[`06-padrao-imap.md`](06-padrao-imap.md). "Não há embargo neste imóvel" é uma informação legítima e
frequentemente é o objetivo do mapa.

## Cache

Cache **local, no PC do usuário** — coerente com a regra de que nada geoespacial trafega pela
nuvem.

| Item | Formato | Chave | TTL |
|---|---|---|---|
| Malhas municipais IBGE | GeoJSON por UF | `municipios_<UF>` | praticamente infinito (revalidar a cada 180 dias) |
| CAR / SIMCAR / uso do solo (SEMA) | GeoJSON recortado | `<id>_<bbox arredondado>_<epsg>` | 7 dias |
| Embargos (SIGA, IBAMA) | GeoJSON recortado | idem | 24 horas |
| Alertas MapBiomas | GeoJSON recortado | idem | 6 horas |
| Tiles de basemap | PNG/JPEG por tile | `z/x/y` | 30 dias |
| `GetCapabilities` | XML | por endpoint | 24 horas |

O TTL é por tema porque a volatilidade é por tema: malha municipal muda quando o IBGE cria
município, alerta de desmatamento muda toda semana. Um TTL único obrigaria a escolher entre
recarregar malha à toa e mostrar alerta velho.

Bbox arredondado na chave (para ~100 m) evita cache miss por diferença irrelevante de extent entre
duas versões do mesmo mapa.

Invalidação manual: comando do agente (`doctor`/limpar cache) e opção na UI por conversa
("regerar buscando dados novos"). Comportamento offline: se há cache válido ou expirado, o agente
usa o expirado e **avisa a idade do dado no log e no relatório de validação**; se não há cache, a
camada externa entra vazia com aviso, e o mapa é gerado com as camadas locais — mapa incompleto com
aviso é melhor que job falhado, porque as camadas locais são a parte que o cliente cobra.

## Autenticação de serviços

| Segredo | Serviço | Como é usado |
|---|---|---|
| `sema_authkey` | GeoServer da SEMA-MT | parâmetro `authkey=<uuid>` na query string de **toda** chamada, inclusive `GetCapabilities` |
| `planet_api_key` | Planet Basemaps | chave na requisição de tiles |

Regras invioláveis:

1. Segredos vivem **apenas no agente local**, em arquivo de configuração fora do repositório
   (permissão restrita ao usuário do Windows). O usuário cola a chave dele na interface do agente.
2. **Nunca no frontend.** Chave em código de navegador é chave pública.
3. **Nunca no repositório.** No projeto anterior houve chave *hardcoded* em código versionado, e a
   regra aqui é explícita para não repetir: o `shared/catalog/camadas.json` declara o **nome** do
   segredo (`auth: "sema_authkey"`), nunca o valor.
4. **Nunca no backend em nuvem.** O backend não faz requisição a geosserviço; quem baixa é o agente.
   Isso resolve de graça o geobloqueio (item abaixo) e mantém a superfície de risco no PC do usuário.
5. Segredo ausente não é erro fatal: `adicionar_camada` avisa (`segredo_ausente`), a camada sai do
   mapa com aviso, e o job conclui.

## Governança do catálogo

Adicionar camada nova é uma alteração de contrato, e passa por PR:

1. Alterar `shared/catalog/camadas.json` com todos os campos, incluindo `data_verificacao`.
2. Anexar ao PR a saída do `GetCapabilities` (ou `DescribeFeatureType`) provando que o `layer`
   existe com esse nome exato, na data declarada.
3. Um teste automatizado que faz `GetCapabilities` do endpoint e verifica que o `layer` está na
   lista. Ele roda em CI numa cadência baixa (diária, fora do PR) porque depende de serviço externo:
   falha dele **não** bloqueia merge, mas abre issue automaticamente.
4. Bump do hash do catálogo, exposto em `GET /v1/catalog/version`
   ([`01-arquitetura.md`](01-arquitetura.md)), para que agente e backend detectem divergência.

Quando um serviço **muda o nome do layer** (acontece sem aviso): o `id` do catálogo **não muda** —
ele é a referência usada em `MapSpec` já persistidos e em jobs históricos. Muda só o campo `layer`,
com a data de verificação atualizada e uma linha no `descricao` registrando a troca. O caso real do
projeto anterior: `Geoportal:TIPOLOGIA` deixou de existir e o certo passou a ser
`Geoportal:SIMCAR_D_TIPOLOGIA_VEGETAL`; o id `tipologia_sema` continuou o mesmo e nenhum mapa
histórico quebrou.

## Qualidade e gotchas

Estes não são riscos hipotéticos — todos foram observados no projeto anterior:

| # | Gotcha | Como o agente trata |
|---|---|---|
| 1 | **`sema.mt.gov.br` recusa conexão de IP fora do Brasil** | quem baixa é o agente, no PC do usuário, no Brasil. É outra razão pela qual o backend não busca geodado |
| 2 | **TLS de servidor governamental com cadeia incompleta** | cliente HTTP com verificação relaxada **apenas** para os domínios listados no catálogo, nunca global, e com User-Agent de navegador |
| 3 | **WMS devolve erro com HTTP 200** | validar `Content-Type: image/*` e os magic bytes antes de tratar a resposta como imagem |
| 4 | **Layer renomeado sem aviso** | `id` estável no catálogo + descoberta por sufixo em minúsculas contra o `GetCapabilities` como último recurso, sempre com aviso |
| 5 | **CRS inesperado / eixo invertido** | alguns servidores devolvem `EPSG:4674` em ordem lat/lon em vez de lon/lat. Detecção por sanidade: se o bbox resultante não intersecta a UF, tentar com os eixos trocados antes de falhar |
| 6 | **Paginação WFS quebra sem chave primária** | HTTP 400 `Cannot do natural order without a primary key` → uma chamada sem paginação, resultado marcado como parcial |
| 7 | **FUNAI só responde WFS 1.0.0** | fallback de versão: 2.0.0 → 1.0.0 (`typeName`/`maxFeatures`) |
| 8 | **INCRA só devolve GML, geometria em lon/lat `EPSG:4326`** | parser GML tolerante a namespace (lê `coordinates` e `posList`), depois reprojeta |
| 9 | **IBAMA/SISCOM atrás de Cloudflare** | PAMGIA (ArcGIS REST) é a fonte primária; SISCOM é fallback e pode ser bloqueado |
| 10 | **Malhas do IBGE respondem gzip** | descomprimir explicitamente se o cliente HTTP não fizer |
| 11 | **Geometria com auto-interseção vinda do serviço** | reparo com registro; se alterar área além do limiar, camada entra com aviso em vez de silenciosamente errada |
| 12 | **Área pedida grande demais** | bbox acima de ~50.000 ha dispara aviso e teto de feições reduzido; imóvel gigante em escala 1:22.000 não caberia na página de todo modo |

## WFS ou WMS: tabela de decisão

| Situação | Use | Por quê |
|---|---|---|
| A camada precisa entrar na **tabela de quantitativos** | **WFS** (ou REST com GeoJSON) | área só se calcula com geometria |
| A camada precisa de **rótulo por feição** | WFS | rótulo precisa de atributo |
| A camada precisa de **estilo IMAP** (hachura, cor, largura específicas) | WFS | WMS vem estilizado pelo servidor; não há como aplicar `#00b050` e `xxx` |
| A camada vai para o **`.mxd` como camada editável** | WFS | camada WMS no `.mxd` é uma imagem de serviço; o técnico não consegue editar |
| A camada é só **fundo visual** (satélite, mosaico histórico, tipologia como pano de fundo) | **WMS** | leve, rápido, e o estilo do servidor é aceitável |
| O serviço **só oferece** WMS (SISCOM, PRODES) | WMS | sem escolha; documentar no catálogo como `wms_raster` |
| A camada tem **milhares de feições** e é só contexto | WMS | evita travar o `.mxd` |

Regra de bolso: **se aparece na tabela ou na legenda com estilo IMAP, é WFS. Se é pano de fundo, é
WMS.** O mapa de Tipologia Vegetal é o caso de fronteira — o modelo do cliente usa o WMS temático
da SEMA como fundo *e* precisa dos quantitativos por tipologia, o que exige as duas coisas ao mesmo
tempo.

## Pendências e decisões abertas

| # | Pendência | Por que ainda não decidido |
|---|---|---|
| P1 | Local exato do cache no Windows | candidatos: `%LOCALAPPDATA%\MapasFacil\cache` ou subpasta dentro da allowlist; a segunda é mais auditável, a primeira é mais limpa |
| P2 | Formato do cache de vetor | GeoJSON é legível e debugável; GeoPackage é menor e mais rápido para o `arcpy` ler. Decidir junto com o [`05`](05-motor-mxd-pdf.md) |
| P3 | Basemap do `.mxd` | o `.mxd` precisa referenciar um serviço de tiles que o ArcMap entenda; verificar se Planet XYZ funciona como camada persistida ou se só serve para o PDF nativo |
| P4 | Tipologia Vegetal com WMS de fundo + WFS de quantitativo | duas requisições para a mesma informação; validar com o cliente se o fundo WMS é obrigatório |
| P5 | Detecção de eixo invertido | a heurística de "bbox não intersecta a UF" precisa de teste com um servidor que realmente inverta, para não virar falso positivo |
| P6 | Limite de 5.000 feições por camada | número escolhido por prudência, não medido; calibrar com o tempo de abertura real do `.mxd` |
| P7 | Camadas locais em formatos além de shapefile | GeoPackage e KML aparecem na prática; fora da v1, mas a convenção de descoberta precisaria mudar |
| P8 | Quem preenche `data_verificacao` na v1 | manual no PR hoje; avaliar se o job diário de `GetCapabilities` pode atualizar o campo automaticamente |
