# Bases geoespaciais versionadas (IBGE)

Malhas oficiais usadas pelos **minimapas** dos `.mxd` IMAP (padrão Harmonia).

## Arquivos

| Shapefile | Conteúdo | Campo da definition query |
|---|---|---|
| `lml_municipio_a.shp` | Municípios do Brasil | `"nome" = 'Vila Rica'` |
| `lml_municipio_mt.shp` | Só MT (mais leve) | idem |
| `lml_uf_a.shp` | UFs do Brasil | `"nome" = 'Mato Grosso'` |

CRS: **WGS84 (EPSG:4326)**. Campos: `nome`, `cod_ibge`, `sigla_uf`, `uf`.

Fonte: [API Malhas IBGE v3](https://servicodados.ibge.gov.br/api/docs/malhas?versao=3)
(`qualidade=minima`) + [Localidades v1](https://servicodados.ibge.gov.br/api/docs/localidades)
para os nomes.

## Regenerar

```bash
python ferramentas/materializar_malhas_ibge.py --baixar
```

## Conectar aos MXDs + trocar município

```bat
C:\Python27\ArcGIS10.8\python.exe ferramentas\conectar_minimapa_ibge_arcpy.py ^
  Referencias_IMAP\MXD Referencias_IMAP\Mapas shared\templates --in-place

C:\Python27\ArcGIS10.8\python.exe ferramentas\mudar_municipio_minimapa_arcpy.py ^
  --aplicar-acervo-harmonia --in-place
```

Modelo visual: PDFs em `Referencias_IMAP/Mapas/01/` — município laranja, rótulo com halo,
quadradinho vermelho no imóvel, **linha-guia em L** até o quadro do mapa, selo da UF.
Doc: [`docs/minimapa-ibge.md`](../../docs/minimapa-ibge.md).

A pasta `_raw/` (GeoJSON bruto) não precisa ir para o git.
