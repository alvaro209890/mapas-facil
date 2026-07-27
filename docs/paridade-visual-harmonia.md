# Paridade visual Harmonia — passo a passo

Guia operacional para reduzir o diff raster de **~81%** para **&lt; 0,3%** entre o PDF gerado
pelo MapasFácil e o modelo em `Referencias_IMAP/Mapas/01/`.

**Para quem vai executar:** você + Claude (ou outro agente) no Windows com ArcMap 10.6–10.8.

**Estado em 2026-07-27:** pipeline M9 pronto (`smoke_m9_harmonia.py`); paridade cartográfica
**não** atingida na Dinâmica 2026. Ver medição em [`m9-conformidade-harmonia.md`](m9-conformidade-harmonia.md).

---

## 1. O que é “paridade visual”

| Conceito | Definição |
|---|---|
| **Baseline** | PDF modelo em `Referencias_IMAP/Mapas/01/<Nome>.pdf` — **nunca** use `Mapas/02/` ou `03/` |
| **Gerado** | `*_arcmap.pdf` exportado pelo ArcMap (motor T1) — **não** o PDF nativo matplotlib |
| **Métrica** | % de pixels que divergem além de limiar RGB 16, DPI 150, tolerância **0,3%** |
| **Ferramenta** | `validacao/comparar_pdf.py` via `smoke_m9_harmonia.py` |

O PDF nativo (`Mapas/<nome>.pdf` sem sufixo) serve para preview/T2 — **não** entra na paridade.

---

## 2. Pré-requisitos

### Máquina

- Windows com **ArcMap 10.6–10.8** fechado antes de scripts ArcPy longos
- Python núcleo: `Fase_1_Desktop\nucleo\.venv`
- ArcPy: `C:\Python27\ArcGIS10.8\python.exe` (ou 10.6/10.7)

### Repositório

```powershell
cd C:\GIS\mapas-facil
git pull origin main
cd Fase_1_Desktop\nucleo
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

### M2 fechado

Template `dinamica_retrato` com `broken: []` — se não tiver certeza:

```powershell
powershell -ExecutionPolicy Bypass -File ferramentas\fechar_m2_windows.ps1 -SemSmoke
```

### Pasta de teste (Harmonia)

Padrão neste PC:

```text
C:\Users\Usuario\Downloads\Analise_de_area\Analise_de_área-Julio Barbosa_ 4_Harmonia
```

Deve conter `Arquivo Processado (1)/ATP.shp` e demais camadas CAR.

### Leitura obrigatória antes de editar MXD

1. [`Referencias_IMAP/MXD/DOCUMENTACAO_MXD_HARMONIA.md`](../Referencias_IMAP/MXD/DOCUMENTACAO_MXD_HARMONIA.md) — seções 5 (armadilha ArcPy) e 8 (como continuar)
2. [`docs/m2-entrega-harmonia.md`](m2-entrega-harmonia.md)
3. [`Fase_1_Desktop/planos/04-motor-mxd.md`](../Fase_1_Desktop/planos/04-motor-mxd.md)

---

## 3. Loop de trabalho (repita a cada ajuste)

**Regra de ouro:** **um ajuste por vez** → medir → anotar % antes/depois.

### 3.1 Gerar e medir

```powershell
cd C:\GIS\mapas-facil

Fase_1_Desktop\nucleo\.venv\Scripts\python.exe ferramentas\smoke_m9_harmonia.py `
  --pasta "C:\Users\Usuario\Downloads\Analise_de_area\Analise_de_área-Julio Barbosa_ 4_Harmonia" `
  --nome-base Dinamica_2026_Paridade
