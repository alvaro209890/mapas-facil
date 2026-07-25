# 05 — Motor de geração (.mxd e .pdf)

Como um `MapSpec` vira um `.mxd` abrível no ArcMap e um `.pdf` no padrão IMAP. O contrato do
`MapSpec`, as 9 etapas do job e o protocolo estão em [01-arquitetura.md](01-arquitetura.md); o
ambiente de execução e a ponte de subprocess, em [04-agente-local.md](04-agente-local.md).

## Princípio: declarativo, nunca gerativo

O `MapSpec` é dado. O motor é código versionado, testado e auditável. A IA produz e edita o
`MapSpec`; ela **nunca** produz código Python, nem expressão `arcpy`, nem `definitionQuery` livre
— filtros passam por um construtor de consulta com campos e operadores validados contra o schema
do shapefile. Uma feature de layout só entra no `MapSpec` se existir equivalente em
`arcpy.mapping` ou `arcpy.mp`, e um spec malformado é rejeitado, nunca "corrigido em silêncio".

Alternativa descartada: IA gerando script `arcpy` sob medida por mapa. Mais flexível e
completamente insegurável — código arbitrário rodando na máquina do cliente, sem como testar
regressão nem reproduzir um bug relatado.

## Estratégia de template

**Não criamos `.mxd` do zero.** `arcpy.mapping` sabe abrir, editar e salvar documentos; não sabe
*criar* layout — não existe API para criar data frames, grade DMS (graticule), indicador de
extensão do minimapa, seta-norte ou barra de escala em documento vazio. Montar o layout IMAP por
código seria reimplementar meio ArcMap.

Partimos de **templates `.mxd` reais**, já diagramados por quem faz esses mapas à mão. Os quatro
`.mxd` do acervo do cliente (`Dinamica_2008`, `Dinamica_2019`, `Embargos_IBAMA`,
`Alertas_MAPBIOMAS_2`) são o ponto de partida: abertos no ArcMap, elementos renomeados segundo a
convenção abaixo, resultado versionado em `shared/templates/`. O motor faz então só o que é
confiável: **repontar fontes, ajustar extent, escrever texto em elementos nomeados e exportar**.

### Convenção de nomes dos elementos

O nome do elemento é o contrato. Template sem um elemento obrigatório com o nome exato = falha
`AG-041` na etapa `abrindo_template`, e não um PDF silenciosamente errado.

| Tipo `arcpy.mapping` | Nome | Obrigatório | Função |
|---|---|---|---|
| `DATAFRAME_ELEMENT` | `MAPA` | sim | data frame principal, com grade DMS configurada |
| `DATAFRAME_ELEMENT` | `MINIMAPA` | não | inset de localização, com *extent indicator* apontando para `MAPA` |
| `TEXT_ELEMENT` | `TITULO` | sim | título na caixa branca do topo |
| `TEXT_ELEMENT` | `META_SATELITE`, `META_ORBITA`, `META_DATA`, `META_DATUM` | não | os quatro campos de `metadados_imagem` |
| `TEXT_ELEMENT` | `TABELA_C<coluna>L<linha>` | não | células da tabela de quantitativos |
| `LEGEND_ELEMENT` | `LEGENDA` | sim | legenda |
| `PICTURE_ELEMENT` | `TABELA_QUANTITATIVOS` | não | alternativa em imagem para a tabela |
| `PICTURE_ELEMENT` | `LOGO` | não | marca; `sourceImage` trocável |
| `MAPSURROUND_ELEMENT` | `SETA_NORTE` | não | seta-norte |
| `MAPSURROUND_ELEMENT` | `ESCALA_BARRA` | não | barra de escala (desligada por padrão no IMAP) |

`TEXT_ELEMENT` aceita texto vazio, mas `MAPSURROUND_ELEMENT` e `GRAPHIC_ELEMENT` **não têm
propriedade `visible`** em `arcpy.mapping`. Para desligar, mover para fora da página
(`elem.elementPositionX = -100`) e restaurar a posição gravada no manifesto. Feio, mas é o que a
API permite, e é estável desde a 10.0.

