# M9 — Conformidade Harmonia (entrega 2026-07-27)

Marco que mede se o gerador reproduz a série IMAP da Harmonia com os 14 checks HARD e paridade
visual contra `Referencias_IMAP/Mapas/01/`.

## O que foi entregue neste commit

| Item | Estado |
|---|---|
| Validador de saída (`validacao/saida.py`) | **H01, H02, H03, H06, H09, H10, S11** |
| `mapa.gerar` compara baseline no **PDF ArcMap** (`*_arcmap.pdf`) quando T1 gera | **feito** |
| Smoke automatizado | `ferramentas/smoke_m9_harmonia.py` |
| Orquestração Windows | `ferramentas/fechar_m9_windows.ps1` |
| Relatório JSON | `output/m9_smoke_relatorio.json` + `Mapas/*_relatorio_m9.json` |
| Testes anel 1 | `tests/test_validacao_saida.py` |

## O que ainda **não** fecha o M9 do roadmap

O roadmap ([F1-12 §M9](../Fase_1_Desktop/planos/12-roadmap.md)) exige:

- 19 mapas da série em &lt; 10 min
- 100% dos 14 HARD em todos os mapas
- Diff raster &lt; **0,3%** contra os PDFs-modelo
- `.mxd` abrindo em outro PC (I3)
- S11 verde em todos

Hoje só o template **`dinamica_retrato`** está `status: pronto` no MANIFEST; os outros 4 modelos da
galeria estão `a_preparar`. A série completa fica bloqueada até M2 repetir para cada MXD.

### Medição na pasta Harmonia (Julio Barbosa, 2026-07-27)

Smoke T1 com ArcMap 10.8:

| Comparação | Diff raster | Passa 0,3%? |
|---|---|---|
| Baseline vs baseline (sanidade) | 0,0% | sim |
| PDF ArcMap gerado vs `Dinamica_2026.pdf` | **~81%** | **não** |
| PDF nativo vs baseline | **~82%** | **não** |

A diferença é real (layout, basemap, tabela, textos) — não é bug do comparador. O PDF nativo
(matplotlib) nunca será paridade cartográfica; o caminho de medição correto é o `*_arcmap.pdf`.

Checks HARD medidos no PDF ArcMap (T1, `quebradas: []`, smoke 2026-07-27):

- **H01, H02, H03, H09, S11** verdes
- **H06** não medido quando `escala: auto` no MapSpec
- **H10** falha — rótulo `Fonte` ausente no texto extraído do PDF ArcMap
- **B09** falha — diff 81,34%

## Como rodar

```powershell
# Com pasta Harmonia local:
powershell -ExecutionPolicy Bypass -File ferramentas\fechar_m9_windows.ps1 `
  -Harmonia "C:\Users\...\Analise_de_área-Julio Barbosa_ 4_Harmonia"

# Só smoke:
Fase_1_Desktop\nucleo\.venv\Scripts\python.exe ferramentas\smoke_m9_harmonia.py --pasta "...\Harmonia"
```

## Critério honesto de fechamento

| Checklist | Marcação |
|---|---|
| F1-13 V3 (smoke visual) | `[~]` infra + medição documentada |
| F1-13 I1–I3 (Bloco I) | `[ ]` / `[~]` — diff e série bloqueiam |
| Roadmap M9 | **parcial** — pipeline pronto, paridade cartográfica pendente |

Próximo passo técnico para reduzir o diff: seguir o roteiro fase a fase em
[`paridade-visual-harmonia.md`](paridade-visual-harmonia.md) (basemap, metadados, tabela no layout ArcMap).

## Arquivos tocados

- `Fase_1_Desktop/nucleo/mapasfacil_nucleo/validacao/saida.py`
- `Fase_1_Desktop/nucleo/mapasfacil_nucleo/motores/gerar.py` — baseline no PDF ArcMap
- `ferramentas/smoke_m9_harmonia.py`, `ferramentas/fechar_m9_windows.ps1`
