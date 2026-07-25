# Bloco B — o que dá para fazer sem ArcMap

Documentação do progresso do **motor `.mxd`** quando o desenvolvimento roda em Linux/CI
(sem ArcMap nem Python 2.7 do ArcGIS).

Plano de referência: [`../planos/04-motor-mxd.md`](../planos/04-motor-mxd.md)  
Checklist: [`../planos/13-checklist-implementacao.md`](../planos/13-checklist-implementacao.md)

## Resumo (v0.3.2)

| Item | Status | Onde |
|---|---|---|
| B1 — Preparar template no ArcMap | **Automatizado parcialmente** via arcpy scriptado (sem GUI) | `ferramentas/normalizar_mxd_arcpy.py` |
| B2 — `sha256` + offsets no MANIFEST | `dinamica_retrato` com sha256 registrado, `status: parcial` | `motores/manifesto.py`, `ferramentas/registrar_template.py` |
| B3 — `arcpy_job.py` + ponte | Esqueleto | `scripts/arcpy_job.py`, `motores/arcpy_ponte.py` |
| B4 — Materializar homônimos em `SHP/` | Cópia + **ogr2ogr opcional** | `camadas/materializar.py`, `geo/ogr2ogr.py` |
| B5 — Extent / escala | Bbox via metadados + patch float64 | `motores/gerar.py`, `motores/patch_mxd.py` |
| B6 — Textos (slots UTF-16LE) | **Infra pronta** — aguarda offsets no MANIFEST | `motores/patch_mxd.py` |
| B7 — Minimapa | Aguarda os 2 últimos elementos de layout (B1) | — |
| B8 — Patch T2 sem ArcMap | Copia do **template preparado** (`shared/templates/`), não mais do acervo bruto | `motores/patch_mxd.py`, `motores/manifesto.resolver_caminho_preparado` |
| B9 — Comparar PDF com Harmonia | **Infra anel 1** — `validacao/comparar_pdf.py`, NDJSON `validacao.comparar_pdf`, flag `comparar_baseline` em `mapa.gerar` | `validacao/comparar_pdf.py`, `motores/gerar.py` |
| Quantitativos (F1-08) | **Cálculo anel 1** — `quantitativos.calcular`; `.xlsx` pendente | `quantitativos/calcular.py` |
| Doctor | Detecção rápida + `--completo` para sondar arcpy | `doctor.py` |
| `validacao.json` do job | Consolidado em `mapa.gerar` | `motores/gerar.py` |

## B1 automatizado via arcpy — o que deu pra fazer sem tocar na GUI

Descoberta desta rodada: **arcpy.mapping permite renomear** (`.name` é gravável em
`DataFrame`, `Layer`, `TextElement`, `LegendElement`, `PictureElement`,
`MapSurroundElement`) sem abrir a interface do ArcMap — só não permite **criar** elementos
novos. Isso deu para automatizar boa parte do B1 com
[`ferramentas/normalizar_mxd_arcpy.py`](../../../ferramentas/normalizar_mxd_arcpy.py),
sempre trabalhando numa **cópia** (nunca no `.mxd` do acervo):

```powershell
C:\Python27\ArcGIS10.8\python.exe ferramentas/normalizar_mxd_arcpy.py `
  Referencias_IMAP/MXD/Dinamica_2026.mxd shared/templates/Dinamica_retrato.mxd
