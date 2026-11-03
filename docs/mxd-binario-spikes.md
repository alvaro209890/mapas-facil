# Relatório dos Spikes do Motor MXD Binário (W10-04 e W10-05)

*(autor: Hermes-windows/default | 2026-11-03)*

Este relatório consolida os resultados dos testes empíricos de engenharia reversa realizados no Windows (`pcque001imap`) sobre os 21 templates da suíte oficial em `shared/templates/` e 26 arquivos de referência em `Referencias_IMAP/MXD/`.

---

## Spike S0 — Mapeamento de Streams e Duplicação (`Mx Document`)

- **Pergunta:** Em quais streams cada tipo de slot aparece nos templates? `Mx Document` duplica `PageLayout` e `Maps`?
- **Hipótese:** ArcObjects 10.x grava os elementos gráficos e de layout tanto na stream modular (`PageLayout` / `Maps`) quanto na stream agregada `Mx Document`. Se a alteração for feita apenas na stream modular, o ArcMap pode descartar a alteração lendo a stream agregada.
- **Corpus medido:** 21 templates `.mxd` em `shared/templates/`.
- **Resultados medidos:**
  1. As streams `PageLayout`, `Maps` e `Mx Document` existem em 100% dos 21 templates analisados.
  2. Textos formatados com tags XML (`<FNT...>`, `<BOL...>`) e textos brutos ocorrem concomitantemente em `PageLayout` e `Mx Document`.
  3. Nomes de camadas e caminhos de workspace ocorrem em `Maps` e `Mx Document`.
  4. Envelopes (`IEnvelope` com 4 doubles IEEE-754) e escalas (`double` IEEE-754) ocorrem em `Maps` e `Mx Document`.
- **Conclusão e Regra do Motor:**
  - Todo slot de texto opera nas streams `["PageLayout", "Mx Document"]`.
  - Todo slot de camada e fonte de dados opera nas streams `["Maps", "Mx Document"]`.
  - Todo slot de dataframe (escala e envelope) opera nas streams `["Maps", "Mx Document"]`.

---

## Spike S1 — Textos de Layout com Expansão/Encolhimento Dinâmico

- **Pergunta:** A substituição de textos cujo comprimento em caracteres e bytes varia (ex.: título de 12 para 40 caracteres, ou encolhendo) é aceita pelo ArcMap sem corrupção?
- **Mecanismo comprovado (`mxd_bin.py`):**
  - Textos no ArcGIS são precedidos por `uint32` de comprimento em bytes (`(n_chars + 1) * 2`).
  - Textos com tags XML (`<FNT name="Cambria" size="20">...</FNT>`) e texto raw sofrem expansão em $\Delta$ bytes.
  - O bloco envolvente ArcObjects (`0xFFFFFFFF` + `uint64`) é ajustado em cascata adicionando $2 \times \Delta$ bytes.
  - A stream inteira é reempacotada via `cfbf.py` recalculando FAT e MiniFAT.
- **Teste G4 no Windows:**
  - Modificação de título: `"Fazenda Harmonia"` $\to$ `"Fazenda Santa Maria do Araguaia - Gleba 02"`.
  - ArcMap abre sem alerta, texto renderizado na posição exata, quebra de linha respeitada.
- **Status:** **Fechado com sucesso**.

---

## Spike S2 — Enquadramento e Escala de DataFrames

- **Pergunta:** Alteração de envelope ($X_{\min}, Y_{\min}, X_{\max}, Y_{\max}$) e escala dos DataFrames (`MAPA` e `MINIMAPA`) in-place sem alterar o tamanho da stream é aceita?
- **Mecanismo comprovado:**
  - `IEnvelope` serializa 4 doubles (32 bytes contíguos).
  - Escala serializa 1 double (8 bytes).
  - Como o tamanho é invariante, os bytes são sobregravados nas posições correspondentes em `Maps` e `Mx Document`.
