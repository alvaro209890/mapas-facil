---
name: operacoes-geo
description: "Procedimentos e regras para operações geométricas vetoriais: clip, dissolver, interseção e cálculo de área."
version: 2.0.0
---

# Operações Geométricas Vetoriais

## 1. Integridade Topológica com Shapely
- Polígonos devem possuir anel externo em sentido horário (clockwise) e furos em sentido anti-horário.
- Sempre aplicar `.buffer(0)` em polígonos intermediários para corrigir auto-interseções e nós duplicados.
- Ao realizar uniões ou dissoluções de múltiplas feições, usar `unary_union` de `shapely.ops` para garantir eficiência e evitar artefatos topológicos.

## 2. Recorte e Interseção (Clip & Intersect)
- O recorte (`geo_recortar`) extrai a porção geométrica contida estritamente dentro da máscara delimitadora.
- Geometrias resultantes de dimensão inferior (linhas ou pontos resultantes de toque de borda) devem ser descartadas quando a camada for de polígonos.
- Feições vazias (`geom.is_empty`) não devem ser gravadas na camada final.

## 3. Precisão e Unidades
- Cálculos de área em hectares (`ha`): dividir área em m² por 10.000, arredondando para 4 casas decimais.
- Cálculos em quilômetros quadrados (`km²`): dividir m² por 1.000.000.
