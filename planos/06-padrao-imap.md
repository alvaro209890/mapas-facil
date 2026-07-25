# 06 — Padrão cartográfico IMAP

Este documento define **o que "mapa correto" significa** no Mapas Fácil. Ele é a especificação
que o motor de `.mxd`/PDF ([`05-motor-mxd-pdf.md`](05-motor-mxd-pdf.md)) precisa reproduzir e que
o validador de conformidade precisa medir. Os contratos (nomes de campo do `MapSpec`, chaves de
`elementos_layout`) vêm de [`01-arquitetura.md`](01-arquitetura.md) e não são redefinidos aqui.

## Origem do padrão

O padrão não foi inventado: ele foi **calibrado contra os PDFs-modelo reais** produzidos à mão no
ArcMap pela equipe do cliente (IMAP, consultoria ambiental em Mato Grosso). O acervo de referência
usado no projeto anterior tem 26 mapas da série, com `Dinamica_2026.pdf` como modelo principal e
`Dinamica_2026_quantitativos.pdf` como modelo da tabela.

A série coberta pela v1:

| Mapa da série | Para que serve |
|---|---|
| Dinâmica de uso do solo | comparar vegetação/uso ao longo do tempo (o mapa mais pedido) |
| Uso Consolidado | provar ocupação anterior a 22/07/2008 |
| Tipologia Vegetal | classificar a vegetação (Floresta, Cerrado, Vereda) |
| Embargos IBAMA | mostrar sobreposição do imóvel com embargos federais |
| Alertas MapBiomas | mostrar alertas de desmatamento recentes |

Formato de página: **A4 paisagem, 297×210 mm**. O cliente não usa A3 — A3 só quando pedido
explicitamente. Esse é um ponto em que o projeto anterior errou por default e teve de ser
corrigido; aqui o default nasce certo.

O critério de aceite é comparativo, não estético: um `.pdf` gerado deve ser sobreponível ao
PDF-modelo da mesma série. Toda decisão abaixo tem essa origem, e "porque é mais bonito" nunca é
justificativa suficiente para mudá-la.

## Anatomia da página

```
A4 paisagem — 297 × 210 mm
┌───────────────────────────────────────────────────────────────────────┐
│  52°15'0"W        ┌──────────────────────────┐        52°13'0"W       │ ← rótulos DMS + ticks
│  ┌────────────────┤ TÍTULO EM CAIXA BRANCA   ├───────────────────┐    │   na moldura
│  │                └──────────────────────────┘                   │    │
│ 1│                                                        N      │    │ ← seta norte ArcMap
│ 2│         QUADRO DO MAPA (satélite full-bleed)           ▲      │    │   (topo-direita)
│ °│                                                               │    │
│ 3│    lote rotulado em branco com halo escuro                    │    │
│ 3│    AVN (xxx verde) · AC (magenta) · AUAS (/// laranja)         │    │
│ '│                                                               │    │
│ 1│                              ┌──────────────────────────────┐ │    │
│ 0│                              │ tabela branca, grade preta   │ │    │
│ "│                              │ cabeçalho + TOTAL em negrito │ │    │
│ S│                              └──────────────────────────────┘ │    │
│  └───────────────────────────────────────────────────────────────┘    │
│  52°15'0"W                                            52°13'0"W       │
│ ┌──────────┐   METADADOS IMAGEM     Legenda                ┌────────┐ │
│ │ minimapa │   Satélite: PLANET     ▭ Lote 65              │  IMAP  │ │ ← faixa inferior 20%
│ │municípios│   Data: Maio/2026      ▨ AVN  ▭ AC  ▨ AUAS    │ (logo) │ │
│ └──────────┘   Datum: SIRGAS...                            └────────┘ │
└───────────────────────────────────────────────────────────────────────┘
```

Frações de página (origem inferior-esquerda, fração de 0 a 1), herdadas da calibração do projeto
anterior e convertidas para milímetros porque o `arcpy` trabalha em unidades de página:

| Região | Fração `(x0, y0, largura, altura)` | Em mm (A4 paisagem) |
|---|---|---|
| Quadro do mapa | `(0.022, 0.245, 0.956, 0.725)` | x 6,5 → 290,4 · y 51,5 → 203,7 |
| Faixa inferior | `(0, 0, 1, 0.20)` | y 0 → 42,0 (largura total) |