### `shared/templates/MANIFEST.json`

```json
{
  "manifest_version": 3,
  "atualizado_em": "2026-07-24",
  "templates": [
    {
      "id": "dinamica_2026",
      "nome": "Dinâmica de uso do solo — A4 paisagem (IMAP)",
      "arquivo": "Dinamica_2026.mxd",
      "sha256": "5b1d0c8f2a7e4a19c3d6b8f0e2a4c6d8091b3d5f7a9c1e3b5d7f9a1c3e5b7d90",
      "versao_arcmap": "10.6",
      "formato_pagina": { "papel": "A4", "orientacao": "paisagem", "mm": [297, 210] },
      "data_frames": [
        { "nome": "MAPA", "papel": "principal", "retangulo_mm": [6.5, 51.5, 284.0, 152.0],
          "grade": "dms", "grade_linhas": false },
        { "nome": "MINIMAPA", "papel": "localizacao", "retangulo_mm": [6.5, 6.0, 62.0, 40.0],
          "extent_indicator_para": "MAPA" }
      ],
      "elementos": [
        { "nome": "TITULO", "tipo": "TEXT_ELEMENT", "obrigatorio": true,
          "posicao_mm": [148.5, 200.0], "fonte_pt": 21 },
        { "nome": "META_SATELITE", "tipo": "TEXT_ELEMENT", "posicao_mm": [96.0, 32.0] },
        { "nome": "META_ORBITA", "tipo": "TEXT_ELEMENT", "posicao_mm": [96.0, 27.5] },
        { "nome": "META_DATA", "tipo": "TEXT_ELEMENT", "posicao_mm": [96.0, 23.0] },
        { "nome": "META_DATUM", "tipo": "TEXT_ELEMENT", "posicao_mm": [96.0, 18.5] },
        { "nome": "LEGENDA", "tipo": "LEGEND_ELEMENT", "obrigatorio": true,
          "posicao_mm": [170.0, 36.0], "colunas": 1 },
        { "nome": "TABELA_GRADE", "tipo": "GRAPHIC_ELEMENT", "linhas_max": 8, "colunas_max": 6 },
        { "nome": "TABELA_QUANTITATIVOS", "tipo": "PICTURE_ELEMENT",
          "posicao_mm": [196.0, 60.0], "tamanho_mm": [86.0, 34.0] },
        { "nome": "LOGO", "tipo": "PICTURE_ELEMENT", "posicao_mm": [268.0, 20.0] },
        { "nome": "SETA_NORTE", "tipo": "MAPSURROUND_ELEMENT", "posicao_mm": [268.0, 143.0] },
        { "nome": "ESCALA_BARRA", "tipo": "MAPSURROUND_ELEMENT",
          "posicao_mm": [40.0, 56.0], "padrao_visivel": false }
      ],
      "camadas_esperadas": [
        { "nome_no_mxd": "LOTE_PRINCIPAL", "obrigatoria": true, "geometria": "Polygon",
          "lyr_simbologia": "estilos/lote_principal.lyr" },
        { "nome_no_mxd": "AVN", "lyr_simbologia": "estilos/avn.lyr" },
        { "nome_no_mxd": "AC", "lyr_simbologia": "estilos/ac.lyr" },
        { "nome_no_mxd": "AUAS", "lyr_simbologia": "estilos/auas.lyr" },
        { "nome_no_mxd": "BASEMAP", "tipo": "esri_world_imagery" }
      ],
      "escalas_permitidas": [10000, 12500, 15000, 20000, 22000, 25000, 30000, 40000, 50000],
      "crs_suportados": ["EPSG:31981", "EPSG:31982", "EPSG:31983"]
    }
  ]
}
```

O `sha256` é conferido pelo doctor e de novo na etapa `abrindo_template`. Template alterado à mão
pelo usuário = job recusado com `AG-032`, porque o layout deixaria de casar com o manifesto.

## Pipeline ArcMap 10.x (`arcpy.mapping`, Python 2.7)

Caminho primário, porque é o único que entrega `.mxd`. Arquivo
`agent/mapasfacil_agent/scripts/arcpy_export.py`, executado pelo interpretador do ArcMap.

