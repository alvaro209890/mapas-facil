# Documentação — Adaptação dos MXD para a Fazenda Harmonia

> **Para o próximo agente/pessoa:** este documento descreve tudo que foi feito para
> adaptar os mapas (.mxd) do ArcMap para a **Fazenda Harmonia** (Julio Barbosa,
> Análise 4, Vila Rica/MT). Leia as seções 5 (armadilha do arcpy) e 8 (como continuar)
> antes de mexer em qualquer MXD. Documento criado em 01/07/2026.

---

## 1. Objetivo

Adaptar os MXD copiados de uma análise-modelo para a propriedade **Fazenda Harmonia**:
trocar o polígono/nome do imóvel, recentrar cada mapa na propriedade, manter o minimapa
de Vila Rica e as imagens por WMS, limpar camadas de projetos antigos e exportar em PDF.

## 2. Identidade do imóvel (extraída do CAR — `CAR - Emitido (6) (1).pdf`)

| Campo | Valor |
|---|---|
| Propriedade | **FAZENDA HARMONIA** |
| Município/UF | **Vila Rica / MT** |
| Proprietária | Silvana Renata Lopes (CPF 900.813.401-25) |
| Nº CAR Estadual | **MT102042/2017** (Ativo / Declarado) |
| Recibo Federal | MT-5108600-055251EFEA624041824B050D583F3EEE |
| Área Total | **3.823,9033 ha** (bate com `Arquivo Processado (1)/ATP.shp`) |
| ARL | 2.496,55 ha · APP 287,37 · Consolidada 483,86 · Veg. Nativa 2.833,75 |
| Tipologia | Floresta 2.584,86 ha · Cerrado 1.224,02 ha |

**Perímetro do imóvel = `Arquivo Processado (1)/ATP.shp`** (1 feição, geográfico SIRGAS 2000 / EPSG 4674).

## 3. Diretórios

```text
Projeto atual:  C:\Users\Usuario\Downloads\Analise_de_area\Analise_de_área-Julio Barbosa_ 4_Harmonia
MXD adaptados:  MXD\claude              <- ENTREGA (contém os .mxd da Harmonia)
Backup Querência: MXD\_backup_querencia_20260701   (cópias antigas substituídas)
PDFs finais:    Mapas\
Shapes de apoio: SHP\  (ver seção 6)
Scripts:        Automacoes\Scripts\mxd_harmonia\
CAR/dados brutos: Arquivo Processado (1)\  (shapes CAR)  |  Automacoes\Resultados\ (JSON alertas/embargos)
```

## 4. Modelo usado (base da cópia)

Os MXD foram copiados de outra análise do **mesmo cliente e mesmo município (Vila Rica)**:

```text
C:\Users\Usuario\Downloads\Analise_de_area\Analise de área - Julio Barbosa _ 2\MXD
```

Vantagem: já vêm com **minimapa de Vila Rica**, **imagens por WMS SEMA/Planet** e layout
prontos. Só muda o polígono/nome do imóvel (o modelo era Fazenda Santa Clara + Serra Verde;
aqui é **um polígono único = Fazenda Harmonia**).

**Decisões do usuário registradas:** base = copiar a Análise 2 e adaptar · rótulo = só
"Fazenda Harmonia" (o CAR emitido não traz matrícula) · saída em `MXD\claude` · imagens da
dinâmica = WMS Landsat da SEMA · overlay dos mapas PRODES = só desmatamento (corte raso) ·
manter os dois mapas PRODES.

## 5. ⚠️ ARMADILHA CRÍTICA: o arcpy trava neste ambiente

Nesta máquina, o **arcpy (Python 2.7 do ArcGIS 10.8) TRAVA (hang infinito)** em qualquer
chamada de **acesso a dados**: `arcpy.Describe(shapefile)`, `Layer.replaceDataSource()`,
`arcpy.Project_management`, cursores (`SearchCursor`/`UpdateCursor`), `GetCount_management`.
Trava mesmo com o ArcMap fechado — é sistêmico (provável checkout de licença/scratch).

