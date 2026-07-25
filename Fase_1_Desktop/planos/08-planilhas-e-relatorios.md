# F1-08 — Planilhas e relatórios

O `.xlsx` de quantitativos é entregável de primeira classe, não um extra. Em toda análise real
ele acompanha os mapas — é o que o cliente abre no Excel e o que alimenta o parecer.

Base: `core/xlsx_builder.py` do NexoGeo, que já padroniza cores institucionais, bordas,
cabeçalho azul, linha de total verde e larguras.

## O cálculo é único

Os quantitativos são calculados **uma vez**, no núcleo, e alimentam três saídas:

```
                    ┌──▶ PNG da tabela  →  PICTURE_ELEMENT do .mxd e do PDF nativo
overlay em UTM  ────┼──▶ MapSpec.tabela  →  contrato, versionado
                    └──▶ .xlsx           →  entregável do cliente
```

Nunca há dois cálculos. Divergência entre o número do mapa e o número da planilha é o tipo de
erro que destrói a confiança do cliente.

### Procedimento

1. Reprojetar todas as camadas para o CRS projetado do `MapSpec` (UTM SIRGAS 2000 da zona do
   centroide — **nunca hardcodada**).
2. Corrigir geometrias inválidas (`make_valid`/`buffer(0)`), registrando quantas.
3. `union` das feições dentro de cada camada — evita contar sobreposição interna duas vezes.
4. Para cada imóvel × cada classe: `intersection`, área em m², ÷ 10.000 = ha.
5. Arredondar para **4 casas** e formatar pt-BR (`3.823,9140`).
6. `TOTAL GERAL` = soma dos valores **já arredondados** (a coluna tem de fechar visualmente).
7. Avisos: sobreposição entre classes, sub-área fora do perímetro, soma que não fecha com a ATP.

O passo 6 parece detalhe e não é: total calculado sobre os brutos difere da soma visível por
centésimos de hectare, e o cliente pergunta toda vez.

## Estrutura do `.xlsx`

| Aba | Conteúdo |
|---|---|
| `Quantitativos` | a mesma tabela do mapa: propriedade × classe, `TOTAL GERAL` |
| `Detalhamento` | uma linha por feição: id, classe, área em ha, validade da geometria |
| `Conferência` | área declarada no recibo × área calculada, por classe, com a diferença e o % |
| `Avisos` | sobreposições, geometrias corrigidas, sub-áreas fora do perímetro |
| `Fontes` | origem de cada camada (arquivo local ou camada do WFS + data da consulta) e o CRS usado |

`Conferência` e `Fontes` são o que transforma a planilha de "tabela" em **documento defensável**:
quando o cliente questiona um número, a resposta está na planilha.

### Estilo

| Elemento | Formato |
|---|---|
| Título da aba | fundo azul `#1F4E79`, texto branco, 14 pt, negrito |
| Cabeçalho | fundo azul `#2E75B6`, texto branco, negrito, centralizado, quebra de linha |
| Dados | branco, bordas cinza finas, números à direita |
| `TOTAL GERAL` | fundo verde `#70AD47`, texto branco, negrito |
| Números de área | formato `#,##0.0000` (4 casas, separador de milhar) |
| Percentuais | `0,00%` |
| Notas | itálico 9 pt, cinza |

Mesma paleta do PNG da tabela do mapa — planilha e mapa parecem do mesmo lugar.

### Larguras e congelamento

- Coluna 1 (propriedade/classe): peso 2,0.
- Coluna 2 (área total): peso 1,5.
- Demais: peso 1,0.
- Congelar a linha de cabeçalho.
- Auto-filtro nas abas `Detalhamento` e `Avisos`.

## PNG da tabela (para o mapa)

Mesmo dado, renderizado com Pillow:

- **≥ 600 dpi efetivos.** O modelo tem 3210 × 472 px para 13,59 × 2,00 cm. Menos que isso borra
  visivelmente no PDF.
- Cabeçalho azul com quebra em duas linhas (`Área total da\npropriedade (ha)`).
- `TOTAL GERAL` em faixa verde.
- Largura proporcional às colunas, altura calculada pelo número de linhas.
- Salvo em `<saida>/recursos/tabela_quantitativos.png`.

Quando o número de linhas ultrapassa o que cabe no `PICTURE_ELEMENT` do template, o motor reduz a
fonte até um piso e, abaixo dele, **avisa e sugere a página de quantitativos separada** — que é o
que o acervo faz com `Dinamica_2026_quantitativos.pdf`.

## Relatório de validação

`validacao.json` acompanha todo mapa gerado:

```json
{
  "gerado_em": "2026-07-25T14:22:03-04:00",
  "motor": "arcpy",
  "versoes": { "app": "0.4.0", "nucleo": "0.4.0", "arcmap": "10.8.1",
               "template": "dinamica_retrato@sha256:…", "catalogo": "2026-07-25" },
  "mapspec": { "id": "spec_01J8X…", "versao": 3 },
  "escala_resolvida": 60000,
  "crs_data_frame": "EPSG:31982",
  "checks": [
    { "id": "H01", "ok": true },
    { "id": "S01", "ok": false, "detalhe": "retângulo do minimapa 0,3 mm fora do centroide" }
  ],
  "avisos": [
    { "codigo": "area_fora_atp", "mensagem": "7,4 ha de AUAS fora do perímetro" },
    { "codigo": "cache_antigo", "mensagem": "tipologia do cache, 12 dias" }
  ],
  "entradas": [ { "arquivo": "SHP/ATP.shp", "sha256": "…", "feicoes": 1, "area_ha": 3823.9140 } ]
}
```

Serve para três coisas: mostrar os checks na UI, reproduzir o mapa depois, e responder "por que
este mapa saiu diferente do de ontem".

## Relatório da análise (opcional, v1.1)

Um `.docx` que junta capa, ficha do imóvel, os mapas gerados e a tabela de quantitativos — base
`core/docx_builder.py` do NexoGeo. Fica **fora da v1**: é entregável de consultoria, não de
cartografia, e o escopo já está grande.

## Checklist de implementação

- [ ] Cálculo único de quantitativos alimentando as três saídas
- [ ] Reprojeção para a UTM da zona do centroide
- [ ] `union` por camada antes do `intersection`
- [ ] Arredondamento em 4 casas e `TOTAL GERAL` sobre valores arredondados
- [ ] Detecção de sobreposição entre classes
- [ ] Detecção de sub-área fora do perímetro
- [ ] Conferência contra o recibo do CAR
- [ ] `.xlsx` com as 5 abas
- [ ] Estilo institucional (azul/verde) igual ao PNG
- [ ] Congelamento de cabeçalho e auto-filtro
- [ ] PNG da tabela ≥ 600 dpi
- [ ] Redução de fonte com piso + aviso de página separada
- [ ] `validacao.json` completo
- [ ] Teste: soma da coluna == `TOTAL GERAL` exibido, em 20 fixtures

## Pendências

| # | Questão |
|---|---|
| P1 | Multi-imóvel: a tabela do acervo Trevisol tinha 2 lotes + TOTAL; a da Harmonia tem 1. O contrato suporta, o layout precisa de teste |
| P2 | Percentual em relação a quê — área total do imóvel ou soma das classes? O acervo não é consistente |
| P3 | Quantas linhas cabem no `PICTURE_ELEMENT` de cada template — medir |
| P4 | `.docx` de relatório: v1.1 ou nunca? Depende de o usuário pedir |