Consequências que importam: a margem útil é de ~6,5 mm, o mapa ocupa 72,5% da altura da página e
a faixa inferior de 20% tem apenas 42 mm para acomodar minimapa, metadados, legenda e logo — é o
lugar onde as sobreposições acontecem, e por isso existe um check *soft* específico para isso.

## Elementos do layout e seus defaults

Chaves exatamente como em `elementos_layout` do `MapSpec`
([`01-arquitetura.md`](01-arquitetura.md)). Tudo é ligável/desligável; a coluna "default" é o que
sai quando o usuário não pede nada.

| Chave | Default | O que é / por que esse default |
|---|---|---|
| `grade` | `true` | rótulos DMS + ticks pretos na moldura, como no modelo |
| `grade_linhas` | `false` | o modelo IMAP **não** tem linhas de grade cruzando o mapa; elas competem com as feições |
| `norte` | `true` | seta estilo ArcMap: triângulo dividido preto/branco com "N" e halo |
| `rosa_dos_ventos` | `false` | alternativa à seta (rosa de 8 pontas); fora do padrão do cliente |
| `escala_grafica` | `false` | o modelo não tem barra de escala — a escala aparece só no texto/datum |
| `creditos` | `false` | sem rodapé "Fontes: ..."; o cliente usa a faixa de metadados no lugar |
| `minimapa` | `true` | inset de municípios do IBGE (ver abaixo) |
| `titulo_caixa` | `true` | caixa branca com borda preta fina, topo-centro, fonte 20–22 |
| `tabela` | `true` | quantitativos por lote × classe, flutuando sobre o mapa |
| `metadados_imagem` | `true` | bloco `METADADOS IMAGEM` centralizado na faixa inferior |
| `logo` | `true` | logo IMAP no canto inferior-direito |
| `inset_tipologia` | `false` | só nos mapas de Tipologia Vegetal |

Não existe chave de visibilidade para a **legenda**: no padrão IMAP a legenda é obrigatória, e o
check `H06` depende disso. Ligar/desligar legenda não é uma operação suportada na v1.

Uma ressalva de viabilidade que atravessa a tabela toda: `grade` e `grade_linhas` **não são
programáveis** em `arcpy.mapping` — a grade DMS, seu intervalo e o formato dos rótulos vêm
configurados no `.mxd` de template e não podem ser criados nem alternados por código
([`05-motor-mxd-pdf.md`](05-motor-mxd-pdf.md)). Na prática isso significa que os dois defaults acima
são *propriedades do template*, e uma variação exige template variante, não uma chave no `MapSpec`.
O mesmo vale para desligar elementos: `arcpy.mapping` não tem propriedade `visible` para elementos
de layout, e a técnica é mover o elemento para fora da página.

## Estilos oficiais das camadas

Valores validados contra o PDF-modelo. Cores em hexadecimal, largura em pontos, hachura no
vocabulário de padrões do renderizador nativo (a tradução para símbolos ArcMap é assunto do
[`05`](05-motor-mxd-pdf.md)).

| Camada | Cor da linha | Largura | Hachura | Preenchimento | Rótulo |
|---|---|---|---|---|---|
| Lote/ATP principal | `#c00000` | 2.8 | — | `none` | branco com halo escuro no centroide |
| Lote secundário | `#00b0f0` | 2.8 | — | `none` | opcional, mesmo estilo |
| AVN (vegetação nativa) | `#00b050` | 0.7 | `xxx` | `none` | não |
| AC (área consolidada) | `#ff00ff` | 1.6 | — | `none` | não |
| AUAS (desmate pós-2008) | `#ffa500` | 0.7 | `///` | `none` | não |

Três regras derivadas:

1. **Nada é preenchido sólido.** Todas as classes são vazadas (`preenchimento: "none"`), porque o
   fundo é imagem de satélite e o técnico precisa ver o terreno sob a classe. Preenchimento com
   opacidade foi tentado no projeto anterior e descaracteriza o modelo.
2. **Lote é polígono, não linha.** Na legenda, os lotes entram como polígono com
   `preenchimento: "none"` e a `largura` preservada, de modo que o swatch saia como **retângulo
   vazado grosso** — igual ao ArcMap. Se entrarem como linha, o swatch vira um tracinho e o mapa
   deixa de ser sobreponível ao modelo.
3. **Rótulo do lote é texto fixo, não expressão de campo.** O `MapSpec` traz
   `rotulo_texto: "Fazenda Trevisol (Lote 65)\nMatrícula 13.533"` na camada. Duas linhas, nome
   comercial + matrícula, desenhado no centroide em branco com halo escuro e desenhado **acima**
   das sub-áreas (AVN/AC/AUAS), senão a hachura come o texto.