**O que FUNCIONA (usar só isto para editar MXD):**
`arcpy.mapping.MapDocument`, `ListDataFrames`, `ListLayers`, ler/gravar
`lyr.name`/`df.extent`/`df.scale`, ler `lyr.dataSource`/`lyr.isBroken`, `df.spatialReference`,
`mxd.findAndReplaceWorkspacePaths(old, new, False)`, `ListLayoutElements` + `el.text`,
`mxd.save()`, `arcpy.mapping.ExportToPDF`.

**Regras de ouro (seguidas aqui):**
1. Reprojetar/converter geometria → **`ogr2ogr`** (`C:\Program Files\QGIS 3.34.15\bin\ogr2ogr.exe`), nunca `arcpy.Project`.
2. Extensão do data frame → ler o **bbox do cabeçalho do .shp** (struct, bytes 36:68), nunca `Describe`.
3. Trocar fonte de dados → criar **shapefiles homônimos** na pasta destino + `findAndReplaceWorkspacePaths` (troca só a pasta), nunca `replaceDataSource`.
4. Rodar todo arcpy com **`timeout N`** (ex.: `timeout 150`). O `save()` às vezes grava o arquivo e trava no cleanup (exit 124) — **o arquivo sai válido**, confirmar com `ExportToPDF`.
5. **Fechar o ArcMap** antes (havia 2 instâncias "Untitled" abertas; foram fechadas). Limpar `*.lock` em `Arquivo Processado (1)`.

**CRS dos data frames (importante para a extensão):**
- Mapas da **Dinâmica** → data frame em **UTM 22S (EPSG 31982)** → usar bbox UTM de `SHP\Fazenda_Harmonia.shp`.
- Mapas **temáticos** (Alertas/Embargos/Tipologia/TI/UC) → data frame em **Web Mercator (EPSG 3857)** → converter o bbox **geográfico** de `ATP.shp` para Web Mercator (fórmula esférica R=6378137) antes de aplicar. Aplicar bbox UTM num frame 3857 gera **mapa em branco** (aconteceu no 1º teste).

## 6. Shapes de apoio criados (pasta `SHP\`)

Todos em **UTM 22S (EPSG 31982)**, gerados por `ogr2ogr` a partir do `ATP.shp`/JSON:

| Arquivo | Conteúdo | Usado por |
|---|---|---|
| `Fazenda_Harmonia.shp` | perímetro do imóvel (referência do bbox) | cálculo de extensão |
| `Fazenda_Santa_Clara.shp` | = perímetro Harmonia (nome homônimo do modelo) | Dinâmica (camada visível amarela) |
| `Fazenda_Serra_verde.shp` | = perímetro Harmonia (homônimo) | (removida dos MXD; não referenciada) |
| `Fazendas_Unidas.shp` | = perímetro Harmonia (homônimo) | minimapa / "Área total das propriedades" |
| `SIEGEF.shp` | = perímetro Harmonia (homônimo) | Embargos_IBAMA (contorno do imóvel) |
| `air_mapbiomas\AIR.shp` | 5 alertas MapBiomas (do JSON, 2021-2022) | Alertas_MAPBIOMAS |
| `air_prodes\AIR.shp` | 8 alertas SCCON "Desmatamento - Corte Raso" (do JSON) | Alertas_PRODES / PRODES_VF |
| `Fazenda_Santa_Clara\AUAS.shp` | AUAS do CAR da Harmonia (UTM) — homônimo da subpasta do modelo | Quantitativos (camada "AUAS") / DLA |
| `Fazenda_Santa_Clara\AC.shp` | AREA_CONSOLIDADA do CAR (UTM) | (reserva; a legenda usa a da Serra_Verde) |
| `Fazenda_Santa_Clara\AVN.shp` | AVN do CAR (UTM) | (reserva) |
| `Fazenda_Serra_Verde\AC.shp` | AREA_CONSOLIDADA do CAR (UTM) | Quantitativos — camada "Área consolidada" (dona da entrada de legenda) |
| `Fazenda_Serra_Verde\AVN.shp` | AVN do CAR (UTM) | Quantitativos — camada "Área de vegetação nativa" (dona da entrada de legenda) |
| `Fazenda_Serra_Verde\AUAS.shp` | AUAS do CAR (UTM) | (reserva) |
| `Embargo.shp` | = perímetro Harmonia (homônimo de `...\MXD\shapes\Embargo.shp` do lote 444) | Tipologia — patch de legenda "Tipologia: Floresta" |
| `tabela_quantitativos_harmonia.png` | tabela de áreas gerada por PIL (não é shape) | Quantitativos — PICTURE_ELEMENT |

