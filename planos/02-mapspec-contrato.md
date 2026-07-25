# 02 — `MapSpec`: o contrato central

Um `MapSpec` é o **JSON declarativo que descreve um mapa por completo**. É o único contrato
entre a IA, o motor de `.mxd`, o renderizador nativo, o validador e — na Fase 2 — o backend e o
site. Nada de mapa trafega em outro formato.

Schema: `shared/schemas/mapspec.schema.json` (JSON Schema draft 2020-12).
Versão: `contract_version`, número inteiro, incrementado em toda mudança incompatível.

## Princípio: declarativo, nunca gerativo

A IA produz e edita o `MapSpec`. Ela **nunca** produz código Python, expressão `arcpy`,
`definitionQuery` livre nem URL de serviço. Um `MapSpec` malformado é **rejeitado**, jamais
"corrigido em silêncio".

A alternativa — IA gerando script `arcpy` sob medida por mapa — é mais flexível e completamente
insegurável: código arbitrário na máquina do cliente, impossível de testar em regressão e de
reproduzir num bug relatado.

Corolário operacional: **uma feature de layout só entra no `MapSpec` se existir equivalente no
motor.** Se não dá para fazer no ArcMap nem no renderizador nativo, não vira campo.

## Exemplo canônico completo

```json
{
  "contract_version": 2,
  "perfil": "harmonia",
  "id": "spec_01J8X...",
  "versao": 3,
  "parent_id": "spec_01J8W...",

  "titulo": "Dinâmica 2026",
  "template": "dinamica_retrato",
  "saidas": ["mxd", "pdf", "png", "xlsx"],

  "imovel": {
    "nome": "Fazenda Harmonia",
    "car": "MT102042/2017",
    "matricula": null,
    "area_total_ha": 3823.9033,
    "municipio": { "nome": "Vila Rica", "ibge": "5108600", "uf": "MT" },
    "geometria": "local.ATP"
  },

  "crs": "EPSG:31982",
  "escala": 60000,
  "extent": null,

  "camadas": [
    {
      "id": "perimetro",
      "nome_no_mxd": "Fazenda Harmonia",
      "fonte": "local.ATP",
      "estilo": "perimetro_imovel",
      "rotulo_texto": "Fazenda Harmonia",
      "legenda": "Fazenda Harmonia",
      "ordem": 10
    },
    {
      "id": "avn",
      "nome_no_mxd": "Área de vegetação nativa",
      "fonte": "local.AVN",
      "estilo": "avn",
      "legenda": "Área de vegetação nativa",
      "ordem": 30
    },
    {
      "id": "auas",
      "nome_no_mxd": "Área Derivada de Desmate Após 2008",
      "fonte": "local.AUAS",
      "estilo": "auas",
      "legenda": "Área Derivada de Desmate Após 2008",
      "ordem": 20
    },
    {
      "id": "municipios",
      "nome_no_mxd": "Limite municipal",
      "fonte": "catalogo.lim_municipios_mt",
      "estilo": "limite_municipal",
      "filtro": { "campo": "nome", "operador": "=", "valor": "Vila Rica" },
      "legenda": "Limite municipal",
      "ordem": 90
    }
  ],

  "basemap": {
    "tipo": "planet_mensal",
    "mosaico": "global_monthly_2026_03_mosaic",
    "fallback": ["mosaico_sema", "esri_world_imagery"]
  },

  "elementos_layout": {
    "titulo_caixa": true, "norte": true, "grade": true, "grade_linhas": false,
    "escala_grafica": false, "minimapa": true, "metadados": true,
    "legenda": true, "logo": true, "tabela": true, "creditos": false
  },

  "metadados": [
    { "rotulo": "Satélite/Sensor", "valor": "PLANET" },
    { "rotulo": "Data da imagem", "valor": "Março/2026" },
    { "rotulo": "Fonte", "valor": "WMS-SEMA" },
    { "rotulo": "Datum", "valor": "SIRGAS 2000 UTM 22 S" },
    { "rotulo": "Escala", "valor": "auto" }
  ],

  "tabela": {
    "titulo_bloco": null,
    "colunas": [
      "Propriedade",
      "Área total da propriedade (ha)",
      "Área de vegetação nativa (ha)",
      "Área consolidada (ha)",
      "Área Derivada de Desmate Após 2008 (ha)"
    ],
    "linhas": [["Fazenda Harmonia", 3823.9140, 2833.7541, 483.8562, 491.2631]],
    "total_geral": true,
    "casas_decimais": 4
  },

  "saida": {
    "pasta": "<pasta_do_projeto>/Mapas",
    "nome_base": "Dinamica_2026",
    "caminhos_relativos": true,
    "materializar_camadas_em": "SHP"
  }
}
```

## Campos, um a um

### Identidade e versionamento

| Campo | Tipo | Regra |
|---|---|---|
| `contract_version` | int | atual: **2**. Motor com versão menor recusa o spec e pede atualização |
| `perfil` | enum | só `"harmonia"` na v1. Reservado para um futuro `"trevisol"` |
| `id` / `versao` / `parent_id` | string/int/string | histórico append-only: editar = **nova** versão com `parent_id`, nunca sobrescrever |

