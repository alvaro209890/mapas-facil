# F1-00 — Visão e escopo do app desktop

## O que é

Um aplicativo **nativo Windows** onde você conecta uma pasta e conversa com um agente de
engenharia florestal. O modelo mental é o do Cursor / Codex / Claude Code, trocando código por
cartografia: o agente **lê a pasta**, entende o imóvel, consulta os portais da SEMA e entrega os
mapas da série IMAP.

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Mapas Fácil                                          Fazenda Harmonia  │
├──────────────┬──────────────────────────────────┬───────────────────────┤
│ PASTA        │  CHAT                            │  MAPA (preview)       │
│              │                                  │                       │
│ 📁 Harmonia  │  você                            │  ┌─────────────────┐  │
│ ├ Arquivo…   │  faz a Dinâmica 2026 dessa pasta │  │                 │  │
│ │ ├ ATP.shp  │                                  │  │  Dinâmica 2026  │  │
│ │ ├ AVN.shp  │  Ana                             │  │                 │  │
│ │ ├ AC.shp   │  ▸ li_recibo_car   CAR - Emi…pdf │  │   [ preview ]   │  │
│ │ └ AUAS.shp │    Fazenda Harmonia · Vila Rica  │  │                 │  │
│ ├ CAR….pdf   │    MT102042/2017 · 3.823,90 ha   │  │                 │  │
│ ├ SHP/       │  ▸ indexar_pasta   4 shapefiles  │  └─────────────────┘  │
│ └ Mapas/     │  ▸ consultar_sema  tipologia ok  │                       │
│              │  ▸ criar_mapa      dinamica_retr │  ✓ 14 HARD   ⚠ 1 SOFT │
│ ⚙ ArcMap 10.8│  ▸ gerar           1:60.000      │                       │
│ ✓ DeepSeek   │                                  │  Dinamica_2026.mxd    │
│              │  Pronto. 3 arquivos em Mapas/.   │  Dinamica_2026.pdf    │
│              │  Aviso: 7,4 ha de AUAS fora da   │  Quantitativos.xlsx   │
│              │  ATP — confere o shape?          │                       │
│              │                                  │  ◀ v1  v2  v3 ▶       │
│              │  [ escreva aqui…            ] ▶  │                       │
└──────────────┴──────────────────────────────────┴───────────────────────┘
```

## Por que desktop, e por que primeiro

| Razão | Detalhe |
|---|---|
| **O `.mxd` só existe no Windows** | `arcpy` é Windows-only e exige licença ArcGIS. Rodar em servidor implicaria licença de servidor — custo proibitivo |
| **Os dados já estão lá** | os shapefiles do CAR, o recibo, os projetos anteriores. Subir tudo para a nuvem é atrito e risco |
| **A SEMA bloqueia IP estrangeiro** | o PC do usuário está no Brasil; resolve de graça um problema que derrubou o backend do NexoGeo em nuvem |
| **O NexoGeo falhou exatamente aqui** | lá o `.mxd` ficou como "quando ArcMap estiver disponível" e nunca saiu do papel. Inverter a prioridade é a lição |
| **Valida o produto sem infraestrutura** | zero servidor, zero conta, zero custo recorrente para começar |

## O agente

Não é um "gerador de mapas com chat em cima". É um **agente de engenharia florestal** que:

- lê o recibo do CAR e sabe o que cada número significa;
- reconhece ATP, AVN, AC, AUAS, APP, ARL pelos nomes e pelo conteúdo;
- sabe que área se calcula em UTM, e qual zona usar para aquele imóvel;
- consulta os portais da SEMA para tipologia, embargo, UC, TI e uso consolidado;
- percebe que a soma das sub-áreas não fecha com a ATP e **avisa antes de gerar o mapa**;
- sabe que o mapa de Terras Indígenas precisa da distância até a TI mais próxima;
- olha um print de um mapa antigo e reproduz o mesmo layout com os dados novos;
- e conversa sobre tudo isso em português, com números em hectare.

Modelo: **DeepSeek V4 Pro**, com chave do próprio usuário. Detalhe em
[`06-agente-eng-florestal.md`](06-agente-eng-florestal.md).

## Entregáveis por mapa

| Arquivo | Motor | Sempre? |
|---|---|---|
| `<Nome>.mxd` | ArcPy, ou patch de template quando não há ArcMap | quando `mxd` está em `saidas` |
| `<Nome>.pdf` | ArcMap, ou renderizador nativo Python | sempre |
| `<Nome>.png` | preview | sempre |
| `Quantitativos.xlsx` | openpyxl | quando há tabela |
| `validacao.json` | validador | sempre |

## Escopo da v1

### Dentro

- [ ] Conectar pasta, indexar e observar mudanças
- [ ] Chat com streaming, ferramentas visíveis e histórico por projeto
- [ ] Ler recibo do CAR, `.zip` do SIMCAR e shapefiles
- [ ] Consultar WFS/WMS de SEMA, IBAMA, FUNAI, MapBiomas, INCRA, IBGE
- [ ] Gerar a série IMAP no perfil Harmonia: Dinâmica (retrato) e temáticos (paisagem)
- [ ] `.mxd` com caminhos relativos e camadas materializadas ao lado
- [ ] Troca automática de definition query de município e UF
- [ ] Minimapa com retângulo recentrado e linha-guia
- [ ] Tabela de quantitativos como PNG de alta resolução + `.xlsx`
- [ ] Edição conversacional com versionamento
- [ ] Modo "olha esse print/zip e faz igual"
- [ ] Validação de conformidade com bloqueio em falha HARD
- [ ] Doctor do ambiente
- [ ] Modo determinístico sem IA
- [ ] Instalador Windows

### Fora

| Fora da v1 | Motivo |
|---|---|
| Linux e macOS | `arcpy` não existe; o núcleo roda, mas sem `.mxd` |
| ArcGIS Pro como caminho primário | Pro 3.x **não salva `.mxd`** — sem volta para o ArcMap |
| Edição de geometria | é trabalho de GIS; usa-se ArcMap ou QGIS |
| Pareceres e laudos | escopo do NexoGeo e do GeoForest Oráculo |
| Escrita no SIMCAR | domínio do GeoForest Oráculo |
| Login em portal da SEMA | a sessão técnica é única e derruba o usuário do navegador |
| Colaboração multiusuário | é a Fase 2 |
| Cobrança | depois da validação |

## Critérios de aceite da Fase 1

1. **Análise completa da Harmonia** (a pasta real, com o CAR real) produz os 19 mapas em menos
   de 10 minutos, contra os dois dias do trabalho manual.
2. Os PDFs gerados batem com os PDFs-modelo por comparação de raster, diferença < 0,3%.
3. O `.mxd` gerado abre no ArcMap **de outro PC**: ou todas as camadas resolvem, ou resolvem com
   um único passo óbvio de vinculação da pasta `SHP/`.
4. Nenhum texto de análise anterior sobrevive no mapa (check `S11`).
5. Sem ArcMap na máquina, o app ainda entrega `.mxd` (por patch de template) + PDF nativo, e diz
   claramente o que muda.
6. Sem internet, o app gera o mapa com os shapes locais e o cache, com aviso de idade.
7. Sem chave DeepSeek, o modo determinístico gera a série a partir do template.

## O que este desenho deliberadamente não faz

- **Não** manda dado do cliente para servidor nenhum. As três exceções (prompt, consulta
  geoespacial, tiles) estão listadas e são controláveis.
- **Não** deixa a IA escrever código. O contrato é `MapSpec` declarativo, validado por schema.
- **Não** depende da Fase 2 para nada.
- **Não** tenta ser um SIG. Não desenha, não edita geometria, não faz geoprocessamento — faz
  cartografia de padrão.

## Ordem de leitura dos planos

| # | Documento | Por quê |
|---|---|---|
| 01 | [Arquitetura](01-arquitetura.md) | como as peças se encaixam; leia antes de tudo |
| 04 | [Motor `.mxd`](04-motor-mxd.md) | o coração do produto e a parte mais difícil |
| 06 | [Agente](06-agente-eng-florestal.md) | tools, prompt, guard rails |
| 02 | [UI e workspace](02-ui-chat-e-workspace.md) | a experiência |
| 03 | [Núcleo Python](03-nucleo-python.md) | onde a geo acontece |
| 05 | [Renderizador nativo](05-motor-pdf-nativo.md) | preview e fallback |
| 07 | [Print → mapa](07-visao-print-e-zip.md) | "faz igual a esse aqui" |
| 08 | [Planilhas](08-planilhas-e-relatorios.md) | `.xlsx` de quantitativos |
| 09 | [Validação](09-validacao-conformidade.md) | os checks HARD/SOFT na prática |
| 10 | [Testes](10-testes-e-qa.md) | como se testa isso sem ArcGIS no CI |
| 11 | [Empacotamento](11-empacotamento-instalador.md) | virar `.exe` |
| 12 | [Roadmap](12-roadmap.md) | milestones com checklist |
| 13 | [Checklist de implementação](13-checklist-implementacao.md) | kickoff do código |