### Abertura

```python
# -*- coding: utf-8 -*-
"""Executado pelo Python 2.7 do ArcMap. NUNCA importado pelo host 3.11."""
import codecs, json, os, shutil
import arcpy

with codecs.open(os.environ["MAPASFACIL_JOB_JSON"], "r", "utf-8") as f:
    entrada = json.load(f)              # caminho por env var, nunca argv (ver 04)

arcpy.env.overwriteOutput = True
# Trabalhar sobre uma CÓPIA: MapDocument mantém lock no arquivo aberto.
trabalho = os.path.join(entrada[u"temp_dir"], u"trabalho.mxd")
shutil.copy2(entrada[u"template"], trabalho)

mxd = arcpy.mapping.MapDocument(trabalho)
mxd.relativePaths = True                # .mxd portátil junto da pasta do job
df = arcpy.mapping.ListDataFrames(mxd, "MAPA")[0]
```

`relativePaths = True` faz o `.mxd` continuar abrindo se o usuário mover a pasta do job inteira —
desde que os shapefiles estejam dentro dela, que é por que o agente materializa camadas WFS em
`<job_id>\camadas\` e não em `%TEMP%` ([04](04-agente-local.md)).

### Repontar fontes

```python
por_nome = dict((c[u"nome_no_mxd"], c) for c in entrada[u"camadas"])

for lyr in arcpy.mapping.ListLayers(mxd, "", df):
    alvo = por_nome.get(lyr.name)
    if alvo is None or not lyr.supports(u"DATASOURCE"):
        continue
    pasta = os.path.dirname(alvo[u"shp"])
    dataset = os.path.splitext(os.path.basename(alvo[u"shp"]))[0]
    lyr.replaceDataSource(pasta, u"SHAPEFILE_WORKSPACE", dataset, True)
    if alvo.get(u"filtro"):
        lyr.definitionQuery = alvo[u"filtro"]
    lyr.visible = True
```

`replaceDataSource(workspace_path, workspace_type, dataset_name, validate)` com `validate=True`
levanta erro se o dataset não existir — que é o que queremos: falhar aqui, não descobrir no PDF.
Para geodatabase o tipo seria `FILEGDB_WORKSPACE`; o produto usa shapefile porque é o que sai do
CAR e do SIMCAR. Camadas do `MapSpec` ausentes do template entram assim:

```python
nova = arcpy.mapping.Layer(alvo[u"lyr_simbologia"])
nova.replaceDataSource(pasta, u"SHAPEFILE_WORKSPACE", dataset, True)
nova.name = alvo[u"nome_no_mxd"]
referencia = arcpy.mapping.ListLayers(mxd, u"LOTE_PRINCIPAL", df)
if referencia:
    arcpy.mapping.InsertLayer(df, referencia[0], nova, u"BEFORE")
else:
    arcpy.mapping.AddLayer(df, nova, u"TOP")
```

`InsertLayer` é preferível a `AddLayer` sempre que a ordem importa — e no IMAP ela importa: AVN e
AUAS são hachuras que precisam ficar abaixo do contorno do lote, senão o contorno vermelho some.
`AddLayer(df, lyr, "TOP" | "BOTTOM" | "AUTO_ARRANGE")` fica só para o basemap (`"BOTTOM"`).

### Simbologia por arquivo `.lyr`

```python
if alvo.get(u"lyr_simbologia") and os.path.exists(alvo[u"lyr_simbologia"]):
    fonte_simb = arcpy.mapping.Layer(alvo[u"lyr_simbologia"])
    arcpy.mapping.UpdateLayer(df, lyr, fonte_simb, True)   # symbology_only
    del fonte_simb
