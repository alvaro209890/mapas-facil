# 04 — Dados, camadas e o CAR

Como o sistema descobre, valida e prepara os dados que viram mapa. As receitas de rede
(endpoints, parâmetros, gotchas de WFS/WMS) estão em
[`03-wfs-e-servicos-geo.md`](03-wfs-e-servicos-geo.md); aqui é o que acontece **antes e depois**
da rede.

## Duas classes de dado

| Classe | Origem | Quem resolve | Confiança |
|---|---|---|---|
| **Local** | pasta do projeto no PC: `.shp`, `.zip` do SIMCAR, recibo do CAR em PDF, prints | núcleo Python da Fase 1 | é a verdade do trabalho — prevalece sempre |
| **Externa** | WFS/WMS da SEMA, IBAMA, FUNAI, MapBiomas, INCRA, IBGE, tiles | cliente HTTP do núcleo, com cache | contexto e conferência |

Regra que resolve conflito: **dado local ganha.** Se o `AVN.shp` da pasta discorda do
`SIMCAR_D_AVN` do WFS, o mapa usa o local e o agente **avisa** a divergência com o número em
hectare. O técnico é que decide.

## A pasta de trabalho

O usuário aponta uma pasta; o núcleo indexa. O layout típico de uma análise real (Harmonia):

```
Analise_de_area-Julio Barbosa_4_Harmonia/
├─ Arquivo Processado (1)/        ← shapes do CAR, SIRGAS 2000 geográfico (EPSG:4674)
│  ├─ ATP.shp                     ← perímetro do imóvel  (1 feição)
│  ├─ AVN.shp                     ← vegetação nativa
│  ├─ AREA_CONSOLIDADA.shp
│  ├─ AUAS.shp
│  ├─ APP.shp · ARL.shp · NASCENTE.shp
├─ CAR - Emitido (6) (1).pdf      ← recibo do CAR
├─ Automacoes/
│  ├─ Resultados/                 ← Alertas_raw.json, Embargos_raw.json (quando houver)
│  └─ Scripts/mxd_harmonia/       ← scripts manuais históricos (referência, não produto)
├─ SHP/                           ← shapes de apoio, UTM 22S (homônimos / materializados)
├─ MXD/                           ← saída (.mxd)
└─ Mapas/                         ← saída (.pdf)
```

Layout de **entrega** do produto (após o motor): pasta autocontida com caminhos relativos —
ver [`../Fase_1_Desktop/planos/04-motor-mxd.md`](../Fase_1_Desktop/planos/04-motor-mxd.md).

### Alertas e embargos a partir de JSON local

Quando a pasta traz `Alertas_raw.json` / `Embargos_raw.json` (padrão Harmonia):

| Fonte | Materialização | Regra |
|---|---|---|
| MapBiomas (`props.geom_simplified`) | `SHP/air_mapbiomas/AIR.shp` | overlay cinza |
| SCCON “Desmatamento - Corte Raso” | `SHP/air_prodes/AIR.shp` | overlay PRODES |
| Embargos IBAMA/SEMA vazios | nenhuma feição | **mapa vazio é correto** |
| Desembargos só-ponto | não desenhar na v1 | evitar falso positivo |

Encoding ao ler DBF FUNAI (latin-1): sanitizar antes de gravar JSON/texto no mapa —
`s.encode('utf-8','surrogateescape').decode('cp1252')` (já quebrou na Harmonia).

### Índice do workspace

Ao conectar a pasta, o núcleo varre e monta um índice — a base de todo o contexto que a IA
recebe:

| Por arquivo | Campo |
|---|---|
| `.shp` | caminho relativo, tipo de geometria, CRS, nº de feições, campos do `.dbf`, bbox, área total (ha, em CRS projetado), validade das geometrias |
| `.zip` | conteúdo listado sem extrair; detecção de shapefile dentro |
| `.pdf` | é recibo do CAR? é laudo? nº de páginas |
| imagem | dimensões; candidata a "print de referência" |
| `.mxd` | template? saída anterior? |

