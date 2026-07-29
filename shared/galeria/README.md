# Galeria de modelos

Catálogo determinístico de modelos de mapa (F1-15). Cards `tipo_execucao: mapspec` usam o mesmo
`galeria.montar_mapspec` na UI e no agente. O card especial `analise_de_area` chama
`analise.executar`, que monta e valida internamente os 20 MapSpecs da série.

## Arquivos

| Arquivo | Função |
|---|---|
| `modelos.json` | Catálogo (`galeria_version` + modelos) |
| `schema.json` | JSON Schema do catálogo |
| `previews/<id>.png` | Preview real exportado de `Referencias_IMAP/Mapas/01/` |

## Como adicionar um modelo

1. O template precisa existir no MANIFEST. SHA real e `status: pronto` são obrigatórios quando
   o card pede `mxd`; saídas PDF/PNG/XLSX nativas não dependem do arquivo ArcMap.
2. Acrescente o item em `modelos.json`. **Não** incremente `galeria_version` só por modelo novo.
3. Gere `previews/<id>.png` a partir de um PDF real do acervo (lado maior ≤ 1024 px, ≤ 300 KB).
4. Defina `tipo_execucao: mapspec` e acrescente caso em `nucleo/tests/test_galeria.py` —
   `montar_mapspec` passa em `mapspec.validar`.
5. Campo novo no MapSpec? Pare: isso é mudança de contrato em `planos/02-mapspec-contrato.md`.

## Status em runtime

Calculado para `saidas_pedidas` (nunca gravado no JSON):
`pronto` · `parcial` · `faltam_dados` · `indisponivel`. Somente a saída `mxd` aplica o gate do
template ArcMap.