```

`UpdateLayer(..., symbology_only=True)` copia a simbologia de um `.lyr` para uma camada já no
documento; `arcpy.ApplySymbologyFromLayer_management` faz algo parecido, mas opera sobre *feature
layers* de geoprocessamento.

**Por que `.lyr` versionado em vez de simbologia por código:** o objeto `lyr.symbology` de
`arcpy.mapping` só expõe um punhado de propriedades (`UniqueValuesSymbology`,
`GraduatedColorsSymbology`, `valueField`, `classBreakValues`…) e **não** dá acesso a
preenchimento, espessura de linha, hachura, transparência nem ordem de renderização. A hachura
`xxx` verde vazada da AVN é impossível de configurar por código na 10.x. Com `.lyr`, o estilo é
definido uma vez no ArcMap por um cartógrafo, versionado e conferido por `sha256` — mesma lógica
do template: quem sabe diagramar é o ArcMap. Em troca, `estilo` do `MapSpec` não é livre: mapeia
para um conjunto finito de `.lyr` catalogados. *"Deixa a ATP amarela"* resolve para
`lote_principal_amarelo.lyr`; cor fora do catálogo é recusada, com sugestão da mais próxima.

### Extent, escala e rótulos

```python
df.extent = arcpy.Extent(*entrada[u"bbox"])
df.scale = entrada[u"escala"]           # SEMPRE depois de df.extent

if alvo.get(u"campo_rotulo"):
    for classe in lyr.labelClasses:
        classe.showClassLabels = True
        classe.expression = u'[%s]' % alvo[u"campo_rotulo"]
    lyr.showLabels = True
```

A ordem não é opcional: atribuir `df.extent` **redefine a escala** para caber no retângulo pedido,
então um `df.scale` anterior é perdido. O padrão é `extent` para centralizar, `scale` para fixar a
escala "bonita".

Rótulo estático de lote (`"Fazenda Trevisol (Lote 65)\nMatrícula 13.533"`) **não** é rótulo de
camada: é um `TEXT_ELEMENT` posicionado sobre o data frame. Rótulo de camada no ArcMap é
reposicionado pelo motor de rotulagem e sai onde ele quiser.

### Elementos de layout

```python
FORA_DA_PAGINA = -100.0
textos = dict((e.name, e) for e in arcpy.mapping.ListLayoutElements(mxd, u"TEXT_ELEMENT"))

def escrever(nome, valor):
    elemento = textos.get(nome)
    if elemento is not None:
        elemento.text = valor if valor else u" "      # unicode, nunca str codificado

meta = entrada.get(u"metadados_imagem") or {}
escrever(u"TITULO", entrada[u"titulo"])
escrever(u"META_SATELITE", meta.get(u"satelite_sensor"))
escrever(u"META_ORBITA", meta.get(u"orbita_ponto"))
escrever(u"META_DATA", meta.get(u"data_aquisicao"))
escrever(u"META_DATUM", meta.get(u"datum"))

for legenda in arcpy.mapping.ListLayoutElements(mxd, u"LEGEND_ELEMENT", u"LEGENDA"):
    legenda.autoAdd = False
    for item in legenda.listLegendItemLayers():
        if item.name not in entrada[u"legenda_camadas"]:
            legenda.removeItem(item)
    legenda.adjustColumnCount(int(entrada.get(u"legenda_colunas", 1)))

for figura in arcpy.mapping.ListLayoutElements(mxd, u"PICTURE_ELEMENT", u"LOGO"):
    if entrada.get(u"logo"):
        figura.sourceImage = entrada[u"logo"]

if not entrada[u"elementos_layout"].get(u"escala_grafica"):
    for barra in arcpy.mapping.ListLayoutElements(mxd, u"MAPSURROUND_ELEMENT", u"ESCALA_BARRA"):
        barra.elementPositionX = FORA_DA_PAGINA
```

`legenda.autoAdd = False` antes de mexer é essencial: com `autoAdd` ligado, toda camada adicionada
depois reaparece na legenda e a lista foge do controle. O que **não** é acessível por
`arcpy.mapping` e precisa vir pronto do template: grade DMS (intervalo, formato dos rótulos,
ticks), *extent indicator* do minimapa, moldura do data frame, estilo da seta-norte, fonte e cor
dos elementos de texto.

### Salvar e exportar

```python
quebradas = [l.name for l in arcpy.mapping.ListBrokenDataSources(mxd)]

if u"mxd" in entrada[u"saidas"]:
    mxd.saveACopy(entrada[u"saida_mxd_tmp"])
