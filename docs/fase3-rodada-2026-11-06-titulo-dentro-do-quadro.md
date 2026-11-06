# Rodada 2026-11-06 — título dentro do quadro (app web)

O Dinâmica 2008 do Lote 43 (projeto `d60c3fdf…`, app `mapasfacil-app.cursar.space`) saiu com a
caixa do título **por cima da moldura**, cobrindo os rótulos de longitude do topo. Não era o
`.mxd` (template da Aline já tem a caixa no lugar): era o recorte do **PDF nativo**, que é o que a
web mostra e entrega.

## Causa

`perfil_pagina` guardava em `titulo` o **bbox do texto** — `y0 = 3,63` no retrato
(`63,72 → 132,71`). O bbox do texto sobe até a linha de base da fonte e é maior que a caixa
desenhada (a caixa real começa em **7,11**). Como `planejar_titulo` ancora a caixa no `y0` do
perfil e cresce para baixo, a caixa branca nascia 3,5 mm acima do topo do quadro (5,0) e tapava a
grade. O mesmo erro estava no perfil paisagem (`3,0` contra a caixa real em `6,09`) e em todos os
20 registros de `shared/padrao-imap/anatomia_serie.json` — o medidor usava o texto, não o
retângulo desenhado.

## Correção

- `perfil_pagina`: `RETRATO.titulo = (61,98 7,11 134,55 21,68)` e
  `PAISAGEM.titulo = (105,33 6,09 186,79 20,48)` — os retângulos **desenhados** medidos nos
  modelos (Dinamica_2026_quantitativos.pdf e Tipologia.pdf).
- `validacao/anatomia.medir`: o título passa a ser o **menor retângulo desenhado** que cobre a
  maior parte do texto (`_moldura_do_titulo`); sem candidato, cai no bbox do texto. Limites em
  fração da página (95 % da largura, 20 % da altura), para valer em A4 e em A0.
- `shared/padrao-imap/anatomia_serie.json` regerado com
  `ferramentas/medir_modelos_serie.py --modelos Referencias_IMAP/Mapas/01`: só o campo `titulo`
  mudou nos 20 mapas (diff conferido campo a campo).
- `planos/01-padrao-imap-harmonia.md`: tabela e desenho passam a citar o retângulo desenhado.
- Testes novos: `test_caixa_de_titulo_medida_comeca_dentro_do_quadro` (perfil) e
  `test_caixa_de_titulo_nunca_sobe_para_fora_do_quadro` (blocos, retrato e paisagem, três textos).
- Golden `tests/golden/anatomia_dinamica_retrato.png` regerado (`MAPASFACIL_ATUALIZAR_GOLDEN=1`).
- `test_cfbf_corpus`: 22 templates (o `Dinamica_2008_SPOT_quadro.mxd` entrou no `67bd477` e a
  contagem do teste ficou em 21 — o `main` estava vermelho nesse teste desde então).

## Medição

PDF sintético (golden, Dinâmica 2026): caixa do título `(60,56 7,11 135,97 21,68)`, quadro
`y0 = 4,83` — topo **2,3 mm dentro** do quadro, rótulos de longitude livres. Antes: `y0 = 3,63`,
**1,2 mm acima** do quadro. Card da Aline com `caixa_justa` (24 pt): `(63,88 7,11 132,65 19,90)`.

## Deploy

`/home/server/mapasfacil/codigo` não é checkout git: cópia de
`perfil_pagina.py`, `validacao/anatomia.py` e `shared/padrao-imap/anatomia_serie.json` +
`systemctl --user restart mapasfacil-app.service`. Verificado no PDF do projeto real,
regerado em cópia de trabalho no server.