Os "homônimos" existem porque `findAndReplaceWorkspacePaths` troca só a **pasta**, mantendo o
nome do dataset. Assim, apontar a pasta do modelo → `SHP\` faz o MXD carregar o perímetro da Harmonia.

Fonte dos alertas: `Automacoes\Resultados\Alertas_raw.json` (mapbiomas: `props.geom_simplified`;
sccon: `geojson`). Embargos (`Embargos_raw.json`): IBAMA e SEMA-embargos **vazios**; 7 desembargos
(só ponto) — **não** foram desenhados.

## 7. O que foi feito (14 mapas prontos em `Mapas\`)

### Bloco 1 — Série Dinâmica (8) ✅
`Dinamica_2000, 2008_LANDSAT, 2008_SPOT, 2013, 2017, 2019, 2023, 2026`
- Polígono da propriedade → `Fazenda Harmonia` (amarelo, único); Serra Verde removida.
- Extensão recentrada na Harmonia (UTM), escala 1:60.000; metadados atualizados.
- Imagem mantida por ano: WMS SEMA (Landsat 5/TM em 2000/2008/2013; SPOT em 2008) e Planet (2017/2019/2023/2026).
- Minimapa Vila Rica + limpeza de camadas quebradas.
- Script: `adapt_dinamica.py`.

### Bloco 2B — Alertas e Embargos (6) ✅
`Alertas_MAPBIOMAS_2, Alertas_PRODES, Alertas_PRODES_VF, Embargos_IBAMA, Embargos_SEMA_Poligono, Embargos_SEMA_SIGA_Poligono`
- Mesma adaptação (propriedade/extensão em Web Mercator/minimapa/limpeza) + textos: matrícula e
  distâncias herdadas apagadas, nome → "Fazenda Harmonia".
- MAPBIOMAS: overlay = 5 alertas MapBiomas (cinza).
- PRODES e PRODES_VF: overlay = 8 alertas corte raso (SCCON). No `Alertas_PRODES` foi corrigido o
  título herdado "Alertas MAPBIOMAS" → "Alertas PRODES" e a legenda → "Alertas emitidos pelo PRODES".
- Embargos: imóvel **sem embargo** (IBAMA/SEMA vazios = correto); camadas GEOBASES estaduais de contexto.
- Script: `adapt_tematico.py` (contém a conversão de extensão para Web Mercator e as receitas por-mapa
  de repontagem — ver dicionário `RECIPE`).

## 8. Blocos 2A e 2C — CONCLUÍDOS em 02/07/2026 (script `adapt_bloco2.py`)

### Bloco 2A — Tipologia, DLA, Quantitativos 2026 ✅
- Homônimos criados: `SHP\Fazenda_Santa_Clara\{AUAS,AC,AVN}.shp` (CAR da Harmonia reprojetado
  p/ UTM 22S via ogr2ogr) e `SHP\Embargo.shp` (= perímetro; alimenta o patch de legenda
  "Tipologia: Floresta"). Camadas Serra Verde removidas; "Área concolidada"→"Área consolidada",
  "rf"→"Área de vegetação nativa"; typo "Dadosr:"→"Fonte:" corrigido; escala 1:60.000 (DLA/Quant)
  e 1:90.000 (Tipologia).
- Tabela de quantitativos = PICTURE_ELEMENT regenerado (`SHP\tabela_quantitativos_harmonia.png`,
  gerado por PIL): ATP 3.823,9140 · AVN 2.833,7541 · AC 483,8562 · AUAS 491,2631 ha
  (áreas planas UTM 22S calculadas no Python do QGIS a partir do CAR).

### Bloco 2C — Terras Indígenas e Unidade de Conservação ✅
- Distâncias calculadas no Python do QGIS (`calc_geo.py`, ogr+shapely, planar UTM 22S):
  - **TI Kapôt Nhinore (Delimitada): 0,51 km** — a Harmonia é praticamente vizinha da TI
    (bem diferente dos ~24-28 km das análises 2/3). Extensão do mapa recentrada (1:105.000).
  - **UC Parque Estadual do Xingu: 21,79 km** — extensão do modelo mantida (a Harmonia já
    aparecia no frame); linha tracejada e texto reposicionados por matemática de página.
- "Zona de amortecimento" repontada para
  `Downloads\Bases\Zonas_de_Amortecimento\Zona_de_Amortecimento_TI\` (o shape foi movido p/ subpasta).
- Matrículas herdadas apagadas; rótulo do imóvel = "Fazenda Harmonia".

### Correção geral — retângulo do minimapa (`fix_minimap_rect.py`)
O retângulo vermelho indicador no minimapa de Vila Rica estava deslocado (~0,4 cm) da marca da
fazenda em quase todos os MXD. O script recentra o retângulo no centroide da Harmonia
(EPSG 3857 → coordenada de página) e reata a linha-guia. Aplicado aos 19 MXD em 02/07/2026.

## 9. Como rodar/refazer (comandos)

Python do ArcGIS (py2) e Python 3.11 (para renderizar PDF→PNG na validação):

```bash
PYA="C:/Python27/ArcGIS10.8/python.exe"     # arcpy (SEMPRE com timeout)
PY3="C:/Users/Usuario/AppData/Local/Programs/Python/Python311/python.exe"  # fitz/pypdf/pillow