if u"pdf" in entrada[u"saidas"]:
    arcpy.mapping.ExportToPDF(mxd, entrada[u"saida_pdf_tmp"],
                              resolution=300, image_quality=u"BEST", colorspace=u"RGB",
                              compress_vectors=True, image_compression=u"ADAPTIVE",
                              embed_fonts=True, layers_attributes=u"LAYERS_ONLY",
                              georef_info=True)
if u"preview_png" in entrada[u"saidas"]:
    arcpy.mapping.ExportToPNG(mxd, entrada[u"saida_png_tmp"], resolution=96)

del mxd                                 # libera o lock do .mxd de trabalho
```

Cuidados que já custaram bug em projeto anterior:

- **`del mxd` é obrigatório**, dentro de `finally`. Sem isso o arquivo fica travado e o
  `os.replace` atômico do host falha com `WindowsError 32`.
- **`arcpy.RefreshActiveView()` e `arcpy.RefreshTOC()` não têm efeito em script standalone** — só
  valem com `MapDocument("CURRENT")` dentro do ArcMap. Chamar não quebra, mas dá falsa sensação de
  garantia; o `ExportToPDF` sempre redesenha.
- **`saveACopy` antes de `ExportToPDF`**, para o `.mxd` entregue ser exatamente o estado que gerou
  o PDF; e **`ListBrokenDataSources` antes do `del`**.
- **Encoding.** `# -*- coding: utf-8 -*-` no topo; ler com `codecs.open(..., "utf-8")`; atribuir
  `unicode` a `elemento.text` — `u"Dinâmica".encode("utf-8")` num `TextElement` sai como
  `DinÃ¢mica` no PDF; escrever a saída com `codecs.open(path, "w", "utf-8")` e
  `json.dump(..., ensure_ascii=False)`.
- **Caminhos de saída em ASCII**: `arcpy` 10.x tem falhas conhecidas com acentuação em caminho de
  arquivo de saída. O agente já sanitiza `<projeto>`.

## Pipeline ArcGIS Pro (`arcpy.mp`, Python 3.x)

Caminho alternativo, no `...\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe` — Python 3,
então `f-string` e `pathlib` são permitidos aqui.

```python
import arcpy

aprx = arcpy.mp.ArcGISProject(entrada["template_aprx"])
mapa = aprx.listMaps("MAPA")[0]
for camada in mapa.listLayers():
    alvo = por_nome.get(camada.name)
    if alvo is None or not camada.supports("CONNECTIONPROPERTIES"):
        continue
    novo = {"dataset": f"{alvo['dataset']}.shp",
            "workspace_factory": "Shape File",
            "connection_info": {"database": alvo["pasta"]}}
    camada.updateConnectionProperties(camada.connectionProperties, novo, validate=True)
    if alvo.get("filtro"):
        camada.definitionQuery = alvo["filtro"]

layout = aprx.listLayouts("IMAP_A4_PAISAGEM")[0]
quadro = layout.listElements("MAPFRAME_ELEMENT", "MAPA")[0]
quadro.camera.setExtent(arcpy.Extent(*entrada["bbox"]))   # bbox já no CRS do mapa
quadro.camera.scale = entrada["escala"]
for texto in layout.listElements("TEXT_ELEMENT", "TITULO"):
    texto.text = entrada["titulo"]
layout.exportToPDF(entrada["saida_pdf_tmp"], resolution=300, image_quality="BEST")
aprx.saveACopy(entrada["saida_aprx_tmp"])
del aprx
```

### A limitação que decide a arquitetura

**ArcGIS Pro não gera `.mxd`.** `arcpy.mp` salva `.aprx`; não existe `saveAsMXD`, e o comando de
interface "Save As ArcMap Document" foi removido na linha 3.x do Pro. A partir do Pro 3, o caminho
de volta para ArcMap não existe.

Portanto ArcMap é o caminho primário e Pro atende PDF e `.aprx`. Um usuário só com Pro que peça
`strict_mxd: true` recebe recusa **na criação do job**, com essa explicação — não uma falha depois
de dois minutos. Isso também implica manter duas famílias de template em paridade visual, custo
real que está nas pendências.

