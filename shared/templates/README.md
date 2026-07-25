# shared/templates/

Templates `.mxd` operacionais (após preparação única descrita em F1-04).

| Arquivo | Status |
|---|---|
| [`MANIFEST.json`](MANIFEST.json) | `dinamica_retrato` → `Dinamica_retrato.mxd` (**parcial**, sha256 ok, **offsets vazios**); demais `a_preparar` |
| `Dinamica_retrato.mxd` | Gerado por `ferramentas/normalizar_mxd_arcpy.py` a partir do acervo. Faltam 4 elementos de layout (ver abaixo) que só dá para criar na GUI do ArcMap. |

`dinamica_retrato` — o que a automação (`normalizar_mxd_arcpy.py`) já resolveu sem GUI:

- `relativePaths = True`
- Data frames `Layers`/`Layers` → `MAPA` (UTM 31982) / `MINIMAPA` (Web Mercator)
- Camadas `Fazenda Harmonia`→`PERIMETRO`, `Uso Consolidado`→`AC`, `Limite municipal`→`MUNICIPIOS`,
  `Limite estadual`→`UF`
- Texto de metadados da imagem → `METADADOS`
- `North Arrow` → `NORTE`; imagem única → `LOGO`; legenda maior → `LEGENDA`

O que **ainda precisa da GUI do ArcMap** (arcpy não cria elementos novos, só renomeia
existentes — ver `ferramentas/normalizar_mxd_arcpy.py` e o relatório de pendências que ele
imprime):

1. Criar texto `TITULO` (título do mapa) e `ROTULO_IMOVEL` (nome do imóvel) — não existem
   como elementos próprios no acervo.
2. Confirmar visualmente que a `LEGENDA` escolhida por heurística de tamanho é mesmo a do
   `MAPA` (há uma segunda, menor, possivelmente do `MINIMAPA`).
3. Identificar/nomear entre os 5 `GRAPHIC_ELEMENT` quais são `MINIMAPA_RETANGULO` e
   `MINIMAPA_GUIA` (retângulo indicador + linha-guia do minimapa).
4. Apontar a imagem de `LOGO` (`sourceImage` está vazio no acervo).

Depois desses 4 ajustes, rodar de novo `preparar_sentinelas_arcpy.py` +
`registrar_template.py dinamica_retrato` (os offsets calibrados antes desses ajustes ficam
inválidos, pois a estrutura binária do `.mxd` muda ao inserir elementos).

Fonte bruta: [`../../Referencias_IMAP/MXD/`](../../Referencias_IMAP/MXD/).
Baseline PDF: [`../../Referencias_IMAP/Mapas/01/`](../../Referencias_IMAP/Mapas/01/).