```

Aplicado automaticamente em `Dinamica_retrato.mxd` (a partir de `Dinamica_2026.mxd`):

- `mxd.relativePaths = True`
- 2 data frames chamados `"Layers"` → `MAPA` (UTM 31982, escala 60.000) e `MINIMAPA`
  (Web Mercator, escolhido por área de extent)
- Camadas: `Fazenda Harmonia`→`PERIMETRO`, `Uso Consolidado`→`AC`, `Limite municipal`→
  `MUNICIPIOS`, `Limite estadual`→`UF` (nas duas ocorrências)
- Texto com conteúdo `<bol>METADADOS IMAGEM</bol>...` → `METADADOS`
- `North Arrow` → `NORTE`; único `PICTURE_ELEMENT` → `LOGO`; maior `LEGEND_ELEMENT` (por
  área) → `LEGENDA`

**O que ficou pendente — exige a GUI do ArcMap** (`arcpy.mapping` não cria elemento novo):

1. Texto `TITULO` e `ROTULO_IMOVEL` — não existem como elementos próprios no acervo (só há
   `"Vila Rica"`, `"MT"` e `"Ano: 2026"` soltos, sem título do imóvel).
2. Confirmar visualmente se a `LEGENDA` escolhida por heurística de tamanho é mesmo a do
   `MAPA` (existe uma segunda, bem menor).
3. Nomear entre os 5 `GRAPHIC_ELEMENT` quais são `MINIMAPA_RETANGULO` e `MINIMAPA_GUIA`.
4. Apontar a imagem de `LOGO` (`sourceImage` vazio no acervo).

Depois desses 4 ajustes manuais, **repetir a normalização e recalibrar os offsets** — a
estrutura binária do `.mxd` muda ao inserir elementos novos, invalidando offsets antigos.

## Bug encontrado e corrigido: `registrar_template.py --dry-run`

`--dry-run` copiava o `.mxd` de teste para `shared/templates/<arquivo>` **antes** de checar
a flag (só pulava a escrita do `MANIFEST.json`). Isso fazia a suíte de testes
(`test_registrar_template_dry_run`) sobrescrever silenciosamente o template real preparado
com o fixture de sentinelas (168 bytes) toda vez que rodava. Corrigido: `--dry-run` agora não
toca em `shared/templates/` — só calcula sha256/offsets do arquivo indicado. Regressão
coberta por `test_registrar_template_dry_run_nao_sobrescreve_template_real`.

## Bug encontrado e corrigido: `copiar_template` usava o acervo bruto, não o preparado

`resolver_caminho_acervo` prioriza `fonte_acervo` sobre `arquivo`, então `copiar_template`
(usado por `gerar_mxd_t2`) sempre copiava `Referencias_IMAP/MXD/*.mxd` (não normalizado),
ignorando qualquer preparação em `shared/templates/`. Nova função
`resolver_caminho_preparado` prioriza o arquivo em `shared/templates/<arquivo>` quando existe
e só cai para o acervo bruto em modo T3 (sem preparação nenhuma).

## Fluxo atual de `mapa.gerar`

```
MapSpec válido
    │
    ├─ materializar_camadas_em (ex.: SHP/)  →  ATP.shp, AVN.shp, AREA_CONSOLIDADA.shp …
    │
    ├─ saidas contém "mxd"
    │     └─ copia Referencias_IMAP/MXD/*.mxd → MXD/<nome_base>.mxd
    │        └─ patch de extent/escala SE o MANIFEST tiver offsets + sentinelas
    │
    └─ saidas contém "pdf"
          └─ renderizador nativo (matplotlib) + validacao.json
```

**Modo T3 implícito:** sem offsets no manifesto, o `.mxd` é cópia fiel do acervo (caminhos
relativos ainda apontam para o template original). O PDF nativo continua sendo a saída confiável
no Linux.

## Módulos novos

```
mapasfacil_nucleo/
  camadas/materializar.py    # nomes canônicos em SHP/
  geo/bbox_shp.py            # bbox do cabeçalho .shp (struct)
  geo/ogr2ogr.py             # reprojeção opcional via ogr2ogr (fallback cópia)
  motores/gerar.py           # orquestra materialização + MXD + PDF
  motores/patch_mxd.py       # cópia template + patch float64 LE
  motores/arcpy_ponte.py     # subprocesso py2.7, payload em MAPASFACIL_JOB_JSON
  scripts/arcpy_job.py       # NUNCA importado pelo núcleo 3.12
  workspace/zip_simcar.py    # listar/extrair ZIP SIMCAR (anti zip-slip)
```

## Métodos NDJSON adicionais

| Método | Descrição |
|---|---|
| `zip.listar` | Lista entradas e `.shp` dentro de um ZIP no workspace |
| `zip.extrair` | Extrai em `_extraido/<nome>/` com proteção zip-slip |
| `template.listar` | Templates do `shared/templates/MANIFEST.json` |
| `template.verificar` | `sha256` do `.mxd` de acervo vs manifesto |

## Preparação de template (B1/B2) — uma vez por template

Ferramentas em [`ferramentas/`](../../../ferramentas/README.md#preparação-de-template-b1b2--requer-arcmap).

1. `inspecionar_mxd_arcpy.py` — diagnóstico do que falta normalizar.
2. `normalizar_mxd_arcpy.py` — aplica automaticamente o que dá pra inferir sem GUI (ver
   seção acima) e lista pendências.
3. Trabalho manual no ArcMap **só para o que sobrou**: 2 textos + 2 gráficos + confirmar
   legenda + apontar logo.
4. `preparar_sentinelas_arcpy.py` — extent/escala sentinela para offsets (só depois do
   passo 3 estar 100% concluído).
5. `registrar_template.py dinamica_retrato` — sha256 + offsets no MANIFEST.
6. Smoke: `doctor --json` + `mapa.gerar` no Windows com ArcMap.

## `doctor` no Windows

Por padrão o `doctor` roda em **modo rápido** (`sondar_arcpy=False`): detecta o executável do
ArcMap sem invocar Python 2.7/arcpy (~60s). Use `doctor --completo` para sondar licença e versão.

O comando define `motor_preferido` (`arcpy` > `patch` > `arcpy_provavel` > `nativo`).
`pronto_para_mxd` exige template com sha256 e (patch pronto ou ArcMap com arcpy sondado).

## ArcPy — o que o usuário final **não** precisa fazer

- O caminho **T2** (patch) + PDF nativo cobre desenvolvimento e CI sem licença ArcGIS.
- **T1** (ArcPy) é referência para paridade máxima com a Harmonia; exige preparação B1 e máquina
  Windows com ArcMap 10.x.
- Exit code **124** após `save()` pode ser normal (trava no cleanup); validar pelo `ExportToPDF`
  seguinte — ver F1-04 §T1.

## Próximos passos técnicos

1. ~~`ogr2ogr` na materialização~~ — feito (opcional, fallback cópia).
2. ~~Slots UTF-16LE para textos no T2~~ — infra em `patch_mxd.py`; falta offsets no MANIFEST.
3. ~~Teste raster B9 contra `Referencias_IMAP/Mapas/01/Dinamica_2026.pdf`~~ — módulo pronto; smoke com PDF nativo Harmonia pendente (motor ainda estrutural).
4. ~~Integrar escolha T1 vs T2 em `doctor`~~ — `motor_preferido` + `arcpy_provavel`.
5. ~~B1 sem GUI~~ — `normalizar_mxd_arcpy.py` fez a parte automatizável.
6. B1 final (GUI, 5-10 min): 2 textos + 2 gráficos + confirmar legenda + logo — ver seção
   acima. Depois disso, calibrar offsets (B2) e o T2 passa a fazer patch de verdade
   (extent/escala/textos), não só cópia.