```

### 3.2 Ler o relatório

| Arquivo | Conteúdo |
|---|---|
| `output\m9_smoke_relatorio.json` | diff %, checks HARD/SOFT, caminhos |
| `Harmonia\Mapas\Dinamica_2026_Paridade_relatorio_m9.json` | cópia na pasta do projeto |

Campos importantes:

```json
"comparacao_baseline": { "diferenca_pct": 81.33, "tipo_pdf": "arcmap", "ok": false },
"resumo_checks": { "hard_falhas": ["H10"], "soft_falhas": ["B09"] }
```

### 3.3 Comparar visualmente

Abrir lado a lado:

| Baseline | Gerado |
|---|---|
| `Referencias_IMAP\Mapas\01\Dinamica_2026.pdf` | `Harmonia\Mapas\Dinamica_2026_Paridade_arcmap.pdf` |

Anotar as **3 maiores diferenças** (normalmente: basemap, tabela, metadados).

### 3.4 Diff visual opcional (debug)

```powershell
Fase_1_Desktop\nucleo\.venv\Scripts\python.exe -c "
from pathlib import Path
import numpy as np
from mapasfacil_nucleo.validacao.comparar_pdf import rasterizar_pdf, medir_diferenca_raster
from PIL import Image

ref = Path('Referencias_IMAP/Mapas/01/Dinamica_2026.pdf')
ger = Path(r'C:\Users\Usuario\Downloads\Analise_de_area\Analise_de_área-Julio Barbosa_ 4_Harmonia\Mapas\Dinamica_2026_Paridade_arcmap.pdf')
a, b = rasterizar_pdf(ref), rasterizar_pdf(ger)
h, w = min(a.shape[0], b.shape[0]), min(a.shape[1], b.shape[1])
diff = np.any(np.abs(a[:h,:w].astype(int) - b[:h,:w].astype(int)) > 16, axis=2)
Image.fromarray((diff * 255).astype('uint8')).save('output/diff_mask.png')
print('diff_mask.png salvo em output/')
"
```

Pixels brancos no `diff_mask.png` = onde ainda diverge.

### 3.5 Registro de progresso (planilha ou markdown)

| Data | Ajuste | diff % antes | diff % depois | H10 | Notas |
|---|---|---:|---:|---|---|
| 2026-07-27 | baseline | 81,34 | — | falha | ponto de partida |

---

## 4. Ordem das fases (não pule)

```text
Fase 0  Diagnóstico visual
Fase 1  Dados + extent + escala
Fase 2  Textos do layout (METADADOS, escala)
Fase 3  Basemap / imagem de fundo        ← maior impacto no %
Fase 4  Tabela de quantitativos no MXD
Fase 5  Legenda e símbolos
Fase 6  Minimapa (retângulo + linha L)
Fase 7  Convergir < 0,3%
Fase 8  Replicar nos outros 18 mapas
```

---

## Fase 0 — Diagnóstico visual

**Objetivo:** saber *onde* está o diff antes de codar.

1. Abrir baseline vs gerado (seção 3.3).
2. Classificar diferenças:

| Sintoma | Fase provável |
|---|---|
| Fundo do mapa totalmente diferente | 3 (basemap) |
| Faixa inferior sem tabela ou tabela diferente | 4 (PICTURE_ELEMENT) |
| Texto de metadados/escala errado ou ausente | 2 |
| Mapa “no lugar errado” ou muito zoom | 1 |
| Inset/minimapa deslocado | 6 |
| Cores das camadas diferentes | 5 |

3. Rodar smoke uma vez e guardar `m9_smoke_relatorio.json` como **linha zero**.

**Critério de saída:** lista de 3–5 itens priorizados anotada.

---

## Fase 1 — Dados, extent e escala

**Objetivo:** mesmas geometrias, mesmo enquadramento 1:60.000 UTM 22S.

### 1.1 Confirmar SHP materializados

Na pasta Harmonia, após smoke:

```text
Harmonia\SHP\ATP.shp
Harmonia\SHP\AVN.shp
Harmonia\SHP\AC.shp  (ou AREA_CONSOLIDADA)
Harmonia\SHP\AUAS.shp
```

Compare áreas com `Arquivo Processado (1)/` (ATP ≈ 3823,9 ha).

### 1.2 Homônimos do template

O job copia stems canônicos para nomes que o MXD ainda espera (`CAR_ATP`, `Fazenda_Santa_Clara`…).
Código: `motores/minimapa_job.py` → `_HOMONIMOS_SHAPE`.

Se uma camada não aparece no PDF gerado, inspecione o MXD:

```powershell
C:\Python27\ArcGIS10.8\python.exe ferramentas\inspecionar_mxd_arcpy.py `
  "Harmonia\Mapas\Dinamica_2026_Paridade.mxd" `
  -o output\inspecao_gerado.json
