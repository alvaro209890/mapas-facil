# Mapas/01 — gabarito Harmonia (fonte da verdade)

PDFs exportados do ArcMap na análise **Fazenda Harmonia** (Julio Barbosa / Vila Rica-MT,
julho/2026). São o **perfil visual oficial** do Mapas Fácil.

Documentação de como os `.mxd` foram adaptados:
[`../../MXD/DOCUMENTACAO_MXD_HARMONIA.md`](../../MXD/DOCUMENTACAO_MXD_HARMONIA.md).

Spec medida: [`../../../planos/01-padrao-imap-harmonia.md`](../../../planos/01-padrao-imap-harmonia.md).

## Inventário

### Série Dinâmica (A4 retrato)

| Arquivo | Notas |
|---|---|
| `Dinamica_2000.pdf` | Landsat 5/TM |
| `Dinamica_2008_LANDSAT.pdf` | Landsat |
| `Dinamica_2008_SPOT.pdf` | SPOT |
| `Dinamica_2013.pdf` | Landsat |
| `Dinamica_2017.pdf` · `Dinamica_2019.pdf` · `Dinamica_2023.pdf` · `Dinamica_2026.pdf` | Planet |
| `Dinamica_2026_quantitativos.pdf` | mesma dinâmica + tabela PIL |

### Outros retrato

| Arquivo | Notas |
|---|---|
| `DLA.pdf` | dinâmica / classes locais |
| `Areas_Cultivaveis_VF.pdf` | áreas cultiváveis |
| `PEF.pdf` · `TCR.pdf` | produtos da série IMAP da consultoria |

### Temáticos (A4 paisagem)

| Arquivo | Notas |
|---|---|
| `Tipologia.pdf` | tipologia vegetal |
| `Terras_Indigenas.pdf` | TI Kapôt Nhinore a **0,51 km** |
| `Unidade_de_Conservação.pdf` | UC Parque Estadual do Xingu a **21,79 km** |
| `Embargos_IBAMA.pdf` · `Embargos_SEMA_SIGA_Poligono.pdf` | sem embargo no imóvel = correto |
| `Alertas_MAPBIOMAS_2.pdf` · `Alertas_PRODES_VF.pdf` | overlays de alerta |

### Compilado

| Arquivo | Notas |
|---|---|
| `Mapas_unidos.pdf` | junção dos mapas na ordem de entrega |

## O que conferir ao comparar um mapa gerado

1. Formato certo (retrato vs paisagem) para o template.
2. Perímetro **amarelo** `#FFFF00`, não vermelho Trevisol.
3. Minimapa Vila Rica com retângulo vermelho **sobre** o imóvel + linha-guia.
4. Tabela (quando houver): cabeçalho azul, `TOTAL GERAL` verde, 4 casas.
5. Nenhum texto herdado (`Área concolidada`, matrícula de outra fazenda, título errado).
6. Diff de raster vs este PDF < 0,3% nos checks HARD.

## Produto v1

A série mínima que o app deve gerar na v1 é a da documentação MXD (Dinâmica + temáticos
listados lá). `PEF`, `TCR` e `Areas_Cultivaveis_VF` ficam no acervo como referência; entram
como templates adicionais só se o catálogo `shared/templates/` os registrar explicitamente.
