# Mapas/06 — Divisão de talhões (Fazenda Macaré) — referência de estilo do B1

`.mxd` + PDF de um mapa de **divisão de talhões** da Fazenda Macaré, A4 **retrato**, escala
**1:50.000**.

> Este acervo estava em `Referencias_IMAP/OneDrive_1_25-07-2026 (1)/Divisão de talhões e mapa
> retrato/` até 2026-07-26, quando o material do OneDrive foi dissolvido no esquema
> `Mapas/NN/`. Referências antigas a esse caminho estão desatualizadas.

## Por que ele está no repositório

Foi a peça que **destravou o B1** (preparação do template Dinâmica no ArcMap). Comparando este
`.mxd` com `Dinamica_2026.mxd`, ficou claro que o template da Harmonia **já tinha** os elementos
que pareciam faltar — título e rótulo do imóvel como caixas balão — só que sem nome canônico.
A conclusão virou a estratégia de "reaproveitar elemento existente em vez de criar", implementada
em [`../../../ferramentas/normalizar_mxd_arcpy.py`](../../../ferramentas/normalizar_mxd_arcpy.py).

Contexto completo: [`../../../Fase_1_Desktop/nucleo/docs/bloco-b-sem-arcmap.md`](../../../Fase_1_Desktop/nucleo/docs/bloco-b-sem-arcmap.md).

## Conteúdo

```
MXD/Divisao_de_talhoes.mxd
PDF/Divisao_de_Talhoes.pdf      A4 retrato, 1 página
```

Elementos identificados no `.mxd`:

| Elemento | Valor |
|---|---|
| Título | `Divisões dos Talhões` |
| Rótulo do imóvel | `Fazenda Macaré` |
| Escala (texto do bloco) | `<bol>Escala:</bol> 1:50.000` |
| Camadas de talhão | `Talhão 1` … `Talhão 11` |
| Área total | `Área total - Lote 34` |
| Campos usados | `AREA_HA`, `CRUZA_AREA`, `MUNICIPIO_` |
| Limite municipal | `Limite municipal` sobre `lml_municipio_a` |

O `<bol>…</bol>` no texto da escala é o mesmo markup de negrito do ArcMap que o bloco de
metadados da Harmonia usa — confirmando que o padrão de `TEXT_ELEMENT` é comum ao escritório,
não específico de um mapa. Ver
[`../../../planos/01-padrao-imap-harmonia.md`](../../../planos/01-padrao-imap-harmonia.md).

## Limites

- **Não é a fonte da verdade visual** — é retrato, mas de outra família de mapa (talhões, não
  Dinâmica). O gabarito continua sendo [`../01/`](../01/).
- Fontes apontam para `C:\Users\Usuario\Downloads\Macare\Talhoes` e `C:\VSCODE\talhoes`.
- Chaves de API zeradas por placeholder.
