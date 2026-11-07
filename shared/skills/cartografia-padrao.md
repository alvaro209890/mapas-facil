---
name: cartografia-padrao
description: "Padrões cartográficos oficiais do escritório IMAP e do Mapas Fácil: enquadramento, margens, escalas e convenções."
version: 2.0.0
---

# Cartografia Padrão do Escritório

## 1. Enquadramento e Margens
- Margem de enquadramento padrão: **15%** (`MARGEM = 0.15`).
- Escalas redondas padronizadas: 1:5.000, 1:10.000, 1:25.000, 1:50.000, 1:100.000, 1:250.000.
- Nunca usar escalas quebradas (ex.: 1:47.382) na prancha final; arredondar para o degrau superior.

## 2. Sistemas de Referência Espacial (CRS)
- Padrão oficial nacional: **SIRGAS 2000** (geodésico EPSG:4674).
- Projeção plana em Mato Grosso:
  - UTM Zona 20S: EPSG:31980 (oeste do estado)
  - UTM Zona 21S: EPSG:31981 (região central e leste)
  - UTM Zona 22S: EPSG:31982 (extremo leste)
- SAD69 (EPSG:4618) deve ser convertido para SIRGAS 2000 via parâmetros oficiais Helmert do IBGE.

## 3. Elementos Obrigatórios na Folha
1. Quadro principal do mapa com grade de coordenadas (UTM ou geográfica).
2. Título claro identificando imóvel, município, estado e tema do mapa.
3. Rosa dos ventos (indicador de Norte) no canto superior ou alinhado à legenda.
4. Escala gráfica e numérica correspondente à projeção do quadro.
5. Legenda com convenções temáticas e cores padronizadas.
6. Bloco de metadados: Datum, Projeção, Responsável Técnico, Data e Fontes das camadas.
7. Minimapa de localização estadual ou municipal destacando o centroide do imóvel.
