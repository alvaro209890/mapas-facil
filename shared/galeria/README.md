# Galeria de modelos

Catálogo determinístico de modelos de mapa (F1-15). A UI e o agente usam **o mesmo**
`galeria.montar_mapspec` — não há caminho paralelo.

## Arquivos

| Arquivo | Função |
|---|---|
| `modelos.json` | Catálogo (`galeria_version` + modelos) |
| `schema.json` | JSON Schema do catálogo |
| `previews/<id>.png` | Preview real exportado de `Referencias_IMAP/Mapas/01/` |

## Como adicionar um modelo

1. O template já precisa existir em `shared/templates/MANIFEST.json` com `sha256` real.
   Sem isso o trabalho é B1/B2, não galeria.
2. Acrescente o item em `modelos.json`. **Não** incremente `galeria_version` só por modelo novo.
3. Gere `previews/<id>.png` a partir de um PDF real do acervo (lado maior ≤ 1024 px, ≤ 300 KB).
4. Acrescente caso em `nucleo/tests/test_galeria.py` — `montar_mapspec` passa em `mapspec.validar`.
5. Campo novo no MapSpec? Pare: isso é mudança de contrato em `planos/02-mapspec-contrato.md`.

## Status em runtime

Calculado (nunca gravado no JSON): `pronto` · `parcial` · `faltam_dados` · `indisponivel`.
