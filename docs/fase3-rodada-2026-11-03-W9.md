# Rodada 2026-11-03 — W9 (PDF nativo em A4–A0) e W8 (palco: núcleo do estado na web)

*(autor: Hermes-windows/default | 2026-11-03)*

O W-09 é o marco que tira o motor nativo da A4: as outras folhas são o **perfil medido
multiplicado por `k`** (D31), com resolução de raster, grade e blocos acompanhando o papel.
O que segue medido aqui é o que os testes provam; o que depende do server está marcado.

## Resultado por tarefa

| Tarefa | O que entrou | Prova |
|---|---|---|
| W9-01 | `perfil_para(folha)` e `escalar_perfil(perfil, folha)` em `perfil_pagina.py`; A4 devolve o objeto medido, o resto é A4 × k | `tests/test_perfil_para.py` — 57 testes |
| W9-02 | `nativo._perfil_do_mapspec` usa a folha (o modelo da série manda na orientação) e `perfil.dpi_raster()` no `savefig` | idem + render A0 |
| W9-03 | toda espessura/halo de `blocos.py` por `perfil.escalado()`; `HALO_*` virou `halos(perfil, claro=)` | `tests/test_blocos_por_folha.py` — 8 |
| W9-04 | `grade_dms.escolher_passo`: varrimento pequeno caía no passo de 1° e deixava o mapa **sem grade** | `tests/test_grade_por_folha.py` — 73 (4–8 rótulos/eixo em 5 folhas × 2 orientações × 7 escalas) |
| W9-05 | `minimapa.layout_de_perfil(perfil)` + linha-guia escalada | `tests/test_minimapa_folha.py` — 8 |
| W9-06 | `basemap.largura_para_folha(perfil)`, `avaliar_resolucao()` e check **S17** | `tests/test_basemap_folha.py` — 12 |
| W9-07 | PNG da tabela cresce com a caixa no papel (`largura_cm`), com teto de 80 MPix | `tests/test_png_tabela_folha.py` — 8 |
| W9-08 | `anatomia.esperada_para_folha()`, `conferir_folha()` (**H15**), `comparar(..., fator=k)` | `tests/test_anatomia_folha.py` (26) + `test_golden_anatomia_folhas.py` (9, render real A4/A3/A0) |
| W9-09 | `pdf.fonttype = 42` — o PDF levava **Type 3**, fonte não embutida | idem (fontes embutidas + `get_text`) |
| W9-11 | `planos/01-padrao-imap-harmonia.md` § Folhas maiores (D31), com H15 e S17 no checklist | revisão do plano |
| W9-12 | `pt_metadados_efetivo()`, check **H16**, regra da legenda por perfil, hachura AC/AVN conferida | `tests/test_blocos_layout_regras.py` — 82 |

## Medições reais (fixture sintética `dinamica_2026_canonico`, sem basemap)

| Folha | Página medida | Quadro do mapa medido | H15 | Tempo | PDF |
|---|---|---|---|---|---|
| A4 retrato | 210,0 × 297,0 mm | 6,86 × 4,83 → 203,45 × 257,05 | ✅ | 4,7 s | 0,09 MB |
| A3 retrato | 297,0 × 420,0 mm | 9,65 × 6,86 → 287,78 × 363,47 | ✅ | 4,0 s | 0,10 MB |
| A0 retrato | 841,0 × 1189,0 mm | 27,94 × 19,81 → 814,83 × 1029,21 | ✅ | 5,0 s | 0,14 MB |

Quadro A3 = quadro A4 × 1,41428 dentro de 0,1 mm; A0 dentro de 0,4 mm (0,05%) — é ruído de
medição do detector de moldura, não de escala. Rótulos DMS por folha: 24 / 22 / 24.

Resolução pedida ao basemap: A4 2.321 px (300 dpi), A3 3.282, A2 4.642, A1 5.449 (249 dpi),
A0 7.002 (226 dpi) — a mesma tabela do plano.

## Achados que mudaram código

1. **ISO não tem razão √2 exata.** `k` da largura não fecha com a altura: A3 é 297 × 420 e
   `297 × 1,41428 = 420,043`. O minimapa, que na A4 termina exatamente em 297,0 mm, vazava do
   papel em A3 (0,04 mm) e A0 (0,41 mm). Resolvido com **encaixe de borda**: coordenada que já
   era borda na A4 continua borda na folha nova; nenhuma caixa interna é deformada.
2. **Grade sumindo.** `escolher_passo` exigia ≥ 2 divisões para aceitar um passo; num imóvel de
   7,2″ de arco nenhum passo cabia e ele caía no de 1° — mapa sem grade nenhuma.
3. **Fonte não embutida.** O default do matplotlib é Type 3: o PDF não leva a fonte, só
   procedimentos de glifo. Pré-impressora recusa; agora é Type 42.
4. **Metadados estourando a caixa.** Com 7 linhas o bloco não cabe em **nenhuma** folha (o
   estouro é folha-invariante). Agora o corpo desce de 10% em 10% até caber, com piso em 60%.
5. **Golden da A4 regenerado uma vez**, por causa do item 3: 0,72% dos pixels mudaram (só a
   rasterização do texto). A anatomia em mm não mudou — é o que o `comparar` continua cobrando.

## Pendências honestas

| Item | Por que |
|---|---|
| W9-10 (medição no server) | precisa do app instalado no `server-desktop`; entra junto com o W12 |
| W9-12 restante | quadro cadastral 2×4 em PNG (é dado pessoal — W-17 §8) e redução de corpo por célula do nome longo |
| W7-08 / W9-06 ao vivo | raster do mosaico só se mede com mosaico real, no anel 3 |

## Testes ao fim da rodada

| Suíte | Resultado |
|---|---|
| núcleo | **956 verdes** em 76 arquivos (0 falha) |
| servidor | 176 verdes |
| web | 147 verdes (W8-05/06 commitados; W8-01..03/07..09 em andamento) |

## Delegado a subagente

- **W9-03** (`blocos.py` por `k`) — relatório revisado: diff lido, `HALO_*` sem uso residual,
  A4 com k=1 sem regressão, suíte completa rodada por mim depois (956 verdes).
- **W8-05/06** (coreografia + store do palco) — 29 testes novos; `npm run test/typecheck/build`
  rodados por mim, não só pelo subagente.
