# Mapas/03 — export SIMCAR + série Dinâmica Landsat 5 (2003–2008)

Acervo auxiliar para calibração do núcleo: **outro imóvel** (~64 ha, bbox ≈ 52°21'W /
12°21'S, MT), com:

1. pasta completa **Arquivo Processado** do CAR/SIMCAR (37 camadas padrão);
2. série **Dinâmica anual Landsat 5** 2003–2008 (`.mxd` + `.pdf`);
3. recorte `Dados/` usado pelos MXD (AIR, AREA_CONSOLIDADA, AVN).

Não substitui [`../01/`](../01/) (Harmonia = fonte da verdade visual). Serve para:

- inventário real dos **nomes de shapefile do SIMCAR**;
- tratar **camadas vazias** (AUAS=0, manguezal=0, …) sem abortar o workspace;
- templates extras de Dinâmica pré-2008 (L5) além da série Harmonia.

## Layout

```
03/
├─ Arquivo Processado (11)/   ← zip SIMCAR descompactado (37 .shp)
├─ Dados/                     ← subset ligado aos MXD dinâmica
├─ MXD/                       ← Dinâmica_2003_L5 … 2008_L5
├─ PDF/                       ← PDFs correspondentes + Dinâmica_2003_2008.pdf
├─ OneDrive_1_25-07-2026 (1).zip   ← TRUNCADO (não usar; ver abaixo)
└─ README.md
```

## ZIP OneDrive — por que não extraía

O arquivo `OneDrive_1_25-07-2026 (1).zip` (~50 MB) está **incompleto**:

| Sintoma | Causa |
|---|---|
| `End-of-central-directory signature not found` | download cortado; falta o diretório central e o EOCD |
| `Unexpected end of archive` (7z) | última entrada (`PRODES_Até_2007.mxd`) pela metade |
| flags `0x0808` nos headers locais | ZIP “streaming” (data descriptor); recuperável parcialmente |

**Correção aplicada:** recuperação pelos cabeçalhos locais com
[`../../../ferramentas/recuperar_zip_truncado.py`](../../../ferramentas/recuperar_zip_truncado.py):

```bash
python3 ferramentas/recuperar_zip_truncado.py \
  "Referencias_IMAP/Mapas/03/OneDrive_1_25-07-2026 (1).zip" \
  -o /tmp/out
```

Resultado: **37 arquivos íntegros** gravados em `Dados/`, `MXD/`, `PDF/`.  
Faltou só `PRODES_Até_2007.mxd` (truncado) — rebaixar do OneDrive se precisar.

O ZIP truncado **não deve ser commitado** (duplica lixo). Conteúdo útil = pastas acima.

## Arquivo Processado — catálogo SIMCAR (37 layers)

Imóvel de teste: `ATP.AREA_HA = 64,4229` (1 feição). Campos típicos: `ID`, `AREA_HA`,
às vezes `TIPO` / `SITUACAO` / `NOME`.

| Papel no Mapas Fácil | Layers presentes | Feições neste imóvel |
|---|---|---|
| Perímetro | `ATP` | 1 |
| Vegetação nativa | `AVN` | 4 |
| Área consolidada | `AREA_CONSOLIDADA` | 3 |
| Desmate pós-2008 | `AUAS` | **0** (vazio válido) |
| APP | `APP`, `APPD`, `APPRL` | 6 / 19 / 6 |
| ARL | `ARL`, `ARL_*`, `ARLREM` | 4 (+ vazios) |
| Hidrografia | `RIO_*`, `RIO_LINHA`, `NASCENTE`, `LAGOA_*`, `RESERVATORIO_*` | misto |
| Tipologia | `TIPOLOGIA_VEGETAL` | 2 (`ORIGEM`, `TIPO`, `AREA_HA`) |
| Alerta | `AIR` | 1 |
| Outros / muitas vazias | `VEREDA`, `MANGUEZAL`, `RESTINGA`, `BORDA_CHAPADA`, `AREA_UMIDA`, `AURD`, … | 0 |

**Regra nova para o índice:** shapefile com 0 feições e ~100 bytes é **export SIMCAR vazio**,
não erro fatal. Indexar com `n_feicoes=0` e seguir. Só falhar HARD se a camada for
**obrigatória** no `MapSpec` (ex.: `ATP` / `AVN` pedidas e vazias).

## Série Dinâmica L5 (2003–2008)

| Arquivo | Papel |
|---|---|
| `MXD/Dinâmica_200Y_L5.mxd` + `PDF/…` | um ano por mapa, fundo Landsat 5 |
| `PDF/Dinâmica_2003_2008.pdf` | compilado da série |

Útil no M2/M5 como templates adicionais de anos históricos (além de 2000/2008 Harmonia).
Sem chaves Planet/SEMA embutidas óbvias (fundo L5 local/WMS diferente).

## Uso no desenvolvimento (núcleo já iniciado)

Fixture de shapes para testes de `workspace` / papéis:

```text
Referencias_IMAP/Mapas/03/Arquivo Processado (11)/
```

Cobrir no anel 1 (fixture no repositório — `tests/test_simcar_03.py`):

- [x] descobrir `ATP`, `AVN`, `AREA_CONSOLIDADA`, `AUAS` (vazio), `TIPOLOGIA_VEGETAL`
- [x] não abortar por `MANGUEZAL.shp` vazio
- [x] área ATP ≈ 64,4229 ha após reprojeção UTM

Ver planos: [`../../../planos/04-dados-camadas-e-car.md`](../../../planos/04-dados-camadas-e-car.md).