### Mapa

| Campo | Tipo | Regra |
|---|---|---|
| `titulo` | string | texto da caixa branca. Vai para `TITULO` no `.mxd` |
| `template` | enum | id no `MANIFEST.json`. Define **formato de página e CRS do data frame** |
| `saidas` | array | ⊆ `{mxd, pdf, png, xlsx, geojson}` |
| `crs` | `EPSG:xxxxx` | **projetado**, usado para área e para o data frame. Derivado do centroide quando ausente |
| `escala` | int \| `"auto"` | ∈ lista de escalas permitidas. `"auto"` é resolvido e **gravado de volta** |
| `extent` | bbox \| `null` | quando `null`, calculado do imóvel + margem. Gravado de volta após resolver |

### `imovel`

O objeto que o agente florestal preenche primeiro, porque quase todo o resto deriva dele.

| Campo | Uso |
|---|---|
| `nome` | rótulo no mapa, nome da camada no `.mxd`, entrada de legenda, coluna `Propriedade` da tabela |
| `car` | consulta ao WFS SEMA (`MVW_REQUERIMENTO_ATP`), rastreabilidade |
| `matricula` | segunda linha do rótulo **só quando existir e for pedida** |
| `area_total_ha` | conferência contra a área calculada da geometria; divergência > 0,5% vira aviso |
| `municipio.nome` | **definition query** da camada de municípios + rótulo do minimapa |
| `municipio.ibge` | identificação da malha IBGE do minimapa |
| `geometria` | fonte do perímetro; alimenta extent, escala, centroide, zona UTM e o retângulo do minimapa |

**A troca automática de município** é este campo. O motor reescreve a `definitionQuery` da camada
de municípios para `"nome" = '<municipio.nome>'` e a da camada de UF para
`"nome" = '<municipio.uf_extenso>'`. Sem isso o mapa sai com o município da análise anterior —
erro real e recorrente no acervo.

### `camadas[]`

| Campo | Regra |
|---|---|
| `id` | estável dentro do spec; usado nos diffs de edição |
| `nome_no_mxd` | **o nome exato da camada no template**. É o contrato com o `.mxd` — ver [motor](../Fase_1_Desktop/planos/04-motor-mxd.md) |
| `fonte` | `local.<arquivo>` (shapefile na pasta do projeto) ou `catalogo.<id>` (WFS/WMS do catálogo). **Nunca URL livre** — anti-SSRF |
| `estilo` | id de estilo do catálogo (`perimetro_imovel`, `avn`, `ac`, `auas`, …). Nunca cores soltas |
| `filtro` | objeto `{campo, operador, valor}` validado contra o schema do shapefile. Nunca SQL livre |
| `rotulo_texto` | texto fixo desenhado no centroide; não é rótulo de camada |
| `legenda` | texto na legenda; `null` remove da legenda sem remover do mapa |
| `ordem` | menor desenha por cima. Perímetro 10, hachuras 20–40, contexto 90+ |

`ordem` importa: AVN e AUAS são hachuras que precisam ficar **abaixo** do perímetro amarelo,
senão a hachura come o contorno.

#### Por que `estilo` é enum e não cores livres

O objeto `lyr.symbology` de `arcpy.mapping` não expõe preenchimento, espessura, hachura nem
transparência. A hachura `xxx` verde vazada da AVN é **impossível** de configurar por código na
10.x. O estilo vem de um `.lyr` versionado, extraído dos `.mxd` do acervo e conferido por
`sha256`.

Quando o usuário pede *"deixa a vegetação nativa azul"*, a IA resolve para um `.lyr` catalogado
(`avn_azul`). Cor fora do catálogo é **recusada com sugestão da mais próxima** — não inventada.
Ampliar o catálogo de estilos é trabalho de cartógrafo no ArcMap, não de runtime.

### `basemap`

| `tipo` | Origem | Nota |
|---|---|---|
| `planet_mensal` | WMTS `tiles.planet.com/.../{mosaico}/gmap/{z}/{x}/{y}.png` | é o dos modelos; exige `planet_api_key` |
| `mosaico_sema` | WMS `Mosaicos:MOSAICO_SPOT_SEPLAN`, `LANDSAT_*`, `SENTINEL_2_*` | exige `sema_authkey` |
| `esri_world_imagery` | tiles Esri | sem chave, qualidade menor |
| `wms_tematico` | ex. `VEGETACAO_RADAMBRASIL` para o mapa de Tipologia | fundo temático, não satélite |
| `nenhum` | — | mapas de contexto (Terras Indígenas usa fundo branco) |

`fallback` é uma lista ordenada. Cair para o fallback aciona o check `S08`.

**Chave nunca entra no `MapSpec`.** O motor injeta `api_key`/`authkey` a partir do cofre local no
momento de montar a URL. Ver [`05-seguranca-e-segredos.md`](05-seguranca-e-segredos.md).

### `metadados[]`

Lista **ordenada** de pares — não um formulário fixo. Cada item vira uma linha
`<bol>Rótulo:</bol> valor` no `TEXT_ELEMENT` de metadados.