## Escala

Escalas permitidas (herdadas do NexoGeo e ampliadas para o padrão do cliente, que usa ~1:22.000):

```
1.000   2.000   2.500   5.000   7.500   10.000  12.500  15.000
20.000  22.000  25.000  30.000  40.000  50.000  60.000  75.000
100.000 150.000 200.000 250.000 500.000 1.000.000
```

Algoritmo de `escala: "auto"`: calcular o bbox da união das geometrias visíveis no CRS projetado
do `MapSpec`; aplicar margem de **15%** em cada eixo (valor do NexoGeo, validado contra os
PDFs-modelo); ler o retângulo do data frame `MAPA` em milímetros no manifesto; a escala mínima é
`max(largura_m / (largura_mm / 1000), altura_m / (altura_mm / 1000))`; escolher a **menor** escala
da lista maior ou igual a esse valor, restrita a `escalas_permitidas` do template; se nenhuma
serve, usar a maior e emitir aviso.

Arredondar sempre **para cima** na lista, nunca para baixo: escala menor que a necessária corta a
área. A escala escolhida é gravada no `MapSpec` da versão, para que reexecutar o job dê o mesmo
resultado mesmo que os dados mudem depois.

## Tabela de quantitativos

Cálculo no host Python 3.11 com `shapely` e `pyproj` — **não** no script `arcpy` 2.7:

1. Reprojetar tudo para o CRS projetado do `MapSpec` (UTM SIRGAS 2000, EPSG:31981/31982/31983
   conforme o fuso). CRS geográfico é rejeitado: área em graus² não existe.
2. Corrigir geometrias inválidas (`make_valid` / `buffer(0)`), registrando quantas.
3. Para cada lote × cada classe temática, `lote.intersection(classe)`, somar a área e converter
   para hectare (`m² / 10.000`).
4. Arredondar cada célula para 2 casas e formatar em pt-BR (`1.234,56`).
5. Linha `TOTAL` = **soma dos valores já arredondados**, para a coluna fechar visualmente. Total
   calculado sobre os brutos difere da soma visível por centavos de hectare e gera pergunta do
   cliente toda vez.
6. Sobreposição entre classes gera aviso: no IMAP, AVN + AC + AUAS deveriam particionar o lote.

Fazer isso no host tem três razões: é testável em CI (Linux, sem ArcGIS), é determinístico, e a
mesma tabela alimenta o renderizador nativo de fallback.

### Como injetar no layout

| Abordagem | Como | A favor | Contra |
|---|---|---|---|
| A — `TEXT_ELEMENT` tabulado | um elemento com texto multilinha em fonte monoespaçada | trivial; número de linhas livre | `arcpy.mapping` não tem tab stops nem borda de célula; alinhamento por contagem de espaços; não parece tabela do ArcMap |
| B — grade gráfica com células nomeadas | template traz retângulos e `TEXT_ELEMENT` `TABELA_C<n>L<m>` até `linhas_max` | visual idêntico ao mapa feito à mão; **editável no ArcMap** | máximo de linhas fixo; linhas sobrando vão para fora da página |
| C — `PICTURE_ELEMENT` com PNG | host renderiza a tabela em matplotlib e troca `sourceImage` | flexível, idêntico ao renderizador nativo | vira imagem no `.mxd`: não editável, não selecionável, borra no zoom |

**Recomendação: B como padrão, C como escape.** O `.mxd` é o produto; entregar a tabela como
imagem colada mata metade do valor do entregável. Templates carregam grade para até 8 linhas
(cobre 1 a 4 lotes + `TOTAL`). Acima disso o motor cai para C e registra aviso. A é descartada.

## Renderizador nativo de fallback

Motor matplotlib, herdado conceitualmente de `core/nexomap_renderer.py` do NexoGeo, onde já
produzia mapas calibrados contra os PDFs-modelo reais do cliente (`docs/PADRAO_IMAP_RENDERER.md`
daquele repositório). É usado em três situações: **preview rápido** durante a conversa, antes de
rodar o ArcMap (que leva 60–120 s); **usuário sem ArcMap nem Pro**, com `strict_mxd: false`; e
**CI**, onde não há ArcGIS nenhum — é o que permite testar layout em pull request.