## Grade DMS

Formato exato, sem variação permitida:

```
g°m's"H      →  52°15'0"W        12°33'10"S
```

- Graus, minutos e segundos **sem zero à esquerda** (`52°15'0"W`, nunca `052°15'00"W`).
- Hemisfério como sufixo de letra (`W`, `S`), sem sinal negativo.
- Alvo de **~3 rótulos por eixo** — o passo é escolhido pelo valor "redondo" mais próximo que
  produza 3 rótulos no extent atual.
- Rótulos das **laterais rotacionados 90°**; rótulos de topo e base na horizontal.
- **Ticks pretos** de 4 pt cruzando a moldura na posição de cada rótulo.
- Sem linhas internas (ver `grade_linhas: false`). Quando ligado, o padrão do projeto anterior
  desenhava linhas tracejadas brancas — aceitável como exceção, nunca como default.

A grade é sempre em coordenadas geográficas (SIRGAS 2000), mesmo quando o mapa está projetado em
UTM: é o que o modelo faz e é o que o cliente lê. Grade UTM não está no escopo da v1.

## Bloco METADADOS IMAGEM

Bloco centralizado na faixa inferior, rótulos em negrito e valores em peso normal, alinhados pelo
dois-pontos. Exemplo exato (é este texto que o validador compara):

```
        METADADOS IMAGEM
       Satélite: PLANET
   Órbita/Ponto: Não se aplica
 Data da imagem: Maio/2026
          Datum: SIRGAS 2000 UTM 22S
```

Mapeamento para o `MapSpec` (objeto `metadados_imagem`):

| Linha impressa | Chave do `MapSpec` | Exemplo |
|---|---|---|
| `Satélite:` | `satelite_sensor` | `PLANET`, `SENTINEL-2`, `LANDSAT 8` |
| `Órbita/Ponto:` | `orbita_ponto` | `Não se aplica` (Planet), `226/069` (Landsat) |
| `Data da imagem:` | `data_aquisicao` | `Maio/2026` |
| `Datum:` | `datum` | `SIRGAS 2000 UTM 22S` |

O bloco **não** tem linha de escala. Quando `metadados_imagem` está ligado e algum campo está
vazio, o check `H10` reprova: metade do bloco preenchida é pior que bloco ausente, porque parece
erro de produção.

## Minimapa de municípios

Reprodução do inset de localização do ArcMap:

- Municípios da UF em bege `#fdf3d7` com contorno preto fino.
- Município do imóvel em laranja `#f59a4b`, com o nome rotulado em halo branco.
- **Retângulo vermelho** na posição do imóvel, com linha-guia vermelha até a moldura do mapa.
- Caixinha da UF no canto (estado em verde-claro, município em laranja, selo `MT`).
- **Dados:** API de malhas do IBGE v3, com `qualidade=minima&intrarregiao=municipio`. A resposta
  vem **gzip** e precisa ser descomprimida explicitamente.
- **Identificação do município:** pelo código IBGE do projeto; fallback por município que contém
  o centroide do imóvel.
- **Cache local** por UF, uma vez por máquina — a malha municipal é praticamente imutável. Local e
  TTL em [`08-dados-e-camadas.md`](08-dados-e-camadas.md).
- **Fallback:** sem internet e sem cache, o minimapa cai para tiles de basemap e o check `S03`
  avisa que nenhum município foi identificado.

## CRS, datum e cálculo de área

| Uso | CRS | EPSG |
|---|---|---|
| Datum de referência / grade / troca de dados | SIRGAS 2000 geográfico | `EPSG:4674` |
| Mapa e cálculo de área — MT oeste | SIRGAS 2000 / UTM 21S | `EPSG:31981` |
| Mapa e cálculo de área — MT leste | SIRGAS 2000 / UTM 22S | `EPSG:31982` |

Regras:

- O campo `crs` do `MapSpec` é **sempre um EPSG projetado** (`31981` ou `31982`), escolhido pelo
  centroide do imóvel. **Nunca hardcodar a zona:** Mato Grosso é cortado pelo meridiano 54°W e tem
  imóveis nas duas zonas. Esse foi um bug real no projeto anterior.