# adaptar 1 dinâmica (recopiar o original do modelo antes se precisar):
timeout 150 "$PYA" -u Automacoes/Scripts/mxd_harmonia/adapt_dinamica.py "MXD/claude/Dinamica_2013.mxd" --apply

# adaptar 1 temático:
timeout 150 "$PYA" -u Automacoes/Scripts/mxd_harmonia/adapt_tematico.py "MXD/claude/Alertas_MAPBIOMAS_2.mxd" --apply

# exportar 1 / vários para PDF:
timeout 200 "$PYA" -u Automacoes/Scripts/mxd_harmonia/export_pdf_one.py "MXD/claude/<nome>.mxd" "Mapas/<nome>.pdf"
timeout 400 "$PYA" -u Automacoes/Scripts/mxd_harmonia/export_pdf_batch.py "MXD/claude" "Mapas" "N1,N2,..."

# validar: renderizar a 1ª página do PDF para PNG e inspecionar
"$PY3" -c "import fitz; fitz.open(r'Mapas/<nome>.pdf')[0].get_pixmap(dpi=110).save(r'check.png')"
```

Regra sempre: **recopiar o .mxd limpo do modelo** (`Analise de área - Julio Barbosa _ 2\MXD`) antes de
re-adaptar um mapa, rodar o adapt, depois exportar. Validar sempre pelo PNG.

## 10. Scripts (em `Automacoes\Scripts\mxd_harmonia\`)

| Script | Função |
|---|---|
| `adapt_dinamica.py` | adapta 1 MXD da série Dinâmica (UTM) para a Harmonia |
| `adapt_tematico.py` | adapta 1 MXD temático (Web Mercator) — inclui receitas `RECIPE` por-mapa e conversão de extensão |
| `adapt_bloco2.py` | adapta Tipologia/DLA/Quantitativos/TI/UC — repontagem, remoção de camadas mortas, extensão, linha de distância TI/UC, tabela de quantitativos |
| `fix_minimap_rect.py` | recentra o retângulo vermelho do minimapa + linha-guia (aceita pasta inteira) |
| `calc_geo.py` | (Python do QGIS) áreas ha em UTM 22S + TI/UC mais próximos, distância e pontos da linha (JSON) |
| `gen_tabela_quantitativos.py` | (Python 3.11/PIL) gera `SHP\tabela_quantitativos_harmonia.png` |
| `export_pdf_one.py` | exporta 1 MXD para PDF |
| `export_pdf_batch.py` | exporta vários MXD para PDF (args decodificados em mbcs p/ caminho com acento) |

## 11. Inventário FINAL (`Mapas\`, 19 PDFs + Mapas_unidos.pdf) — 02/07/2026

```text
Dinamica_2000  Dinamica_2008_LANDSAT  Dinamica_2008_SPOT  Dinamica_2013
Dinamica_2017  Dinamica_2019  Dinamica_2023  Dinamica_2026
Dinamica_2026_quantitativos  DLA  Tipologia
Alertas_MAPBIOMAS_2  Alertas_PRODES  Alertas_PRODES_VF
Embargos_IBAMA  Embargos_SEMA_Poligono  Embargos_SEMA_SIGA_Poligono
Terras_Indigenas  Unidade_de_Conservação
Mapas_unidos.pdf   (os 19 na ordem acima, juntados com PyMuPDF)
```

**Nada pendente.** Todos exportados a 150 dpi depois das correções de 02/07/2026
(adaptação do Bloco 2 + recentragem do retângulo do minimapa em todos os 19).

## 12. Como editamos os SHP — passo a passo (para reproduzir)

Ferramenta: **`ogr2ogr` do QGIS** (`C:\Program Files\QGIS 3.34.15\bin\ogr2ogr.exe`) —
nunca `arcpy.Project` (trava nesta máquina, ver seção 5). Fonte de tudo: shapes do CAR em
`Arquivo Processado (1)\` (geográfico SIRGAS 2000, EPSG 4674).

### 12.1 Reprojeção + homônimos (a única "edição" feita nos SHP)

Nenhuma geometria foi editada/recortada — os shapes do CAR foram apenas **reprojetados
para UTM 22S (EPSG 31982)** e gravados com o **nome/pasta que o MXD do modelo espera**
(técnica do homônimo: `findAndReplaceWorkspacePaths` troca só a pasta, então o arquivo
novo precisa ter o mesmo nome do antigo):

```bash
cd "C:/Users/Usuario/Downloads/Analise_de_area/Analise_de_área-Julio Barbosa_ 4_Harmonia"
OGR="C:/Program Files/QGIS 3.34.15/bin/ogr2ogr.exe"
AP="Arquivo Processado (1)"

