---
name: revisao-visual
description: "Padrões de auditoria visual, legibilidade, colisão de elementos e conformidade com LGPD."
version: 2.0.0
---

# Revisão Visual e Proteção de Dados

## 1. Verificações Geométricas em Coordenadas de Página (mm)
- **S21**: Nenhuma caixa de texto ou elemento decorativo deve cobrir a linha perimetral do imóvel.
- **S22**: Todo elemento visual deve respeitar a margem de segurança da folha (mínimo 5 mm da borda).
- **S23**: Todos os símbolos e hachuras exibidos na legenda devem existir de fato no mapa principal.
- **S24**: O minimapa de localização deve exibir claramente o polígono ou ponto do centroide do imóvel.
- **S25**: Sobreposição entre caixas de texto e tabelas deve ser corrigida com deslocamento ou redução tipográfica.

## 2. Conformidade LGPD (Privacidade Estrita)
- **Varredura PII**: Varredura prévia de CPF, CNPJ e nomes completos de pessoas físicas.
- **Tarjamento Opaco**: Retângulos pretos opacos (`draw_rect(fill=(0,0,0))`) devem ser desenhados sobre qualquer bounding box contendo dados pessoais antes de enviar imagens para modelos de visão externos.
- Nunca enviar CPFs em prompts, parâmetros de tools ou relatórios compartilhados.