- **Área se calcula sempre em CRS projetado.** Em coordenadas geográficas, `area` é um número em
  graus quadrados — sem significado físico e com erro que cresce com a latitude. O procedimento é:
  reprojetar para a UTM da zona, calcular em m², dividir por 10.000 para hectares, e só então
  formatar em pt-BR (`1.234,56`).
- O `datum` impresso no bloco de metadados tem de concordar com `crs`: `EPSG:31982` implica
  `SIRGAS 2000 UTM 22S`. Divergência entre os dois é falha `H03`.
- Imóvel que cruza as duas zonas: escolher a zona da maior parte da área e registrar aviso. Não é
  caso comum, mas acontece.

## Escalas permitidas

A escala é escolhida de uma lista de valores "bonitos", nunca livre — escala quebrada
(`1:23.847`) denuncia mapa gerado por máquina:

```
5.000 · 7.500 · 10.000 · 15.000 · 20.000 · 22.000 · 25.000 · 30.000 ·
40.000 · 50.000 · 75.000 · 100.000 · 150.000 · 200.000
```

A preferência do cliente é **~1:22.000**, que é a escala do PDF-modelo principal. O algoritmo:
calcular a escala mínima que cabe o extent do imóvel com folga, subir para o próximo valor da
lista e, se o resultado ficar entre 20.000 e 25.000, preferir 22.000. O projeto anterior pulava de
15.000 direto para 25.000 e nunca acertava o modelo — a inclusão de 20k/22k/30k/40k na lista foi
correção explícita.

`escala: "auto"` é aceito no `MapSpec` e resolvido pelo agente no momento da geração; o valor
efetivamente aplicado volta no relatório de validação.

## Variações por tipo de mapa

| Mapa | `mxd_template` | Camadas típicas | O que muda no layout |
|---|---|---|---|
| Dinâmica de uso do solo | `Dinamica_2026.mxd` | lotes + AVN + AC + AUAS | nenhuma variação — é o modelo de referência |
| Uso Consolidado | `Uso_Consolidado.mxd` | lotes + AC (+ uso consolidado do SIMCAR) | tabela com colunas de área consolidada; fundo de satélite de 2008 |
| Tipologia Vegetal | `Tipologia_Vegetal.mxd` | lotes + tipologia vegetal | `inset_tipologia: true`; fundo temático (WMS SEMA) em vez de satélite |
| Embargos IBAMA | `Embargos_IBAMA.mxd` | lotes + embargos IBAMA (+ embargos SIGA) | legenda com os embargos; tabela por auto/área embargada |
| Alertas MapBiomas | `Alertas_MapBiomas.mxd` | lotes + alertas MapBiomas | tabela por alerta com data de detecção |

Todos usam `layout_template: "dinamica_a4_paisagem"` — a geometria de página é a mesma para a série
inteira; o que muda é o `.mxd` de origem, as camadas e o conteúdo da tabela. Os nomes de
`mxd_template` acima são a proposta a ser selada no manifesto de `shared/templates/`; só valem
depois que o arquivo real existir (invariante do [`01`](01-arquitetura.md)).

## Checklist de conformidade

O validador roda **no agente local**, depois de exportar o PDF, e o relatório sobe como
`validacao.json` (artefato do job, ver [`01-arquitetura.md`](01-arquitetura.md)). Checks `HARD`
**bloqueiam a entrega**: o job termina em `failed` e a UI mostra o que falhou. Checks `SOFT`
apenas avisam e o job conclui em `succeeded` com ressalvas.