# Quantitativos/DLA — AUAS, AC, AVN nas subpastas homônimas do modelo:
"$OGR" -t_srs EPSG:31982 "SHP/Fazenda_Santa_Clara/AUAS.shp" "$AP/AUAS.shp"
"$OGR" -t_srs EPSG:31982 "SHP/Fazenda_Santa_Clara/AC.shp"   "$AP/AREA_CONSOLIDADA.shp"
"$OGR" -t_srs EPSG:31982 "SHP/Fazenda_Santa_Clara/AVN.shp"  "$AP/AVN.shp"
"$OGR" -t_srs EPSG:31982 "SHP/Fazenda_Serra_Verde/AC.shp"   "$AP/AREA_CONSOLIDADA.shp"
"$OGR" -t_srs EPSG:31982 "SHP/Fazenda_Serra_Verde/AVN.shp"  "$AP/AVN.shp"
"$OGR" -t_srs EPSG:31982 "SHP/Fazenda_Serra_Verde/AUAS.shp" "$AP/AUAS.shp"

# Tipologia — patch de legenda "Tipologia: Floresta" (homônimo de Embargo.shp):
"$OGR" -t_srs EPSG:31982 "SHP/Embargo.shp" "$AP/ATP.shp"
```

(Os homônimos da fase anterior — `Fazenda_Santa_Clara.shp`, `Fazenda_Serra_verde.shp`,
`Fazendas_Unidas.shp`, `SIEGEF.shp`, `Fazenda_Harmonia.shp`, todos = perímetro — foram
criados da mesma forma a partir do `ATP.shp`.)

Por que existem AC/AVN duplicados nas duas subpastas: no MXD do modelo, as **entradas de
legenda** pertencem às camadas da *Serra Verde* ("Área consolidada"/"Área de vegetação
nativa"), enquanto a camada "AUAS" da legenda é a da *Santa Clara*. Remover a camada dona
da entrada apaga a entrada da legenda (não dá para recriar via arcpy) — então mantivemos
as camadas certas e apontamos cada uma para um homônimo com o dado da Harmonia.
As duplicatas do modelo que NÃO estão na legenda ("Área concolidada" [typo], "rf",
"AUAS_2026", "Fazenda Serra Verde") foram removidas do MXD.

### 12.2 Cálculos geoespaciais (áreas e distâncias TI/UC)

Script `calc_geo.py` (rodado no **Python do QGIS**: `python-qgis-ltr.bat`, libs osgeo/ogr
+ shapely — o Python do sistema não tem libs geo):
- **Áreas (ha)** = área plana em UTM 22S do union das feições de cada shape do CAR:
  ATP 3.823,9140 · AVN 2.833,7541 · AC 483,8562 · AUAS 491,2631.
- **Distâncias** = menor distância planar (UTM) do perímetro (ATP) à feição mais próxima:
  - TI: `GEOBASES\VETOR\FUNAI\tis_poligonais_V_15_05_2025\tis_poligonaisPolygon.shp`
    → **Kapôt Nhinore (Delimitada), 0,51 km** (fazenda dentro da zona de amortecimento!).
  - UC: `GEOBASES\VETOR\SEMA-MT\...\UNIDADES_CONSERVACAOPolygon.shp`
    → **Parque Estadual do Xingu, 21,79 km**.
- `shapely.ops.nearest_points` deu os 2 pontos da linha tracejada; convertidos p/ EPSG 3857
  e depois p/ coordenada de página (cm) com a extensão do data frame — é assim que o
  `adapt_bloco2.py` posiciona a linha e o texto "X km" nos mapas TI/UC.
- Atenção ao encoding: o DBF da FUNAI é latin-1; sanear strings antes de gravar JSON
  (`s.encode('utf-8','surrogateescape').decode('cp1252')`).

### 12.3 Tabela de quantitativos (imagem)

`SHP\tabela_quantitativos_harmonia.png` gerada com **PIL** (Python 3.11), replicando o
estilo do modelo (cabeçalho azul-claro, valores em verde, linha TOTAL GERAL verde-claro),
3210×472 px = proporção do PICTURE_ELEMENT (13,59 × 2,00 cm). O `adapt_bloco2.py` troca a
imagem via `PICTURE_ELEMENT.sourceImage` e reposiciona para (6,71 · 4,07) — igual ao m3.

### 12.4 Exportação

```powershell
# PowerShell (não bash-background: cwd com acento se perde e o mbcs quebra ç/ã)
$py  = "C:\Python27\ArcGIS10.8\python.exe"
$scr = "...\Automacoes\Scripts\mxd_harmonia\export_pdf_batch.py"
& $py -u $scr "<pasta MXD\claude>" "<pasta Mapas>" "Nome1,Nome2,..."   # 150 dpi
```

Validação: renderizar cada PDF em PNG (PyMuPDF/fitz, dpi 70-220) e inspecionar layout,
legenda e o minimapa ampliado. Juntar tudo: `fitz.insert_pdf` → `Mapas_unidos.pdf`.
