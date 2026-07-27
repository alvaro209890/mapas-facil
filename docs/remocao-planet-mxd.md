# Remoção do basemap Planet quebrado nos MXDs

Data: 2026-07-27  
Máquina: Acer Aspire A515-45 (Windows + ArcMap 10.8)  
Repo: `alvaro209890/mapas-facil`

## Problema

Com a chave Planet zerada (placeholder `PLAK_CHAVE_REMOVIDA_VER_FERRAMENTAS_`), o ArcMap
abre o diálogo **GIS Server Connection** (usuário/senha) em todo `.mxd` que ainda aponta
para `tiles.planet.com` / `api.planet.com`. Cancelar à mão em dezenas de arquivos não escala.

## Solução em 2 passos

### 1) Remover a camada Planet via ArcPy

```bat
C:\Python27\ArcGIS10.8\python.exe ferramentas\remover_planet_mxd_arcpy.py ^
  Referencias_IMAP\MXD Referencias_IMAP\Mapas shared\templates --in-place --todos ^
  -o relatorio_remover_planet_final.json
```

- Remove camadas cujo nome/URL contém marcadores Planet (`planet`, `plak_`, `global monthly`, …).
- Trabalha em cópia ASCII sob `%TEMP%` (evita crash com nomes acentuados).
- Opcional em paralelo: `powershell -File ferramentas\fechar_dialogs_gis.ps1`

### 2) Abrir no ArcMap, fechar a janelinha e **salvar na GUI**

Só remover a camada não basta: o documento ainda carrega conexões mortas até ser
aberto no ArcMap, as janelas canceladas e o arquivo **salvo dentro do ArcMap**.
Na próxima abertura a janelinha do Planet não volta.

```powershell
powershell -ExecutionPolicy Bypass -File ferramentas\salvar_mxd_gui.ps1 `
  -TimeoutSec 45 -Relatorio relatorio_salvar_mxd_gui.json
```

Fluxo por arquivo: abrir → cancelar `GIS Server Connection` → esperar janela do ArcMap →
Ctrl+S → fechar.

## Escopo processado

| Pasta | Conteúdo |
|---|---|
| `Referencias_IMAP/MXD/` | mapas de referência |
| `Referencias_IMAP/Mapas/03–06/MXD/` | lotes organizados |
| `shared/templates/` | template `Dinamica_retrato.mxd` |

Total: **62** `.mxd`.

## Resultados (esta rodada)

| Etapa | Resultado |
|---|---|
| Remoção ArcPy (lote geral) | 50/62 ok; 12 falhas por encoding (nomes com acento) |
| Remoção ArcPy (reprocesso acentuados) | **12/12 ok** (ex.: `Unidade_de_Conservação`, `Dinâmica_*`, `DINÂMINCA_*`) |
| Salvamento GUI | **62/62 ok**, 55 abriram diálogo na 1ª vez, 0 falhas |

Relatórios versionáveis:

- `relatorio_remover_planet_final.json` — lote ArcPy
- `relatorio_salvar_mxd_gui.json` — lote abrir/salvar GUI (`ok=62/62`)
- `relatorio_salvar_mxd_gui.log` — log texto do lote GUI

Após o salvamento na GUI, a reabertura dos `.mxd` tratados **não** deve mais pedir
login Planet (validado em amostragem: `Untitled`, `Dinamica_2026`, `DINAMICA_2002`).

## O que NÃO foi feito de propósito

- **Não** embutir `SEMA_WMS_AUTHKEY` / chave Planet real nos `.mxd` (repo público).
- Camadas WMS SEMA com placeholder `5ema4key-…` e WMS SIGEF/i3Geo podem continuar
  existindo; o alvo desta operação é só o diálogo do **Planet**.
- Basemap SEMA/Esri automático via ArcPy 10.8 é limitado; o objetivo primário é abrir
  sem a janelinha Planet.

## Scripts

| Script | Função |
|---|---|
| `ferramentas/remover_planet_mxd_arcpy.py` | remove camadas Planet (Python 2.7 / ArcMap) |
| `ferramentas/fechar_dialogs_gis.ps1` | cancela diálogos GIS Server Connection |
| `ferramentas/salvar_mxd_gui.ps1` | abre → fecha diálogos → salva → fecha (lote) |

## Como repetir num MXD novo

1. Rodar `remover_planet_mxd_arcpy.py` no arquivo/pasta.
2. Rodar `salvar_mxd_gui.ps1` (ou abrir no ArcMap, Cancel, Salvar).
3. Conferir: reabrir o `.mxd` — não deve pedir login Planet.
