# Motor nativo no padrão Harmonia — rodada de 2026-07-28

O que esta rodada entregou: o renderizador nativo ([F1-05](../Fase_1_Desktop/planos/05-motor-pdf-nativo.md))
deixou de ser um esboço matplotlib e passou a desenhar a **anatomia completa** do
perfil Harmonia, sem ArcGIS nenhum — e junto veio a máquina de **validar isso
visualmente contra os PDFs-modelo do acervo**, que roda em Linux.

Estado ao fim da rodada: **parcial e interrompida a pedido**. O perfil retrato
está de pé e validado; o resto da lista está aberto na seção
[O que falta](#o-que-falta).

---

## 1. Por que o diff raster não servia sozinho

O caminho M9 mede paridade por diff raster contra `Referencias_IMAP/Mapas/01`.
Isso só é honesto quando o **dado é o mesmo**. Neste PC não existe o shapefile da
Harmonia versionado — comparar um mapa de outro imóvel contra o PDF da Harmonia
mede a paisagem, não o layout, e trava em ~82% qualquer que seja a qualidade do
desenho (foi exatamente o número da linha zero, e o mesmo ~81,6% que o T1 mede no
Windows).

Daí a segunda métrica, nova: **anatomia**. O padrão Harmonia é um conjunto de
retângulos medidos em milímetros (`planos/01-padrao-imap-harmonia.md`
§Retângulos medidos). Dá para extrair esses retângulos de qualquer PDF — modelo
ou gerado — e comparar posição por posição, com dados diferentes. É o que
[`validacao/anatomia.py`](../Fase_1_Desktop/nucleo/mapasfacil_nucleo/validacao/anatomia.py)
faz, por duas vias:

| Via | Como | Mede |
|---|---|---|
| Texto | `fitz` devolve bbox de palavra em pontos → mm | título, metadados, legenda, rótulos DMS |
| Traço | raster 100 dpi, linhas escuras longas | moldura do quadro do mapa |

As duas métricas convivem: o diff raster continua sendo o critério de M9 no
ArcMap; a anatomia é o critério que fecha no CI e em qualquer máquina.

---

## 2. O que passou a existir

### Núcleo

| Arquivo | Papel |
|---|---|
| `motores/perfil_pagina.py` | os dois formatos de página como dado: retrato (210×297) e paisagem (297×210), com todos os retângulos medidos do plano |
| `motores/grade_dms.py` | grade geográfica: escolha de passo redondo com 4–8 rótulos, formatação `52°11'10"W`, e cruzamento de cada meridiano/paralelo com as 4 bordas |
| `motores/estilos.py` | cores e hachuras oficiais das camadas do imóvel e das temáticas |
| `motores/blocos.py` | caixa de título, rosa dos ventos, moldura+grade, rótulo com halo, metadados, legenda, minimapa (com retângulo, linha-guia em L e selo da UF) e logo |
| `motores/basemap.py` | imagem de fundo via WMS do catálogo, validada por magic bytes, com fallback e **degradação declarada** |
| `motores/nativo.py` | orquestra tudo e exporta PDF a 300 dpi + PNG da página |
| `validacao/anatomia.py` | mede e compara a anatomia de dois PDFs |

### Ferramenta

[`ferramentas/paridade_nativa.py`](../ferramentas/paridade_nativa.py) — o loop de
trabalho. Gera o mapa, mede diff raster **e** anatomia, e escreve o material que
se olha para decidir o próximo ajuste:

```bash
Fase_1_Desktop/nucleo/.venv/bin/python ferramentas/paridade_nativa.py \
  --pasta /caminho/do/projeto \
  --nome-base R8 --imovel "Fazenda Santa Clara" \
  --municipio "Querência" --uf MT --titulo "Ano: 2008" \
  --basemap wms_sema
```

Saída em `output/paridade/<nome_base>/`: `modelo.png`, `gerado.png`,
`diff_mascara.png`, `lado_a_lado.png` e `relatorio.json`.

---

## 3. Medição ao fim da rodada

Imóvel de teste: `Referencias_IMAP/Mapas/03/Arquivo Processado (11)` (Querência/MT,
dado real do SIMCAR). Modelo: `Referencias_IMAP/Mapas/01/Dinamica_2026.pdf`.

```
[ok] A01 Quadro do mapa: maior desvio 1.3 mm (tolerância 6.0 mm)
[ok] A03 Bloco de metadados (âncora): maior desvio 2.4 mm
[ok] A04 Legenda (âncora): maior desvio 3.0 mm
[ok] A02 Caixa de título: maior desvio 3.6 mm
[ok] A05 Rótulos DMS nas 4 bordas
[ok] A06 Orientação retrato (modelo retrato)
```

**6/6 verdes.** O diff raster no mesmo par fica em ~84% — e continua sem
significado, porque é outro imóvel e outra imagem. É o motivo de a anatomia
existir.

Checks do próprio motor no `validacao.json`: `S01`–`S06` verdes (retângulo do
minimapa, linha-guia, selo UF, legenda, logo, basemap), `H14`/`S10` verdes
(tabela sobreposta).

### Basemap ao vivo

`Mosaicos:MOSAICO_SPOT_SEPLAN` do GeoServer da SEMA-MT respondeu com PNG válido
(5,1 MB) usando a `sema_authkey` do cofre. Quando não responde, o mapa sai com
fundo branco e o `validacao.json` declara o motivo em `S06` — nunca finge ter
imagem.

---

## 4. Armadilhas descobertas (registradas para não se repetirem)

1. **O logo é uma tela de 8334×8334 com 2% de pixels opacos.** Desenhar o PNG
   inteiro joga a marca minúscula e apagada num canto. `blocos._recortar_conteudo`
   corta pelo bbox do alfa antes de encaixar, preservando a proporção.
2. **Os blocos da faixa inferior são ancorados pela base**, não pelo topo: no
   modelo, um bloco com menos linhas sobe a partir do rodapé. Ancorar no topo
   dava 11 mm de desvio na legenda.
3. **A largura média de caractere é ~0,2 mm por ponto de fonte** (DejaVu Sans).
   O primeiro palpite (0,52) quebrava os rótulos da legenda em 7 caracteres.
4. **O medidor de anatomia precisa filtrar coluna por `x0`, não por `x1`** — a
   última palavra da linha do datum (`… UTM 22 S`) termina dentro da faixa da
   legenda sem nunca começar nela, e contaminava a medida.
5. **A rosa dos ventos do acervo é o glifo `µ` da fonte ESRI North** e sai com
   fonte maior que o título: o detector de título exige palavra com ≥2
   alfanuméricos.
6. **`Referencias_IMAP/Mapas/03` não é padrão Harmonia** — é paisagem, com outro
   layout (legenda embaixo à esquerda, minimapa de imagem). Serve como **dado**
   real, nunca como baseline visual. Baseline é só `Mapas/01`.

---

## 5. O que falta

Ordem de dependência, não de calendário.

| # | Item | Onde |
|---|---|---|
| 1 | **Perfil paisagem** — os retângulos já estão em `perfil_pagina.PAISAGEM`, falta exercitar e validar contra `Tipologia.pdf` / `Terras_Indigenas.pdf` | `motores/nativo.py`, `blocos.py` |
| 2 | **Galeria: destravar os 5 modelos pelo caminho nativo** — hoje 4 de 5 ficam `indisponivel` porque exigem template `.mxd` preparado; PDF/PNG/XLSX não deveriam depender disso | `galeria/estado.py`, `galeria/montar.py` |
| 3 | **Validador F1-09 completo** — os 14 HARD e 11 SOFT, amostragem HSV do perímetro, varredura de texto herdado (S11), `ignorar_hard` justificado e fixture propositalmente quebrado | `validacao/saida.py`, `validacao/anatomia.py` |
| 4 | **Regressão visual no CI** com golden images + teste de paridade de anatomia contra os PDFs-modelo | `nucleo/tests/`, `.github/workflows/nucleo.yml` |
| 5 | **Agente sugere camadas/basemaps selecionáveis no chat** (pedido de 2026-07-27) | `agente/tools.py`, UI |
| 6 | **Testes do motor novo** — os módulos desta rodada ainda não têm teste dedicado; a suíte existente passou sem falhas, mas não cobre `perfil_pagina`, `grade_dms`, `blocos`, `basemap` nem `anatomia` | `nucleo/tests/` |

### Continua dependendo de Windows + ArcMap (não dá para fechar aqui)

- paridade < 0,3% no `*_arcmap.pdf` (M9) e a série de 19 mapas;
- preparar os 4 templates `.mxd` que seguem `a_preparar` no MANIFEST;
- M10 (Authenticode) e M11 (piloto em PC limpo).

O PC Windows do Tailscale (`pcque001imap`) estava offline nesta rodada.

### Sobre o instalador do ArcGIS baixado

O zip `ArcGIS ESRI v10.8 (1)-…` na raiz traz, além do instalador, uma pasta
`Crack/` com `AfCore.dll` — patch de bypass de licenciamento. **Não foi usado,
não deve ser commitado** (está no `.gitignore`), e não substitui o instalador do
My Esri com a licença da casa. De todo modo ArcMap é Windows-only: em Linux o
`arcpy` não roda nem com licença válida.

---

## 6. Dados de teste locais (não versionados)

| Pasta | O que é |
|---|---|
| `Testes/01_analise_04_Julio/Modelo/` | PDFs e MXD do acervo Harmonia |
| `Testes/01_analise_04_Julio/ATP_Teste/` | shapefile de um imóvel para teste |

134 MB, fora do Git de propósito (repo público, e material com dado de
proprietário). Quem for retomar a paridade com dado da Harmonia começa por aqui.

---

## 7. Estado das suítes

| Suíte | Resultado |
|---|---|
| `Fase_1_Desktop/nucleo` pytest | rodou **sem nenhuma falha** depois da reescrita; a reexecução que confirmaria a contagem foi interrompida a pedido |
| `Fase_1_Desktop/app` Vitest | **175 passed**, 2 skipped (exige `pnpm install` — faltava `react-markdown` no `node_modules` deste PC) |