```

### 1.3 Extent e escala

- Data frame: `MAPA`, CRS **EPSG:31982**
- Escala alvo: **1:60.000** — no smoke, force no MapSpec se necessário (editar
  `smoke_m9_harmonia.py` temporariamente ou montar MapSpec com `"escala": 60000`).

No ArcMap, abra o `.mxd` gerado e confira:

- View → Data Frame Properties → Extent
- Barra de escala ≈ 1:60.000

### 1.4 Se editar o template versionado

Qualquer save no `shared/templates/Dinamica_retrato.mxd` exige recalibrar B2:

```powershell
C:\Python27\ArcGIS10.8\python.exe ferramentas\preparar_sentinelas_arcpy.py shared\templates\Dinamica_retrato.mxd
Fase_1_Desktop\nucleo\.venv\Scripts\python.exe ferramentas\registrar_template.py dinamica_retrato shared\templates\Dinamica_retrato.mxd
Fase_1_Desktop\nucleo\.venv\Scripts\python.exe ferramentas\chaves_mxd.py limpar
Fase_1_Desktop\nucleo\.venv\Scripts\python.exe ferramentas\chaves_mxd.py verificar
```

**Critério de saída:** perímetro e classes no lugar certo; escala legível como 1:60.000.
Diff ainda alto é esperado (basemap domina).

---

## Fase 2 — Textos do layout

**Objetivo:** fechar checks **H03, H06, H10** no PDF ArcMap.

### 2.1 Inventariar TEXT_ELEMENT no template

```powershell
C:\Python27\ArcGIS10.8\python.exe ferramentas\inspecionar_mxd_arcpy.py `
  shared\templates\Dinamica_retrato.mxd -o output\inspecao_template_textos.json
```

Nomes esperados (handoff M2): `TITULO`, `METADADOS`, `ROTULO_IMOVEL`, `ROTULO_MUNICIPIO`, `UF_SELO`.

### 2.2 Conteúdo alvo (Dinâmica 2026 — Harmonia)

Alinhar com o baseline `Dinamica_2026.pdf`:

| Campo | Valor de referência |
|---|---|
| Título | Dinâmica 2026 |
| Satélite/Sensor | PLANET (ou o que estiver no PDF modelo) |
| Data da imagem | Março/2026 |
| **Fonte** | WMS-SEMA |
| Datum | SIRGAS 2000 UTM 22 S |
| Escala | 1:60.000 |

Hoje o smoke falha **H10** porque `Fonte` não aparece no texto extraído do PDF gerado.

### 2.3 Onde alterar no código

| Arquivo | O quê |
|---|---|
| `motores/minimapa_job.py` | expandir dict `textos` enviado ao job |
| `scripts/arcpy_job.py` | já aplica `textos[nome].text = valor` para elementos existentes |

Exemplo do que falta enviar (pseudocódigo para o agente implementar):

```python
textos = {
    "TITULO": "Dinâmica 2026",
    "METADADOS": "Satélite/Sensor: PLANET\nData da imagem: Março/2026\nFonte: WMS-SEMA\n...",
    "ROTULO_IMOVEL": imovel["nome"],
    ...
}
```

