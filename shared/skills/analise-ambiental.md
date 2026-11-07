---
name: analise-ambiental
description: "Diretrizes e fontes para análise ambiental: CAR, embargos IBAMA/SEMA, terras indígenas e unidades de conservação."
version: 2.0.0
---

# Análise Ambiental e Territorial

## 1. Bases de Dados Oficiais
- **SIMCAR / SICAR**: Limite do imóvel rural, Área de Preservação Permanente (APP), Reserva Legal (RL), Uso Consolidado.
- **IBAMA**: Embargos ambientais federais (polígonos e termos).
- **SEMA-MT**: Embargos estaduais, autorizações de desmate (AEF/ADF), vistorias.
- **FUNAI**: Terras Indígenas (físicas e zonas de amortecimento de 10 km).
- **ICMBio / SEMA**: Unidades de Conservação de proteção integral e uso sustentável.

## 2. Regras de Sobreposição
- Sobreposição total ou parcial com Unidade de Conservação de Proteção Integral impede licenciamento regular sem autorização específica do órgão gestor.
- Zona de Amortecimento (ZA): 10 km de raio em torno de Unidades de Conservação e Terras Indígenas.
- Distâncias mínimas devem ser calculadas em projeção Azimutal Equidistante centrada no imóvel (`+proj=aeqd`).

## 3. Dinâmica Temporal e Marcos Legais
- Marco de 22 de julho de 2008 (Lei Federal 12.651/2012): consolidação de áreas desmatadas.
- Lascas de fronteira menores que 100 m² (0.01 ha) devem ser descartadas como ruído de digitalização.
- Desmate pós-2008 deve segregar áreas autorizadas (com licença/AEF) de desmates sem autorização.
