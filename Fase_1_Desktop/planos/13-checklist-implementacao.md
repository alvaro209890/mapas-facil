# F1-13 — Checklist de implementação (kickoff)

Lista operacional para **começar a escrever código** da Fase 1. Complementa o
[roadmap](12-roadmap.md): aqui cada item é uma tarefa concreta, na ordem segura.

Estado em 2026-07-25: **M0 quase fechado** — planos e acervo reorganizados; falta schema JSON
e manifesto de templates. **M1 é o próximo passo.**

## Pré-voo (antes do primeiro `git commit` de código)

- [x] Repositório em duas fases (`Fase_1_Desktop/`, `Fase_2_Site/`, `planos/` comuns)
- [x] Visão, MapSpec, Harmonia, WFS, dados, segurança documentados
- [x] F1-00…F1-12 escritos; F2 rascunhada (legado marcado)
- [x] Chaves removidas dos `.mxd` (`ferramentas/chaves_mxd.py verificar` = seguro)
- [x] Acervo PDF em `Referencias_IMAP/Mapas/01` (Harmonia) e `02` (Trevisol)
- [x] Receita operacional Harmonia em [`DOCUMENTACAO_MXD_HARMONIA.md`](../../Referencias_IMAP/MXD/DOCUMENTACAO_MXD_HARMONIA.md)
- [x] `shared/schemas/mapspec.schema.json` (draft 2020-12) — validar contra exemplo canônico no 1º PR de código
- [x] `shared/templates/MANIFEST.json` listando templates v1 (sha256 ainda null até preparação)
- [x] Fixture mínima: `shared/fixtures/mapspecs/dinamica_2026_canonico.json`
- [ ] Ambiente de dev: Python 3.12, Node 20+, (opcional) ArcMap 10.8 + QGIS/ogr2ogr

**Critério para declarar M0 fechado:** os três itens abertos acima + validação automatizada do
schema no CI do bloco A + nenhum plano da Fase 1 exigindo backend/site.

---

## Ordem de implementação (M1 → M2…)

### Bloco A — Fundação do núcleo (M1, semana 1)

Faça **nesta ordem**. Nada de Electron ainda.

| # | Tarefa | Onde | Feito |
|---|---|---|---|
| A1 | Scaffold `Fase_1_Desktop/nucleo/` (`pyproject.toml`, pacote, `__main__.py` NDJSON) | nucleo | [x] |
| A2 | `fsguard` + suíte adversária (symlink, `..`, UNC, CON/PRN, escrita fora de `Mapas/MXD/SHP`) | nucleo | [x] |
| A3 | Schema MapSpec + validador (schema + catálogo + invariantes) | shared + nucleo | [x] |
| A4 | `workspace.abrir` / `reindexar` / `inspecionar` (shapefile: CRS, bbox, área UTM) | nucleo | [ ] |
| A5 | Parser do recibo do CAR (CPF descartado na entrada) | nucleo | [ ] |
| A6 | CLI `python -m mapasfacil_nucleo doctor` | nucleo | [x] |
| A7 | Um PDF nativo mínimo (matplotlib) a partir de MapSpec válido + `validacao.json` | nucleo | [ ] |
| A8 | `pytest` anel 1 verde em CI Linux | .github/tests | [x] |

**Saída do bloco A:** sidecar sozinho, sem UI, gera um PDF feio mas válido e rejeita path malicioso.

### Bloco B — Motor `.mxd` (M2, após A)

