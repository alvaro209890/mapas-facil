# Rodada 2026-11-05 — MXD de projeto do modelo Dinâmica 2008 (SPOT)

O card `dinamica_2008_spot_quadro` gerava o PDF no modelo da Aline e o `.mxd` no
template do Dinâmica 2026. O site passa a usar o template preparado
`shared/templates/Dinamica_2008_SPOT_quadro.mxd`.

O que o motor grava, além do texto e da extensão do mapa:

- cópias em `SHP/` com os nomes que o template espera (`AIR.shp`, `AVN.shp`,
  `AREA_CONSOLIDADA.shp`, limites do IBGE, raster da imagem do PDF);
- a extensão do minimapa no município, na proporção do quadro;
- a extensão visível do mesmo data frame (o ArcMap guarda as duas). No ArcMap 10.8,
  `df.extent` do minimapa do `.mxd` gerado coincidiu com a extensão do município
  (Querência), no SPOT em graus e no retrato em EPSG:3857.

A preparação não lê shapefile pelo ArcPy: nesta máquina `Describe` e
`replaceDataSource` travam. O script só troca a pasta da camada
(`findAndReplaceWorkspacePath`, `validate=False`). Configuração em
`ferramentas/templates_projeto/`.

A chave SEMA que veio no MXD da Aline foi substituída pelo placeholder de
`ferramentas/chaves_mxd.py` antes de versionar. O `.mxd` anterior do retrato continua
no histórico do git (`Dinamica_retrato.mxd` antes deste commit); a cópia solta
`Referencias_IMAP/MXD/Dinamica_retrato_pre_projeto.mxd` não entra no repositório.