Garante: A4 paisagem no padrão IMAP, grade DMS com rótulos `52°15'0"W`, título em caixa branca,
bloco METADADOS IMAGEM, tabela com linha TOTAL em negrito, minimapa de municípios IBGE,
seta-norte, legenda com swatches vazados. Não garante: identidade pixel a pixel com o ArcMap,
fidelidade de hachuras, o basemap PLANET do cliente e — o principal — **não produz `.mxd`**.

Regra vinculante: o PDF nativo nunca é o entregável principal. Sai marcado no `validacao.json`
como `motor: "nativo"`, a interface o rotula como "prévia", e a validação de conformidade IMAP
roda com o mesmo rigor, para que a diferença de motor não vire desculpa.

## Validação de saída (etapa `validando_saida`)

| # | Check | Ferramenta | Severidade |
|---|---|---|---|
| 1 | **Nenhuma camada com fonte quebrada no `.mxd`** | `arcpy.mapping.ListBrokenDataSources` | *hard* |
| 2 | PDF abre sem erro | PyMuPDF (`fitz.open`) | *hard* |
| 3 | 1 página, no tamanho do manifesto (±1 mm) | PyMuPDF | *hard* |
| 4 | Página não está em branco (pixels não-brancos > 5%) | rasterizar a 150 dpi | *hard* |
| 5 | Título do `MapSpec` aparece no texto extraível | `page.get_text()` | *hard* |
| 6 | Escala do PDF igual à do `MapSpec` | `df.scale` reportado pelo script | *hard* |
| 7 | Os 4 metadados de imagem aparecem no texto | `page.get_text()` | *soft* |
| 8 | Elementos por região: título topo-centro, legenda na faixa inferior, minimapa à esquerda, tabela no quadrante indicado | recortes do raster | *soft* |
| 9 | Tamanho do arquivo entre 300 KB e 40 MB | `os.stat` | *soft* |
| 10 | Feições desenhadas por camada > 0 quando esperado | relatório do script | *soft* |

O check 1 é o mais importante do produto inteiro. Um `.mxd` bonito no PDF mas com `!` vermelho ao
abrir no ArcMap é, para o usuário, entrega quebrada — é literalmente o critério de sucesso 4 de
[00-visao-e-escopo.md](00-visao-e-escopo.md). Falha em qualquer check *hard* bloqueia a entrega:
job vai para `failed` com `AG-070` e o relatório abre na interface.

## Determinismo e reprodutibilidade

Mesmo `MapSpec` + mesmos dados = mesmo PDF. É o que torna possível teste de regressão visual, e o
que permite responder "por que este mapa saiu diferente do de ontem".

- **Ordenação estável de camadas**: a ordem no `.mxd` vem do array `camadas` do `MapSpec`, nunca
  de iteração sobre `dict`; deduplicação usa `dict.fromkeys`, jamais `set`.
- **Semente fixa** onde houver aleatoriedade (deslocamento de rótulo, jitter do minimapa).
- **Escala e extent gravados no `MapSpec`** depois de resolvidos, não recalculados na reexecução.
- **Versões registradas** no `validacao.json`: agente, ArcMap, template com `sha256`, catálogo e
  `sha256` de cada shapefile de entrada.
- **Comparação por raster, não por bytes**: o PDF do ArcMap embute `CreationDate` e IDs internos,
  então dois PDFs idênticos têm `sha256` diferentes. O teste de regressão rasteriza a 150 dpi e
  compara com um *golden image* versionado, tolerância de 0,3% de pixels diferentes.

## Matriz de compatibilidade

