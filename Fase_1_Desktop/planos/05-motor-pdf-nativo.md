# F1-05 — Renderizador nativo de PDF

Motor Python puro (matplotlib + Pillow) que desenha o mapa no padrão Harmonia **sem ArcGIS
nenhum**. Herdado conceitualmente de `core/nexomap_renderer.py` do NexoGeo, onde já produzia
mapas calibrados contra PDFs-modelo reais.

## Quando é usado

| Situação | Papel |
|---|---|
| Preview rápido durante a conversa | sempre — o ArcMap leva 60–120 s; o nativo, 3–8 s |
| Máquina sem ArcMap (T2/T3) | **é o PDF entregue** |
| ArcMap presente | preview; o PDF final vem do ArcMap |
| CI | único motor disponível — é o que permite testar layout em pull request |

## O que ele garante

- Os **dois formatos de página** do perfil Harmonia (retrato para Dinâmica, paisagem para
  temáticos), com os retângulos medidos do
  [padrão](../../planos/01-padrao-imap-harmonia.md#retângulos-medidos-perfil-retrato).
- Grade DMS `52°11'10"W` com ticks, 4–8 rótulos por eixo, laterais a 90°.
- Caixa de título branca com borda preta.
- **Rosa dos ventos** (não seta simples).
- Perímetro amarelo, AVN verde `xxx`, AC magenta `xxx`, AUAS laranja `///`, todas vazadas.
- Rótulo do imóvel branco com halo, acima das hachuras.
- Bloco de metadados como lista de pares, com rótulo em negrito.
- Legenda com swatch de **polígono vazado grosso** (não linha).
- Minimapa de municípios com o município em laranja, retângulo vermelho e linha-guia.
- Tabela como a mesma imagem PNG usada no `.mxd`.
- Logo IMAP.

## O que ele não garante

- Identidade pixel a pixel com o ArcMap.
- Fidelidade perfeita de hachura (matplotlib e ArcMap desenham `xxx` com espaçamento diferente).
- O basemap Planet com o mesmo *tiling* e realce do ArcMap.
- **Não produz `.mxd`** — isso é do [motor de `.mxd`](04-motor-mxd.md).

Regra vinculante: quando o nativo gerou o PDF, o `validacao.json` traz `motor: "nativo"`, a UI
rotula como *"PDF nativo"*, e **a validação de conformidade roda com o mesmo rigor** — a
diferença de motor não vira desculpa para check falhando.

## Pipeline

```
MapSpec  →  resolver camadas (mesmo código do motor .mxd)
         →  reprojetar para o CRS do perfil
         →  figura matplotlib no tamanho da página, dpi 300
         →  basemap (tiles ou WMS GetMap) como imagem de fundo
         →  camadas vetoriais na ordem do MapSpec
         →  rótulo do imóvel
         →  moldura + grade DMS + ticks
         →  caixa de título
         →  rosa dos ventos
         →  faixa inferior: minimapa · metadados · legenda · logo
         →  tabela (PNG) sobreposta
         →  savefig PDF + PNG
```

Cada bloco da faixa inferior é desenhado num eixo próprio, com o retângulo vindo do manifesto do
perfil — não há posição hardcoded no código.

## Grade DMS

```python
def passo_dms(extensao_graus: float, alvo: int = 6) -> float:
    """Escolhe o passo 'redondo' que produz ~alvo rótulos."""
```

Passos candidatos, em segundos: 10, 15, 20, 30, 60, 90, 120, 150, 300, 600, 900, 1800, 3600.
Escolhe o que produz o número de rótulos mais próximo do alvo dentro do extent. Formato sem zero
à esquerda, hemisfério como letra.

## Basemap

| Tipo | Como |
|---|---|
| `planet_mensal` | tiles XYZ do mosaico, montados e recortados no extent |
| `mosaico_sema` | um `GetMap` WMS no bbox reprojetado, com validação de magic bytes |
| `esri_world_imagery` | tiles XYZ |
| `wms_tematico` | `GetMap` (é o caso do mapa de Tipologia: fundo Radam Brasil) |
| `nenhum` | fundo branco (é o caso do mapa de Terras Indígenas) |

Para WMS, **reprojetar o bbox antes** do `GetMap` e pedir `srs` no CRS do mapa, para o extent
casar. Validar a resposta: `Content-Type` começando com `image/` **e** magic bytes `\x89PNG` ou
`\xFF\xD8\xFF` — HTTP 200 com XML de erro é comum nesses serviços.

## Minimapa

Reprodução do inset do ArcMap, e o mesmo cálculo que o motor `.mxd` usa:

1. Malha municipal da UF da API do IBGE v3 (`qualidade=minima&intrarregiao=municipio`) —
   **a resposta vem gzip e precisa ser descomprimida explicitamente**.
2. Cache por UF, 180 dias (a malha é praticamente imutável).
3. Municípios em bege `#FDF3D7`; o do imóvel em laranja `#F4A460` com rótulo em halo branco.
4. Identificação pelo código IBGE do `MapSpec`; fallback por município que contém o centroide.
5. Retângulo vermelho no centroide do imóvel + linha-guia até a moldura do mapa principal.
6. Caixinha da UF no canto, com selo `MT`.

Sem internet e sem cache: o minimapa cai para um retângulo com o nome do município em texto, e o
check `S03` avisa.

## Fidelidade e regressão

Teste de regressão visual roda no CI (Linux, sem ArcGIS):

1. Gerar o mapa a partir de uma fixture determinística.
2. Rasterizar a 150 dpi.
3. Comparar com o *golden image* versionado.
4. Tolerância: **0,3% de pixels diferentes**.
5. Falhou? O CI publica as três imagens (esperado, obtido, diff) como artefato.

Além disso, um teste de **paridade com o modelo**: gerar o equivalente de
`Dinamica_2026_quantitativos.pdf` com os dados da Harmonia e comparar com o PDF real do acervo.
Esse não é bit a bit — mede posição de blocos, cores amostradas e presença de texto.

## Checklist de implementação

- [~] Perfil **retrato** feito (2026-07-28), com os retângulos medidos em `motores/perfil_pagina.py`; paisagem definido mas ainda não exercitado
- [x] Grade DMS com passo automático e formato correto — `motores/grade_dms.py`
- [x] Caixa de título
- [x] Rosa dos ventos
- [x] Estilos oficiais das 6 camadas do imóvel + temáticas sólidas — `motores/estilos.py`
- [x] Rótulo do imóvel com halo, no centroide, acima das hachuras
- [x] Bloco de metadados como lista de pares com negrito (ancorado na base da caixa)
- [x] Legenda com swatch de polígono vazado, com quebra de rótulo longo
- [x] Minimapa completo (IBGE, laranja, retângulo, linha-guia em L, selo UF)
- [~] Basemap **WMS** do catálogo com validação de magic bytes e degradação declarada (`motores/basemap.py`); faltam os demais tipos
- [x] Tabela PNG sobreposta
- [x] Logo (com recorte do alfa: o PNG do acervo tem 2% de pixels opacos)
- [x] Export PDF 300 dpi + PNG da página
- [x] `motor: "nativo"` no relatório
- [ ] Regressão visual no CI com golden images — **falta**
- [~] Paridade por **anatomia** contra os PDFs-modelo, 6/6 verdes (`validacao/anatomia.py`, `ferramentas/paridade_nativa.py`); falta virar teste de CI

## Pendências

| # | Questão |
|---|---|
| P1 | Hachura: calibrar espaçamento e ângulo do matplotlib contra o ArcMap para o olho não distinguir |
| P2 | A fonte do título nos modelos é serifada; identificar a família exata com PyMuPDF |
| P3 | Rosa dos ventos: redesenhar em vetor ou embutir o glifo da fonte ESRI North? |
| P4 | Golden images no repositório (tamanho) ou geradas num job de release? |
| P5 | Tempo de render com basemap Planet em imóvel grande — medir e otimizar o cache de tiles |
