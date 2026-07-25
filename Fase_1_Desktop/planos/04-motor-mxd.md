# F1-04 — Motor de `.mxd`

O documento mais importante da Fase 1. Como um `MapSpec` vira um `.mxd` que **abre no ArcMap de
outra pessoa** e um `.pdf` no padrão Harmonia.

O contrato do `MapSpec` está em
[`../../planos/02-mapspec-contrato.md`](../../planos/02-mapspec-contrato.md); o padrão visual, em
[`../../planos/01-padrao-imap-harmonia.md`](../../planos/01-padrao-imap-harmonia.md); o
renderizador de PDF sem ArcMap, em [`05-motor-pdf-nativo.md`](05-motor-pdf-nativo.md).

## O problema central

Um `.mxd` guarda **referências**, não dados. As camadas apontam para `C:\Users\Usuario\Downloads\
Analise_de_area\...\SHP\ATP.shp`. Abrir esse arquivo em outro PC dá `!` vermelho em tudo.

É por isso que, no trabalho manual, "adaptar os mapas" significa recriar a estrutura de pastas
que o `.mxd` espera. O objetivo do motor é fazer isso automaticamente, de forma que o entregável
seja **uma pasta autocontida**:

```
Entrega/
├─ Dinamica_2026.mxd        ← caminhos RELATIVOS, apontando para SHP\ e recursos\
├─ Dinamica_2026.pdf
├─ Quantitativos.xlsx
├─ SHP\                     ← todas as camadas materializadas, nomes canônicos
│  ├─ ATP.shp  ·  AVN.shp  ·  AREA_CONSOLIDADA.shp  ·  AUAS.shp
│  └─ lml_municipio_a.shp  ·  lml_uf_a.shp
└─ recursos\
   ├─ tabela_quantitativos.png
   └─ logo_imap.png
```

Mova a pasta inteira para qualquer PC com ArcMap: o `.mxd` abre e desenha. Isso vale tanto para o
caminho com ArcPy quanto para o caminho sem ArcMap.

## Princípio: declarativo, nunca gerativo

O `MapSpec` é dado. O motor é código versionado, testado e auditável. A IA **nunca** produz
código Python, expressão `arcpy` ou `definitionQuery` livre. Um spec malformado é rejeitado,
nunca "corrigido em silêncio".

Alternativa descartada: IA gerando script `arcpy` sob medida por mapa. Mais flexível e
completamente insegurável — código arbitrário na máquina do cliente, sem como testar regressão
nem reproduzir um bug relatado.

## Estratégia de template

**Não criamos `.mxd` do zero.** `arcpy.mapping` sabe abrir, editar e salvar; não sabe *criar*
layout — não há API para criar data frames, grade DMS, indicador de extensão do minimapa, rosa
dos ventos ou moldura em documento vazio. Montar o layout IMAP por código seria reimplementar
meio ArcMap.

Partimos dos **`.mxd` reais do acervo** em [`../../Referencias_IMAP/MXD/`](../../Referencias_IMAP/MXD/):
24 arquivos já diagramados por quem faz esses mapas à mão. Eles passam por uma **preparação
única** (seção seguinte) e viram templates versionados em `shared/templates/`.

O motor faz então só o que é confiável: **repontar fontes, ajustar extent e escala, escrever
texto em elementos nomeados, trocar a definition query do município e exportar**.

### Preparação do template (trabalho manual, uma vez por template)

Feito no ArcMap, por uma pessoa, e é **caminho crítico** do M2 — ninguém mais pode fazer por nós.

