# Referências IMAP

Gabaritos visuais e cartográficos do padrão IMAP (consultoria ambiental, Mato Grosso).

Qualquer ajuste de layout no Mapas Fácil deve ser conferido contra estes arquivos.

## Organização

Todo acervo de mapas vive em `Mapas/NN/`, um número por cliente/análise, cada um com seu próprio
`README.md` e inventário. Pastas com nome de download (`OneDrive_*`) **não existem mais** —
foram dissolvidas nesse esquema em 2026-07-26.

| Pasta | O que é | Papel | Tamanho |
|---|---|---|---|
| [`Mapas/01/`](Mapas/01/) | PDFs da **Fazenda Harmonia** (Vila Rica/MT, 2026-07) | **fonte da verdade visual** | 29 MB |
| [`Mapas/02/`](Mapas/02/) | PDFs da **Fazenda Trevisol** (Querência/MT) | contraste — perfil **descartado** | 28 MB |
| [`Mapas/03/`](Mapas/03/) | Export SIMCAR completo + Dinâmica L5 2003–2008 | calibração de papéis / anos históricos | 95 MB |
| [`Mapas/04/`](Mapas/04/) | **Análise de Área multi-imóvel** (Ribeirão Cascalheira/MT, 2025) — 29 `.mxd` + 29 PDFs, paisagem | multi-imóvel, série 2000–2025, embargos | 420 MB |
| [`Mapas/05/`](Mapas/05/) | **Mapa de AEP** (área que será desmatada) — 1 `.mxd`, sem PDF | tipo de mapa novo; tabela como `PICTURE_ELEMENT` | 4 MB |
| [`Mapas/06/`](Mapas/06/) | **Divisão de talhões** (Fazenda Macaré) — retrato, 1:50.000 | referência de estilo que destravou o B1 | 6 MB |
| [`MXD/`](MXD/) | Templates `.mxd` Harmonia + documentação da adaptação | gabarito para o motor | 106 MB |
| [`Logos IMAP/`](<Logos IMAP/>) | 4 PNGs oficiais do logo (com/sem fundo × tom claro/escuro, 8334×8334) | fonte do `LOGO.sourceImage` do template | 3 MB |

### O que fica fora do git, e por quê

| Fora | Motivo |
|---|---|
| `Mapas/04/PDF/CAR - Recibo_*.pdf` (4 arquivos) | contêm **CPF e CNPJ de proprietários reais**. Repositório é público — ficam só no disco local, via `.gitignore` |
| `OneDrive_1_25-07-2026 (1).zip` (517 MB) | download bruto; conteúdo já extraído e organizado em `Mapas/04–06` |
| `Mapas/03/OneDrive_*.zip` | truncado; ver [`Mapas/03/README.md`](Mapas/03/README.md) |

Descartados na organização de 2026-07-26 por redundância: `Dinâmicas_2000_2025.pdf` (duplicata
exata de `Dinamica 2000-2025.pdf`, 42,6 MB) e `Mapas/04/PDF/PDF.zip` (21,3 MB).

## O que cada acervo resolve

| Pergunta do produto | Acervo |
|---|---|
| Como é o padrão visual oficial? | `Mapas/01` (Harmonia) — **só ele** |
| Como **não** é o padrão? | `Mapas/02` (Trevisol) |
| Quais os nomes reais de shapefile do SIMCAR? | `Mapas/03` |
| Como se faz um mapa com **vários imóveis**? | `Mapas/04` — 5 polígonos, 4 matrículas |
| Que satélite se usa em cada ano da série Dinâmica? | `Mapas/04` — tabela de sensores no README |
| Como é um mapa de embargo real? | `Mapas/04` — 3 variantes (SEMA+IBAMA, SIGA, por imóvel) |
| Como é um mapa de AEP? | `Mapas/05` |
| De onde saiu a estratégia do B1? | `Mapas/06` |

## Documentação operacional

| Arquivo | Conteúdo |
|---|---|
| [`MXD/DOCUMENTACAO_MXD_HARMONIA.md`](MXD/DOCUMENTACAO_MXD_HARMONIA.md) | receita completa da adaptação manual: arcpy hang, homônimos, scripts, CRS, minimapa |
| [`../planos/01-padrao-imap-harmonia.md`](../planos/01-padrao-imap-harmonia.md) | geometria medida, cores, checks HARD/SOFT |
| [`../Fase_1_Desktop/planos/04-motor-mxd.md`](../Fase_1_Desktop/planos/04-motor-mxd.md) | como o produto reproduz estes mapas |

## Uso no projeto

- Spec do padrão: só o perfil **Harmonia** (`Mapas/01` + `MXD/`).
- `Mapas/02` existe para que ninguém "corrija" o padrão de volta ao Trevisol por engano.
- `Mapas/04–06` são acervos de **cobertura**: casos que Harmonia não tem. Não redefinem o padrão.
- Templates operacionais vão em `shared/templates/`, derivados dos `.mxd` deste acervo.
- Chaves de API nos `.mxd` versionados: placeholders — ver [`../ferramentas/`](../ferramentas/README.md).

## Antes de qualquer commit que toque `.mxd`

```bash
python3 ferramentas/chaves_mxd.py limpar      # chave real -> placeholder
python3 ferramentas/chaves_mxd.py verificar   # tem de dizer "Seguro para commit"
```

A varredura é **recursiva** a partir de `Referencias_IMAP/MXD/` e `Referencias_IMAP/Mapas/`,
então uma pasta `Mapas/NN/` nova já entra automaticamente. Não é preciso editar `MXD_DIRS` —
mas é preciso **rodar** o comando: todo `.mxd` que chega do escritório traz chave real embutida.

## Nota

Arquivos binários grandes. Fazem parte do repositório de propósito. Não apague nem "otimize"
sem regenerar a baseline de regressão.
