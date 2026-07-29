# Análise de área — a série de 20 mapas em PDF nativo

Rodada de **2026-07-29**. O que esta rodada entregou: a série completa do padrão
IMAP/Harmonia sai de um shapefile só, com dado real, sem ArcMap e sem ninguém
digitar nada sobre o imóvel — e cada PDF é medido contra o modelo do acervo.

Resultado na propriedade de teste (**Fazenda Aruanã I**, Ribeirão Cascalheira/MT):
**20 de 20 mapas gerados**, **19 aprovados na anatomia** contra os PDFs-modelo,
1 reprovação conhecida e explicada (§5).

Contrato da meta: [`planos/GOAL_analise_de_area.md`](../planos/GOAL_analise_de_area.md).

---

## 1. O que o sistema descobre sozinho

Entrada: `SHP/ATP.shp`. Nada mais.

| Descoberta | Como | Resultado na Aruanã |
|---|---|---|
| Município | ponto-em-polígono contra `shared/bases/ibge/lml_municipio_a.shp` — **sem rede** | Ribeirão Cascalheira (IBGE 5107180) |
| Registro no CAR | maior IoU entre o polígono e a camada `car_atp` da SEMA | `MT117446/2017`, IoU **0,9995** |
| Nome do imóvel | `NOMEPROPRIEDADE` do CAR, recapitalizado | "Fazenda Aruanã I" (de `FAZENDA ARUANÃ I`) |
| Área e módulos fiscais | atributos do mesmo registro | 7.406,55 ha · 92,58 MF |
| Camadas temáticas | 18 camadas do catálogo resolvidas no extent | 20 shapefiles em `SHP/` |

**IoU e não "interseção"**: um imóvel pequeno dentro de um CAR gigante tem
cobertura alta e identidade errada. Área parecida **e** posição parecida é o que
caracteriza o mesmo imóvel.

**LGPD não é detalhe aqui.** A camada do CAR traz `NOMESPROPRIETARIOS` e a de
embargos traz `CPF_CNPJ`. `analise/identidade.py` tem uma lista branca de campos
(`CAMPOS_CAR`) e nada fora dela é lido — nem para log, nem para relatório.

## 2. Como rodar

```python
from pathlib import Path
from mapasfacil_nucleo.fsguard import WorkspaceGuard
from mapasfacil_nucleo.analise.executar import executar

guard = WorkspaceGuard("/caminho/do/projeto")   # com SHP/ATP.shp dentro
relatorio = executar(
    guard=guard,
    modelos=Path("Testes/01_analise_04_Julio/Modelo/Mapas"),  # opcional: valida anatomia
)
```

Saída em `Mapas/`: os 20 PDFs, o compilado `Analise_de_area.pdf` (20 páginas, na
ordem do `Mapas_unidos.pdf` do escritório) e `analise_de_area_relatorio.json`.

`executar(apenas=("dinamica_2026",))` roda um mapa só, e
`preparar_camadas=False` reusa o que já está no disco — é o loop de ajuste, sem
repetir 90 s de rede a cada tentativa.

## 3. Peças novas

| Arquivo | Papel |
|---|---|
| `analise/identidade.py` | município + CAR a partir do polígono, com lista branca de campos |
| `analise/preparar.py` | 18 camadas do catálogo + 3 derivadas → shapefiles locais com nome canônico |
| `analise/serie.py` | as 20 receitas: título, camadas, metadados e legenda de cada modelo |
| `analise/executar.py` | orquestra, compila o PDF único e mede a anatomia mapa a mapa |
| `ferramentas/medir_modelos_serie.py` | mede os modelos → `shared/padrao-imap/anatomia_serie.json` |
| `ferramentas/amostrar_cores_modelo.py` | amostra as cores oficiais dos quadradinhos de legenda |

### Por que camada temática vira shapefile local

Materializar antes, uma vez, resolve três coisas: o motor nativo, os
quantitativos e o caminho `.mxd` já sabem ler `local.*`; o perímetro aparece nos
20 mapas e é resolvido uma vez só; e camada que se pinta **por classe**
(Floresta × Cerrado) vira um shapefile por classe, com estilo e item de legenda
próprios, sem o motor precisar entender atributo.

### As três camadas derivadas

Nenhum serviço publica estas, e os modelos têm o item na legenda:

| Camada | Conta | Origem da regra |
|---|---|---|
| `AREA_PRECISA_DLA` | `AUAS − DLA` | desmate após 2008 ainda sem declaração de limpeza |
| `UC_AMORTECIMENTO` | anel de 3 km da UC | CONAMA 428/2010 |
| `TI_AMORTECIMENTO` | anel de 10 km da TI | **aproximação declarada** — não há norma equivalente |

## 4. Anatomia: o layout vem do modelo, um por um

Não existe "o" layout paisagem. Medindo os 20 modelos, a base do quadro do mapa
vai de **151,4 mm** (Terras Indígenas, que abre espaço para uma legenda alta) a
**168,9 mm** (Tipologia) — 17 mm de diferença, quase três vezes a tolerância de
6 mm. Um retângulo médio erraria os dois.

Por isso `shared/padrao-imap/anatomia_serie.json` guarda, por mapa: página,
quadro, caixa de título, âncora e tamanho de fonte do bloco de metadados e da
legenda, e o título do bloco. `perfil_pagina.por_template("serie_<id>")` monta o
perfil a partir daí; `nativo.py` usa esse perfil quando o template é da série.

Regerar (exige o acervo em `Testes/`, gitignored):

```bash
python3 ferramentas/medir_modelos_serie.py
```

## 5. Estado da validação

