# Mapas/04 — Análise de Área multi-imóvel (Ribeirão Cascalheira/MT)

Acervo real de uma **análise de área com quatro imóveis num mesmo mapa**, em Ribeirão
Cascalheira/MT, entregue em 2025. É o maior acervo do repositório: **29 `.mxd` + 29 PDFs**,
A4 **paisagem**, datum SIRGAS 2000 UTM 22S.

Traz duas coisas que nenhum outro acervo tinha:

1. **Multi-imóvel real** — 5 polígonos de 4 matrículas num único layout, com legenda por imóvel.
   É o caso que a pendência **P2** de [`../../../planos/02-mapspec-contrato.md`](../../../planos/02-mapspec-contrato.md)
   descreve como aberto (`imovel` viraria `imoveis[]`?). Aqui ele existe em produção.
2. **Série Dinâmica de 2000 a 2025 com sensor declarado por ano** — a tabela abaixo é a
   evidência para a seção "Basemap por ano" de
   [`../../../Fase_1_Desktop/planos/04-motor-mxd.md`](../../../Fase_1_Desktop/planos/04-motor-mxd.md).

> **Não é a fonte da verdade visual.** O perfil oficial continua sendo
> [`../01/`](../01/) (Harmonia). Este acervo é **paisagem**, de outro cliente e de outro ano;
> use-o para o que Harmonia não cobre: multi-imóvel, série histórica longa, embargos.

## Os imóveis

Legenda do mapa, na ordem em que aparece:

| Imóvel | Matrícula | CAR | Recibo |
|---|---|---|---|
| Fazenda São Sebastião | 7.128 | `MT173163/2019` | local (não versionado) |
| Fazenda Planalto I | 402 | `MT165855/2019` | local (não versionado) |
| Fazenda Conquista — Desmembrada | 8.995 | — | — |
| Fazenda Conquista | 5.065 | `MT239101/2023` | local (não versionado) |
| Fazenda Planalto | 403 | `MT215/2017` | local (não versionado) |

Município: **Ribeirão Cascalheira/MT**. Extensão aproximada: 51°45'–51°57'W, 13°12'–13°15'S.

### Por que os 4 recibos do CAR não estão no repositório

Os PDFs `CAR - Recibo_*.pdf` que vieram com este acervo contêm **CPF e CNPJ dos proprietários
reais**. O repositório é **público**, então eles ficam **só no disco local** e estão no
`.gitignore` (`Referencias_IMAP/**/CAR - Recibo*.pdf`).

Consequência prática: quem clonar o repositório tem os mapas, mas não tem os recibos. Para
testar o parser de recibo, use os fixtures anonimizados do núcleo, não este acervo.

## Série Dinâmica — sensor e data da imagem por ano

Extraído do bloco `METADADOS IMAGEM` de cada PDF. **Esta é a informação operacional mais
valiosa do acervo**: mostra que a série histórica não usa um basemap só, e que o rótulo do
sensor muda com o ano disponível.

| PDF | Satélite/Sensor | Data da imagem |
|---|---|---|
| `DINÂMICA_2000_LANDSAT_v2.pdf` | LANDSAT 7/ETM | 30/07/2000 |
| `DINAMICA_2002.pdf` | LANDSAT 7/ETM | 12/07/2002 |
| `DINÂMICA_2004_LANDSAT_v2.pdf` | LANDSAT 5/TM | 23/06/2004 |
| `DINAMICA_2005.pdf` | LANDSAT-5/TM | 16/10/2005 |
| `DINAMICA_2008.pdf` | SPOT | Ano de 2008 |
| `DINÂMINCA_2008_LANDSAT.pdf` | LANDSAT 5/TM | 20/07/2008 |
| `DINÂMINCA_2008_SPOT.pdf` | SPOT | 2008 |
| `DINÂMINCA_2010_LANDSAT.pdf` | LANDSAT 5/TM | 26/07/2010 |
| `DINAMICA_2012_Resource_SAT.pdf` | RESOURCE-SAT | Ano de 2012 |
| `DINAMICA_2014.pdf` | LANDSAT-8/OLI | 22/08/2014 |
| `DINAMICA_2016.pdf` | LANDSAT-8/OLI | 11/08/2016 |
| `DINAMICA_2018.pdf` | LANDSAT-8/OLI | 02/09/2018 |
| `DINAMICA_2020.pdf` | LANDSAT-8/OLI | 03/06/2020 |
| `DINAMICA_2023.pdf` | LANDSAT-8/OLI | 22/07/2023 |
| `DINAMICA_2025.pdf` | PLANET | Abril/2025 |
| `Dinamica 2005-2025.pdf` | SPOT/Planet | 2005-2025 |
| `Dinamica 2008-2025.pdf` | SPOT/Planet | 2008-2025 |
| `Dinamica 2000-2025.pdf` (13 páginas) | LANDSAT 7/ETM (capa) | 30/07/2000 |