| Ambiente | `.mxd` | `.pdf` | `preview.png` | Motor | Observação |
|---|---|---|---|---|---|
| ArcMap 10.8 + licença | sim | sim (ArcMap) | sim | `arcpy.mapping` | alvo de desenvolvimento e referência de qualidade |
| ArcMap 10.7 / 10.6 + licença | sim | sim (ArcMap) | sim | `arcpy.mapping` | mesma API; 10.6 é o mínimo suportado |
| ArcMap sem licença disponível | não | sim (nativo) | sim | matplotlib | `AG-031`, mensagem específica de licença |
| ArcGIS Pro 3.x | **não** | sim (Pro) | sim | `arcpy.mp` | entrega `.aprx`; `strict_mxd` recusado |
| ArcMap + Pro na mesma máquina | sim | sim (ArcMap) | sim | `arcpy.mapping` | ArcMap tem prioridade quando `mxd` está em `saidas` |
| Sem ArcGIS | não | sim (nativo) | sim | matplotlib | rótulo "prévia" na interface |

Um template salvo em 10.8 **não abre** em 10.6; por isso os templates são salvos na versão mínima
suportada — versões novas abrem documentos antigos, o contrário não.

## Smoke test manual em máquina com ArcMap

A cada release do agente ou mudança de template, em Windows 11 + ArcMap 10.8.1, licença single-use.

1. Rodar o doctor pela bandeja: `licenca.estado: "Available"`, `templates[*].sha256_ok: true`,
   `pronto_para_mxd: true`.
2. Abrir cada template no ArcMap e conferir que os nomes de elemento batem com o manifesto.
3. Gerar a Dinâmica de um imóvel-fixture com 2 lotes, AVN, AC e AUAS, `escala: "auto"`.
4. Cronometrar: do envio ao `job.done` em menos de 3 minutos.
5. Abrir `mapa.mxd` no ArcMap: **nenhum `!` vermelho**, todas as camadas desenham.
6. Conferir escala mostrada, grade DMS no formato `52°15'0"W`, legenda só com as camadas do spec,
   título e METADADOS IMAGEM com acentuação correta.
7. Abrir `mapa.pdf` lado a lado com o PDF-modelo do cliente da mesma série.
8. Conferir a tabela: valores por lote × classe em hectare, `TOTAL` fechando com a soma visível.
9. Mover a pasta `<job_id>` inteira e reabrir o `.mxd`: camadas continuam resolvendo.
10. Repetir o mesmo job e comparar os dois PDFs por raster: diferença abaixo de 0,3%.
11. Cancelar um job aos 20 s: nenhum `python.exe` órfão, nenhum `.tmp` na pasta de saída.
12. Desligar a rede e repetir com camadas em cache: aviso `basemap_ausente` e PDF gerado.

## Pendências e decisões abertas

| # | Questão | Situação |
|---|---|---|
| P1 | Preparar os 4 `.mxd` do acervo como templates | trabalho manual no ArcMap; caminho crítico do M2 e ninguém mais pode fazer por nós |
| P2 | Manter família `.aprx` em paridade com a `.mxd` | custo dobrado de manutenção; adiar até haver usuário só-Pro |
| P3 | Grade DMS não é controlável por `arcpy.mapping` | se um mapa precisar de intervalo diferente, será um template por intervalo — medir quantos casos reais existem |
| P4 | Basemap Esri World Imagery exige login do ArcGIS Online no ArcMap | avaliar PLANET via `.lyr` de serviço, raster local recortado pelo agente, ou mosaico SEMA (`Mosaicos:MOSAICO_SPOT_SEPLAN` / Landsat) como fundo WMS — receitas em [13](13-wfs-e-servicos-geo.md) |
| P5 | Tabela com mais de 8 linhas | fallback para imagem definido; avaliar template "tabela grande" em página separada, como o `Dinamica_2026_quantitativos.pdf` do cliente |
| P6 | Catálogo de `.lyr` de simbologia | quantas variações de cor e hachura oferecer sem virar editor gráfico? |
| P7 | Golden images de regressão visual | precisam ser geradas na máquina com ArcMap; decidir se entram no repositório |
| P8 | `Dinamica_2008` e `Dinamica_2019`: dois templates ou um parametrizado? | inspecionar os `.mxd` antes de decidir; um só reduz manutenção pela metade |
| P9 | GeoTIFF / PNG georreferenciado | fora da v1; `georef_info=True` no PDF já cobre parte do caso |
