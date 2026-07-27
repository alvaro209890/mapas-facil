# Minimapa IBGE — conexão e troca de município

## Modelo visual (PDF Harmonia)

Fonte da verdade: `Referencias_IMAP/Mapas/01/` (ex.: `Dinamica_2026.pdf`).

No canto inferior-esquerdo do mapa:

1. **Municípios do entorno** em bege, contorno fino.
2. **Município da propriedade** em laranja `#F4A460`, com **nome rotulado** (halo branco).
3. **Quadradinho vermelho** sobre o centroide do imóvel.
4. **Linha-guia em L** (vermelha) do retângulo até a moldura do mapa principal.
5. **Inset da UF** (canto do minimapa) com o estado em verde-claro e selo `MT`.

Quando a propriedade muda de município, os quatro itens (query, rótulo, retângulo, linha L)
têm de se mover juntos — senão o PDF fica como o incidente Harmonia (retângulo 0,4 cm fora).

## Base no repo

`shared/bases/ibge/`:

- `lml_municipio_a.shp` — Brasil
- `lml_uf_a.shp` — UFs
- regenerar: `python ferramentas/materializar_malhas_ibge.py --baixar`

## Fluxo no app desktop (agente)

1. **`analisar_referencia`** (imagem/PDF/.mxd/.zip):
   - Visão: campo `minimapa_presente` no JSON; se true, o MapSpec candidato liga
     `elementos_layout.minimapa`.
   - `.mxd` sem ArcMap: `mxd_strings` detecta `MINIMAPA` / `MINIMAPA_RETANGULO` /
     `MINIMAPA_GUIA` e queries `"nome" = '…'`; sugere município + minimapa.
2. **`galeria.montar_mapspec`**: resolve `imovel.municipio.ibge` na base local a partir
   do nome do recibo (ex.: Vila Rica → código IBGE).
3. **`gerar_mapa`**:
   - **T1** (ArcMap 10.8 em `C:\Python27\ArcGIS10.8\python.exe`): aplica definition
     query, zoom do inset, rótulo, retângulo e linha L (`motores/minimapa_job.py` +
     `scripts/arcpy_job.py`).
   - **T2** (patch sem ArcMap): gera o `.mxd` estrutural e emite aviso `NU-128` se o
     minimapa estava ligado — o inset não é reposicionado.

## Scripts

| Script | Função |
|---|---|
| `ferramentas/materializar_malhas_ibge.py` | Baixa API IBGE → shapefiles |
| `ferramentas/conectar_minimapa_ibge_arcpy.py` | Reconecta todos os MXDs à base + nomeia elementos |
| `ferramentas/mudar_municipio_minimapa_arcpy.py` | Definition query + zoom + rótulo + retângulo/L |
| `mapasfacil_nucleo/camadas/ibge.py` | Cliente API + resolução local + extent |
| `mapasfacil_nucleo/motores/minimapa.py` | Cálculo página do retângulo/linha L |
| `mapasfacil_nucleo/motores/minimapa_job.py` | Contexto T1 a partir do MapSpec |

### Trocar município de um MXD

```bat
C:\Python27\ArcGIS10.8\python.exe ferramentas\mudar_municipio_minimapa_arcpy.py ^
  caminho\mapa.mxd --municipio "Confresa" --uf-sigla MT --uf-nome "Mato Grosso" ^
  --lon -51.8 --lat -10.6 --in-place
```

### Lote Harmonia (Vila Rica)

```bat
C:\Python27\ArcGIS10.8\python.exe ferramentas\mudar_municipio_minimapa_arcpy.py ^
  --aplicar-acervo-harmonia --in-place -o relatorio_mudar_municipio.json
```

## Contrato das camadas no MXD

| Data frame | Camada | Definition query |
|---|---|---|
| `MINIMAPA` | `MUNICIPIOS` | `"nome" = '<municipio>'` (laranja) |
| `MINIMAPA` | `MUNICIPIOS_ENTORNO` | (vazio — bege) |
| `UF_INSET` | `UF` | `"nome" = '<uf por extenso>'` |
| `MAPA` | `MUNICIPIOS` | mesmo município (limite no mapa principal) |

Elementos de layout: `MINIMAPA_RETANGULO`, `MINIMAPA_GUIA`, `ROTULO_MUNICIPIO`, `UF_SELO`.