```
19/20 anatomia verde · 20/20 gerados · 355 s a série inteira
```

A única reprovação é **TCR (A02, caixa de título)**, e a causa é dado, não
layout: o modelo escreve "Termo de Recuperação de / Área 4089/2023" em duas
linhas porque tem o número do termo. Os pontos de TAC/TCR não existem em WFS
público nenhum — é dado do escritório (lacuna **C4** do GOAL). Sem o número, o
título é uma linha mais curta e a caixa não bate. **Some quando o usuário
informar o TCR**, e é o caso legítimo de `chat.pergunta`.

## 6. Bugs reais encontrados e corrigidos nesta rodada

1. **Vazio de soluço virava mapa em branco pelo TTL inteiro.** O REST do IBAMA
   devolveu `features: []` num soluço; isso foi cacheado e todo mapa seguinte
   saiu sem embargo, sem erro nenhum para investigar. Agora resposta vazia
   **não entra no cache**, e a preparação repergunta ao vivo antes de aceitar
   "não tem nada aqui".
2. **O validador de MapSpec tinha uma cópia velha da paleta.** `NU-211` reprovava
   `limite_estadual` porque `mapspec/validar.py` guardava 9 nomes de estilo de
   2026-07-25. Agora ele lê `motores/estilos.py`, que é a fonte única.
3. **O limite municipal pintava o mapa inteiro de laranja.** A cor amostrada do
   modelo é o preenchimento do **quadradinho da legenda**; no mapa esses limites
   são só linha. Daí `cor_preenchimento_legenda`.
4. **A escala saía 1:300.000 em vez de 1:93.000.** O motor enquadra pelo id
   `perimetro`; com outro id ele usava o bbox de *todas* as camadas — incluindo
   o limite estadual recortado no extent.
5. **A fonte estava errada.** O ArcMap compõe os modelos em Arial; o motor
   desenhava em DejaVu Sans, mais larga, e o bloco de metadados dos paisagem
   saía ~9 mm mais largo — o bastante para reprovar 5 mapas. Agora
   `Arial → Liberation Sans → Nimbus Sans`, e as larguras de texto são medidas
   com `TextPath`, não estimadas por "largura média de caractere".
6. **A âncora do bloco de metadados era a borda esquerda.** Mas o bloco é
   **centralizado** nos modelos (o `x0` das próprias linhas do modelo varia
   14 mm entre si): comparar a esquerda media comprimento de texto, não posição.
   `anatomia.comparar` passou a comparar o centro nesse bloco — a legenda, que é
   alinhada à esquerda, continua ancorada em `x0`.
7. **Mosaico furado.** A SEMA devolve 200 com a cena cheia de buracos brancos.
   O basemap agora mede a fração sem dado e cai para o ano anterior acima de
   12% — vale mais a imagem inteira de outro ano que a do ano certo pela metade.

## 7. Imagem de fundo por ano (lacuna C2, fechada)

Os 43 mosaicos WMS da SEMA (`shared/catalog/mosaicos_sema.json`) viviam num JSON
que ninguém lia: o basemap só conhecia o SPOT 2008. Agora
`basemap.camada_de_mosaico()` aceita o id (`landsat5_2000`) ou só o ano
(`2013`), escolhendo o sensor mais nítido do ano, e **declara** quando o ano
pedido não existe e caiu no anterior — o metadado do mapa escreve a data da
imagem que entrou, nunca a que se pediu.

| Mapa | Modelo pedia | Entrou na Aruanã |
|---|---|---|
| Dinâmica 2000 | Landsat 5/TM 2000 | `LANDSAT_5_2000` |
| Dinâmica 2008 (Landsat) | Landsat 5/TM 2008 | `LANDSAT_5_2008` |
| Dinâmica 2008 (SPOT) | SPOT 2007-2010 | `MOSAICO_SPOT_SEPLAN` |
| Dinâmica 2013 | "Landsat 5/TM" | `LANDSAT_8_2013` — o Landsat 5 já não operava (§4.1 do GOAL) |
| Dinâmica 2017/2019/2023 | Planet | `SENTINEL_2_<ano>` |
| Dinâmica 2026 e temáticos | Planet 2025/2026 | `SENTINEL_2_2024`/`2023` — a SEMA para em 2024 |

Planet continua disponível (`planet_api_key` no cofre, `basemap_planet.py`) para
quem quiser paridade de imagem com o modelo; a série usa SEMA por padrão porque
não gasta quota.

## 8. O que falta

| # | Item | Onde |
|---|---|---|
| 1 | Card **"Análise de área"** na galeria + progresso rico no front | `shared/galeria/modelos.json`, `galeria/estado.py`, `app/src/` |
| 2 | Destravar a galeria para saída nativa (hoje modelo sem `.mxd` nasce `indisponivel`) | `galeria/estado.py` |
| 3 | Groq Vision no backend (a chave ainda não existe no cofre) | `validacao/`, `agente/provisao.py` |
| 4 | Quantitativos por classe no mapa da tabela | `quantitativos/` |
| 5 | TCR e pontos de TAC via `chat.pergunta` | `agente/tools.py` |
| 6 | Os 20 `.mxd` da série no Windows | §11 do GOAL (Fase W) |

## 9. Testes

```bash
cd Fase_1_Desktop/nucleo && .venv/bin/python -m pytest -q
python3 ferramentas/validar_goal_analise.py
```

`tests/test_analise_serie.py` cobre receitas, perfis medidos, mosaico por ano e
o critério de anatomia; `tests/test_analise_preparar.py` cobre as derivadas e a
regra de não cachear vazio. Nenhum dos dois vai à rede.