**Nota:** `arcpy.mapping` **não cria** TextElement novo — só edita os que já existem no template.

### 2.4 Validar

```powershell
# smoke de novo → H10 deve virar verde
Fase_1_Desktop\nucleo\.venv\Scripts\python.exe ferramentas\smoke_m9_harmonia.py --pasta "...\Harmonia" --nome-base Dinamica_2026_Paridade
```

**Critério de saída:** H03, H06 (com escala 60000), H10 verdes. Diff ainda pode estar &gt; 50%.

---

## Fase 3 — Basemap / imagem de fundo

**Objetivo:** alinhar a camada raster/WMS que ocupa a maior área do mapa — **maior alavanca do diff**.

### 3.1 Descobrir a camada no modelo

1. Abra `Referencias_IMAP/MXD/Dinamica_2026.mxd` no ArcMap (cópia de trabalho, não commitar chaves).
2. Liste camadas de imagem ativas no data frame `MAPA` (WMS SEMA, Planet, etc.).
3. Anote URL, nome da camada e mosaico (ex.: `global_monthly_2026_03_mosaic`).

Documentação Harmonia: Dinâmica 2026 usa **Planet** (WMS) na entrega manual; anos antigos usam Landsat SEMA.

### 3.2 Alinhar no template versionado

Opções (em ordem de fidelidade):

| Opção | Prós | Contras |
|---|---|---|
| A. Mesma URL WMS no template | Paridade online | Quebra offline; tile pode mudar |
| B. Cache GeoTIFF local no `SHP/` ou `shared/templates/recursos/` | Estável, reproduzível | Trabalho de export/cache |
| C. Raster estático extraído do PDF baseline | Diff mínimo garantido | Não atualiza com novo mosaico |

Para **0,3% estrito**, a opção B ou C costuma ser necessária.

### 3.3 Planet quebrado

Scripts existentes: `ferramentas/remover_planet_mxd_arcpy.py` — remove WMTS quebrado e troca por WMS SEMA.
Se usar fallback, **documente** que o diff pode não chegar a 0,3% vs baseline Planet.

### 3.4 Validar

Smoke + comparação visual. Meta intermediária: diff cair de ~81% para &lt; 30% só com basemap.

**Critério de saída:** fundo do mapa visualmente similar ao baseline (mesma tonalidade/cobertura).

---

## Fase 4 — Tabela de quantitativos no layout ArcMap

**Objetivo:** o `*_arcmap.pdf` deve ter a mesma faixa de tabela que o baseline.

No trabalho manual: `PICTURE_ELEMENT` com `tabela_quantitativos_harmonia.png` (PIL, valores do CAR).

Hoje o núcleo:

- gera `recursos/tabela_quantitativos.png` (600 dpi)
- sobrepõe só no **PDF nativo**
- **não** injeta no MXD/ArcMap

### 4.1 Passos

1. No template, identifique o `PICTURE_ELEMENT` da tabela (nome do elemento no layout).
2. Estenda o payload do `arcpy_job` com `imagens={ "NOME_ELEMENTO": caminho_png }` — o job já suporta:

```python
# arcpy_job.py (já existe)
for fig in arcpy.mapping.ListLayoutElements(mxd, u"PICTURE_ELEMENT"):
    if fig.name in (e.get(u"imagens") or {}):
        fig.sourceImage = _u(e[u"imagens"][fig.name])
```

3. Em `minimapa_job.py` / `gerar.py`, passe o PNG gerado por `renderizar_png_tabela`.
4. Posição no layout: conferir mm no perfil Harmonia retrato (F1-05 / `nativo.py` `_TABELA_RETRATO`).

Valores de referência (Harmonia):

| Coluna | Valor (ha) |
|---|---|
| ATP | 3823,9140 |
| AVN | 2833,7541 |
| AC | 483,8562 |
| AUAS | 491,2631 |

### 4.2 Validar