| # | Tarefa | Ref | Feito |
|---|---|---|---|
| B1 | Preparar **1** template Dinâmica 2026 (relative paths, nomes canônicos, padding T2) | F1-04 | [ ] |
| B2 | Registrar no `MANIFEST.json` + smoke | F1-04 | [ ] |
| B3 | `arcpy_job.py` (py2.7): só API permitida + timeout; payload em arquivo JSON | DOC MXD §5 | [ ] |
| B4 | Materializar homônimos / nomes canônicos em `SHP/` via `ogr2ogr` | F1-04, DOC §6 | [ ] |
| B5 | Extent: bbox do `.shp` (struct) + CRS certo (31982 dinâmica / 3857 temático) | DOC §5 | [ ] |
| B6 | Textos, definition query município, troca de `PICTURE_ELEMENT` da tabela | F1-04 | [ ] |
| B7 | Minimapa: retângulo + linha-guia (núcleo calcula página) | DOC §8 | [ ] |
| B8 | Caminho **patch T2** sem ArcMap (mesmo template) | F1-04 | [ ] |
| B9 | Export PDF 150 dpi + comparar raster com `Mapas/01/Dinamica_2026.pdf` | Mapas/01 | [ ] |

**Saída do bloco B:** um `.mxd` + `.pdf` da Dinâmica 2026 que abre noutra máquina.

### Bloco C — UI Electron (M3, paralelo a B depois de A)

| # | Tarefa | Feito |
|---|---|---|
| C1 | Scaffold Electron + React (janela, IPC stub) | [ ] |
| C2 | Spawn do sidecar NDJSON + doctor na UI | [ ] |
| C3 | Árvore da pasta + abrir workspace | [ ] |
| C4 | Preview PDF/PNG + lista de artefatos | [ ] |
| C5 | Botão “gerar mapa” determinístico (sem IA) | [ ] |
| C6 | Credential Manager (DeepSeek / SEMA / Planet) | [ ] |

### Bloco D — Agente (M4)

| # | Tarefa | Feito |
|---|---|---|
| D1 | Loop tools tipadas → MapSpec (sem código gerado) | [ ] |
| D2 | Streaming na UI + tool calls visíveis | [ ] |
| D3 | Modo determinístico sem chave | [ ] |
| D4 | Prompt + guard rails (números só de tools) | [ ] |

### Bloco E — Conformidade e resto (M5–M7)

| # | Tarefa | Feito |
|---|---|---|
| E1 | 14 HARD + 11 SOFT verdes na série Harmonia (`Mapas/01`) | [ ] |
| E2 | Diff raster < 0,3% nos modelos medidos | [ ] |
| E3 | Instalador NSIS + PyInstaller onedir | [ ] |
| E4 | Piloto com técnico real | [ ] |

---

## Regras de ouro (colar no PR template)

1. **Nunca** `Describe` / `replaceDataSource` / cursores / `Project_management` no ArcPy desta família de PCs — hang. Ver DOC MXD §5.
2. Geometria → `ogr2ogr`. Extent → bytes do `.shp`. Fonte → homônimo + `findAndReplaceWorkspacePaths`.
3. Data frame Dinâmica = UTM 22S; temático = Web Mercator. Bbox errado = mapa em branco.
4. Não remover camada “dona” de entrada de legenda (Santa Clara = AUAS; Serra Verde = AC/AVN) até o template estar normalizado — ver [F1-04](04-motor-mxd.md#donos-de-legenda-e-homônimos-do-acervo).
5. IA não gera código. Só MapSpec validado.
6. `chaves_mxd.py limpar` antes de commit que toque `.mxd`.
7. Baseline visual = `Referencias_IMAP/Mapas/01/`, nunca `02/`.

## Leitura obrigatória antes do primeiro PR de código

1. [`../../planos/00-visao-e-duas-fases.md`](../../planos/00-visao-e-duas-fases.md) — D1–D9  
2. [`01-arquitetura.md`](01-arquitetura.md) — três processos, fsguard  
3. [`04-motor-mxd.md`](04-motor-mxd.md) — coração  
4. [`../../Referencias_IMAP/MXD/DOCUMENTACAO_MXD_HARMONIA.md`](../../Referencias_IMAP/MXD/DOCUMENTACAO_MXD_HARMONIA.md) — receita real  
5. Este checklist  

## Onde marcar progresso

Atualize as caixas `[ ]` → `[x]` neste arquivo **no mesmo PR** que fecha a tarefa.
O [roadmap](12-roadmap.md) só muda de marco quando o critério de saída do marco inteiro passa.