| ID | Descrição | Verificação automática | Severidade |
|---|---|---|---|
| `H01` | Nenhuma fonte de dados quebrada no `.mxd` | `ListBrokenDataSources` no `.mxd` salvo deve retornar lista vazia | HARD |
| `H02` | Título presente e igual ao do `MapSpec` | elemento de texto do título existe e seu conteúdo casa com `titulo` | HARD |
| `H03` | Datum/CRS corretos e coerentes | CRS do data frame ∈ {`31981`, `31982`} e `metadados_imagem.datum` descreve a mesma zona | HARD |
| `H04` | Escala na lista permitida | escala do data frame ∈ lista de escalas (tolerância 0) | HARD |
| `H05` | Todas as camadas do `MapSpec` presentes no mapa | conjunto de camadas do `.mxd` ⊇ ids de `camadas[]` | HARD |
| `H06` | Legenda com todas as camadas visíveis | itens da legenda ⊇ camadas visíveis com `legenda` definida | HARD |
| `H07` | Página A4 paisagem | dimensões da página = 297×210 mm, orientação paisagem | HARD |
| `H08` | PDF abre e não está em branco | arquivo abre, tem 1 página, e o `preview.png` tem cobertura de pixels não-brancos acima do limiar | HARD |
| `H09` | Elementos obrigatórios ligados estão presentes | para cada chave `true` em `elementos_layout`, existe o elemento correspondente no layout | HARD |
| `H10` | Bloco de metadados completo quando ligado | as 4 chaves de `metadados_imagem` preenchidas e não vazias | HARD |
| `H11` | Linha `TOTAL` presente quando pedida | `tabela.total == true` implica última linha com primeira célula `TOTAL` em negrito | HARD |
| `H12` | `.mxd` reabre | reabrir o `.mxd` salvo e listar camadas sem exceção | HARD |
| `S01` | Rótulo de lote truncado | largura do texto renderizado excede a caixa do polígono no `preview.png` | SOFT |
| `S02` | Sobreposição de legenda com tabela | interseção dos retângulos de legenda e tabela > 2% da área de qualquer um deles | SOFT |
| `S03` | Minimapa sem município identificado | nenhuma feição de município marcada em laranja (fallback de tiles ativado) | SOFT |
| `S04` | Escala fora da preferência do cliente | escala resolvida ≠ 22.000 quando o extent permitiria | SOFT |
| `S05` | Basemap em fallback | `basemap` pedido era Planet e o agente usou Esri World Imagery | SOFT |
| `S06` | Hachura sem equivalente no ArcMap | camada com `hachura` sem símbolo correspondente na biblioteca de `.lyr` | SOFT |
| `S07` | Imóvel cortado pelo quadro | bbox do `area_base` não cabe inteiro no extent do data frame | SOFT |
| `S08` | Grade com poucos rótulos | menos de 2 rótulos em algum eixo | SOFT |
| `S09` | Camada externa vazia após recorte | WFS respondeu 0 feições no bbox e a camada entrou vazia na legenda | SOFT |

Duas regras de processo em cima da tabela:

- O mesmo checklist roda em **modo predição**, sobre o `MapSpec`, antes de criar o job (é o que a
  tool `validar_mapspec` faz, ver [`07-ia-e-tools.md`](07-ia-e-tools.md)). Nem todo check é
  predizível sem render — `H01`, `H08` e `H12` só existem depois do arquivo. Predizer o que é
  predizível economiza um job inteiro por erro evitado.
- `strict_mxd` (campo do job no [`01`](01-arquitetura.md)) transforma "não foi possível gerar o
  `.mxd`" em falha `HARD`. Sem ele, o sistema entrega o PDF do renderizador nativo e avisa.

## Pendências e decisões abertas

| # | Pendência | Por que ainda não decidido |
|---|---|---|
| P1 | Hachuras `xxx` e `///` não têm equivalente direto e programável em `arcpy` do ArcMap | resolver com biblioteca de `.lyr` versionada em `shared/templates/`; depende de ter os arquivos reais do cliente ([`05`](05-motor-mxd-pdf.md)) |
| P2 | Tabela com mais de 8 linhas | o [`05`](05-motor-mxd-pdf.md) já decidiu a tabela como grade de células nomeadas no template (com fallback de imagem); o teto de linhas do template é o resíduo, e afeta `H11` |
| P3 | Enum de `basemap.tipo` | precisa ser selado no `mapspec.schema.json`; candidatos: Esri World Imagery, Planet mensal, mosaico SEMA (`Mosaicos:MOSAICO_SPOT_SEPLAN` / Landsat — ver [13](13-wfs-e-servicos-geo.md)), WMS temático, nenhum |
| P4 | Limiar exato do `H08` (cobertura de pixels) | precisa de amostra de PDFs válidos e inválidos para calibrar sem falso positivo |
| P5 | Tolerância do `S02` (sobreposição) | 2% é chute inicial; calibrar contra os 26 PDFs-modelo |
| P6 | Legenda sem chave de visibilidade em `elementos_layout` | avaliar se algum mapa da série dispensa legenda; se sim, exige alterar o contrato no [`01`](01-arquitetura.md) |
| P7 | Fonte tipográfica oficial | os PDFs-modelo precisam ser inspecionados para extrair a família de fonte; hoje só o tamanho (20–22 no título) é conhecido |
| P8 | Mapa que cruza UTM 21S/22S | regra da "maior área" é razoável mas não foi validada com o cliente |