Faixa inferior do PDF gerado ≈ baseline; diff deve cair vários pontos percentuais.

**Critério de saída:** tabela visível no `*_arcmap.pdf` com valores corretos.

---

## Fase 5 — Legenda e símbolos

**Objetivo:** mesmas entradas de legenda e cores (H11 parcial).

1. Conferir `legenda` no payload do `arcpy_job` (lista de nomes de camada).
2. No MXD gerado: perímetro amarelo, AVN verde, AC magenta, AUAS laranja.
3. Remover camadas mortas que ainda exportam artefato visual.

Inspeção:

```powershell
C:\Python27\ArcGIS10.8\python.exe ferramentas\inspecionar_mxd_arcpy.py "Harmonia\Mapas\....mxd"
```

**Critério de saída:** legenda com os mesmos itens e cores que o baseline.

---

## Fase 6 — Minimapa

**Objetivo:** inset de Vila Rica + retângulo vermelho + linha L alinhados (checks S01–S03).

Referência: `fix_minimap_rect.py` na documentação Harmonia (recentragem manual nos 19 MXDs).

No MapasFácil T1:

- `minimapa_job.py` → `graficos_para_centroide`
- IBGE em `shared/bases/ibge/`

Se o retângulo estiver ~0,3–0,5 cm fora:

1. Compare centroide ATP no gerado vs baseline.
2. Ajuste offsets em `motores/minimapa.py` ou gráficos do job.
3. Smoke + inspeção visual do inset.

**Critério de saída:** retângulo sobre a fazenda no minimapa; município “Vila Rica” legível.

---

## Fase 7 — Convergir para &lt; 0,3%

### Tabela de diagnóstico

| Diff ainda… | Provável causa | Ação |
|---|---|---|
| &gt; 50% | Basemap | Fase 3 |
| 20–50% | Tabela + metadados | Fases 2 e 4 |
| 5–20% | Extent, legenda, símbolos | Fases 1 e 5 |
| 1–5% | Fontes, compressão PDF, antialiasing | Export 300 dpi, `embed_fonts=True` (já no job) |
| 0,3–1% | Ruído de rasterização | Verificar DPI/limiar; último ajuste fino no layout |
| **≤ 0,3%** | — | **Dinâmica 2026 fechada** |

### Comando de aceite

```powershell
Fase_1_Desktop\nucleo\.venv\Scripts\python.exe ferramentas\smoke_m9_harmonia.py --pasta "...\Harmonia" --nome-base Dinamica_2026_FINAL
```

Deve retornar exit 0 **e** `"diferenca_pct" <= 0.3` **e** todos HARD verdes.

### Após passar

1. Se mexeu no template: `fechar_m2_windows.ps1` ou passos B2 da Fase 1.4.
2. Atualizar [`m9-conformidade-harmonia.md`](m9-conformidade-harmonia.md) com a medição final.
3. Marcar F1-13 **I2** e **V3** como `[x]` no checklist.
4. Commit + push.

---

## Fase 8 — Série completa (19 mapas)

**Só depois** da Dinâmica 2026 &lt; 0,3%.

| # | Modelo / MXD | Baseline PDF | CRS frame |
|---|---|---|---|
| 1 | Dinâmica 2026 | `Dinamica_2026.pdf` | 31982 |
| 2 | Dinâmica quantitativos | `Dinamica_2026_quantitativos.pdf` | 31982 |
| 3+ | Tipologia, TI, UC, Alertas… | ver `Referencias_IMAP/Mapas/01/` | 3857 (paisagem) |

Para cada mapa:

1. Repetir pipeline M2 (`fechar_m2_template_arcpy` adaptado ou script por família).
2. `registrar_template.py` → `status: pronto` no MANIFEST.
3. Smoke com `--modelo <id_galeria>`.
4. Anotar diff no relatório.

