# Validação Windows 2026-08-10 — suítes verdes, auditoria ArcPy 21/21, CI corrigido, M10 reproduzido

Rodada neste **PC Windows + ArcMap 10.8** (mesma máquina do handoff). Sem interação do dono:
rodou tudo o que era possível sem os dados gitignored da Aruanã (`Testes/` — não existem neste
PC), corrigiu o CI vermelho, validou os templates com o ArcPy real e reproduziu o instalador.

## O que foi encontrado e corrigido

### CI do `main` estava vermelho (3 runs falhos)

| Run | Data | Falhas |
|---|---|---|
| `30486988567` (f28791c → templates série) | 2026-07-29 | `test_aviso_template_sem_sha256` + `test_montar_pdf_nativo_com_template_a_preparar` |
| `31028862211` (6306ee3) | 2026-08-05 | `test_aviso_template_sem_sha256` |
| `31397223747` (fix do teste) | 2026-08-10 | `test_doctor_cli_json` — PyMuPDF novo imprime o deprecation do `fitz` **no stdout**, poluindo o JSON do `doctor --json` |

**Causa raiz 1:** o commit que preparou os 25 templates `.mxd` (`aaa97e0`) pôs **todos** com
`status: pronto` e `sha256` — e o teste `test_aviso_template_sem_sha256` assumia que
`tipologia_paisagem` ainda estava sem sha256 (caso `a_preparar`). O teste virou falso negativo.

**Causa raiz 2:** o CI instala PyMuPDF recente, que emite `warning: The fitz API is deprecated`
direto no stdout ao `import fitz` — o `doctor --json` (e qualquer CLI que imprima JSON) ficava
com o JSON poluído e `json.loads` quebrava.

**Correções:**
1. `nucleo/tests/test_mapspec_validar.py` monkeypatcha `_template_ids` / `_templates_por_id`
   para simular um template sem `sha256` — o caso `AG-030` continua coberto sem depender do
   estado mutável do MANIFEST. (O teste da galeria já havia sido corrigido no commit `6306ee3`.)
2. Todos os módulos do núcleo trocaram `import fitz` por `import pymupdf as fitz` (nome novo,
   sem warning): `validacao/{saida,comparar_pdf,anatomia}.py`, `workspace/recibo_car.py`,
   `agente/visao/pdf.py`, `analise/executar.py`.

### Suítes locais (venv do núcleo + pnpm)

| Suíte | Resultado |
|---|---|
| `pytest -q` (núcleo, anel 1) | **521 passed** em 168 s |
| CI GitHub Actions (`nucleo.yml`) | **verde** (run `31399588694`, 2026-08-10) |
| `pnpm test` (app) | **27 arquivos, 180 passed** em 14 s |
| `pnpm typecheck` | limpo |
| `pnpm build` | renderer + electron ok |
| `python -m mapasfacil_nucleo doctor` | ArcMap 10.8 encontrado, licença Available, `Pronto para MXD: True` |

## Auditoria dos templates com ArcPy real (W3)

`ferramentas/auditar_templates_mxd.ps1 -IncluirDinamicaRetrato` (Python 2.7 do ArcGIS 10.8,
`inspecionar_mxd_arcpy.py` em cada `.mxd`):

```
TOTAL=21 PRONTOS=21 PENDENTES=0
```

- **21/21 `pronto_b1: True`**, zero links quebrados de elemento (`codigo 0` em todos).
- Camadas `quebradas` > 0 em 20 dos 21 é **esperado**: os templates apontam para a pasta de
  dados do job; T1/T2 substitui por `findAndReplaceWorkspacePaths` na geração.
- **Observação registrada:** os templates paisagem (Alertas, Embargos, TI, UC, Tipologia,
  Terras Indígenas) têm data frame `MAPA` em **EPSG:3857** (Web Mercator) — conferido contra o
  MXD-modelo original do acervo (`Referencias_IMAP/MXD/`), o 3857 é **herança fiel do modelo
  do Julio**, não defeito introduzido na clonagem. Os retrato são todos EPSG:31982 (UTM 22S).
- MANIFEST 25/25 ids apontam para arquivo existente (alguns `.mxd` servem 2 ids, ex.
  `Tipologia.mxd` ↔ `tipologia_paisagem` + `serie_tipologia`).

## Smoke M9 com o motor ArcPy de ponta a ponta

Sem a pasta da Aruanã, o smoke oficial (W5) não roda. Como exercício real do motor T1
(ArcPy) montou-se um workspace descartável em `tmp/` (gitignored) com os shapes do acervo
03 (`Referencias_IMAP/Mapas/03/Arquivo Processado (11)/`) + recibo CAR de fixture, e rodou:

```powershell
python ..\..\ferramentas\smoke_m9_harmonia.py --pasta C:\GIS\mapas-facil\tmp\ws_m9
```

`output/m9_smoke_relatorio.json`:

| Item | Resultado |
|---|---|
| Motor | `arcpy` (T1), ArcMap 10.8, licença Available |
| Artefatos | `Dinamica_2026_MapasFacil_M9.mxd` (28 MB) + `.pdf` nativo + `_arcmap.pdf` |
| Checks HARD | **6/6 verdes** (H01–H03, H06, H09, H10) + S11 (sem texto herdado) |
| MXD gerado | `broken: []`, `quebradas: 0`, `relative_paths: true` |
| Diff raster | 82,1% (soft B09/A01 vermelhos) — **esperado**: baseline é da Harmonia e os
  dados são de outro imóvel; diff só é honesto com o mesmo dado |

O critério **I3 (`.mxd` abre sem `!`)** foi exercitado localmente no ArcPy: o MXD gerado
abre sem link quebrado e com caminhos relativos. A confirmação em **outro** PC continua
manual, mas a base estrutural está verificada.

## M10 — instalador reproduzido do repo

```powershell
pnpm dist
```

| Item | Resultado |
|---|---|
| Sidecar PyInstaller | `nucleo/dist/mapasfacil-nucleo/mapasfacil-nucleo.exe` (onedir) — `doctor` roda: `Pronto para MXD: True` |
| electron-builder NSIS | `release/MapasFacil-Setup-0.5.2.exe` — **144.097.484 bytes** (144 MB) |
| `latest.yml` | gerado (electron-updater) |
| Assinatura | `signtool verify /pa` → **"No signature found"** — Authenticode continua pendente (depende de certificado, fora do alcance sem o dono) |
| `sha256.txt` | atualizado para o hash do exe reconstruído (75307597…D5BBE086F); `release/` é gitignored — o artefato e o checksum sobem na Release do GitHub, não no repo |

## O que NÃO deu para fazer (depende do dono ou de outro PC)

| Item | Por quê |
|---|---|
| Smoke W5 na Aruanã (`smoke_serie_mxd.py`) | `Testes/01_analise_04_Julio/` (gitignored) não existe neste PC; dado de proprietário, não versionável |
| Paridade raster < 0,3% (M9) | precisa da pasta real da Harmonia + dados iguais entre motores |
| Instalar em PC limpo (M10→M11) | outro PC, sem Python pré-instalado |
| Authenticode (R25) | certificado de assinatura |

## Ordem do que resta (inalterada)

**M9 (paridade/cobertura da série) → M10 (assinatura + PC limpo) → M11 (piloto)** — nada
neste repositório bloqueia a continuação; o CI volta a ficar verde com este commit.