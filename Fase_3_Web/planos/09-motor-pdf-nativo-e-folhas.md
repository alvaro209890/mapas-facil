# W-09 — PDF vetorial nativo em todas as folhas (A4–A0)

## Objetivo

Fazer o motor nativo (`motores/nativo.py` e companhia) produzir o PDF de entrega em **A4, A3,
A2, A1 e A0**, retrato e paisagem, com a mesma anatomia medida do acervo (perfil Harmonia) e
qualidade de impressão: texto como texto, fontes embutidas, vetores como vetores, raster do
mosaico na resolução certa para o tamanho do papel. A A4 continua sendo o **gabarito medido**;
as outras folhas são o perfil A4 escalado por igual (D31).

## Estado atual vs alvo

| Item | Hoje | Alvo |
|---|---|---|
| Perfis | `motores/perfil_pagina.py`: dois perfis medidos em mm (retrato, paisagem), carregados de JSON | + perfil **derivado** por folha: `perfil_para(folha)` |
| Anatomia | `validacao/anatomia.py`; golden no CI com tolerância 0,3%; 19/20 da série verdes | golden por folha (A4 medido, demais derivados) |
| Grade DMS | `motores/grade_dms.py` | intervalo escolhido pela escala **e** pelo tamanho do quadro |
| Minimapa | `motores/minimapa.py`, `minimapa_job.py`, base IBGE em `shared/bases/ibge` | igual, escalado |
| Basemap | `motores/basemap.py`, `basemap_planet.py` (mosaico mensal Planet, SEMA, fallback) | resolução do recorte proporcional à folha |
| Fonte | `FAMILIA_FONTE = ["Arial", "Liberation Sans", "Nimbus Sans", "DejaVu Sans"]` (`nativo.py`) | no server: `fonts-liberation` instalada; fonte **embutida** no PDF |

## Dependências

W1 (`MapSpec.folha`, `motores/folhas.py`). Independente da web: pode correr em paralelo a W3–W8.

## Contratos

### Perfil derivado

```python
# motores/perfil_pagina.py
def perfil_para(folha: dict) -> PerfilPagina:
    """A4 medido escalado por k = fator_k(folha). Para A4, devolve o perfil medido idêntico."""
```

Regras (D31 — é o comportamento do ArcMap com "escalar elementos proporcionalmente"):

| Grandeza | Regra para folha com fator `k` |
|---|---|
| `largura_mm`, `altura_mm` | `folha_mm(formato, orientacao)` (exato, tabela de [W-02](02-projeto-folha-e-upload.md)) |
| Todas as `Caixa` (mapa, título, rosa, minimapa, metadados, legenda, logo, tabela) | `x0·k, y0·k, x1·k, y1·k` |
| Tamanhos de fonte (`pt_titulo`, `pt_metadados`, `pt_legenda`, `pt_grade`, `pt_legenda_titulo`) | `pt · k` |
| Espessuras de linha (moldura, perímetro, grade) | `pt · k` |
| Escala do mapa | **não** escala: é recalculada pelo enquadramento ([W-10](10-inteligencia-cartografica.md)) — folha maior ⇒ quadro maior ⇒ escala de denominador menor (mais detalhe) |
| Intervalo da grade DMS | recalculado (S07: 4–8 rótulos por eixo) |
| Raster do basemap | resolução ver §Raster |
| Textos | os mesmos; quebra de linha recalculada pelo mesmo algoritmo (largura média de caractere já usada em `blocos.py`) |

Como as folhas A têm todas razão √2, a escala uniforme preserva o layout exatamente: a A0 é a
A4 "ampliada", com a diferença essencial de que o **mapa** dentro do quadro ganha detalhe.

`folha.escala_elementos` admite só `"proporcional"` na v1. A alternativa `"legivel"` (elementos
crescem menos que a folha, mapa ganha a área) fica registrada como futuro — exige medir um modelo
real de prancha grande no acervo antes de existir.

### Raster (mosaico/basemap) por folha

Alvo: **300 dpi efetivos no papel** para o raster dentro do quadro do mapa, com teto de pixels
para não estourar memória:

Quadro do mapa do perfil retrato medido: `Caixa(7,0; 5,0; 203,5; 257,0)` → 196,5 × 252,0 mm
(paisagem: 285,5 × 163,7 mm). Escalado por `k`:

| Folha | Quadro do mapa (retrato) | Pixels a 300 dpi no lado maior | Teto aplicado |
|---|---|---|---|
| A4 | 196,5 × 252,0 mm | ~2.980 | — |
| A3 | 277,9 × 356,4 mm | ~4.210 | — |
| A2 | 393,0 × 504,0 mm | ~5.950 | — |
| A1 | 555,8 × 712,8 mm | ~8.420 | 7.000 (≈ 249 dpi) |
| A0 | 786,0 × 1.008,0 mm | ~11.900 | 9.000 (≈ 227 dpi) |

Se a resolução nativa do mosaico (Planet mensal ~4,77 m/px; Landsat 30 m) for menor que a
pedida, **não** reamostrar para cima além de 2× (imagem borrada grande é pior): grava no PDF na
resolução nativa ×2 no máximo e registra `S17` (aviso de resolução do mosaico para a folha).

PDF: raster como JPEG qualidade 90 dentro do PDF (o PNG do acervo pesa demais em A0); vetores
como caminhos; `MAPASFACIL_PDF_HQ` (já existe) continua controlando a qualidade.