- [ ] Abrir o `.mxd` do acervo
- [ ] Renomear cada camada para o nome canônico da tabela abaixo
- [ ] Remover camadas mortas de análises anteriores
- [ ] Corrigir textos herdados (`Área concolidada`, `Dadosr:`, título de outro mapa)
- [ ] Apontar cada camada para `.\SHP\<nome_canonico>.shp` (pasta ao lado do `.mxd`)
- [ ] Ligar **File → Map Document Properties → Store relative pathnames**
- [ ] Renomear os elementos de layout conforme a convenção
- [ ] Dar **padding** aos elementos de texto patcháveis (ver [T2](#t2--patch-calibrado-sem-arcmap))
- [ ] Salvar na **versão mínima suportada (10.6)** — 10.8 não abre em 10.6; o contrário sim
- [ ] Registrar no `MANIFEST.json`: `sha256`, retângulos, escalas, CRS, offsets de patch
- [ ] Rodar o smoke test do template

### Nomes canônicos de camada

O nome da camada **é o contrato** entre o template e o `MapSpec` (`camadas[].nome_no_mxd`).
Nome ausente no template = falha `AG-120`, não um PDF silenciosamente errado.

| Nome no `.mxd` | Papel | Shapefile em `SHP\` |
|---|---|---|
| `PERIMETRO` | perímetro do imóvel (amarelo) | `ATP.shp` |
| `AVN` | vegetação nativa | `AVN.shp` |
| `AC` | área consolidada | `AREA_CONSOLIDADA.shp` |
| `AUAS` | desmate pós-2008 | `AUAS.shp` |
| `APP` / `ARL` / `NASCENTE` | contexto | homônimos |
| `MUNICIPIOS` | limite municipal | `lml_municipio_a.shp` |
| `UF` | limite estadual | `lml_uf_a.shp` |
| `TEMATICA` | camada temática do mapa (TI, embargo, tipologia, UC) | conforme o mapa |
| `BASEMAP` | fundo (WMTS Planet / WMS SEMA) | camada de serviço, sem arquivo |

> **Nota sobre a técnica do homônimo.** No trabalho manual da Harmonia, os shapefiles foram
> gravados com os nomes que o `.mxd` do modelo esperava (`Fazenda_Santa_Clara.shp`,
> `SIEGEF.shp`, `Fazendas_Unidas.shp`), porque `findAndReplaceWorkspacePaths` troca só a **pasta**,
> não o nome do dataset. Na preparação do template, esses nomes herdados são **normalizados**
> para os canônicos acima. É preparação única; o motor nunca lida com o nome herdado.

### Elementos de layout

| Tipo `arcpy.mapping` | Nome | Obrigatório | Função |
|---|---|---|---|
| `DATAFRAME_ELEMENT` | `MAPA` | sim | data frame principal, com grade DMS |
| `DATAFRAME_ELEMENT` | `MINIMAPA` | sim | inset, com *extent indicator* apontando para `MAPA` |
| `TEXT_ELEMENT` | `TITULO` | sim | texto da caixa branca |
| `TEXT_ELEMENT` | `METADADOS` | sim | bloco inteiro, com marcação `<bol>` |
| `TEXT_ELEMENT` | `ROTULO_IMOVEL` | sim | nome da fazenda sobre o polígono |
| `TEXT_ELEMENT` | `DISTANCIA` | não | "0,51 km" nos mapas de TI/UC |
| `LEGEND_ELEMENT` | `LEGENDA` | sim | legenda |
| `PICTURE_ELEMENT` | `TABELA` | não | imagem da tabela de quantitativos |
| `PICTURE_ELEMENT` | `LOGO` | sim | marca IMAP |
| `MAPSURROUND_ELEMENT` | `NORTE` | sim | rosa dos ventos |
| `GRAPHIC_ELEMENT` | `MINIMAPA_RETANGULO` | sim | retângulo vermelho do imóvel |
| `GRAPHIC_ELEMENT` | `MINIMAPA_GUIA` | sim | linha-guia vermelha |

`MAPSURROUND_ELEMENT` e `GRAPHIC_ELEMENT` **não têm propriedade `visible`** em `arcpy.mapping`.
Para desligar, move-se para fora da página (`elem.elementPositionX = -100`), restaurando a posição
gravada no manifesto. Feio, mas é o que a API permite, e é estável desde a 10.0.

### `shared/templates/MANIFEST.json`

```jsonc
{
  "manifest_version": 1,
  "perfil": "harmonia",
  "templates": [{
    "id": "dinamica_retrato",
    "nome": "Dinâmica de uso do solo — A4 retrato (IMAP/Harmonia)",
    "arquivo": "Dinamica_retrato.mxd",
    "sha256": "…",
    "versao_arcmap": "10.6",
    "formato_pagina": { "papel": "A4", "orientacao": "retrato", "mm": [210, 297] },
    "crs_data_frame": "EPSG:31982",
    "data_frames": [
      { "nome": "MAPA",     "retangulo_mm": [7.0, 5.0, 203.5, 257.0], "grade": "dms" },
      { "nome": "MINIMAPA", "retangulo_mm": [0.0, 262.0, 62.0, 297.0],
        "crs": "EPSG:3857", "extent_indicator_para": "MAPA" }
    ],
    "elementos": [
      { "nome": "TITULO",    "tipo": "TEXT_ELEMENT", "obrigatorio": true,
        "posicao_mm": [98.2, 12.7], "fonte_pt": 24, "slot_caracteres": 64 },
      { "nome": "METADADOS", "tipo": "TEXT_ELEMENT", "obrigatorio": true,
        "posicao_mm": [92.0, 278.0], "slot_caracteres": 320 },
      { "nome": "TABELA",    "tipo": "PICTURE_ELEMENT",
        "posicao_mm": [52.0, 240.0], "tamanho_mm": [148.0, 16.0] }
    ],
    "camadas_esperadas": [
      { "nome_no_mxd": "PERIMETRO", "obrigatoria": true, "geometria": "Polygon",
        "dataset": "SHP/ATP.shp", "lyr": "estilos/perimetro_imovel.lyr" },
      { "nome_no_mxd": "AVN", "dataset": "SHP/AVN.shp", "lyr": "estilos/avn.lyr" },
      { "nome_no_mxd": "MUNICIPIOS", "dataset": "SHP/lml_municipio_a.shp",
        "campo_filtro": "nome", "lyr": "estilos/limite_municipal.lyr" }
    ],
    "escalas_permitidas": [20000, 22000, 25000, 30000, 40000, 50000, 60000, 75000, 90000, 105000],
    "patch": {
      "suportado": true,
      "offsets": {
        "extent":  { "stream": "…", "offset": 123456, "formato": "4×float64 LE" },
        "escala":  { "stream": "…", "offset": 123500, "formato": "float64 LE" }
      }
    }
  }]
}
```

O `sha256` é conferido pelo doctor e de novo antes de cada geração. Template alterado à mão pelo
usuário = job recusado com `AG-030`, porque o layout deixaria de casar com o manifesto.

---

# Os três caminhos de geração

| Tier | Quando | `.mxd` | `.pdf` | Fidelidade |
|---|---|---|---|---|
| **T1** | ArcMap 10.6+ com licença | ArcPy | ArcMap | referência |
| **T2** | Sem ArcMap (ou sem licença) | patch calibrado | renderizador nativo | alta / média |
| **T3** | T2 não cobre algum campo | patch parcial + instrução | nativo | declarada ao usuário |

O app escolhe sozinho, e **sempre diz qual usou** — no `validacao.json` e na conversa.

---

## T1 — ArcPy (caminho de referência)

Arquivo `nucleo/motores/arcpy_job.py`, executado pelo **Python 2.7 do ArcMap**, nunca importado
pelo núcleo 3.12.

### ⚠️ A armadilha que decide o desenho: o arcpy trava

Na máquina onde a análise Harmonia foi feita (ArcGIS 10.8), **toda chamada de acesso a dados do
`arcpy` dava *hang* infinito** — não erro, travamento:

```
arcpy.Describe(shapefile)          ← trava
Layer.replaceDataSource(...)       ← trava
arcpy.Project_management(...)      ← trava
SearchCursor / UpdateCursor        ← trava
arcpy.GetCount_management(...)     ← trava
```

Travava com o ArcMap fechado; é sistêmico (provável checkout de licença ou scratch workspace).
**Não dá para assumir que a máquina do usuário não tem esse problema.**

O motor usa **só a API comprovadamente estável**:

```
arcpy.mapping.MapDocument          ListDataFrames        ListLayers
lyr.name  ·  lyr.dataSource  ·  lyr.isBroken  ·  lyr.definitionQuery
df.extent  ·  df.scale  ·  df.spatialReference
mxd.findAndReplaceWorkspacePaths(antigo, novo, False)
arcpy.mapping.ListLayoutElements   el.text  ·  el.elementPositionX/Y  ·  el.sourceImage
mxd.save() · mxd.saveACopy() · arcpy.mapping.ExportToPDF / ExportToPNG
arcpy.mapping.ListBrokenDataSources
```

E **não usa**: `Describe`, `replaceDataSource`, cursores, `Project_management`,
`GetCount_management`, `ApplySymbologyFromLayer_management`.

Consequências diretas:

| Precisa de… | Solução sem tocar o `arcpy` de dados |
|---|---|
| Reprojetar geometria | **`ogr2ogr`** (GDAL, empacotado com o app) |
| Contar feições, ler campos | leitura direta do `.dbf` no núcleo Python 3 |
| bbox de um shapefile | **cabeçalho do `.shp`**, bytes 36:68 (`struct`, 4 × float64 LE) |
| Trocar a fonte de uma camada | shapefile homônimo na pasta canônica + `findAndReplaceWorkspacePaths` |
| Calcular área | núcleo Python 3, `shapely` + `pyproj` |

### Regras de ouro do subprocesso

1. **Sempre com timeout.** `timeout 150` (ou equivalente no Windows). O `save()` às vezes grava o
   arquivo e trava no *cleanup* (exit 124) — **o arquivo sai válido**; confirmar com o
   `ExportToPDF` seguinte, não abortar.
2. **Payload por arquivo, nunca por `argv`.** Caminho do JSON numa variável de ambiente
   (`MAPASFACIL_JOB_JSON`). `argv` com acento quebra no `mbcs` do Windows.
3. **Fechar o ArcMap antes.** O núcleo detecta `ArcMap.exe` rodando e avisa. Limpar `*.lock` das
   pastas de shapefile.
4. **`del mxd` obrigatório**, dentro de `finally`. Sem isso o arquivo fica travado e o `os.replace`
   atômico falha com `WindowsError 32`.
5. **Encoding.** `# -*- coding: utf-8 -*-` no topo; ler com `codecs.open(..., "utf-8")`; atribuir
   `unicode` a `el.text` — `u"Dinâmica".encode("utf-8")` sai como `DinÃ¢mica` no PDF.
6. **Caminho de saída em ASCII.** `arcpy` 10.x tem falhas conhecidas com acento em caminho de
   saída; o núcleo sanitiza `nome_base`.

### Esqueleto

```python
# -*- coding: utf-8 -*-
"""Executado pelo Python 2.7 do ArcMap. NUNCA importado pelo nucleo 3.12."""
import codecs, json, os, shutil
import arcpy

with codecs.open(os.environ["MAPASFACIL_JOB_JSON"], "r", "utf-8") as f:
    e = json.load(f)

arcpy.env.overwriteOutput = True
# Trabalhar sobre uma COPIA: MapDocument mantem lock no arquivo aberto.
trabalho = os.path.join(e[u"tmp"], u"trabalho.mxd")
shutil.copy2(e[u"template"], trabalho)

mxd = arcpy.mapping.MapDocument(trabalho)
try:
    mxd.relativePaths = True
    df = arcpy.mapping.ListDataFrames(mxd, u"MAPA")[0]

    # 1. repontar: so a PASTA muda; os datasets ja tem o nome canonico
    mxd.findAndReplaceWorkspacePaths(e[u"pasta_template_shp"], e[u"pasta_saida_shp"], False)

    # 2. definition query de municipio e UF  (a "troca automatica")
    for lyr in arcpy.mapping.ListLayers(mxd, u"", df):
        if lyr.name == u"MUNICIPIOS":
            lyr.definitionQuery = u'"%s" = \'%s\'' % (e[u"campo_municipio"], e[u"municipio"])
        elif lyr.name == u"UF":
            lyr.definitionQuery = u'"%s" = \'%s\'' % (e[u"campo_uf"], e[u"uf_extenso"])
        elif lyr.name in e[u"camadas_visiveis"]:
            lyr.visible = True

    # 3. extent DEPOIS, escala POR ULTIMO — a ordem nao e opcional
    df.extent = arcpy.Extent(*e[u"bbox_no_crs_do_data_frame"])
    df.scale = e[u"escala"]

    # 4. textos
    textos = dict((t.name, t) for t in arcpy.mapping.ListLayoutElements(mxd, u"TEXT_ELEMENT"))
    for nome, valor in e[u"textos"].items():
        if nome in textos:
            textos[nome].text = valor if valor else u" "

    # 5. tabela e logo (caminhos RELATIVOS a pasta de saida)
    for fig in arcpy.mapping.ListLayoutElements(mxd, u"PICTURE_ELEMENT"):
        if fig.name in e[u"imagens"]:
            fig.sourceImage = e[u"imagens"][fig.name]

    # 6. minimapa: retangulo + linha-guia, ja em coordenada de pagina (calculado no nucleo)
    for g in arcpy.mapping.ListLayoutElements(mxd, u"GRAPHIC_ELEMENT"):
        if g.name in e[u"graficos"]:
            g.elementPositionX = e[u"graficos"][g.name][u"x"]
            g.elementPositionY = e[u"graficos"][g.name][u"y"]

    # 7. legenda
    for leg in arcpy.mapping.ListLayoutElements(mxd, u"LEGEND_ELEMENT", u"LEGENDA"):
        leg.autoAdd = False
        for item in leg.listLegendItemLayers():
            if item.name not in e[u"legenda"]:
                leg.removeItem(item)

    quebradas = [l.name for l in arcpy.mapping.ListBrokenDataSources(mxd)]

    if u"mxd" in e[u"saidas"]:
        mxd.saveACopy(e[u"saida_mxd"])
    if u"pdf" in e[u"saidas"]:
        arcpy.mapping.ExportToPDF(mxd, e[u"saida_pdf"], resolution=300,
                                  image_quality=u"BEST", colorspace=u"RGB",
                                  compress_vectors=True, image_compression=u"ADAPTIVE",
                                  embed_fonts=True, georef_info=True)
    if u"png" in e[u"saidas"]:
        arcpy.mapping.ExportToPNG(mxd, e[u"saida_png"], resolution=96)

    with codecs.open(e[u"relatorio"], "w", "utf-8") as f:
        json.dump({u"quebradas": quebradas, u"escala": df.scale,
                   u"crs": df.spatialReference.factoryCode},
                  f, ensure_ascii=False)
finally:
    del mxd    # OBRIGATORIO: libera o lock
```

### `df.extent` antes de `df.scale` — não é estilo

Atribuir `df.extent` **redefine a escala** para caber o retângulo pedido. Um `df.scale` anterior
é perdido. O padrão é: `extent` para centralizar, `scale` para fixar a escala "bonita".

### O CRS do data frame decide o bbox

Da [seção de CRS do padrão](../../planos/01-padrao-imap-harmonia.md#crs-por-família-de-mapa):
série Dinâmica usa data frame em **UTM 22S (31982)**, temáticos usam **Web Mercator (3857)**.

**Aplicar bbox UTM num data frame 3857 gera mapa em branco.** Aconteceu de verdade no primeiro
teste da Harmonia. O núcleo lê `crs_data_frame` do manifesto e converte o bbox antes de mandar.

### Simbologia por `.lyr`, não por código

`lyr.symbology` em `arcpy.mapping` expõe um punhado de propriedades (`UniqueValuesSymbology`,
`valueField`, `classBreakValues`…) e **não** dá acesso a preenchimento, espessura, hachura,
transparência nem ordem de renderização. A hachura `xxx` verde vazada da AVN é **impossível** de
configurar por código na 10.x.

Solução: os estilos já vêm no template (extraídos dos `.mxd` do acervo) e a biblioteca de `.lyr`
em `shared/templates/estilos/` cobre as variações catalogadas. `UpdateLayer(..., symbology_only=True)`
troca o estilo de uma camada já no documento.

Em troca, `estilo` no `MapSpec` **não é livre**: mapeia para um conjunto finito de `.lyr`.
*"Deixa a AVN azul"* resolve para `avn_azul.lyr`; cor fora do catálogo é recusada com sugestão da
mais próxima.

---

## T2 — Patch calibrado (sem ArcMap)

Este é o caminho que torna o produto viável fora de máquinas com ArcGIS, e o que o dono do
produto descreveu: *"o `.mxd` com caminho relativo, só vendo um `.zip` ou print, para a pessoa
abrir no PC dela e apenas vincular os shapes."*

### A base: caminho relativo resolve 90% do problema

Com **Store relative pathnames** ligado na preparação, o `.mxd` guarda o caminho relativo do
dataset (`.\SHP\ATP.shp`) além do absoluto. Se a pasta de saída reproduzir essa estrutura com os
nomes canônicos, **o `.mxd` resolve sem patch nenhum de caminho**.

```
Entrega/
├─ Dinamica_2026.mxd     ← copia byte a byte do template
└─ SHP/
   ├─ ATP.shp            ← escrito pelo nucleo com o nome que o template espera
   ├─ AVN.shp
   └─ lml_municipio_a.shp
```

Nenhuma manipulação binária para os dados. É a mesma técnica do homônimo do trabalho manual,
promovida a design.

### O que ainda precisa mudar dentro do arquivo

| Valor | Tipo no arquivo | Estratégia |
|---|---|---|
| Extent do data frame | 4 × `float64` LE | **patch por offset** — comprimento fixo, seguro |
| Escala | `float64` LE | idem |
| Título | string UTF-16LE | **slot de tamanho fixo** |
| Bloco de metadados | string UTF-16LE | slot de tamanho fixo |
| Rótulo do imóvel | string UTF-16LE | slot de tamanho fixo |
| `definitionQuery` do município | string UTF-16LE | slot de tamanho fixo |
| Posição do retângulo/linha do minimapa | `float64` LE | patch por offset |
| Imagem da tabela e logo | caminho relativo | já resolve pelo caminho relativo |

### Patch por offset

Como **nós** preparamos os templates, podemos descobrir e registrar onde cada valor mora:

1. Salvar o template com um valor sentinela inconfundível (extent = `111111.0, 222222.0,
   333333.0, 444444.0`; escala = `987654.0`).
2. Localizar os bytes desses `float64` no arquivo.
3. Gravar `stream` e `offset` no `MANIFEST.json`.
4. Em produção, o núcleo escreve os valores novos naqueles offsets — mesmo comprimento, zero
   risco estrutural.

Validação obrigatória a cada uso: **ler o valor atual no offset e conferir que bate com o que o
manifesto diz estar lá.** Se não bater, o template mudou → `AG-030`, cai para T3.

### Slot de tamanho fixo para texto

Strings em OLE são de comprimento variável e mudar o tamanho exigiria reescrever a alocação de
setores. Contorno: na preparação do template, o elemento de texto recebe **padding** até um
tamanho generoso.

```
TITULO no template :  "Dinâmica 2026" + 51 espaços = 64 caracteres  (slot_caracteres: 64)
TITULO na saída    :  "Tipologia Vegetal" + 47 espaços = 64 caracteres
```

Regras:

- O padding é feito com **espaços à direita**; o elemento é configurado com alinhamento
  **centralizado**, então espaço à direita não desloca o texto visualmente.
- Texto maior que o slot é **truncado com aviso**, nunca escrito por cima do que vem depois.
- O slot vale por elemento e está no manifesto (`slot_caracteres`).
- Para o bloco de metadados (multilinha, com `<bol>`), o slot é maior (320) e o padding vai
  depois da última linha.

### Limites honestos do T2

| Não dá para fazer sem ArcMap | Consequência |
|---|---|
| Adicionar camada que não existe no template | o mapa só tem as camadas previstas. Cobrir com templates variantes |
| Trocar simbologia por `.lyr` | o estilo é o do template. Variação de cor exige template variante |
| Reordenar camadas | ordem é a do template |
| Remover item da legenda | a legenda é a do template |
| Mudar grade DMS | já não dá nem com ArcMap |

Em compensação, o T2 cobre **o caso real dominante**: mesmo mapa, imóvel diferente. Que é
exatamente o que o trabalho manual da Harmonia fazia — copiar a análise anterior e trocar o
imóvel.

### Checklist do T2

- [ ] Copiar o template byte a byte para a pasta de saída
- [ ] Conferir `sha256` do template antes de tocar
- [ ] Escrever os shapefiles em `SHP/` com os nomes canônicos, no CRS do data frame
- [ ] Ler os sentinelas nos offsets do manifesto e conferir
- [ ] Patch de extent (4 × float64)
- [ ] Patch de escala (float64)
- [ ] Patch dos textos por slot, com truncamento avisado
- [ ] Patch da definition query do município e da UF
- [ ] Patch das posições do retângulo e da linha-guia do minimapa
- [ ] Gravar `recursos/tabela_quantitativos.png` e `recursos/logo_imap.png`
- [ ] Reabrir o arquivo como OLE e conferir a assinatura + tamanho idêntico
- [ ] Gerar o PDF pelo renderizador nativo
- [ ] Registrar `motor: "patch"` no `validacao.json`

---

## T3 — Patch parcial com instrução

Quando o T2 não consegue cobrir algo (template sem offset registrado, texto acima do slot, camada
pedida que não existe no template), o motor **não desiste e não mente**. Ele:

1. gera o `.mxd` com o que conseguiu;
2. gera o PDF correto pelo renderizador nativo (que não tem essas limitações);
3. escreve no `validacao.json` e mostra na conversa **a lista exata do que falta fazer à mão**.

```
O .mxd foi gerado, mas 2 coisas precisam de um ajuste no ArcMap:

  1. Extent — abra o mapa, clique com o botão direito na camada PERIMETRO
     e escolha "Zoom to Layer", depois digite 1:60.000 na escala.
  2. Título — está "Dinâmica 2026"; o pedido era um título de 71 caracteres,
     acima do limite de 64 deste template.

O PDF já está correto — a diferença é só no .mxd editável.
```

Isso é infinitamente melhor que um `.mxd` silenciosamente errado, e é o comportamento que o
usuário descreveu: *"deixar relativo para a pessoa abrir e apenas vincular."*

---

## A troca automática de município

Requisito explícito do produto, e um dos erros mais comuns do trabalho manual.

**O que existe no acervo.** A camada `lml_municipio_a` carrega uma *definition query* por nome:

```
"nome" = 'Vila Rica'         ← análise Harmonia
"nome" = 'Querência'         ← sobra de análise anterior, no mesmo .mxd
"nome" = 'Ribeirão…'         ← outra sobra
"nome" = 'Mato Grosso'       ← camada de UF
```

**O que o motor faz**, em toda geração, nos três tiers:

1. Município e UF vêm de `imovel.municipio` no `MapSpec` — que vem do recibo do CAR ou do WFS
   `LIM_MUNICIPIOS_MT`, não de digitação.
2. Normaliza para o valor exato do campo (acento, caixa, `Querência` ≠ `QUERENCIA`). Se não
   houver correspondência exata, faz *fuzzy match* contra o `.dbf` da camada e **pergunta** antes
   de aplicar.
3. Reescreve `definitionQuery` de `MUNICIPIOS` e de `UF`.
4. Recalcula o extent do data frame `MINIMAPA` para enquadrar o município selecionado.
5. Recalcula a posição do **retângulo vermelho** (centroide do imóvel → coordenada do data frame
   do minimapa → coordenada de página) e reata a **linha-guia** até a moldura do mapa.
6. Roda os checks `H12`, `S01`, `S02`, `S03`.

O passo 5 é o que a análise Harmonia teve de corrigir em 19 mapas depois de prontos. Aqui é parte
da geração.

---

## Tabela de quantitativos

Cálculo **no núcleo Python 3.12** com `shapely` e `pyproj` — nunca no script `arcpy` 2.7 (onde
cursores travam):

1. Reprojetar tudo para o CRS projetado do `MapSpec` (UTM SIRGAS 2000 da zona do centroide).
2. Corrigir geometrias inválidas, registrando quantas.
3. `union` por camada, depois `intersection` com o perímetro.
4. m² ÷ 10.000 = hectare; 4 casas decimais; formato pt-BR.
5. `TOTAL GERAL` = soma dos valores **já arredondados**.
6. Sobreposição entre classes gera aviso.

A tabela vira um **PNG ≥ 600 dpi** (Pillow) com cabeçalho azul `#2E75B6`, linhas brancas e
`TOTAL GERAL` verde `#70AD47` — o estilo medido do modelo. O motor injeta em `PICTURE_ELEMENT
TABELA` (T1 via `sourceImage`; T2 via caminho relativo já apontado no template).

Fazer no núcleo tem três razões: é testável em CI sem ArcGIS, é determinístico, e a mesma tabela
alimenta o renderizador nativo e o `.xlsx`.

---

## Determinismo

Mesmo `MapSpec` + mesmos dados = mesmo PDF. É o que torna possível teste de regressão visual.

- **Ordenação estável**: ordem das camadas vem do array do `MapSpec`, nunca de iteração sobre
  `dict`; deduplicação com `dict.fromkeys`, jamais `set`.
- **Extent e escala gravados no `MapSpec`** depois de resolvidos, não recalculados.
- **Versões registradas** no `validacao.json`: app, núcleo, ArcMap, template + `sha256`,
  catálogo, `sha256` de cada shapefile de entrada.
- **Comparação por raster, não por bytes**: o PDF do ArcMap embute `CreationDate`, então dois
  PDFs idênticos têm `sha256` diferentes. O teste rasteriza a 150 dpi e compara com um *golden
  image*, tolerância de 0,3%.

---

## Smoke test manual (máquina com ArcMap)

A cada release ou mudança de template. Windows 11 + ArcMap 10.8.1, licença single-use.

- [ ] Doctor: licença `Available`, `templates[*].sha256_ok`, `pronto_para_mxd: true`
- [ ] Abrir cada template no ArcMap e conferir nomes de elemento contra o manifesto
- [ ] Gerar a Dinâmica 2026 da pasta real da Harmonia, `escala: "auto"`
- [ ] Cronometrar: menos de 3 minutos
- [ ] Abrir `Dinamica_2026.mxd`: **nenhum `!` vermelho**
- [ ] Conferir escala 1:60.000, grade DMS `52°11'10"W`, título, metadados com acento
- [ ] Conferir a definition query da camada de municípios = `Vila Rica`
- [ ] Conferir o retângulo do minimapa sobre o imóvel e a linha-guia conectada
- [ ] Conferir a tabela: 4 casas, `TOTAL GERAL` fechando com a soma visível
- [ ] Abrir o PDF lado a lado com `Referencias_IMAP/Mapas/Dinamica_2026_quantitativos.pdf`
- [ ] **Mover a pasta de entrega inteira para outro disco** e reabrir o `.mxd`: continua resolvendo
- [ ] **Copiar para outro PC** com ArcMap e reabrir
- [ ] Repetir o job e comparar os dois PDFs por raster: < 0,3%
- [ ] Cancelar um job aos 20 s: nenhum `python.exe` órfão, nenhum `.tmp` na saída
- [ ] Desligar a rede e repetir com cache: aviso de basemap e PDF gerado
- [ ] Repetir tudo numa máquina **sem ArcMap** (T2) e comparar

## Pendências

| # | Questão | Situação |
|---|---|---|
| P1 | Preparar os templates a partir dos 24 `.mxd` do acervo | trabalho manual no ArcMap; caminho crítico do M2 |
| P2 | Descobrir os offsets de patch de forma repetível | precisa de uma máquina com ArcMap para gerar os sentinelas; automatizar como script de calibração |
| P3 | Slot de texto: 64 caracteres cobre os títulos reais? | medir os títulos do acervo antes de fechar |
| P4 | Reescrita de stream OLE (elimina o limite do slot) | possível, mas é um escritor OLE completo. Avaliar só se o slot se mostrar insuficiente |
| P5 | Basemap Planet no `.mxd`: a chave do usuário vai embutida | decidido em [segurança](../../planos/05-seguranca-e-segredos.md); falta o texto do aviso |
| P6 | ArcGIS Pro: manter família `.aprx` em paridade? | custo dobrado; adiar até haver usuário só-Pro |
| P7 | Golden images de regressão precisam ser geradas com ArcMap | decidir se entram no repositório (tamanho) ou num release |
| P8 | Templates de Dinâmica por ano (2000…2026) — um por ano ou um parametrizado? | inspecionar os `.mxd`; um só reduz manutenção pela metade |
