# `shared/padrao-imap/` — o padrão visual **medido**, não descrito

O padrão Harmonia em prosa está em
[`planos/01-padrao-imap-harmonia.md`](../../planos/01-padrao-imap-harmonia.md). Esta pasta
guarda a parte dele que não cabe em texto: os **números tirados dos próprios PDFs-modelo**.

| Arquivo | O que é |
|---|---|
| `anatomia_serie.json` | anatomia dos 20 modelos da série Análise de área, em milímetros |

## `anatomia_serie.json`

Por mapa: tamanho da página, orientação, retângulo do quadro do mapa, caixa de título, e — para
o bloco de metadados e a legenda — caixa, tamanho de fonte dos itens, tamanho de fonte do título
e as linhas de texto do modelo.

Quem lê: `motores/perfil_pagina.por_template("serie_<id>")`, que monta o perfil de página do
mapa; `motores/nativo.py` usa esse perfil quando o template começa com `serie_`.

**Por que existe um registro por mapa, e não um perfil por orientação.** Medindo os 20 modelos,
a base do quadro dos paisagem vai de **151,4 mm** (Terras Indígenas, que abre espaço para uma
legenda alta) a **168,9 mm** (Tipologia). São 17 mm — quase três vezes a tolerância de 6 mm da
validação de anatomia. Um retângulo médio erraria os dois extremos; o modelo de cada mapa acerta
o seu.

### Como regerar

```bash
python3 ferramentas/medir_modelos_serie.py
```

Exige o acervo de modelos em `Testes/01_analise_04_Julio/Modelo/Mapas/`, que é **gitignored**
(134 MB, material com dado de proprietário). Por isso o JSON medido entra no Git e o acervo
não: quem não tem o acervo continua gerando mapa no layout certo.

As caixas de metadados e legenda vêm de `validacao/anatomia.py` — a **mesma** função que depois
compara o PDF gerado com o modelo. Medir aqui com heurística própria já deslocou o centro do
bloco em 9 mm, e o mapa saía centralizado num lugar que o validador considerava errado.

### Cores

Não estão neste JSON: vivem em `motores/estilos.py`, amostradas dos modelos por
`ferramentas/amostrar_cores_modelo.py` (cor dominante do quadradinho à esquerda de cada rótulo
de legenda, a 300 dpi). Amostrar em vez de transcrever corrigiu dois valores que estavam errados
no código: `ac` era `#FF00FF` e é `#C500FF`; `auas` era `#FF8000` e é `#E59800`.