### Tamanho e desempenho

| Folha | Alvo de tamanho do PDF (Dinâmica típica) | Alvo de tempo de render no server (4 núcleos) |
|---|---|---|
| A4 | ≤ 8 MB | ≤ 20 s |
| A3 | ≤ 14 MB | ≤ 30 s |
| A2 | ≤ 25 MB | ≤ 45 s |
| A1 | ≤ 40 MB | ≤ 70 s |
| A0 | ≤ 60 MB | ≤ 110 s |

Valores de alvo, não de contrato: o agente mede no W9 e atualiza a tabela com o medido.

### Qualidade vetorial (checks novos — detalhados em [W-10](10-inteligencia-cartografica.md))

- Texto do título, metadados, legenda e grade **extraível** pelo PyMuPDF (`get_text`) — já é
  base do H03; vale para todas as folhas.
- Fontes **embutidas** (subset) — `fitz` lista as fontes da página; nenhuma pode estar como
  "não embutida".
- Página no tamanho da folha ±1 mm (H15).

### Golden por folha

| Folha | Fonte da verdade | Tolerância |
|---|---|---|
| A4 retrato/paisagem | perfis medidos + PDFs-modelo do acervo (`Referencias_IMAP/Mapas/01`) — golden atual | 0,3% (como hoje) |
| A3–A0 | **derivado** do A4: a anatomia esperada é a do A4 × `k` | 0,3% sobre as medidas escaladas |
| A3 e A1 de `dinamica_retrato` | + PDF exportado pelo ArcMap da variante (fábrica do W-08, passo 6) | anatomia ± 0,5 mm × `k` |

`nucleo/tests/golden/` ganha subpastas por folha; o teste `test_golden_anatomia.py` é
parametrizado por folha × orientação × 3 modelos (Dinâmica, Uso do solo, TI/UC).

## Tarefas agentáveis

- [ ] **W9-01** `motores/perfil_pagina.py::perfil_para(folha)` + teste: `perfil_para(A4 retrato)` é idêntico ao perfil medido; A0 = A4 × 4 em toda caixa e todo pt.
- [ ] **W9-02** `motores/nativo.py`: usar `perfil_para(mapspec.folha)`; tamanho da figura matplotlib em polegadas pela folha; `dpi` do raster por folha (§Raster).
- [ ] **W9-03** `motores/blocos.py`: espessuras e fontes multiplicadas por `k`; quebra de linha recalculada.
- [ ] **W9-04** `motores/grade_dms.py`: intervalo pela escala e pelo tamanho do quadro (4–8 rótulos por eixo em qualquer folha).
- [ ] **W9-05** `motores/minimapa.py` / `minimapa_job.py`: caixa e espessuras por `k`; retângulo localizador recalculado (S01).
- [ ] **W9-06** `motores/basemap.py`: resolução do recorte pela folha; teto de pixels; aviso S17.
- [ ] **W9-07** `quantitativos/png_tabela.py`: PNG da tabela com dpi ≥ 400 efetivos na folha (S10) — em A0 isso significa PNG maior.
- [ ] **W9-08** `validacao/anatomia.py`: anatomia esperada = A4 × `k`; golden por folha; H15.
- [ ] **W9-09** Verificação de fontes embutidas e texto extraível em todas as folhas.
- [ ] **W9-10** Medição real de tamanho/tempo por folha no server; atualizar a tabela §Tamanho com o medido.
- [ ] **W9-11** `planos/01-padrao-imap-harmonia.md`: seção "Folhas maiores (D31)" com a regra de escala e os checks H15/S17.
- [ ] **W9-12** Regras de layout das skills ([W-17](17-conhecimento-das-skills.md) §5) no motor nativo: legenda 0,5 cm abaixo do quadro e 0,2 cm antes do logo (encolhe se não couber); corpo dos METADADOS pelo número de linhas (16 → 14 → 12 pt); quadro cadastral `PROPRIEDADE · PROPRIETÁRIO(A) · CAR · ÁREA (HA)`; hachura de AC/AVN nas dinâmicas. Conferir o que `blocos.py` já faz antes — e manter o golden da A4 sem regressão.

## Critérios de aceite

- [ ] `pytest -k golden` verde para 5 folhas × 2 orientações × 3 modelos.
- [ ] PDF A0 de Dinâmica do `imovel_ficticio`: página 841 × 1189 mm ± 1 mm; título extraível; fontes embutidas; raster ≥ 220 dpi efetivos ou aviso S17.
- [ ] A4 continua **byte-equivalente em anatomia** ao golden atual (nenhuma regressão da série 19/20).
- [ ] Render A0 não passa de 3 GB de RSS no worker (medido com `/usr/bin/time -v`).

## Fora de escopo

- Folhas fora da série A (Carta, Ofício, personalizada) — o `MapSpec.folha.formato` é enum fechado.
- `escala_elementos: "legivel"`.
- Paridade pixel a pixel com o ArcMap (é anatomia em mm; já decidido no M9).

## Anti-padrões

- Medir "à mão" um perfil novo para A3 e gravar números (D31: derivado, não medido).
- Rasterizar texto para "ficar igual" (perde H03 e o texto selecionável).
- Reamostrar o mosaico 4× para "parecer" mais nítido em A0.