Três leituras diretas para o produto:

- O rótulo `Satélite` do bloco de metadados é **texto livre do analista**, não um enum: aparece
  como `LANDSAT 7/ETM`, `LANDSAT-8/OLI`, `RESOURCE-SAT`, `SPOT`, `Planet` e `PLANET` — inclusive
  com e sem hífen, e com caixa inconsistente. O `MapSpec` trata isso como string
  (`metadados[].valor`), o que está certo; normalizar seria perder fidelidade ao acervo.
- Mapas de **comparação de período** (`2005-2025`, `2008-2025`) declaram dois sensores num campo
  só (`SPOT/Planet`) — não existe um `basemap` único para eles.
- O sufixo `_AC` marca a variante do mapa com **área consolidada** desenhada por cima.

## Inventário

### `MXD/` — 29 arquivos

| Grupo | Arquivos |
|---|---|
| Dinâmica anual | `DINAMICA_2000_v2`, `DINAMICA_2002`, `DINAMICA_2004`, `DINAMICA_2005`, `DINAMICA_2006`, `DINAMICA_2008`, `DINAMICA_2010`, `DINAMICA_2012`, `DINAMICA_2014`, `DINAMICA_2016`, `DINAMICA_2018`, `DINAMICA_2020`, `DINAMICA_2023`, `DINAMICA_2025` |
| Dinâmica por sensor | `DINÂMINCA_2000_LANDSAT`, `DINÂMINCA_2008_LANDSAT`, `DINÂMINCA_2008_LANDSAT_AC`, `DINÂMINCA_2008_SPOT`, `DINÂMINCA_2008_SPOT_AC` |
| Dinâmica de período | `Dinamica 2005-2025`, `Dinamica 2008-2025`, `Dinamica 2008-2025_AC` |
| Temáticos | `Analise_Area_UCs_e_TIs`, `Tipologia_Vegetal`, `Mapa_de_uso_consolidado`, `Distancia_de_uso_restrito` |
| Embargos | `Embargos_SEMA_IBAMA`, `Embargos_SIGA`, `EMBARGO_SAO_SEBASTIAO` |

### `PDF/` — 29 arquivos versionados

Mesma divisão. Os PDFs **não pareiam um-a-um** com os `.mxd`: alguns `.mxd` não foram exportados
(`DINAMICA_2006`, `DINAMICA_2010`, `DINAMICA_2012`, `DINAMICA_2000_v2`, `DINAMICA_2004`,
`DINÂMINCA_2000_LANDSAT`, `Mapa_de_uso_consolidado`) e alguns PDFs saíram de `.mxd` renomeados
ou não entregues (`DINÂMICA_2000_LANDSAT_v2`, `DINÂMICA_2004_LANDSAT_v2`,
`DINAMICA_2012_Resource_SAT`, `DINÂMINCA_2010_LANDSAT`, `Mapa_de_uso_consolidado_VF`,
`Dinamica 2000-2025`, `Dinamica 2000-2025_c`).

Isso é típico de entrega real e **não é para "corrigir"**: é a evidência de que o nome do
arquivo não é contrato. O contrato é o `MapSpec`.

### Descartados na organização (2026-07-26)

| Arquivo | Motivo |
|---|---|
| `Dinâmicas_2000_2025.pdf` | duplicata exata (mesmo `sha256`) de `Dinamica 2000-2025.pdf`, 42,6 MB |
| `PDF/PDF.zip` | 21,3 MB de cópia compactada do que já está solto na mesma pasta |

## Uso no projeto

| Serve para | Como |
|---|---|
| Multi-imóvel (`MapSpec` P2) | 5 polígonos, 4 matrículas, legenda por imóvel num layout só |
| Basemap por ano | a tabela de sensores acima |
| Mapas de embargo | 3 variantes reais: SEMA+IBAMA, SIGA, e um por imóvel |
| Distância até uso restrito | `Distancia_de_uso_restrito` — o mesmo padrão do mapa de TI da Harmonia |
| Tipologia vegetal | segundo exemplar, para conferir se o layout de Harmonia generaliza |
| Regressão de layout **paisagem** | Harmonia só tem 1 temático paisagem por tema; aqui há 29 |

## Avisos

- As chaves de API embutidas nos `.mxd` estão **zeradas por placeholder**. Para abrir no ArcMap
  com o basemap funcionando: `python3 ferramentas/chaves_mxd.py restaurar` (e `limpar` antes de
  qualquer commit).
- Os `.mxd` apontam para caminhos `C:\Users\User\...` da máquina do analista original. Abrir sem
  os dados vai mostrar `!` vermelho — é esperado, e é exatamente o problema que o produto resolve
  com `caminhos_relativos: true`.
