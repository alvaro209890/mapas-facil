# META / GOAL — Análise de área (Mapas Fácil)

Especificação **fechada e validada contra o disco** em 2026-07-29. Idioma de trabalho e UI:
**português BR**. Este arquivo é o contrato de uma meta: cole-o inteiro num `/goal`, ou aponte
o agente executor para ele.

> **Regra de precedência.** Este documento **não** redefine nada de
> [`01-padrao-imap-harmonia.md`](01-padrao-imap-harmonia.md) (visual) nem de
> [`02-mapspec-contrato.md`](02-mapspec-contrato.md) (formato de dado). Onde divergir, os comuns
> ganham e a divergência se corrige no mesmo commit — igual a qualquer plano de fase
> ([`README.md`](README.md)).

| | |
|---|---|
| Estado do documento | **completo** — inventário, matriz de imagem, lacunas e plano Windows fechados |
| Estado da implementação | **série em PDF nativo entregue** (2026-07-29): 20/20 mapas gerados na Aruanã, 19/20 aprovados na anatomia. Falta o card na galeria, o progresso no front e a Fase W. Detalhe: [`docs/analise-de-area-serie.md`](../docs/analise-de-area-serie.md) |
| Validador | `python3 ferramentas/validar_goal_analise.py` (checa este arquivo contra o disco) |
| Última validação | 2026-07-29 — ver [§15](#15-registro-de-validação) |

---

## 1. Objetivo

Validar de ponta a ponta o Mapas Fácil com a ATP **Aruanã** (`Aruana_l_MAT_4242`) e entregar a
funcionalidade de galeria **"Análise de área"**: um único card que gera a **série completa** de
mapas, com PDFs **visualmente perfeitos** em relação aos modelos do Julio — tamanho, cores,
layout, minimapa, título, metadados — **sem bug nenhum**, nem mínimo.

A IA executora deve **programar, testar como usuário, corrigir e retestar** até fechar.
Não entregar só plano.

## 2. Propriedade de teste — conferida

| Item | Valor | Como foi conferido |
|---|---|---|
| Polígono | `Testes/01_analise_04_Julio/ATP_Teste/Aruana_l_MAT_4242.shp` | 1 feição, `pyshp` |
| CRS | **EPSG:31982** (SIRGAS 2000 / UTM 22S) | `.prj` + `ogrinfo` |
| Área | **7.408,8844 ha** | shoelace sobre a geometria (o campo `AREA` do `.dbf` vem **nulo**) |
| BBox UTM | `426607,25 · 8542455,88` → `436664,02 · 8563331,83` | cabeçalho do `.shp` |
| BBox geográfico | `-51,6773 · -13,1837` → `-51,5840 · -12,9951` | reprojeção `pyproj` para EPSG:4674 |
| Município | **Ribeirão Cascalheira / MT** (IBGE `5107180`) | ponto-em-polígono do centroide contra `shared/bases/ibge/lml_municipio_mt.shp` |
| Atributos | só `Id` e `AREA` (nulo) | **nenhum metadado do imóvel vem do shapefile** |
| Entrada local | **só o polígono ATP** — o resto o sistema puxa (requerimento CAR, CAR digital, WFS SEMA, SIGEF, portal recibo SIMCAR/SEMA, catálogo interno) | — |
| Expectativa | se algo falhar por SEMA/rede, **avisa no chat e segue** os demais | — |

> **Atenção — o gabarito é de outro imóvel.** Os PDFs/MXD de `Modelo/` são da **Fazenda
> Harmonia, Vila Rica/MT** (CAR MT102042/2017, 3.823,9033 ha). A Aruanã é outro imóvel, outro
> município e **quase o dobro da área**. Logo: o gabarito vale para **anatomia, cores, blocos e
> textos**, nunca para diff raster pixel a pixel — é a mesma lição registrada em
> [`docs/motor-nativo-harmonia.md §1`](../docs/motor-nativo-harmonia.md). O critério aqui é
> **anatomia em milímetros**, não similaridade de imagem.

## 3. A série — inventário 1:1 PDF ↔ MXD

`Modelo/Mapas/` tem **21 PDFs**: 20 mapas individuais + `Mapas_unidos.pdf`, que é a
**compilação de 20 páginas** na ordem de entrega do escritório. `Modelo/MXD/` tem **24 `.mxd`**:
os 20 pares + 4 que não entram na série (§3.2). O pareamento abaixo foi conferido página a
página por similaridade de texto (Jaccard 1,00 em todas as 20).

### 3.1 Ordem oficial da série (= ordem das páginas de `Mapas_unidos.pdf`)

| # | Mapa (PDF) | MXD par | Página | Tema | Fonte declarada | Imagem de fundo declarada |
|---|---|---|---|---|---|---|
| 1 | `Alertas_MAPBIOMAS_2.pdf` | `Alertas_MAPBIOMAS_2.mxd` | paisagem 297×210 | Alertas MapBiomas | WMS MapBiomas | PLANET out/2025 |
| 2 | `Alertas_PRODES_VF.pdf` | `Alertas_PRODES_VF.mxd` | paisagem | Alertas PRODES | TerraBrasilis/INPE | PLANET out/2025 |
| 3 | `DLA.pdf` | `DLA.mxd` | retrato 210×297 | Declaração de Limpeza de Área | WMS-SEMA | PLANET mar/2026 |
| 4 | `Unidade_de_Conservação.pdf` | `Unidade_de_Conservação.mxd` | paisagem | UC + zona de amortecimento | SEMA | PLANET out/2025 |
| 5 | `Tipologia.pdf` | `Tipologia.mxd` | paisagem | Tipologia vegetal (Floresta/Cerrado) | Radam Brasil via WMS SEMA | — (não declara satélite) |
| 6 | `Terras_Indigenas.pdf` | `Terras_Indigenas.mxd` | paisagem | TI + amortecimento | WMS FUNAI | — no PDF; PLANET fev/2026 no MXD |
| 7 | `TCR.pdf` | `TCR.mxd` | retrato | Termo de Recuperação 4089/2023 + APP degradada | WMS-SEMA + dado do escritório | PLANET mar/2026 |
| 8 | `PEF.pdf` | `PEF.mxd` | retrato | Desmate licenciado | `Geoportal:AUTORIZACAO_DESMATE_SEMA` | PLANET mar/2026 |
| 9 | `Embargos_SEMA_SIGA_Poligono.pdf` | `Embargos_SEMA_SIGA_Poligono.mxd` | paisagem | Embargos SEMA + SIGA polígono | WMS-SEMA | PLANET out/2025 |
| 10 | `Embargos_IBAMA.pdf` | `Embargos_IBAMA.mxd` | paisagem | Embargos IBAMA | WMS SISCOM/IBAMA | PLANET out/2025 |
| 11 | `Areas_Cultivaveis_VF.pdf` | `Areas_Cultivaveis_VF.mxd` | retrato | Cultivável consolidada / derivada de desmate / que precisará de DLA / AVN | WMS-SEMA + derivação | PLANET mar/2026 |
| 12 | `Dinamica_2026_quantitativos.pdf` | `Dinamica_2026_quantitativos.mxd` | retrato | AUAS/AC/AVN **+ tabela** | WMS-SEMA | PLANET mar/2026 |
| 13 | `Dinamica_2026.pdf` | `Dinamica_2026.mxd` | retrato | dinâmica do ano | — | PLANET mar/2026 |
| 14 | `Dinamica_2023.pdf` | `Dinamica_2023.mxd` | retrato | dinâmica do ano | — | PLANET out/2023 |
| 15 | `Dinamica_2019.pdf` | `Dinamica_2019.mxd` | retrato | dinâmica do ano | — | PLANET mai/2019 |
| 16 | `Dinamica_2017.pdf` | `Dinamica_2017.mxd` | retrato | dinâmica do ano | — | PLANET out/2017 |
| 17 | `Dinamica_2013.pdf` | `Dinamica_2013.mxd` | retrato | dinâmica do ano | WMS-SEMA | "LANDSAT 5/TM 2013" (**ver §4.1**) |
| 18 | `Dinamica_2008_SPOT.pdf` | `Dinamica_2008_SPOT.mxd` | retrato | marco do Código Florestal | WMS-SEMA | SPOT 2007-2010 |
| 19 | `Dinamica_2008_LANDSAT.pdf` | `Dinamica_2008_LANDSAT.mxd` | retrato | marco do Código Florestal | WMS-SEMA | LANDSAT 5/TM 2008 |
| 20 | `Dinamica_2000.pdf` | `Dinamica_2000.mxd` | retrato | dinâmica do ano | WMS-SEMA | LANDSAT 5/TM 2000 |

**Contagem de perfis:** 12 retrato (210×297 mm) e 8 paisagem (297×210 mm). Os dois perfis estão
exercitados desde 2026-07-29 — e o layout de cada mapa vem **medido do seu próprio modelo**
(`shared/padrao-imap/anatomia_serie.json`), porque entre os paisagem a base do quadro varia
17 mm de um mapa para outro.

**Escala:** os 12 retratos declaram `Escala: 1:60.000` no bloco de metadados; os paisagem não
declaram escala. Na Aruanã (7.408 ha, ~10 km × 21 km) 1:60.000 **não cabe** em A4 retrato —
a escala tem de ser recalculada por bbox e o texto do metadado seguir o valor real (é o
comportamento de `escala_padrao: "auto"` da galeria).

### 3.2 MXDs que **não** entram na série

| MXD | Por quê |
|---|---|
| `Alertas_PRODES.mxd` | versão anterior de `Alertas_PRODES_VF.mxd` (o `_VF` é o final) |
| `Areas_Cultivaveis.mxd` | idem, anterior a `Areas_Cultivaveis_VF.mxd` |
| `Dinamica_2026_cultivo.mxd` | variação sem PDF correspondente na entrega |
| `Untitled.mxd` | sobra de sessão do ArcMap |

`Modelo/MXD/_chk_texts.py` e `DOCUMENTACAO_MXD_HARMONIA.md` são apoio, não mapa.

### 3.3 Entrega da série

Além dos 20 PDFs individuais, a série produz o equivalente ao `Mapas_unidos.pdf`: **um PDF
único com as 20 páginas na ordem da §3.1**. Ele é parte do produto, não um extra.

## 4. Matriz de imagem de fundo — o que o modelo pede × o que o sistema serve

O texto original desta meta dizia "todos os mapas usam Landsat". **É falso**, e a diferença
muda o plano: só 3 dos 20 usam Landsat/SPOT; **17 usam mosaicos Planet**, que são pagos e cuja
chave (`planet_api_key`) já está no cofre do projeto.

Fontes disponíveis hoje, conferidas em `shared/catalog/mosaicos_sema.json` (43 mosaicos WMS da
SEMA, `authkey` obrigatória) e `shared/catalog/camadas.json` (41 camadas):

| Mapa | Modelo pede | O sistema já tem | Decisão a propor ao usuário |
|---|---|---|---|
| Dinâmica 2000 | LANDSAT 5/TM 2000 | `Mosaicos:LANDSAT_5_2000` | **paridade direta** — nada a decidir |
| Dinâmica 2008 LANDSAT | LANDSAT 5/TM 2008 | `Mosaicos:LANDSAT_5_2008` | **paridade direta** |
| Dinâmica 2008 SPOT | SPOT 2007-2010 | `Mosaicos:MOSAICO_SPOT_SEPLAN` (2,5 m) | **paridade direta**; é o marco do Código Florestal |
| Dinâmica 2013 | "LANDSAT 5/TM 2013" | `Mosaicos:LANDSAT_8_2013` | **§4.1** — o metadado do modelo está errado |
| Dinâmica 2017 | PLANET out/2017 | Planet (chave no cofre) · `LANDSAT_8_2017` · `SENTINEL_2_2017` | Planet para paridade; Sentinel-2 se a quota preocupar |
| Dinâmica 2019 | PLANET mai/2019 | Planet · `SENTINEL_2_2019` | idem |
| Dinâmica 2023 | PLANET out/2023 | Planet · `SENTINEL_2_2023` | idem |
| Dinâmica 2026 (+ quantitativos, DLA, PEF, TCR, Áreas Cultiváveis) | PLANET mar/2026 | Planet `global_monthly_2026_03_mosaic` · SEMA **para em 2024** | Planet, **ou** cena Landsat 9/Sentinel-2 via STAC (§4.2) |
| Alertas MAPBIOMAS / PRODES / Embargos SEMA / Embargos IBAMA / UC | PLANET out/2025 | Planet `global_monthly_2025_10_mosaic` · SEMA `SENTINEL_2_2024` | idem |
| Tipologia | sem satélite declarado | vetor Radam (`vegetacao_radam`) | nada a decidir |
| Terras Indígenas | sem satélite no PDF | `terras_indigenas_funai` | nada a decidir |

### 4.1 O erro herdado do modelo (Dinâmica 2013)

O metadado do `Dinamica_2013.pdf` diz **LANDSAT 5/TM**, mas o Landsat 5 foi desativado em 2013 e
a SEMA só publica `LANDSAT_8_2013` para aquele ano. Copiar o texto do modelo propaga um erro
factual. **Decisão da meta:** gerar com `Mosaicos:LANDSAT_8_2013` e escrever
`Satélite/Sensor: LANDSAT 8/OLI` no metadado — perguntando antes ao usuário, via
`chat.pergunta`, porque diverge do gabarito (é exatamente o caso previsto no critério 2 da §7).

### 4.2 Quando o pipeline STAC (estilo GeoForest) é realmente necessário

Só para o que **nem SEMA nem Planet** entregam bem: cena completa, sem recorte, para anos que a
SEMA não cobre (2025/2026) quando não se quiser gastar quota Planet. Receita a copiar de
`/home/acer/Documentos/GeoForest-IA` (STAC USGS/Planetary Computer para Landsat, STAC INPE para
CBERS, GDAL para composição RGB/pansharpen), rodando **neste PC / no Mapas Fácil**, sem depender
do servidor GeoForest.

Regras invioláveis do acervo de imagens:

- cena **completa**, nunca recortada na ATP no momento da geração;
- armazenamento em **acervo compartilhado do sistema**, reusável entre usuários e jobs;
- se a imagem já existe no acervo, **não regenerar** (chave: sensor + ano/mês + tile/bbox).

## 5. Camadas — o que o catálogo resolve e o que falta

O catálogo tem **41 camadas com cliente em runtime** (`shared/catalog/camadas.json`,
`nucleo/.../camadas/`). Mapeando a série contra ele:

**Já resolvido:** `car_atp`, `car_avn`, `car_auas`, `car_app`, `car_appd`, `car_arl`,
`area_consolidada_simcar`, `simcar_*`, `embargos_sema`, `embargos_siga`, `embargos_ibama`,
`embargos_ibama_siscom`, `terras_indigenas_funai`, `terras_indigenas_sema`,
`unidades_conservacao`, `alertas_mapbiomas`, `prodes_inpe`, `prodes_yearly`, `tipologia_sema`,
`vegetacao_radam`, `dla`, `lim_municipios_mt`, `sigef_particular_mt`, `mosaico_spot_2008`.

**Falta (tarefa da meta):**

| # | O que faltava | Estado em 2026-07-29 |
|---|---|---|
| C1 | `autorizacao_desmate_sema` (mapa PEF) — existia no WFS vivo e faltava no catálogo | **fechada** — no catálogo (agora 43 camadas), respondendo ao vivo |
| C2 | Mosaicos SEMA por ano como basemap selecionável | **fechada** — `basemap.camada_de_mosaico()` aceita id ou ano, escolhe o sensor mais nítido, declara ano aproximado e recusa cena furada |
| C3 | Camadas derivadas ("que precisará de DLA", amortecimentos) | **fechada** — `analise/preparar.DERIVADAS`: `AUAS − DLA`, anel de 3 km da UC, anel de 10 km da TI (aproximação declarada) |
| C4 | TCR / pontos de TAC | **aberta** — não existe em WFS público; é dado do escritório. É a única reprovação de anatomia da série (TCR, A02) |
| C5 | Compilação da série num PDF único | **fechada** — `Mapas/Analise_de_area.pdf`, 20 páginas na ordem da §3.1 |

**AP-04 continua valendo:** nada de inventar camada fora do catálogo/MANIFEST. Cada item acima
entra no catálogo **antes** de ser usado por um mapa.

## 6. Produto na galeria

- Novo card: **"Análise de área"**, `modelo_id: analise_de_area`.
- Comportamento **(A)**: um clique gera a **série inteira** (20 mapas + compilado).
- Progresso no front bonito e vivo, estilo Claude/Codex/Cursor — o usuário vê o passo corrente
  (buscar CAR, resolver camada X, baixar mosaico ano Y, montar Tipologia, validar PDF…).
  Amarrado a evento real (`job.progresso`, `job.artefato_parcial`) — **AP-07** proíbe spinner
  desconectado.
- Ordem de execução: a IA decide; a regra é **priorizar o que já tem dado** e enfileirar o que
  depende de imagem/fonte externa. A **ordem de entrega** no PDF compilado é fixa (§3.1).
- Falha isolada (SEMA fora, mosaico 500) **não derruba a série**: avisa no chat, marca o mapa
  como pendente e segue.

### 6.1 O card não pode depender de `.mxd`

`galeria/estado.py` hoje devolve `indisponivel` para qualquer modelo cujo template `.mxd` esteja
`a_preparar` — e 4 dos 5 modelos estão nesse estado. Como esta meta entrega **PDF nativo**,
o gate tem de considerar a saída pedida: PDF/PNG/XLSX pelo motor nativo **não** exigem template
ArcMap; só `mxd` exige. Sem isso, o card "Análise de área" nasce morto.

## 7. Critério de qualidade do PDF

1. Seguir os PDFs-modelo: anatomia, tamanho de página, cores/estilos oficiais, título, minimapa,
   metadados, moldura/grade, legenda, logo, perímetro, escala/norte — **zero bugs**.
2. Se precisar desviar do modelo (ano, camada, basemap, texto de metadado — §4.1), a IA
   **propõe antes**, com opções, e só aplica com confirmação.
3. Validação visual obrigatória, em três camadas:
   - **anatomia em milímetros** (`validacao/anatomia.py`) contra o PDF-modelo correspondente —
     é o critério que fecha em qualquer máquina, hoje 6/6 no retrato;
   - **Groq Vision** no backend, comparando saída × modelo (§14 — a chave **ainda não existe**);
   - a própria IA executora olhando os pares lado a lado (`ferramentas/paridade_nativa.py` já
     escreve `modelo.png`, `gerado.png`, `diff_mascara.png`, `lado_a_lado.png`).
4. Motor de saída nesta meta: **PDF nativo perfeito é prioridade**. O caminho MXD/ArcMap fica
   documentado (§11) e **não bloqueia** a meta se o ArcPy não rodar neste Linux.

## 8. Autonomia de dados

- Com só o polígono ATP, descobrir sozinha: município (já funciona — ponto-em-polígono contra a
  base IBGE do repo), CAR, camadas WFS/WMS, recibos, tipologias, embargos.
- Implementar no fluxo do agente/tools, para **qualquer imóvel futuro**, não só a Aruanã.
- Só pedir ao usuário o que **realmente** não dá para obter (hoje: TCR — C4; e a chave Groq).
- UX do pedido: **chips clicáveis + caixa digitável**, reusando `chat.pergunta` /
  `CartaoPergunta` (R27, já pronto).
- Falha transitória de SEMA/rede: mensagem clara no chat, série continua.

## 9. Âncoras do repositório — validadas em 2026-07-29

| Caminho | Existe? | Papel nesta meta |
|---|---|---|
| `AGENT_BRIEF.md` | ✔ | leitura obrigatória antes de codar |
| `docs/motor-nativo-harmonia.md` | ✔ | o que o motor nativo faz e as 6 armadilhas já pagas |
| `docs/estado-2026-07-27.md` | ✔ | causa raiz dos bugs da rodada anterior |
| `docs/handoff-windows-fase1.md` | ✔ | o que já rodou no Windows — **não refazer** |
| `Fase_1_Desktop/GUIA_WINDOWS.md` | ✔ | checklist da máquina Windows |
| `motores/gerar.py` → PDF nativo | ✔ | orquestração do job |
| `motores/{nativo,basemap,blocos,estilos,grade_dms,perfil_pagina}.py` | ✔ | anatomia Harmonia |
| `motores/basemap_planet.py` | ✔ | WMTS Planet (chave no cofre) |
| `motores/{patch_mxd,arcpy_ponte}.py` | ✔ | caminho MXD (T2 copia template; T1 é ponte) |
| `validacao/{anatomia,saida,comparar_pdf,relatorio}.py` | ✔ | as métricas |
| `shared/galeria/modelos.json` | ✔ | **5 cards**; `dinamica_2026_retrato` é o único com template `pronto` — os outros 4 caem em `indisponivel` (§6.1) |
| `shared/templates/MANIFEST.json` | ✔ | 1 `pronto` + 4 `a_preparar` |
| `shared/catalog/{camadas,mosaicos_sema,sema_layers_live,servicos_geo}.json` | ✔ | 41 camadas + 43 mosaicos |
| `shared/bases/ibge/lml_municipio_mt.shp` | ✔ | resolve município sem rede |
| `agente/{tools,prompt}.py` | ✔ | 27 tools reais; galeria primeiro |
| `contas/banco.py`, `conversas/banco.py` | ✔ | conta local + conversas (`Documentos/database/MapasFacil/`) |
| `ferramentas/paridade_nativa.py` | ✔ | loop de comparação modelo × gerado |
| `ferramentas/*_arcpy.py`, `ferramentas/fechar_m*_windows.ps1` | ✔ | tudo que o Windows precisa (§11) |
| `Testes/01_analise_04_Julio/` | ✔ (local) | **gitignored** — 134 MB, dado de proprietário real |
| Chave `groq_api_key` no cofre | ✘ | **pendência bloqueante** da validação por visão (§14) |

**DeepSeek V4 não tem visão na API** (`400 image_url`, P1 fechada em 2026-07-26). Por isso a
visão desta meta é **Groq**, provisionada como as outras chaves.

## 10. Lacunas → tarefas (trilha Linux / motor nativo)

Ordem de dependência, não de calendário (AP-13).

| # | Tarefa | Arquivos | Fecha o quê |
|---|---|---|---|
| L1 | Destravar a galeria para saídas nativas (§6.1) | `galeria/estado.py`, `galeria/montar.py` | **aberta** — card ainda nasceria `indisponivel` |
| L2 | **Perfil paisagem** exercitado e validado | `motores/{nativo,blocos,perfil_pagina}.py` | **fechada** — 8 mapas paisagem, todos verdes; o layout vem medido do modelo de cada um |
| L3 | Basemap por ano/sensor lendo `mosaicos_sema.json` (C2) | `motores/basemap.py` | **fechada** |
| L4 | Acervo compartilhado de rasters | novo módulo em `nucleo/.../acervo/` | **aberta** — hoje o reuso é o cache de camadas + `Mapas/recursos/` do projeto |
| L5 | Camada do PEF (C1) + derivadas (C3) | `shared/catalog/camadas.json`, `analise/preparar.py` | **fechada** |
| L6 | Pipeline da série + compilado (C5) | `analise/{serie,executar}.py` | **fechada** — falta só o card na galeria |
| L7 | Progresso rico no front, amarrado a evento real | `app/src/paineis/`, `progresso.py` | **aberta** — o executor já emite passo a passo por callback |
| L8 | Groq Vision no backend + provisão da chave | `nucleo/.../validacao/`, `agente/provisao.py` | **aberta** — chave ainda não existe no cofre |
| L9 | Testes dedicados + golden de anatomia no CI | `nucleo/tests/` | **fechada** — `test_analise_serie.py` e `test_analise_preparar.py`, 19 testes sem rede |
| L10 | Rodar na Aruanã, validar os 20 PDFs, corrigir, repetir | — | **fechada** — 20/20 gerados, 19/20 anatomia verde |

## 11. Fase W — fechar o que falta **no Windows, sem intervenção humana**

Premissa desta seção: uma máquina Windows com **ArcMap 10.6–10.8 instalado e licenciado**, e
**Claude Code** rodando nela. Nenhum humano clica em nada. O que segue é o roteiro que o agente
executa sozinho, com o que já existe no repositório.

### 11.0 Por que isso é possível

`arcpy.mapping` **não cria** elemento de layout novo — foi o que travou o B1 em 2026-07-27 e
exigiu GUI. Mas a série **não precisa criar nada**: os 20 `.mxd` de `Modelo/MXD/` já têm todos
os elementos (título, metadados, legenda, minimapa, rosa, logo). O caminho autônomo é
**herdar**, nunca criar:

> copiar o `.mxd` do modelo → trocar a fonte de dados → renomear camadas para os nomes
> canônicos → recentrar → exportar.

Tudo isso está na lista do que **funciona** segundo
`Testes/01_analise_04_Julio/Modelo/MXD/DOCUMENTACAO_MXD_HARMONIA.md §5`.

### 11.1 Pré-requisitos verificáveis por script (W0)

| Item | Como o agente confirma | Se faltar |
|---|---|---|
| ArcMap | `Test-Path 'C:\Program Files (x86)\ArcGIS\Desktop10.8\bin\ArcMap.exe'` (fallback por glob, igual `salvar_mxd_gui.ps1`) | aborta com relatório; não tenta instalar |
| ArcPy | `C:\Python27\ArcGIS10.8\python.exe -c "import arcpy"` | idem |
| Licença | `arcpy.CheckProduct("ArcView"/"ArcEditor"/"ArcInfo")` ≠ `Unavailable` | aborta — **licença é a única coisa que o agente não resolve** |
| Python 3.12 + venv do núcleo | `Fase_1_Desktop\nucleo\.venv\Scripts\python.exe -c "import mapasfacil_nucleo"` | cria: `py -3.12 -m venv .venv; pip install -e ".[dev]"` |
| Node + pnpm | `pnpm -v` | `corepack enable` |
| Cofre provisionado (`sema_authkey`, `planet_api_key`) | `python -m mapasfacil_nucleo doctor --json` | segue com basemap degradado e **declara** no `validacao.json` |
| `Testes/01_analise_04_Julio/` presente | `Test-Path` | copia da fonte local; **não** versiona (134 MB, dado de proprietário) |

### 11.2 Roteiro (W1 → W8)

| Passo | O que o agente faz | Ferramenta | Aceite |
|---|---|---|---|
| **W1** | Cria o orquestrador `ferramentas/analise_area_windows.ps1` (contrato na §11.3) e o executa | novo | script existe e roda ponta a ponta |
| **W2** | Detecta ArcMap/ArcPy/licença e escreve `output/w0_ambiente.json` | novo `detectar_arcmap.ps1` | JSON com versão, caminho do Python 2.7 e nível de licença |
| **W3** | **Deriva os 20 templates** dos MXD-modelo: copia para `shared/templates/`, `findAndReplaceWorkspacePaths` para a pasta de dados do job, renomeia elementos para os nomes canônicos, **sem criar nada** | `normalizar_mxd_arcpy.py`, `corrigir_template_b1_arcpy.py`, `conectar_minimapa_ibge_arcpy.py` | `inspecionar_mxd_arcpy.py` reporta `pronto_b1: true` em cada um |
| **W4** | Limpa as chaves embutidas e recalibra offsets | `chaves_mxd.py limpar` → `preparar_sentinelas_arcpy.py` → `registrar_template.py` | `chaves_mxd.py verificar` diz **"Seguro para commit"**; MANIFEST com `status: pronto`, sha256 e offsets |
| **W5** | Gera a série da Aruanã pelos dois motores: T1 (ArcPy) e nativo | `smoke_m2_harmonia.py`, `smoke_m9_harmonia.py`, `motores/gerar.py` | 20 PDFs por motor + o compilado |
| **W6** | Mede: diff raster T1 × modelo, anatomia nativo × modelo, checks HARD/SOFT | `fechar_m9_windows.ps1`, `validacao/{saida,anatomia}.py`, `paridade_nativa.py` | `output/m9_smoke_relatorio.json` + `output/anatomia_serie.json` |
| **W7** | Loop de correção guiado pelo relatório: enquanto houver check vermelho e `tentativas < 5`, ajusta o `.mxd`/parâmetro apontado e remede | — | todos HARD verdes; paridade raster **< 0,3 %** no par T1 × modelo do **mesmo imóvel** |
| **W8** | Publica: `pytest -q`, `pnpm test`, `chaves_mxd.py verificar`, commit **direto no `main`** e push | — | CI verde |

### 11.3 Contrato do orquestrador `ferramentas/analise_area_windows.ps1`

```powershell
# Parâmetros
-Repo        <caminho>   # padrão: pai de ferramentas\
-Dados       <caminho>   # pasta do job (ATP + shapes CAR); padrão: Testes\01_analise_04_Julio\ATP_Teste
-Modelo      <caminho>   # padrão: Testes\01_analise_04_Julio\Modelo
-Tentativas  <int>       # padrão 5 (limite do loop W7)
-SemCommit               # roda tudo e para antes do push
-SemArcpy                # só o motor nativo (útil para máquina sem licença)
```

Invariantes obrigatórias:

- **timeout por chamada ArcPy** (a documentação do acervo registra hang infinito em qualquer
  acesso a dado): `timeout 150` por invocação, e `exit 124` **não** é falha se o arquivo de
  saída existir e abrir — reconferir com `ExportToPDF`;
- **ArcMap fechado** antes de qualquer script (`Stop-Process -Name ArcMap`), e `*.lock` da pasta
  de dados removidos;
- se algum passo precisar de GUI (só a rota de "salvar para o diálogo não voltar"), usar
  `salvar_mxd_gui.ps1` + `fechar_dialogs_gis.ps1` — GUI dirigida por script **continua sendo
  sem humano**;
- **nunca** `arcpy.Project`, `Describe`, `replaceDataSource` ou cursor: reprojeção por
  `ogr2ogr`, bbox lido do cabeçalho do `.shp`, troca de fonte por
  `findAndReplaceWorkspacePaths`;
- todo passo escreve um JSON em `output/` (gitignored) e o exit code do orquestrador é o do
  primeiro passo que falhou;
- **nada de segredo no relatório** — os `.mxd` do acervo trazem `authkey`/`api_key` reais
  embutidos; `chaves_mxd.py limpar` roda **antes** de qualquer commit (AP-03).

### 11.4 Armadilhas já pagas (não redescobrir)

1. Salvar o `.mxd` **move os offsets binários** de extent/escala → recalibrar B2 **sempre**
   depois de qualquer save (`preparar_sentinelas_arcpy.py` + `registrar_template.py`).
2. O extent do template é **sentinela** (valor artificial); parecer "estranho" no ArcMap é o
   esperado — T1/T2 substituem pelo bbox real na geração.
3. `arcpy.mapping` não cria TextElement — se um elemento faltar, **copie outro MXD que o tenha**
   em vez de tentar criar.
4. Há duas legendas no layout Harmonia; a do `MAPA` é a maior. Conferir o vínculo antes de
   renomear.
5. Os `.mxd` de `Modelo/MXD/` apontam para `C:\Users\Usuario\...` e para um `.wms` do ArcCatalog
   de outra máquina — `findAndReplaceWorkspacePaths` resolve; caminho de logo absoluto idem
   (`corrigir_template_b1_arcpy.py --logo`).
6. O logo é uma tela 8334×8334 com 2 % de pixels opacos: recortar pelo bbox do alfa antes de
   encaixar (já resolvido no motor nativo, vale para quem mexer no MXD).

### 11.5 O que **continua** exigindo um humano (e por quê)

Ser honesto aqui é parte da meta:

| Item | Por quê | Mitigação |
|---|---|---|
| **Licença do ArcMap ativada** | ESRI exige ativação de licença; nenhum script contorna isso legalmente. O ZIP `ferramentas/ArcGIS ESRI v10.8 (1)` traz uma pasta `Crack/` — **não usar, não commitar** | usar a licença da casa; o agente só **detecta** e reporta |
| **Chave Groq no cofre** | não existe hoje em `secrets.local.json` (§14) | agente pede via `chat.pergunta` e segue com anatomia + comparação própria até chegar |
| **Dado do TCR** (C4) | não está em nenhum WFS público inventariado | chips + campo livre no chat |

Fora esses três, a Fase W roda sozinha.

## 12. Definição de pronto (DoD) — verificável

| # | Critério | Como se prova |
|---|---|---|
| 1 | Card **"Análise de área"** na galeria; um clique inicia a série | `galeria.listar` devolve `analise_de_area` com status ≠ `indisponivel` |
| 2 | Front mostra progresso rico durante o job | eventos `job.progresso`/`job.artefato_parcial` reais na timeline (AP-07) |
| 3 | Só com o `.shp` da Aruanã, o sistema resolve município/CAR/camadas | log do job sem pergunta ao usuário fora de C4 |
| 4 | Os 20 PDFs + o compilado saem **aprovados** na validação visual | `output/anatomia_serie.json` com todos os checks verdes; parecer Groq favorável por mapa |
| 5 | Imagens geradas ou **reusadas** do acervo | segunda execução não rebaixa nenhuma cena (log do acervo) |
| 6 | Pedidos ao usuário só quando inevitável, com chips + digitável | `chat.pergunta` |
| 7 | Falha de SEMA avisa e não derruba a série | teste com endpoint forçado a erro |
| 8 | Contrato MXD documentado para o Windows | §11 deste arquivo + `docs/handoff-windows-fase1.md` |
| 9 | Teste ponta a ponta como usuário, bugs corrigidos, reteste verde | `pytest -q` + `pnpm test` + roteiro manual no app |

Comandos que fecham a meta:

```bash
python3 ferramentas/validar_goal_analise.py          # este documento × disco
cd Fase_1_Desktop/nucleo && .venv/bin/python -m pytest -q
cd Fase_1_Desktop/app && pnpm test
python3 ferramentas/chaves_mxd.py verificar          # "Seguro para commit"
```

## 13. Fora de escopo

- Escrita no SIMCAR / "Oráculo" GeoForest.
- Parecer jurídico / laudo.
- Fase 2 site.
- Authenticode (M10) / piloto em PC limpo (M11).
- Paridade ArcMap M9 completa **como bloqueio** — a Fase W persegue, mas não trava o PDF nativo.
- Commitar instalador ArcGIS, `Crack/`, dado de proprietário ou segredo.

## 14. Segredos

| Chave | Onde | Estado |
|---|---|---|
| `deepseek_api_key` | `secrets.local.json` (gitignored) | presente |
| `sema_authkey` | idem | presente — destrava 30 das 41 camadas |
| `planet_api_key` | idem | presente — basemap dos 17 mapas Planet |
| `groq_api_key` | idem, campo a criar | **ausente** — bloqueia o item 4 do DoD por visão |

- Provisionar no login/cofre no mesmo espírito das outras
  ([`docs/provisao-deepseek-instalador.md`](../docs/provisao-deepseek-instalador.md): env var →
  `MAPASFACIL_PROVISAO_PATH` → `provisao.local.json` → `secrets.local.json`).
- **Nunca** em código, commit, prompt versionado ou log.
- ⚠️ Os `.mxd` de `Testes/01_analise_04_Julio/Modelo/MXD/` trazem **chave Planet e `authkey`
  SEMA reais embutidas**. A pasta `Testes/` está no `.gitignore`, mas qualquer `.mxd` que saia
  dali para `Referencias_IMAP/` ou `shared/templates/` passa **obrigatoriamente** por
  `python3 ferramentas/chaves_mxd.py limpar && python3 ferramentas/chaves_mxd.py verificar`
  antes do commit (AP-03; incidente de 2026-07-25).

## 15. Registro de validação

### Execução da série (2026-07-29, Aruanã, PC Linux sem ArcMap)

| O que | Resultado |
|---|---|
| Identidade descoberta só do polígono | Fazenda Aruanã I · CAR `MT117446/2017` · Ribeirão Cascalheira · IoU 0,9995 |
| Camadas materializadas | 20 (18 do catálogo + ATP + UF) + 3 derivadas |
| Mapas gerados | **20/20** em 355 s, mais o compilado de 20 páginas |
| Anatomia contra os modelos | **19/20 verdes**; a exceção é o TCR (A02), por falta do número do termo (C4) |
| Imagem de fundo | mosaicos SEMA de 2000, 2008 (Landsat e SPOT), 2013, 2017, 2019, 2023 e 2024 |
| Suítes | núcleo `pytest -q` verde (501 testes); `validar_goal_analise.py` sem falhas |

Detalhe da rodada, com os 7 bugs achados e corrigidos:
[`docs/analise-de-area-serie.md`](../docs/analise-de-area-serie.md).

### Conferência do documento (2026-07-29)

Feito neste PC Linux (sem ArcMap):

| O que | Resultado |
|---|---|
| Pareamento 20 PDFs ↔ 20 MXDs | conferido por texto, Jaccard **1,00** em todas as páginas |
| Ordem da série | extraída de `Mapas_unidos.pdf` (20 páginas) |
| Tamanhos de página | 12× 210×297 mm e 8× 297×210 mm, medidos com `fitz` |
| Fontes/basemaps por mapa | lidos do bloco `METADADOS` de cada PDF + strings dos `.mxd` |
| ATP Aruanã | 7.408,8844 ha, EPSG:31982, Ribeirão Cascalheira (IBGE 5107180) — calculado, não copiado |
| Catálogo | 41 camadas e 43 mosaicos SEMA conferidos; lacunas C1–C5 levantadas |
| Âncoras da §9 | todas verificadas no disco |
| `Fase_1_Desktop/nucleo` `pytest -q` | **481 passed, 1 skipped** (482 coletados), exit 0 |
| `Fase_1_Desktop/app` `pnpm test` | **175 passed, 2 skipped** (27 arquivos) |
| Flake observado | um teste de `BarraChats` (`chat.listar_conversas`) falhou por timing numa execução e passou na reexecução — **instabilidade de teste, não do app** |
| Segredos | `chaves_mxd.py verificar` e revisão do `.gitignore`: `Testes/`, `output/`, `secrets.local.json`, `*.exe` e `ArcGIS*.zip` fora do Git |

## 16. Método de trabalho da IA executora

1. Ler `AGENT_BRIEF.md`, `docs/motor-nativo-harmonia.md` e este arquivo inteiro.
2. Não repetir o inventário — ele está na §3 e é conferível com
   `ferramentas/validar_goal_analise.py`.
3. Fechar a trilha Linux (§10) na ordem L1→L10; a Fase W (§11) só depende de máquina Windows.
4. Rodar na Aruanã, validar cada PDF, corrigir, repetir até a §12.
5. Não expandir escopo. Não versionar segredo nem dado de proprietário.
6. Fechar item = atualizar a linha do gap analysis do `AGENT_BRIEF.md` **no mesmo commit**
   (AP-15).
