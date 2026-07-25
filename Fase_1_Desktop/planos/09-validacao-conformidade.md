# F1-09 — Validação e conformidade

Como os 14 checks HARD e 11 SOFT do
[padrão Harmonia](../../planos/01-padrao-imap-harmonia.md#checklist-de-conformidade) são
implementados e aplicados. **Este documento não redefine os checks** — ele diz como cada um é
medido e o que acontece quando falha.

## Três momentos de validação

```
1. PREDIÇÃO       antes de gerar, sobre o MapSpec        →  tool validar_mapspec
2. EXECUÇÃO       durante o job, a cada etapa            →  aborta cedo
3. SAÍDA          sobre o .mxd e o .pdf gerados          →  validacao.json
```

Validar cedo economiza um job inteiro por erro evitado — e um job com ArcMap leva 60–120 s.

### 1. Predição

Roda sobre o `MapSpec`, sem tocar em arquivo de saída. Cobre tudo que é decidível sem render:

| Check | Predizível? |
|---|---|
| `H02` formato de página | sim — vem do template |
| `H04` datum coerente com CRS | sim |
| `H05` escala na lista | sim |
| `H07` camadas do spec existem | sim — contra o manifesto do template |
| `H08` legenda cobre as camadas | sim |
| `H10` metadados sem linha vazia | sim |
| `H12` query de município | sim |
| `H14` `TOTAL GERAL` quando há tabela | sim |
| `H01`, `H09`, `H11`, `H13` | **não** — só existem depois do arquivo |
| `H03`, `H06` | parcial — o texto certo está no spec, mas só o PDF prova que foi escrito |

O agente é instruído a chamar `validar_mapspec` **antes** de `gerar_mapa`, sempre.

### 2. Execução

Cada etapa do job tem um portão. Falhar cedo dá mensagem melhor que falhar no fim:

| Etapa | Portão |
|---|---|
| `validando_spec` | schema + invariantes |
| `resolvendo_camadas_locais` | shapefile existe, tem `.prj`, geometria válida |
| `baixando_externas` | falha isolada vira aviso, nunca aborta |
| `calculando_quantitativos` | área total bate com a declarada (±0,5%) senão avisa |
| `preparando_template` | `sha256` do template confere; elementos obrigatórios presentes |
| `aplicando_layout` | texto cabe no slot (T2); extent no CRS certo |
| `salvando_mxd` | arquivo escrito e reabre |
| `exportando_pdf` | PDF existe e tem tamanho plausível |

### 3. Saída

Roda sobre os arquivos finais e produz o `validacao.json`.

## Como cada check é medido

### Estrutura do `.mxd`

| Check | Com ArcMap | Sem ArcMap (T2) |
|---|---|---|
| `H01` fonte quebrada | `ListBrokenDataSources(mxd)` vazio | resolver cada caminho relativo do `.mxd` contra o disco |
| `H07` camadas presentes | `ListLayers` ⊇ ids do spec | nomes de camada lidos do OLE |
| `H12` query de município | `lyr.definitionQuery` == esperada | string lida do OLE após o patch |
| `H13` `.mxd` reabre | abrir de novo e listar camadas | reabrir como OLE e conferir assinatura + diretório |

Sem ArcMap os checks são mais fracos — e isso é **declarado** no `validacao.json`
(`confianca: "estrutural"` vs `"arcpy"`), não escondido.

### Página e conteúdo do PDF

Com PyMuPDF (`fitz`):

```python
doc = fitz.open(pdf)
pagina = doc[0]

# H02 — formato
larg_mm, alt_mm = pagina.rect.width * 25.4/72, pagina.rect.height * 25.4/72

# H03/H06/H10 — texto extraível
texto = pagina.get_text()

# H09 — não está em branco
px = pagina.get_pixmap(dpi=150)
cobertura = fracao_de_pixels_nao_brancos(px)
```

| Check | Medida |
|---|---|
| `H02` | 210×297 ou 297×210 mm, ±1 mm |
| `H03` | `titulo` do spec ∈ `texto` |
| `H06` | `Escala: 1:60.000` ∈ `texto`, e o número == escala resolvida |
| `H09` | abre, 1 página, cobertura de pixels não-brancos > 5% |
| `H10` | cada `rotulo` de `metadados` ∈ `texto`, com valor não vazio depois dele |
| `H14` | faixa verde detectada na última linha da região da tabela |

### Cor do perímetro (`H11`)

O perímetro amarelo é o traço mais característico do perfil, e o erro mais provável de uma
regressão de estilo.

1. Rasterizar a 150 dpi.
2. Projetar o contorno do perímetro (que o núcleo conhece em coordenadas de mapa) para pixels.
3. Amostrar N pontos ao longo do contorno, pegando o pixel mais saturado numa janela de 3×3.
4. Converter para HSV e conferir contra a faixa do amarelo.
5. Aprovar se ≥ 80% das amostras estiverem na faixa.

Janela e HSV em vez de RGB exato porque o PDF passa por compressão e antialiasing.

### Layout por região (`S05`)

Recortes do raster nas regiões declaradas no manifesto do perfil. Interseção entre os retângulos
de legenda, metadados e logo maior que 2% da área de qualquer um deles → aviso.

### Minimapa (`S01`, `S02`, `S03`)

- `S01`: o núcleo sabe onde o retângulo **deveria** estar (calculou a posição); mede a distância
  até onde ele **está** no raster, detectando o retângulo vermelho por cor.
- `S02`: procura uma linha vermelha conectando retângulo e moldura do mapa.
- `S03`: procura pixels laranja na região do minimapa + o nome do município no texto extraído.

Esses três existem porque o desalinhamento do retângulo aconteceu em **19 de 19 mapas** no
trabalho manual da Harmonia. É o erro que o produto mais precisa não cometer.

### Texto herdado (`S11`)

Varre todos os textos extraídos do PDF e todos os `TEXT_ELEMENT` do `.mxd` procurando:

- nome de município diferente de `imovel.municipio.nome`;
- nome de fazenda diferente de `imovel.nome`;
- número de matrícula quando `imovel.matricula` é nulo;
- título de outro mapa da série (`Alertas MAPBIOMAS` num mapa PRODES);
- palavras de uma lista negra de typos conhecidos do acervo (`concolidada`, `Dadosr`).

Todos vistos de verdade no acervo. É o check que mais protege a reputação da entrega.

## O que acontece quando falha

| Severidade | Efeito |
|---|---|
| **HARD** | job termina em `failed`; os arquivos parciais vão para `_falhou/`; a UI abre o relatório; o agente explica em português o que deu errado e o que fazer |
| **SOFT** | job conclui em `succeeded`; a UI mostra o aviso; os arquivos ficam onde deveriam |

Regra: **nada de "gerado com sucesso" quando um HARD falhou.** O usuário confia no verde.

Exceção controlada: o usuário pode marcar `ignorar_hard: ["H11"]` num projeto específico, com
justificativa registrada no `validacao.json`. Serve para o caso de um cliente que quer o
perímetro de outra cor — sem isso o produto brigaria com o usuário.

## Relatório na interface

```
Dinâmica 2026                                        motor: arcpy · 68 s

✓ 14 checks HARD
⚠ 1 check SOFT

  S01  Retângulo do minimapa 0,3 mm fora do centroide
       Tolerância: 1,0 mm. Não afeta a entrega, mas se repetir em vários
       mapas vale conferir o CRS do data frame do minimapa.
       [ ver no mapa ]

Avisos
  7,4 ha de AUAS fora do perímetro da ATP
  Tipologia veio do cache (12 dias)
```

Cada check tem um texto de explicação escrito para o técnico, não para o desenvolvedor.

## Checklist de implementação

- [ ] `validar_mapspec` cobrindo os 8 checks predizíveis
- [ ] Portão por etapa no job
- [ ] Validador de saída com os 14 HARD e 11 SOFT
- [ ] Caminho degradado sem ArcMap, com `confianca` declarada
- [ ] Amostragem de cor do perímetro em HSV
- [ ] Detecção do retângulo e da linha-guia do minimapa
- [ ] Varredura de texto herdado (`S11`) com a lista negra do acervo
- [ ] `validacao.json` completo e versionado
- [ ] Textos de explicação de cada check, em português, para o técnico
- [ ] `ignorar_hard` por projeto, com justificativa registrada
- [ ] Teste: cada check falha quando deve, num fixture propositalmente quebrado

## Pendências

| # | Questão |
|---|---|
| P1 | Limiar de 5% de pixels não-brancos (`H09`) — calibrar com PDFs válidos e inválidos |
| P2 | Tolerância de 1,0 mm do `S01` — medir a dispersão real nos 19 mapas do acervo |
| P3 | `S11` pode dar falso positivo quando o mapa cita legitimamente outro município (TI vizinha). Precisa de lista de exceções |
| P4 | Detectar a faixa verde do `TOTAL GERAL` por cor é frágil se o usuário mudar a paleta |
| P5 | Vale um check de "o PDF gerado é sobreponível ao modelo da série" rodando por padrão, ou só em teste? |
