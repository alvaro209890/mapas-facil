# 01 — Padrão cartográfico IMAP (perfil Harmonia)

**Fonte da verdade visual do projeto inteiro.** Define o que "mapa correto" significa no Mapas
Fácil, para as duas fases. O motor `.mxd` da Fase 1, o renderizador nativo, o validador de
conformidade e o preview do site medem-se contra este documento.

Calibrado contra o acervo real em [`../Referencias_IMAP/`](../Referencias_IMAP/README.md):

| Pasta | Papel |
|---|---|
| [`Mapas/01/`](../Referencias_IMAP/Mapas/01/) | PDFs **Harmonia** — **fonte da verdade** |
| [`Mapas/02/`](../Referencias_IMAP/Mapas/02/) | PDFs **Trevisol** — contraste; perfil descartado |
| [`MXD/`](../Referencias_IMAP/MXD/) | `.mxd` + [`DOCUMENTACAO_MXD_HARMONIA.md`](../Referencias_IMAP/MXD/DOCUMENTACAO_MXD_HARMONIA.md) |

Os números de geometria abaixo foram **medidos** dos PDFs de `Mapas/01` (rasterização a 100 dpi
+ bbox de texto), não estimados. Receita operacional completa da adaptação manual: a
documentação MXD (armadilha do arcpy, homônimos, scripts, CRS).

