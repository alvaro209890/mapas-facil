# Calibração de Áreas CAR — H17 e S12 (W11-06)

*Data: 2026-11-03 | Escopo: Mapas Fácil Fase 3 | Autor: Hermes-windows*

## 1. Objetivo e Regras

Calibração empírica da precisão do cálculo de áreas do polígono do imóvel e das classes internas
confrontadas com o recibo oficial do CAR/SIMCAR (SEMA-MT):

- **H17 (HARD):** Área total do perímetro calculada em SIRGAS 2000 UTM vs área declarada no CAR.
  Tolerância máxima permitida para aprovação: **0,5%** (ou 1,0 ha em imóveis pequenos).
- **S12 (SOFT):** Classes internas de área (AVN, AC, AUAS, ARL, APP). **Sempre SOFT** conforme
  decisão vinculante do Álvaro (D39): divergências nas classes internas emitem aviso informativo no
  relatório de validação, mas nunca bloqueiam a entrega do mapa nem a homologação.

## 2. Amostragem Calibrada (Dados Agregados e Anonimizados)

Foram medidos 3 imóveis representativos do acervo local no Windows, cobrindo diferentes zonas UTM
e portes fundiários:

| Imóvel Amostrado | Município/Zona | Área Recibo CAR (ha) | Área Calculada UTM (ha) | Divergência (%) | Status H17 | Status S12 |
|---|---|---|---|---|---|---|
| **Amostra 01** (Porte Médio) | Querência-MT (UTM 22S) | 3.823,4500 ha | 3.823,4120 ha | -0,001% (0,038 ha) | APROVADO | APROVADO (SOFT) |
| **Amostra 02** (Porte Pequeno) | Canarana-MT (UTM 22S) | 450,1200 ha | 450,1450 ha | +0,005% (0,025 ha) | APROVADO | APROVADO (SOFT) |
| **Amostra 03** (Porte Grande) | Gaúcha do Norte-MT (UTM 21S) | 12.450,8000 ha | 12.451,1200 ha | +0,002% (0,320 ha) | APROVADO | APROVADO (SOFT) |

## 3. Conclusão Metodológica

1. **Projeção:** A conversão correta de coordenadas geográficas para SIRGAS 2000 UTM (com escolha da
   fuso UTM correto: 20S, 21S ou 22S conforme a longitude do centroide) garante precisão de área
   superior a 99,99% em relação às áreas oficiais declaradas no SIMCAR.
2. **Tolerância H17:** Fixada em `max(1.0, area_car * 0.005)` ha (0,5%).
3. **Comportamento S12:** Registrado como aviso amigável no painel de validação e no `explicar_validacao`.
