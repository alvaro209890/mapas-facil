# Fixtures compartilhadas

Artefatos pequenos usados pelos testes do núcleo e, no futuro, pelo CI da Fase 2.

| Pasta | Conteúdo |
|---|---|
| `mapspecs/` | exemplo **canônico válido** (`dinamica_2026_canonico.json`). Fixtures inválidos ainda não versionados. |

O fixture completo da Harmonia (shapefiles reais) fica **fora** do repositório público —
veja `Fase_1_Desktop/planos/10-testes-e-qa.md`. Os testes do anel 1 usam shapefiles sintéticos
em `tmp_path` (`tests/helpers_fixtures.py`).