O índice é **incremental**: um *watcher* observa a pasta e reindexa só o que mudou. Arquivo novo
aparece na conversa sem o usuário pedir.

### Descoberta do papel de cada shapefile

O nome do arquivo é a primeira pista, mas não a única — o acervo real tem
`AREA_CONSOLIDADA.shp` num projeto e `AC.shp` noutro.

Ordem de resolução:

1. **Nome canônico** (tabela abaixad), sem acento e em maiúsculas.
2. **Aliases conhecidos**: `AC` → `AREA_CONSOLIDADA`, `VEREDA` → `VEREDAS`,
   `AREA_USO_RESTRITO` → `AREAS_USO_RESTRITO`, `SIEGEF`/`SIGEF` → perímetro.
3. **Heurística de conteúdo**: 1 feição de polígono grande que contém as demais = perímetro;
   campos do `.dbf` característicos (`COD_IMOVEL`, `NUM_AREA`, `TIPO`).
4. **Pergunta ao usuário**, quando ainda ambíguo. Nunca chuta em silêncio.

| Papel | Nomes canônicos | Vira no mapa |
|---|---|---|
| Perímetro do imóvel | `ATP`, `AREA_IMOVEL`, `PERIMETRO` | camada amarela + extent + centroide + zona UTM |
| Vegetação nativa | `AVN`, `VEGETACAO_NATIVA` | hachura verde `xxx` |
| Área consolidada | `AREA_CONSOLIDADA`, `AC` | hachura magenta `xxx` |
| Desmate pós-2008 | `AUAS` | hachura laranja `///` |
| APP | `APP`, `APPD` | contexto |
| Reserva legal | `ARL`, `ARLD` | contexto |
| Nascente | `NASCENTE` | pontos |
| Tipologia | `TIPOLOGIA`, `TIPOLOGIA_VEGETAL` | mapa de Tipologia |

## Validação de shapefile

Todo `.shp` passa por esta bateria antes de virar camada. Falha em qualquer item vira aviso na
conversa, não exceção silenciosa.

- [ ] Os quatro arquivos existem: `.shp`, `.shx`, `.dbf`, `.prj`
- [ ] `.prj` presente e reconhecível — **ausente é o erro mais comum**; sem ele o CRS é
      adivinhado pela magnitude das coordenadas e o usuário é avisado
- [ ] CRS identificado; se geográfico, reprojeta para a UTM do centroide antes de calcular área
- [ ] Tipo de geometria coerente com o papel (perímetro = polígono)
- [ ] Nº de feições > 0
- [ ] Geometrias válidas — `make_valid`/`buffer(0)` com contagem de quantas foram corrigidas
- [ ] Anéis fechados (GeoJSON com anel aberto quebra a conversão para WKT)
- [ ] Encoding do `.dbf`: tenta `latin-1` **primeiro**, depois `utf-8`, depois `cp1252`
      (mojibake em `.dbf` de origem brasileira é regra, não exceção)
- [ ] Área calculada bate com a declarada no recibo do CAR — divergência > 0,5% vira aviso
- [ ] Sub-áreas contidas no perímetro — o que sobra vira o aviso "X ha fora da ATP"

### Cálculo de área — a regra que não se negocia

1. Reprojetar para a UTM SIRGAS 2000 da zona do **centroide** (`31981` oeste, `31982` leste).
2. Corrigir geometrias inválidas.
3. `union` das feições da camada (evita contar sobreposição duas vezes).
4. Área em m² ÷ 10.000 = hectare.
5. Arredondar para 4 casas; formatar pt-BR (`3.823,9140`).
6. `TOTAL GERAL` = soma dos valores **já arredondados**.

Área em CRS geográfico é área em graus² — número sem significado físico. Isso já foi bug real em
projeto anterior.

## Recibo do CAR (PDF)

O recibo é a fonte mais rica de contexto da pasta, e o usuário sempre tem um. Parser portado de
`core/recibo.py` do NexoGeo (PyMuPDF).