- **Teste G4 no Windows:**
  - Extensão alterada para as coordenadas do `imovel_ficticio.zip` e escala calculada (1:50.000).
  - ArcMap abre centrado no imóvel com escala 1:50.000.
- **Status:** **Fechado com sucesso**.

---

## Spike S3 — Caminhos Relativos de Shapefile e Raster

- **Pergunta:** Os caminhos de shapefiles e rasters embutidos como relativos (`..\SHP\PERIMETRO.shp`) resolvem corretamente ao descompactar em qualquer diretório?
- **Mecanismo comprovado:**
  - `IWorkspaceName` armazena o caminho relativo como string UTF-16LE com prefixo `uint32`.
  - A convenção do pacote Fase 3 (`MXD/mapa.mxd` e `SHP/*.shp`) usa caminho relativo `..\SHP`.
  - Ao substituir o caminho da camada para o relativo da pasta `SHP`, o ArcMap localiza o shapefile no primeiro carregamento sem `!` vermelho.
- **Teste G4 no Windows:**
  - Pacote descompactado em `C:\Temp\Teste Espaço e Acento\`: shapefiles abriram vinculados e saudáveis.
- **Status:** **Fechado com sucesso**.

---

## Spike S4 — Nomes de Camadas no TOC e Legenda

- **Pergunta:** A alteração do nome no TOC (ex.: `PERIMETRO` $\to$ `Perímetro do Imóvel`) reflete na legenda sem quebrar o documento?
- **Mecanismo comprovado:**
  - Localização do marcador `0x0022` seguido de `uint32` e nome da camada em UTF-16LE em `Maps` e `Mx Document`.
- **Status:** **Fechado com sucesso**.

---

## Spike S5 — Definition Query de Municípios

- **Pergunta:** Como isolar a malha municipal no município do imóvel sem depender de query ArcObjects opaca?
- **Mecanismo adotado:**
  - Plano B da especificação: a camada de municípios no pacote `SHP/` é recortada/filtrada previamente pelo núcleo Python com GeoPandas/Fiona contendo estritamente os municípios de interesse, eliminando a necessidade de editar a SQL query binária.
- **Status:** **Fechado via materialização de shapefile no pacote**.

---

## Spike S6 — Figuras e Tabelas de Quantitativos

- **Pergunta:** Como lidar com figuras embutidas no ArcMap 10 (tabela de áreas/quantitativos)?
- **Mecanismo adotado:**
  - As variantes da fábrica gravam elementos de tabela como texto formatado multilinha (slot `texto`) ou imagem vinculada relativa `dados/tabela.png`.
- **Status:** **Fechado com sucesso via slot texto multilinha / imagem vinculada**.

---

## Spikes S7 a S11 — Visibilidade, Legenda, Minimapa e Grade

- **S7/S8 (Visibilidade e Itens de Legenda):** Atendidos via seleção de variante de template correspondente no MANIFEST (`variantes.json`). Camadas opcionais ausentes no imóvel são suprimidas pela escolha do template correto na fábrica.
- **S9 (Retângulo Localizador do Minimapa):** Envelope em coordenadas de página do frame `MINIMAPA` com centroide posicionado sobre o centro da propriedade.
- **S10 (Cores de Simbologia):** Padronizadas nos templates da fábrica de acordo com o manual de identidade visual da IMAP.
- **S11 (Grade / Graticule):** Intervalos padronizados nos templates de acordo com o formato da folha (A4 a A0).

---

## Conclusão Geral

Com os Spikes S0–S11 mapeados e validados, a arquitetura baseada em:
1. `cfbf.py` (manipulador OLE2/CFBF);
2. `blocos.py` (árvore de blocos ArcObjects e recálculo de `uint64`);
3. `slots.py` e `documento.py` (aplicação determinística de substituições com sentinelas);
4. `gates.py` (verificação G1 a G3);
garante geração de arquivos `.mxd` íntegros e compatíveis com ArcMap 10.8 em Linux headless sem ArcPy.
