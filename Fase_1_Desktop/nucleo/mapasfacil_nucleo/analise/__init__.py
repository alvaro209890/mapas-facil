"""Análise de área — a série completa de mapas a partir só do polígono do imóvel.

O contrato desta pasta é o da meta `planos/GOAL_analise_de_area.md`: o usuário
entrega **um shapefile** e o sistema descobre o resto (município, CAR, camadas
temáticas, imagem de fundo), monta a série de mapas do padrão IMAP/Harmonia e
valida cada PDF contra o modelo correspondente do acervo.

Módulos:

- `identidade` — quem é o imóvel (município + registro no CAR), sem perguntar;
- `preparar` — materializa as camadas da análise no workspace, já recortadas;
- `serie` — as receitas dos mapas: uma por PDF-modelo;
- `executar` — roda a série, compila o PDF único e mede a anatomia.
"""