Dois valores são especiais e resolvidos pelo motor:

- `"valor": "auto"` no rótulo `Escala` → preenchido com `1:<escala resolvida>`.
- `"valor": "auto"` no rótulo `Datum` → derivado do CRS do data frame.

### `tabela`

| Campo | Regra |
|---|---|
| `colunas` | cabeçalhos exatos, com `(ha)` incluso |
| `linhas` | valores **numéricos**, não formatados. A formatação pt-BR é do renderizador |
| `total_geral` | acrescenta a linha `TOTAL GERAL` verde = soma dos valores **já arredondados** |
| `casas_decimais` | 4 no perfil Harmonia |

A tabela vira um PNG ≥ 600 dpi que o motor injeta como `PICTURE_ELEMENT`, e vira também a aba
principal do `.xlsx` quando `xlsx` está em `saidas`.

### `saida`

| Campo | Regra |
|---|---|
| `pasta` | dentro do workspace autorizado. Validado contra a allowlist antes de qualquer I/O |
| `nome_base` | ASCII, sem acento — `arcpy` 10.x falha com acento em caminho de saída |
| `caminhos_relativos` | `true` grava o `.mxd` com `relativePaths` e materializa as camadas ao lado dele |
| `materializar_camadas_em` | subpasta relativa onde os shapefiles resolvidos são escritos (default `SHP`) |

`caminhos_relativos: true` é o modo que resolve o problema central do produto: **o `.mxd`
entregue abre no PC de outra pessoa**. Detalhe em
[`../Fase_1_Desktop/planos/04-motor-mxd.md`](../Fase_1_Desktop/planos/04-motor-mxd.md).

## Invariantes validadas antes de gerar

Rejeição, nunca correção silenciosa:

- [ ] `contract_version` compatível com o motor
- [ ] `template` existe no `MANIFEST.json` e o `sha256` do arquivo bate
- [ ] toda `fonte` é `local.<id>` presente no workspace **ou** `catalogo.<id>` existente
- [ ] todo `estilo` existe na biblioteca de `.lyr`
- [ ] todo `filtro.campo` existe no shapefile e `filtro.operador` está na allowlist
      (`=`, `<>`, `>`, `<`, `>=`, `<=`, `IN`, `LIKE`)
- [ ] `escala` ∈ lista permitida ou `"auto"`
- [ ] `crs` é EPSG **projetado** e compatível com a UF do imóvel
- [ ] `saidas` ⊆ `{mxd, pdf, png, xlsx, geojson}`
- [ ] `imovel.municipio.nome` não vazio quando `minimapa` está ligado
- [ ] `metadados` sem valor vazio
- [ ] `tabela.linhas` com o mesmo número de colunas de `tabela.colunas`
- [ ] `saida.pasta` dentro da allowlist do workspace
- [ ] `saida.nome_base` ASCII

Essa mesma lista roda em **modo predição** antes de o usuário mandar gerar (tool
`validar_mapspec`), o que economiza uma geração inteira por erro evitado.

## Edição = nova versão

Toda alteração pedida no chat cria uma **nova linha** de `MapSpec` com `parent_id` apontando
para a anterior. Nunca há sobrescrita.

```
spec v1  ──▶  spec v2  ──▶  spec v3
  │             │             │
  └─ mapa.mxd   └─ mapa_v2    └─ mapa_v3      (arquivos anteriores intactos)
```

Vantagens que pagam o custo de armazenamento: histórico de "por que este mapa ficou assim",
possibilidade de voltar uma versão, e diff legível na interface (`campo`, `de`, `para`).

O diff é calculado por caminho JSON, não por texto:

```json
[
  { "op": "replace", "path": "/camadas/1/estilo", "de": "avn", "para": "avn_azul" },
  { "op": "replace", "path": "/elementos_layout/tabela", "de": true, "para": false }
]
```

## Evolução do contrato

| Tipo de mudança | Ação |
|---|---|
| Campo novo opcional | não incrementa `contract_version` |
| Campo novo obrigatório, remoção, mudança de tipo/semântica | **incrementa** |
| Novo `estilo`, novo `template`, nova camada de catálogo | só atualiza o catálogo — não é mudança de contrato |

Motor mais antigo que o spec recebe `contract_version` maior → recusa com mensagem de
atualização. Motor mais novo que o spec **aceita** e aplica defaults.

## Pendências

| # | Questão |
|---|---|
| P1 | `extent` explícito vs sempre derivado — hoje é opcional; decidir se algum mapa realmente precisa de extent manual |
| P2 | Multi-imóvel (vários lotes num mapa): `imovel` viraria `imoveis[]`? O acervo Trevisol tinha 2 lotes; o Harmonia tem 1 |
| P3 | `saidas: ["geojson"]` — útil para o site da Fase 2, inútil no desktop. Manter no contrato ou mover para a Fase 2? |
| P4 | Onde vive o schema: `shared/schemas/` versionado em git, ou embutido no pacote do núcleo Python? |
| P5 | Mapas com dois data frames de conteúdo (inset de tipologia) não têm representação no contrato ainda |