Roteiro manual já feito uma vez: [`DOCUMENTACAO_MXD_HARMONIA.md`](../Referencias_IMAP/MXD/DOCUMENTACAO_MXD_HARMONIA.md) seções 7–8.

**Critério de saída M9 completo:** 19 mapas, 14 HARD verdes, diff &lt; 0,3% em todos, S11 verde.

---

## 5. Arquivos-chave (mapa para o agente)

| Área | Arquivo |
|---|---|
| Comparar PDFs | `Fase_1_Desktop/nucleo/mapasfacil_nucleo/validacao/comparar_pdf.py` |
| Checks saída | `Fase_1_Desktop/nucleo/mapasfacil_nucleo/validacao/saida.py` |
| Job ArcMap | `Fase_1_Desktop/nucleo/mapasfacil_nucleo/scripts/arcpy_job.py` |
| Montar payload T1 | `Fase_1_Desktop/nucleo/mapasfacil_nucleo/motores/minimapa_job.py` |
| Template | `shared/templates/Dinamica_retrato.mxd` |
| MANIFEST | `shared/templates/MANIFEST.json` |
| Smoke | `ferramentas/smoke_m9_harmonia.py` |
| Fechar M2 | `ferramentas/fechar_m2_windows.ps1` |
| Inspecionar MXD | `ferramentas/inspecionar_mxd_arcpy.py` |

---

## 6. Prompt sugerido para Claude (copiar à tarde)

```text
Estou no repo mapas-facil (Windows + ArcMap 10.8). Quero reduzir o diff raster da
Dinâmica 2026 de ~81% para < 0,3% contra Referencias_IMAP/Mapas/01/Dinamica_2026.pdf.

Leia docs/paridade-visual-harmonia.md e docs/m9-conformidade-harmonia.md.

Estou na Fase [N]. Última medição: [X]% diff. Hard falhas: [lista].

Execute o loop da seção 3: implemente o ajuste da Fase [N], rode smoke_m9_harmonia.py
na pasta Harmonia, e me diga o novo diff % e o que fazer na próxima fase.
```

Substitua `[N]` e `[X]` pelo progresso do dia.

---

## 7. O que NÃO fazer

- Perseguir 0,3% no PDF **nativo** (matplotlib).
- Marcar M9/I2 como fechado com diff &gt; 0,3%.
- Empacotar instalador (M10) antes da Harmonia passar.
- Editar MXD sem `chaves_mxd.py limpar` antes do commit.
- Usar `replaceDataSource` / `Describe` em shapefile (trava no ArcPy desta máquina).
- Atacar os 19 mapas antes de fechar **um** (Dinâmica 2026).

---

## 8. Critérios de fechamento (checklist)

- [ ] `smoke_m9` exit 0 com `diferenca_pct <= 0.3` no `*_arcmap.pdf`
- [ ] Checks HARD verdes no relatório (incl. H10)
- [ ] S11 verde (sem texto herdado)
- [ ] `quebradas: []` no MXD gerado
- [ ] Documentação atualizada (`m9-conformidade-harmonia.md`, F1-13 I2/V3)
- [ ] `git commit` + push `main`

---

## 9. Referências cruzadas

- Medição atual M9: [`m9-conformidade-harmonia.md`](m9-conformidade-harmonia.md)
- Motor MXD: [`m2-entrega-harmonia.md`](m2-entrega-harmonia.md)
- Guia Windows §2: [`Fase_1_Desktop/GUIA_WINDOWS.md`](../Fase_1_Desktop/GUIA_WINDOWS.md)
- Plano validação: [`Fase_1_Desktop/planos/09-validacao-conformidade.md`](../Fase_1_Desktop/planos/09-validacao-conformidade.md)
- Trabalho manual Harmonia: [`Referencias_IMAP/MXD/DOCUMENTACAO_MXD_HARMONIA.md`](../Referencias_IMAP/MXD/DOCUMENTACAO_MXD_HARMONIA.md)