> **Decisão de 2026-07-25.** O segundo acervo (`Mapas/02`, Fazenda Trevisol / Querência) tem
> padrão visual **diferente**: perímetro vermelho, tudo em paisagem, seta-norte simples, tabela
> branca. O dono do produto decidiu que **só o perfil Harmonia é a fonte da verdade**. O perfil
> Trevisol fica no [apêndice](#apêndice--o-perfil-trevisol-descartado) e em `Mapas/02/` apenas
> para que ninguém "corrija" o padrão de volta por engano.

## Os dois formatos de página

Erro do plano anterior: assumir A4 paisagem para a série inteira. **A série Dinâmica é A4
retrato.** Medido nos 21 PDFs:

| Formato | Página | Mapas |
|---|---|---|
| **A4 retrato** — 210 × 297 mm | `595,5 × 842,3 pt` | Dinâmica (2000, 2008 LANDSAT, 2008 SPOT, 2013, 2017, 2019, 2023, 2026), Dinâmica quantitativos, DLA, Áreas Cultiváveis, PEF, TCR |
| **A4 paisagem** — 297 × 210 mm | `841,5 × 595,5 pt` | Tipologia, Terras Indígenas, Unidade de Conservação, Embargos IBAMA, Embargos SEMA SIGA, Alertas MapBiomas, Alertas PRODES |

A regra por trás: **imóvel alongado no eixo N-S → retrato; mapa de contexto regional →
paisagem.** A Harmonia é um retângulo alto, por isso a série Dinâmica (que enquadra só o imóvel)
é retrato, e os temáticos (que precisam mostrar a TI a 0,51 km, a UC a 21,79 km, o entorno de
embargos) são paisagem.

Consequência para o produto: `formato_pagina` é propriedade do **template**, não do `MapSpec` —
e existem duas famílias de template. Ver [`02-mapspec-contrato.md`](02-mapspec-contrato.md).

## Anatomia — perfil retrato (série Dinâmica)

```
A4 retrato — 210 × 297 mm
┌──────────────────────────────────────────────────┐  y=0
│        ┌────────────────────────┐         ╭─╮    │
│        │  Dinâmica 2026         │         │N│    │  título y 3,6–21,8 · rosa y 4,0–27,0
│        └────────────────────────┘         ╰─╯    │
│ ┌──────────────────────────────────────────────┐ │  quadro do mapa
│ │                                              │ │  x 7,0 → 203,5 mm
│9│                                              │9│  y  5,0 → 257,0 mm
│°│        satélite full-bleed (Planet/WMS)      │°│
│4│                                              │4│  rótulos DMS laterais
│3│   perímetro AMARELO + hachuras das classes   │5│  rotacionados 90°
│'│                                              │1│
│5│                                              │'│
│0│  ┌────────────────────────────────────────┐  │1│
│"│  │ tabela: cab. AZUL / TOTAL GERAL verde  │  │0│  tabela y ≈ 240–256 mm
│S│  └────────────────────────────────────────┘  │"│
│ └──────────────────────────────────────────────┘ │
│  52°11'10"W    52°9'20"W   52°7'30"W  52°5'40"W  │  y 257,7–263,4
│ ┌────────┐   METADADOS IMAGEM    Legenda   ┌───┐ │
│ │minimapa│   Satélite/Sensor: …  ▭ Área…   │IMA│ │  faixa inferior 257 → 297
│ │Vila    │   Data da imagem: …   ▭ Área…   │ P │ │  (40,1 mm)
│ │Rica/MT │   Fonte: WMS-SEMA     ▭ Fazenda │   │ │
│ └────────┘   Datum: …            ▭ Limite… └───┘ │
│              Escala: 1:60.000                    │
└──────────────────────────────────────────────────┘  y=297
```

### Retângulos medidos (perfil retrato)

| Região | x (mm) | y (mm, do topo) | Como foi medido |
|---|---|---|---|
| Quadro do mapa | 7,0 → 203,5 | 5,0 → 257,0 | centro dos rótulos DMS das 4 bordas |
| Caixa do título | 63,7 → 132,7 | 3,6 → 21,8 | bbox do texto "Dinâmica 2026" |
| Rosa dos ventos | 186,3 → 202,0 | 4,0 → 27,0 | glifo `µ` da fonte ESRI North |
| Tabela quantitativos | 67,1 → 203,0 | 40,7 → 60,7 | `adapt_bloco2.py`: elem (6,71·4,07) cm + 13,59×2,00 cm; PNG 3210×472 px |
| Rótulos DMS inferiores | linha inteira | 257,7 → 263,4 | bbox dos rótulos |
| Minimapa | 0 → 62 | 262 → 297 | bbox de "Vila Rica" + "MT" |
| METADADOS IMAGEM | 64,9 → 120 | 265,2 → 291,2 | bbox das 6 linhas |
| Legenda | 131,8 → 172 | 266 → 295 | bbox dos itens |
| Logo IMAP | ≈ 175 → 208 | ≈ 265 → 292 | raster |

## Anatomia — perfil paisagem (temáticos)

```
A4 paisagem — 297 × 210 mm
┌───────────────────────────────────────────────────────────────┐  y=0
│              ┌──────────────────────┐                   ╭─╮   │
│ ┌────────────┤  Tipologia Vegetal   ├───────────────────┤N├─┐ │  título y 3,0–20,5
│ │            └──────────────────────┘                   ╰─╯ │ │  rosa x 276,7–288,5
│9│                                                           │9│
│°│              quadro do mapa: x 5,6 → 291,1                 │°│  ← medição limpa
│4│                             y 4,8 → 168,5                  │4│    (moldura preta
│4│                                                           │4│     detectada no raster)
│'│                        Fazenda Harmonia                    │'│
│0│                                                           │0│
│"│                                                           │"│
│S└───────────────────────────────────────────────────────────┘S│
│  52°13'50"W   52°11'30"W   52°9'10"W   52°6'50"W   52°4'30"W  │  y 170,0–173,9
│┌──────┐      METADADOS IMAGEM      LEGENDA         ┌────────┐ │
││minima│      Base: Radam Brasil    ▭ Fazenda…      │  IMAP  │ │  faixa inferior
││ Vila │      Fonte: WMS SEMA       ▭ Tipologia:…   │        │ │  168,5 → 210,1
││Rica  │      Datum: SIRGAS…        ▭ Tipologia:…   └────────┘ │  (41,6 mm)
│└──────┘                                                       │
└───────────────────────────────────────────────────────────────┘  y=210
```

### Retângulos medidos (perfil paisagem)

| Região | x (mm) | y (mm, do topo) | Como foi medido |
|---|---|---|---|
| Quadro do mapa | 5,6 → 291,1 | 4,8 → 168,5 | detecção da moldura preta no raster 100 dpi |
| Caixa do título | 107,2 → 185,0 | 3,0 → 20,5 | bbox do texto |
| Rosa dos ventos | 276,7 → 288,5 | 4,3 → 21,7 | glifo `µ` |
| Rótulos DMS inferiores | linha inteira | 170,0 → 173,9 | bbox |
| Minimapa | 2 → 62 | 172 → 208 | bbox de "Vila Rica" + "MT" |
| METADADOS | 76,4 → 156,2 | 173,8 → 205,3 | bbox das linhas |
| LEGENDA | 177,1 → 227 | 172,0 → 208,2 | bbox do título + itens |
| Logo IMAP | ≈ 245 → 292 | ≈ 175 → 205 | raster |

Os dois perfis compartilham a estrutura: **quadro do mapa ocupando ~85% da altura, faixa
inferior de ~40 mm com quatro blocos na ordem minimapa → metadados → legenda → logo.**

## Cores e estilos oficiais

Extraídos das legendas dos PDFs-modelo e dos `.mxd`. **Estes valores são vinculantes.**

### Camadas do imóvel

| Camada | Nome exato na legenda | Linha | Preenchimento | Hachura | Largura |
|---|---|---|---|---|---|
| Perímetro do imóvel | `Fazenda <Nome>` | **amarelo `#FFFF00`** | nenhum | — | 2,0–2,5 |
| Área de vegetação nativa (AVN) | `Área de vegetação nativa` | verde `#00E64D` | nenhum | `xxx` (cruzada) | 1,0 |
| Área consolidada (AC) | `Área consolidada` | magenta `#FF00FF` | nenhum | `xxx` (cruzada) | 1,0 |
| Área derivada de desmate pós-2008 (AUAS) | `Área Derivada de Desmate Após 2008` | laranja `#FF8000` | nenhum | `///` | 1,0 |
| Limite municipal | `Limite municipal` | laranja `#E8722C` | nenhum | — | 1,0 |
| Limite estadual | `Limite estadual` | verde-claro `#C5E0B4` | verde-claro | — | 0,8 |

### Camadas temáticas

| Camada | Nome na legenda | Estilo |
|---|---|---|
| Terra indígena | `Terras Indígenas` | preenchimento marrom `#8B2500` sólido |
| Zona de amortecimento (TI) | `Zona de amortecimento` | linha magenta `#FF00FF`, sem preenchimento |
| Embargo IBAMA | `Áreas embargadas pelo Ibama` | preenchimento cinza `#BFBFBF`, borda escura |
| Tipologia: Floresta | `Tipologia: Floresta` | verde `#00D26A` sólido |
| Tipologia: Cerrado | `Tipologia: Cerrado` | ocre `#C9B94A` sólido |
| Unidade de conservação | `Unidade de Conservação` | conforme o `.lyr` do template |

Três regras derivadas, e uma inversão importante do plano anterior:

1. **O perímetro do imóvel é AMARELO, não vermelho.** Vermelho `#c00000` é o perfil Trevisol,
   descartado. Amarelo sobre imagem de satélite (verde/marrom) tem contraste muito maior — é
   por isso que o padrão migrou.
2. **Camadas do imóvel são todas vazadas**; camadas temáticas de contexto (TI, embargo,
   tipologia) são **sólidas**, porque nelas o fundo não importa.
3. **Rótulo do imóvel é só o nome** (`Fazenda Harmonia`), branco com halo escuro, no centroide.
   Sem matrícula — o CAR emitido da Harmonia não traz matrícula, e o padrão consolidou assim.
   Quando o imóvel tiver matrícula e o usuário pedir, ela entra numa segunda linha.

## Elementos do layout

| Elemento | Default | Especificação |
|---|---|---|
| `titulo_caixa` | ligado | caixa **branca**, borda preta ~1 pt, topo-centro, fonte serifada bold ~24 pt. Texto varia: `Dinâmica 2026`, `Ano: 2026`, `Tipologia Vegetal`, `Terras Indígenas` |
| `norte` | ligado | **rosa dos ventos** com N/S/E/W (glifo `µ` da fonte *ESRI North*), topo-direita, ~16 × 23 mm. **Não** é a seta triangular simples |
| `grade` | ligado | rótulos DMS + ticks nas 4 bordas; laterais rotacionados 90° |
| `grade_linhas` | desligado | o modelo não tem linhas cruzando o mapa |
| `escala_grafica` | desligado | a escala aparece como **texto** no bloco de metadados |
| `minimapa` | ligado | inset de município (ver abaixo) |
| `metadados_imagem` | ligado | bloco central da faixa inferior |
| `legenda` | ligado | à direita dos metadados; título `Legenda` (retrato) ou `LEGENDA` (paisagem) |
| `logo` | ligado | marca IMAP no canto inferior-direito |
| `tabela` | conforme mapa | só nos mapas com quantitativos |
| `creditos` | desligado | não existe rodapé de fontes |
| `rosa_dos_ventos` | — | **não é opção**: no perfil Harmonia a rosa É o indicador de norte |

## Bloco METADADOS IMAGEM

Diferença relevante em relação ao plano anterior: **o bloco tem `Fonte:` e `Escala:`, e não tem
`Órbita/Ponto:`.** O rótulo é `Satélite/Sensor:`, não `Satélite:`.

Nos `.mxd` o bloco é um único `TEXT_ELEMENT` com marcação de formatação do ArcMap — o motor
precisa preservar as tags:

```
<bol>METADADOS IMAGEM</bol>
<bol>Satélite/Sensor:</bol> PLANET
<bol>Data da imagem:</bol> Março/2026
<bol>Fonte:</bol> WMS-SEMA
<bol>Datum:</bol> SIRGAS 2000 UTM 22 S
<bol>Escala:</bol> 1:60.000
```

Variantes reais observadas, todas legítimas:

| Mapa | Linhas do bloco | Título |
|---|---|---|
| Dinâmica / quantitativos | Satélite/Sensor, Data da imagem, Fonte, Datum, Escala | `METADADOS IMAGEM` |
| Tipologia | **Base** (`Radam Brasil`), Fonte (`WMS SEMA`), Datum | `METADADOS IMAGEM` |
| Terras Indígenas | Fonte (`WMS FUNAI`), Datum | `METADADOS` |
| Embargos IBAMA | Satélite, Data da imagem, Datum | `METADADOS IMAGEM` |

Regra do produto: o bloco é uma **lista ordenada de pares rótulo/valor**, não um formulário de 4
campos fixos. O `MapSpec` carrega a lista; o validador exige que toda linha declarada tenha valor
não vazio, e que o `Datum:` concorde com o CRS do data frame.

| Chave do MapSpec | Rótulo impresso | Exemplo |
|---|---|---|
| `satelite_sensor` | `Satélite/Sensor:` | `PLANET` |
| `data_aquisicao` | `Data da imagem:` | `Março/2026`, `OUTUBRO/2025` |
| `fonte` | `Fonte:` | `WMS-SEMA`, `WMS SEMA`, `WMS FUNAI` |
| `base` | `Base:` | `Radam Brasil` |
| `datum` | `Datum:` | `SIRGAS 2000 UTM 22 S` |
| `escala_texto` | `Escala:` | `1:60.000` |

## Tabela de quantitativos

**Achado que inverte a recomendação do plano anterior:** no perfil Harmonia a tabela **é uma
imagem** (`PICTURE_ELEMENT`), não uma grade de células de texto. Prova: `pdftotext` não extrai
uma única palavra da região da tabela em `Dinamica_2026_quantitativos.pdf`, e o `.mxd`
referencia `SHP\tabela_quantitativos_harmonia.png`.

Estilo, medido do raster e confirmado na documentação da análise:

| Faixa | Fundo | Texto |
|---|---|---|
| Cabeçalho | azul `#2E75B6` | branco, negrito, centralizado, quebra em 2 linhas |
| Linhas de dados | branco | preto, valores centralizados |
| `TOTAL GERAL` | verde `#70AD47` | branco, negrito |

- Colunas do modelo: `Propriedade` · `Área total da propriedade (ha)` · `Área de vegetação
  nativa (ha)` · `Área consolidada (ha)` · `Área Derivada de Desmate Após 2008 (ha)`.
- Valores com **4 casas decimais** e vírgula decimal (`3.823,9140`) — não 2 casas.
- A imagem do modelo tem 3210 × 472 px para um `PICTURE_ELEMENT` de 13,59 × 2,00 cm ≈ **600 dpi
  efetivos**. Gerar com menos que isso borra visivelmente no PDF a 150 dpi.
- Linha `TOTAL GERAL` = **soma dos valores já arredondados**, para a coluna fechar visualmente.

Consequência de projeto: o motor de tabela é um **renderizador de PNG** (Pillow) compartilhado
entre o caminho `.mxd` e o renderizador nativo. Ele é testável em CI sem ArcGIS nenhum, o que é
uma vantagem, não um remendo. Detalhe em
[`../Fase_1_Desktop/planos/04-motor-mxd.md`](../Fase_1_Desktop/planos/04-motor-mxd.md).

## Grade DMS

```
g°m's"H     →     52°11'10"W          9°43'50"S
```

- Sem zero à esquerda (`9°44'0"S`, nunca `09°44'00"S`).
- Hemisfério como letra sufixa; nunca sinal negativo.
- **Alvo de 4 a 8 rótulos por eixo** (medido: 5 no eixo x do retrato, 9 no eixo x da paisagem,
  8 no eixo y da paisagem) — mais denso que os "~3" do plano anterior.
- Passo em valor redondo de minutos/segundos: os modelos usam 1'50", 1'10", 1'0".
- Rótulos laterais rotacionados 90°; superiores e inferiores na horizontal.
- Sem linhas internas.
- Grade sempre em **coordenadas geográficas SIRGAS 2000**, mesmo com o data frame em UTM ou
  Web Mercator.

## Minimapa de localização

Fiel ao inset do ArcMap, nos dois perfis:

- Municípios do entorno em bege `#FDF3D7`, contorno preto fino.
- **Município do imóvel em laranja `#F4A460`**, nome rotulado em negrito com halo branco
  (`Vila Rica`).
- **Retângulo vermelho** na posição do imóvel + **linha-guia vermelha** saindo dele até a
  moldura do quadro do mapa principal.
- Caixinha da UF no canto inferior-esquerdo: estado em verde-claro, município em laranja, selo
  `MT`.
- Moldura preta em volta do inset inteiro.

Duas armadilhas registradas do trabalho real:

1. **O retângulo vermelho desalinha.** Na análise Harmonia ele estava ~0,4 cm fora do centroide
   em 19 dos 19 mapas, e precisou de um script dedicado (`fix_minimap_rect.py`) para recentrar e
   reatar a linha-guia. No Mapas Fácil isso é **cálculo obrigatório do motor**, não correção
   posterior: centroide do imóvel → coordenada do data frame do minimapa → coordenada de página.
   Vira o check `S01`.
2. **A troca de município é uma *definition query*.** A camada de municípios do `.mxd`
   (`lml_municipio_a`) carrega `"nome" = 'Vila Rica'`; nos `.mxd` do acervo ainda há
   `"nome" = 'Querência'` e `"nome" = 'Ribeirão...'` sobrando de análises anteriores. Trocar de
   imóvel **exige** reescrever essa query, e a camada de UF carrega `"nome" = 'Mato Grosso'`.
   Isso é automatizado — ver [`02-mapspec-contrato.md`](02-mapspec-contrato.md), campo
   `municipio`.

## CRS por família de mapa

Descoberta do acervo que decide o motor: **as duas famílias usam CRS de data frame diferentes.**

| Família | CRS do data frame | EPSG |
|---|---|---|
| Série Dinâmica (retrato) | SIRGAS 2000 / UTM 22S | `31982` |
| Temáticos (paisagem) | WGS 84 / Pseudo-Mercator | `3857` |

Regra vinculante: **o bbox aplicado em `df.extent` precisa estar no CRS do data frame.** Aplicar
um bbox UTM num data frame 3857 produz **mapa em branco** — aconteceu de verdade na análise
Harmonia. O motor lê o CRS do data frame do template e converte o bbox do imóvel antes de
aplicar; nunca assume.

E: **nunca hardcodar a zona UTM.** Mato Grosso é cortado pelo meridiano 54°W — imóveis a oeste
são 21S (`31981`), a leste 22S (`31982`). A zona sai do centroide do imóvel. Área **sempre** se
calcula em CRS projetado (m² ÷ 10.000 = ha); em coordenadas geográficas o número está em graus²
e não significa nada.

## Escalas

Os modelos da Harmonia usam **1:60.000** (Dinâmica, DLA, quantitativos), **1:90.000**
(Tipologia) e **1:105.000** (Terras Indígenas) — bem mais afastadas que as ~1:22.000 do perfil
Trevisol, porque a Harmonia tem 3.823 ha contra 378 ha da Trevisol.

Lista de escalas permitidas, ampliada para cobrir os dois portes:

```
  5.000 ·   7.500 ·  10.000 ·  12.500 ·  15.000 ·  20.000 ·  22.000 ·  25.000
 30.000 ·  40.000 ·  50.000 ·  60.000 ·  75.000 ·  90.000 · 100.000 · 105.000
125.000 · 150.000 · 200.000 · 250.000
```

Algoritmo de `escala: "auto"`:

1. bbox da união das geometrias visíveis, no CRS do data frame;
2. margem de 15% em cada eixo;
3. ler o retângulo do quadro do mapa em mm (tabelas acima, por perfil);
4. escala mínima = `max(largura_m / (largura_mm/1000), altura_m / (altura_mm/1000))`;
5. **arredondar para cima** na lista — para baixo corta o imóvel;
6. gravar a escala resolvida no `MapSpec` da versão, para reexecução dar o mesmo resultado;
7. o texto `Escala: 1:60.000` do bloco de metadados é derivado deste valor, nunca digitado à mão.

## Checklist de conformidade

Roda depois de exportar o PDF; relatório vai para `validacao.json`. **HARD bloqueia a entrega**;
SOFT conclui com ressalva.

| ID | Check | Como verificar | Sev. |
|---|---|---|---|
| `H01` | Nenhuma fonte quebrada no `.mxd` | `ListBrokenDataSources` vazio (ou, sem ArcMap, todo caminho do `.mxd` resolve em disco) | HARD |
| `H02` | Página no formato do perfil | 210×297 mm (retrato) ou 297×210 mm (paisagem), ±1 mm | HARD |
| `H03` | Título presente e igual ao `MapSpec` | texto extraível do PDF contém o título | HARD |
| `H04` | Datum coerente com o CRS | `Datum:` do bloco descreve o EPSG do data frame | HARD |
| `H05` | Escala na lista permitida | escala do data frame ∈ lista, tolerância 0 | HARD |
| `H06` | `Escala:` impressa = escala real | texto do bloco casa com `df.scale` | HARD |
| `H07` | Todas as camadas do `MapSpec` no mapa | conjunto do `.mxd` ⊇ ids de `camadas[]` | HARD |
| `H08` | Legenda com todas as camadas visíveis | itens ⊇ camadas com `legenda` definida | HARD |
| `H09` | PDF abre, 1 página, não está em branco | PyMuPDF + cobertura de pixels não-brancos > 5% | HARD |
| `H10` | Bloco de metadados sem linha vazia | toda linha declarada tem valor | HARD |
| `H11` | Perímetro do imóvel amarelo | amostragem de cor da borda do polígono no raster | HARD |
| `H12` | Query de município correta | `definitionQuery` da camada de municípios = município do imóvel | HARD |
| `H13` | `.mxd` reabre | reabrir e listar camadas sem exceção | HARD |
| `H14` | `TOTAL GERAL` presente quando há tabela | última linha da imagem da tabela com faixa verde | HARD |
| `S01` | Retângulo do minimapa centrado | distância centro-do-retângulo ↔ centroide do imóvel < 1 mm de página | SOFT |
| `S02` | Linha-guia do minimapa conectada | linha vermelha toca retângulo e moldura | SOFT |
| `S03` | Município identificado no minimapa | há feição em laranja e rótulo | SOFT |
| `S04` | Rótulo do imóvel não truncado | largura do texto cabe na caixa do polígono | SOFT |
| `S05` | Legenda não sobrepõe metadados nem logo | interseção dos retângulos < 2% | SOFT |
| `S06` | Imóvel inteiro dentro do quadro | bbox do imóvel ⊂ extent do data frame | SOFT |
| `S07` | Grade com 4–8 rótulos por eixo | contagem de rótulos DMS | SOFT |
| `S08` | Basemap resolvido | camada de fundo desenhou; não caiu para branco | SOFT |
| `S09` | Camada externa não vazia | WFS retornou > 0 feições após o recorte | SOFT |
| `S10` | Tabela em resolução suficiente | PNG da tabela ≥ 400 dpi efetivos | SOFT |
| `S11` | Sem texto herdado de outra análise | nenhum `TEXT_ELEMENT` cita município/fazenda diferentes do `MapSpec` | SOFT |

`S11` merece destaque: na análise Harmonia sobraram textos de matrícula, distâncias e até o
título `Alertas MAPBIOMAS` num mapa PRODES, herdados do `.mxd` copiado. É o erro mais provável
de um sistema que parte de template, e o mais embaraçoso na frente do cliente.

## Checklist de implementação do padrão

Marcar conforme o motor for cobrindo cada item. Vale para os dois motores (ArcPy e nativo).

- [ ] Duas famílias de template registradas no manifesto (retrato + paisagem)
- [ ] Retângulos de página por perfil lidos do manifesto, nunca hardcoded
- [ ] Perímetro amarelo `#FFFF00` com largura 2,0–2,5
- [ ] AVN verde `xxx`, AC magenta `xxx`, AUAS laranja `///` — todas vazadas
- [ ] Limite municipal e estadual desenhados e na legenda
- [ ] Camadas temáticas sólidas (TI, embargo, tipologia)
- [ ] Rótulo do imóvel = só o nome, branco com halo, acima das hachuras
- [ ] Caixa de título branca com borda preta, texto do `MapSpec`
- [ ] Rosa dos ventos (não seta) no canto superior direito
- [ ] Grade DMS `g°m's"H` sem zero à esquerda, 4–8 rótulos/eixo, laterais a 90°
- [ ] Bloco de metadados como lista de pares, com `<bol>` preservado
- [ ] `Escala:` derivado da escala resolvida
- [ ] `Datum:` derivado do CRS do data frame
- [ ] Tabela como PNG ≥ 600 dpi, cabeçalho azul, `TOTAL GERAL` verde, 4 casas decimais
- [ ] Minimapa com município em laranja + retângulo vermelho **recentrado** + linha-guia
- [ ] Definition query de município e de UF reescritas por imóvel
- [ ] Logo IMAP no canto inferior direito
- [ ] Nenhum texto herdado de análise anterior (varredura `S11`)
- [ ] Os 21 PDFs-modelo reproduzidos e comparados por raster (tolerância 0,3%)

## Apêndice — o perfil Trevisol (descartado)

Registrado só para evitar "correção" acidental de volta. Não implementar.

| Aspecto | Harmonia (vale) | Trevisol (não vale) |
|---|---|---|
| Perímetro | amarelo `#FFFF00` | vermelho `#c00000` |
| Lote secundário | — | azul `#00b0f0` |
| Dinâmica | A4 retrato | A4 paisagem |
| Norte | rosa dos ventos | seta triangular preto/branco |
| Metadados | Satélite/Sensor, Data, Fonte, Datum, Escala | Satélite, Órbita/Ponto, Data, Datum |
| Tabela | imagem, cab. azul, `TOTAL GERAL` verde | células de texto, cab. branco, `TOTAL` preto |
| Rótulo do imóvel | só o nome | nome + matrícula |
| Escala típica | 1:60.000 | 1:22.000 |
| AC | magenta hachurado `xxx` | magenta vazado sem hachura |

Se um dia um cliente pedir o padrão Trevisol, ele entra como **segundo perfil** em
`shared/padrao-imap/`, com sua própria família de templates — nunca como alteração deste.

## Pendências

| # | Pendência | Situação |
|---|---|---|
| P1 | Cores em hex foram amostradas do raster do PDF, não do símbolo do `.mxd` | confirmar abrindo os `.lyr`/`.mxd` no ArcMap e lendo o RGB exato; erro esperado ≤ 3% por canal |
| P2 | Fonte tipográfica do título e dos metadados | os PDFs embutem as fontes; extrair o nome da família com PyMuPDF antes de calibrar o renderizador nativo |
| P3 | Largura/posição exata da tabela por mapa | varia entre modelos; medir os 4 mapas com tabela e decidir se é 1 posição ou 1 por template |
| P4 | Hachura `xxx` e `///` não são programáveis em `arcpy` 10.x | resolver com biblioteca de `.lyr` versionada, extraída dos próprios `.mxd` do acervo |
| P5 | Símbolo da rosa dos ventos depende da fonte *ESRI North* | conferir se o instalador precisa garantir a fonte no PC do usuário para o renderizador nativo |
| P6 | Nem todo mapa do acervo foi medido | 5 dos 21 medidos; medir os 16 restantes antes de fechar o M4 |
