---
name: layout-e-exportacao
description: "Padrões de prancha, formatos de papel A4 a A0, especificações de layout e empacotamento de entrega."
version: 2.0.0
---

# Layout e Exportação de Produtos

## 1. Formatos de Folha (ISO 216)
- **A4**: 210 × 297 mm (mapas individuais de lote, declarações simples).
- **A3**: 297 × 420 mm (padrão preferencial para mapas de imóveis médios e dinâmicas).
- **A2**: 420 × 594 mm (fazendas extensas ou múltiplos módulos).
- **A1**: 594 × 841 mm (visão regional e grandes bacias hidrográficas).
- **A0**: 841 × 1189 mm (projetos especiais de infraestrutura e colonização).

## 2. Padrão de Exportação PDF
- Resolução raster de mapas: 300 DPI para impressão comercial, 150 DPI para conferência em tela.
- Fontes embutidas: fontes padrão sans-serif (Liberation Sans, Arial) com renderização vetorial nítida.
- Metadados PDF limpos de credenciais e nomes de caminhos absolutos do host de compilação.

## 3. Estrutura do Pacote de Entrega (D37)
- Pasta `Mapas/`: arquivos `.pdf` e planilhas `.xlsx` dos quantitativos.
- Pasta `SHP/`: shapefiles consolidados gerados no projeto.
- Arquivo `LEIA-ME.txt`: resumo descritivo das camadas, projeções e conformidade técnica.