| Campo extraído | Uso no mapa |
|---|---|
| Nome do imóvel | rótulo, nome da camada, legenda, coluna `Propriedade` |
| Município / UF | **definition query** do município + minimapa |
| Nº do CAR estadual (`MT102042/2017`) | consulta ao WFS, rastreabilidade |
| Recibo federal | rastreabilidade |
| Área total (ha) | conferência contra a geometria |
| ARL / APP / Consolidada / Vegetação nativa | pré-preenchimento da tabela |
| Tipologia (Floresta / Cerrado, ha) | mapa de Tipologia |
| Situação (Ativo / Declarado) | contexto para o agente |
| Tabela "Dados das Áreas dos Imóveis Rurais" | matrícula/posse por documento |

**CPF do proprietário é descartado na entrada.** O parser não o retorna, então ele não existe em
memória, em log nem em prompt. Ver [`05-seguranca-e-segredos.md`](05-seguranca-e-segredos.md).

Armadilha do formato: rótulos de documento quebram em duas linhas no PDF. O parser junta linhas
antes de casar, e trata `Matrícula` e `Posse` como tipos distintos.

## `.zip` do SIMCAR

Quando o usuário baixa o "Arquivo Processado" do SIMCAR, vem um `.zip` com os shapefiles.

1. Listar o conteúdo **sem extrair** e mostrar na conversa.
2. Verificação anti *zip slip*: nenhuma entrada com `..` ou caminho absoluto.
3. Extrair para `<pasta>/_extraido/<nome_do_zip>/`, nunca sobre os arquivos existentes.
4. Indexar como qualquer shapefile.
5. Se já houver um shapefile de mesmo papel na pasta, **perguntar** qual usar — não substituir.

## Camadas externas

O `id` do catálogo é o que entra no `MapSpec` (`catalogo.embargos_siga`). Se o GeoServer
renomear o layer, muda só o campo `layer` no catálogo — o `id` permanece. Caso real:
`Geoportal:TIPOLOGIA` → `Geoportal:SIMCAR_D_TIPOLOGIA_VEGETAL` em 2026-07-08.

Catálogo versionado em [`../shared/catalog/`](../shared/catalog/README.md):

| Arquivo | Conteúdo |
|---|---|
| `camadas.json` | camadas com `id` estável, endpoint, layer, auth, tema |
| `servicos_geo.json` | provedores (SEMA, INCRA, IBAMA, MapBiomas, FUNAI, Planet…) |
| `sema_layers_live.json` | inventário de 135 FeatureTypes do GeoServer da SEMA (sondado de IP brasileiro) |
| `mosaicos_sema.json` | mosaicos WMS: SPOT 2008, Landsat 5/7/8, Sentinel-2 2016–2024 |
| `simcar_template_map.json` | descoberta fuzzy de layer por template curto |

### Pipeline de resolução de uma camada externa

```
1. cache?  →  devolve
2. GetFeature com BBOX expandido ~25% (mín. 0,002°) + count
3. clip fino local (shapely) pelo polígono do imóvel
4. se vazio → tentar INTERSECTS como complemento
5. reprojetar para o CRS do data frame
6. materializar como shapefile em <saida>/SHP/
7. gravar no cache
```

**BBOX antes de INTERSECTS, sempre.** O `INTERSECTS` do GeoServer da SEMA perde feições em
imóveis grandes — bug real de 2026-07-10: 27 de 75 feições de Área Consolidada sumiram. O
INTERSECTS "parece funcionar": devolve menos e não dá erro.

### Materialização

Camada externa vira **shapefile em disco**, dentro da pasta de saída do mapa — nunca em `%TEMP%`.
Duas razões: o `.mxd` com caminho relativo precisa que o arquivo esteja ao lado dele, e o usuário
precisa poder abrir o `.mxd` amanhã sem regenerar nada.

## Cache

`%LOCALAPPDATA%\MapasFacil\cache\` (Fase 1) · `~/.mapasfacil/cache/` (Fase 2).

| Item | TTL | Chave |
|---|---|---|
| GetCapabilities | 10 min | endpoint |
| DescribeFeatureType (campo de geometria) | 30 min | layer |
| Vetor recortado (CAR/SIMCAR) | 7 dias | `id + bbox~100m + epsg` |
| Embargos | 24 h | idem |
| Alertas MapBiomas | 6 h | idem |
| Malha municipal IBGE por UF | 180 dias | `municipios_<UF>` |
| Tiles de basemap | 30 dias | `z/x/y + mosaico` |

Offline: usa o cache expirado **com aviso de idade** na conversa e no `validacao.json`. Camada
sem cache entra vazia, aciona o check `S09` e o job continua com o que tem — falha de uma camada
externa **nunca** aborta o mapa.

## Qualidade e gotchas

Lista de campo, herdada do GeoForest e do Cerebro. Cada item já causou um bug real.

| # | Gotcha | Consequência se ignorado |
|---|---|---|
| 1 | `sema.mt.gov.br` bloqueia IP fora do Brasil | timeout inexplicável em nuvem estrangeira |
| 2 | Paginação `startIndex` na SEMA (`PagingIsTransactionSafe=FALSE`) | timeout ou `Cannot do natural order without a primary key` |
| 3 | INTERSECTS perde feições | tabela de quantitativos errada, silenciosamente |
| 4 | WMS responde HTTP 200 com XML de erro | imagem "vazia" no mapa; validar magic bytes |
| 5 | FUNAI só fala WFS 1.0 (`typeName`, `maxFeatures`) | 400 em toda chamada |
| 6 | INCRA só devolve GML, e é lento (120 s+) | parser próprio, timeout maior |
| 7 | SISCOM atrás de Cloudflare | usar PAMGIA como fonte primária de embargo |
| 8 | CAR com vários requerimentos | ordenar por `REQUERIMENTO_ID` desc |
| 9 | Zona UTM hardcoded | imóvel do oeste de MT sai deslocado |
| 10 | Mojibake em `.dbf` | `Ãrea` no rótulo do mapa |
| 11 | Anel GeoJSON aberto | WKT inválido, CQL quebra |
| 12 | Malhas do IBGE vêm **gzip** | JSON ilegível se não descomprimir |
| 13 | `count`/`maxFeatures` ausente | resposta gigante, timeout |
| 14 | `Chave` de município do SIMCAR ≠ código IBGE | município errado no minimapa |
| 15 | `.prj` ausente no shapefile do cliente | CRS adivinhado, área errada por ordens de grandeza |
| 16 | `.lock` do ArcMap na pasta | escrita falha com erro obscuro |

## Checklist de implementação

- [ ] Indexador de pasta com watcher incremental
- [ ] Resolução de papel por nome → alias → heurística → pergunta
- [ ] Bateria de validação de shapefile completa
- [ ] Cálculo de área em UTM com `union` e arredondamento de 4 casas
- [ ] Parser de recibo do CAR com descarte de CPF
- [ ] Leitor de `.zip` do SIMCAR com anti *zip slip*
- [ ] Cliente de catálogo lendo `shared/catalog/`
- [ ] Pipeline BBOX → clip → reprojeção → materialização
- [ ] Cache com TTL por tema e modo offline com aviso de idade
- [ ] Conferência área declarada × área calculada
- [ ] Detecção de sub-área fora do perímetro
- [ ] Os 16 gotchas cobertos por teste ou por comentário no código apontando para esta tabela

## Pendências

| # | Questão |
|---|---|
| P1 | GeoPackage em vez de shapefile para camadas materializadas — o ArcMap 10.x lê `.gpkg` mal; provável que shapefile continue |
| P2 | Teto de feições por camada num mapa: 500? 2000? O GeoForest usa até 50.000, mas é análise, não cartografia |
| P3 | Reindexação de pasta muito grande (> 5.000 arquivos) precisa de estratégia de amostragem |
| P4 | Como versionar o cache entre atualizações do app sem invalidar tudo |
| P5 | Detectar automaticamente que a pasta é uma "análise" (padrão de nomes) e sugerir a série inteira de mapas |
