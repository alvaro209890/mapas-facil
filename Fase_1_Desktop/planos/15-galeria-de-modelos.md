# F1-15 — Galeria de modelos de mapa

## Objetivo

A galeria é a segunda porta de entrada do produto, ao lado do chat, e a **única que funciona sem
chave de IA**. O usuário abre a pasta, vê uma grade de modelos com preview real, escolhe
"Dinâmica 2026 — retrato", e o núcleo monta um `MapSpec` a partir do modelo + do índice da pasta +
do recibo do CAR. Chat e galeria são duas entradas para **o mesmo contrato**: os dois terminam em
`mapspec.validar` → `mapa.gerar`, e nenhum dos dois tem um caminho privilegiado.

## Estado atual vs alvo

| Item | Atual | Alvo |
|---|---|---|
| `shared/galeria/` | **existe** — `modelos.json` + schema + 5 previews | catálogo `modelos.json` + previews PNG |
| Métodos `galeria.*` | **fechados** (M4) | `galeria.listar`, `galeria.detalhar`, `galeria.montar_mapspec` |
| Montagem determinística de `MapSpec` | **fechada** em `galeria/montar.py` | implementada e testada no anel 1 |
| UI da galeria | **fechada** — painel direito do shell | painel `painel-galeria` ([F1-02](02-ui-chat-e-workspace.md)) |
| Templates disponíveis | `dinamica_retrato` **parcial**; 4 `a_preparar` | ver [MANIFEST](../../shared/templates/MANIFEST.json) |

Consequência operacional que o agente **não pode esconder do usuário**: hoje só um modelo pode
sair do estado `indisponivel` (`dinamica_2026_retrato` → `parcial` ou `faltam_dados`), e os
outros quatro ficam `indisponivel` com motivo honesto. A galeria exibe o estado real.

## Dependências

| Precisa de | Estado |
|---|---|
| `shared/templates/MANIFEST.json` (id, `sha256`, formato de página, CRS) | existe |
| `workspace.abrir` (índice + papéis dos shapefiles) | existe |
| `car.ler_recibo` | existe |
| `mapspec.validar` | existe |
| M3 — shell da UI | **fechado** (C1–C11) |
| Sessão válida para **gerar** (não para navegar) | [F1-14](14-auth-e-conta.md) |

## Contratos

### `shared/galeria/modelos.json`

```json
{
  "galeria_version": 1,
  "contract_version": 2,
  "modelos": [
    {
      "id": "dinamica_2026_retrato",
      "nome": "Dinâmica de uso do solo",
      "subtitulo": "Série Dinâmica · A4 retrato",
      "descricao": "Perímetro, vegetação nativa, área consolidada e desmate após 2008, com tabela de quantitativos.",
      "template": "dinamica_retrato",
      "perfil": "harmonia",
      "preview": "previews/dinamica_2026_retrato.png",
      "orientacao": "retrato",
      "tags": ["dinamica", "car", "quantitativos"],
      "saidas_padrao": ["mxd", "pdf", "png", "xlsx"],
      "escala_padrao": "auto",
      "requisitos_camadas": [
        { "papel": "ATP",  "obrigatorio": true,  "nome_no_mxd": "{imovel.nome}",                        "estilo": "perimetro_imovel", "ordem": 10 },
        { "papel": "AVN",  "obrigatorio": false, "nome_no_mxd": "Área de vegetação nativa",             "estilo": "avn",  "ordem": 30 },
        { "papel": "AC",   "obrigatorio": false, "nome_no_mxd": "Área consolidada",                     "estilo": "ac",   "ordem": 40 },
        { "papel": "AUAS", "obrigatorio": false, "nome_no_mxd": "Área Derivada de Desmate Após 2008",   "estilo": "auas", "ordem": 20 }
      ],
      "camadas_catalogo": [
        { "fonte": "catalogo.lim_municipios_mt", "nome_no_mxd": "Limite municipal", "estilo": "limite_municipal", "ordem": 90,
          "filtro_de": "imovel.municipio.nome" }
      ],
      "basemap_padrao": { "tipo": "planet_mensal", "fallback": ["mosaico_sema", "esri_world_imagery"] },
      "elementos_layout_padrao": {
        "titulo_caixa": true, "norte": true, "grade": true, "grade_linhas": false,
        "escala_grafica": false, "minimapa": true, "metadados": true,
        "legenda": true, "logo": true, "tabela": true, "creditos": false
      },
      "tabela_padrao": {
        "colunas_de": ["ATP", "AVN", "AC", "AUAS"],
        "total_geral": true,
        "casas_decimais": 4
      },
      "metadados_padrao": [
        { "rotulo": "Satélite/Sensor", "valor": "PLANET" },
        { "rotulo": "Data da imagem",  "valor": "auto" },
        { "rotulo": "Fonte",           "valor": "WMS-SEMA" },
        { "rotulo": "Datum",           "valor": "auto" },
        { "rotulo": "Escala",          "valor": "auto" }
      ]
    }
  ]
}
```

Regras do arquivo:

| Campo | Regra |
|---|---|
| `id` | estável e único; nunca reaproveitado depois de publicado |
| `template` | **tem** de existir em `shared/templates/MANIFEST.json`. Validado no boot; ausente → o modelo some da galeria e registra `NU-231` no log |
| `preview` | caminho relativo a `shared/galeria/`; PNG, lado maior ≤ 1024 px, ≤ 300 KB, gerado a partir de um PDF real do acervo, **nunca** mockup desenhado à mão |
| `requisitos_camadas[].papel` | vocabulário fechado do índice do workspace: `ATP`, `AVN`, `AC`, `AUAS`, `APP`, `ARL`, `SIGEF`, `RESERVA_LEGAL` |
| `nome_no_mxd` | aceita `{imovel.nome}`; qualquer outra chave de interpolação é erro de validação |
| `filtro_de` | caminho no `MapSpec` que alimenta o `filtro` da camada; só `imovel.municipio.nome` e `imovel.municipio.uf` na v1 |
| `colunas_de` | lista de papéis; o rótulo da coluna vem do padrão Harmonia, não do JSON |
| `galeria_version` | inteiro; sobe quando muda a **forma** do arquivo, não quando entra um modelo novo |

### Estado derivado (calculado em runtime, nunca gravado no JSON)

`galeria.listar` devolve, por modelo, um `status` que combina três fontes:

| `status` | Quando |
|---|---|
| `pronto` | template com `status: "pronto"` no MANIFEST **e** `sha256_ok` **e** todos os `requisitos_camadas` obrigatórios presentes no índice do workspace |
| `parcial` | template `parcial` no MANIFEST, ou algum requisito **não** obrigatório ausente |
| `faltam_dados` | template ok, mas falta requisito **obrigatório** na pasta |
| `indisponivel` | template `a_preparar`, `sha256` nulo ou divergente |

O cartão da galeria mostra o motivo em uma linha (`falta ATP.shp na pasta`), nunca só um ícone.

### Métodos NDJSON novos

```json
{"v":1,"id":"01J…","tipo":"req","metodo":"galeria.listar","params":{"workspace":"C:\\…"}}
```

| Método | Params | Retorno |
|---|---|---|
| `galeria.listar` | `{workspace?}` | `{galeria_version, modelos:[{id, nome, subtitulo, tags, orientacao, preview, status, motivo?, requisitos_faltando:[]}]}` — **sem** `requisitos_camadas` completos, sem base64 |
| `galeria.detalhar` | `{modelo_id, workspace?}` | o item completo + `status` + `mapeamento_sugerido` (papel → `local.<id>` do índice) |
| `galeria.montar_mapspec` | `{modelo_id, workspace, sobrescritas?}` | `{mapspec, avisos:[]}` — **não gera nada**, só monta |

`sobrescritas` é um objeto raso e tipado, não um `MapSpec` parcial livre:

```json
{ "titulo": "Dinâmica 2026", "escala": 60000, "saidas": ["pdf","xlsx"],
  "mapeamento": { "AVN": "local.AVN_corrigido" },
  "elementos_layout": { "tabela": false } }
```

Qualquer chave fora dessas cinco → `NU-232`. Isto impede que a galeria vire um caminho paralelo
para injetar `MapSpec` arbitrário.

### Algoritmo de `galeria.montar_mapspec`

Determinístico. Mesma entrada, mesma saída, byte a byte — é testável no anel 1 e é o caminho do
modo sem IA.

```
 1. carrega o modelo por id            → erro NU-230 se não existe
 2. confere o template no MANIFEST     → erro NU-231 se ausente/sha256 divergente
 3. lê o índice do workspace           → papéis já resolvidos por workspace.abrir
 4. lê o recibo do CAR (se houver)     → imovel.{nome, car, municipio, area_total_ha}
 5. resolve requisitos_camadas:
       papel obrigatório ausente       → aviso "faltam_dados" e ABORTA com NU-233
       papel opcional ausente          → omite a camada, acrescenta aviso
       aplica sobrescritas.mapeamento
 6. acrescenta camadas_catalogo, resolvendo filtro_de a partir do imóvel
 7. crs: zona UTM pelo centroide do perímetro (nunca chutar); se o template fixa
    crs_data_frame, o template ganha
 8. escala: escala_padrao; "auto" fica "auto" e é resolvido na geração
 9. tabela: monta colunas a partir de colunas_de + rótulos do padrão Harmonia
10. metadados: copia metadados_padrao, mantendo "auto" para o motor resolver
11. saida.nome_base: ASCII, derivado do nome do modelo + ano; sem acento
12. id ULID novo, versao 1, parent_id null
13. devolve {mapspec, avisos}
```

O passo 5 aborta em vez de gerar um mapa incompleto: **o produto prefere recusar a entregar um
mapa errado sem aviso** (é a regra do bug bar S2 em [F1-10](10-testes-e-qa.md)).

### Códigos de erro novos

| Código | Significado |
|---|---|
| `NU-230` | modelo de galeria inexistente |
| `NU-231` | template do modelo ausente do MANIFEST ou `sha256` divergente |
| `NU-232` | `sobrescritas` com chave fora da allowlist |
| `NU-233` | requisito de camada obrigatório ausente no workspace |
| `NU-234` | `modelos.json` inválido contra o schema |

## Fluxo na interface

```
usuário abre a pasta
   │
   ▼
painel-galeria mostra a grade (galeria.listar)
   │  cartão: preview · nome · subtítulo · chip de status · motivo
   ▼
clique no cartão → painel-galeria-detalhe
   │  mapeamento papel → arquivo, editável por combobox
   │  toggles de elementos de layout
   │  seleção de saídas
   ▼
"Montar" → galeria.montar_mapspec → painel-mapspec mostra o JSON e os avisos
   ▼
"Validar" → mapspec.validar        → lista de erros/avisos, sem gerar
   ▼
"Gerar"   → mapa.gerar             → job.progresso anima o painel-preview
```

A galeria **nunca** chama `mapa.gerar` direto. `mapspec.validar` no meio é obrigatório — economiza
uma geração inteira por erro evitado, e é a mesma regra imposta ao agente de IA.

### Relação com o chat

| Situação | Comportamento |
|---|---|
| Usuário escolhe na galeria e depois abre o chat | o `MapSpec` montado entra no contexto do agente como versão 1; o chat edita a partir dele |
| Usuário pede no chat "faz a Dinâmica 2026" | o agente chama a tool `usar_modelo_da_galeria(modelo_id)`, que executa **o mesmo** `galeria.montar_mapspec` |
| Sem chave DeepSeek | a galeria é o caminho principal; o chat mostra o banner de modo determinístico |

O agente **não** monta `MapSpec` do zero quando existe modelo equivalente. Ver
[F1-06 §Catálogo de tools](06-agente-eng-florestal.md#catálogo-de-tools).

## Como adicionar um modelo sem quebrar o núcleo

Receita fechada, para um agente seguir sem julgamento:

1. O template já tem de existir em `shared/templates/MANIFEST.json` com `sha256` real. Se não
   tem, o trabalho é B1/B2 ([F1-13](13-checklist-implementacao.md)), não galeria.
2. Acrescente o item em `shared/galeria/modelos.json`. **Não** incremente `galeria_version`.
3. Gere `shared/galeria/previews/<id>.png` a partir de um PDF real de
   `Referencias_IMAP/Mapas/01/`.
4. Acrescente um caso em `nucleo/tests/test_galeria.py`: `montar_mapspec` do modelo novo contra a
   fixture da Harmonia produz um `MapSpec` que passa em `mapspec.validar`.
5. Se o modelo exigir um campo que o `MapSpec` não tem, **pare**: isso é mudança de contrato, vai
   em [`planos/02-mapspec-contrato.md`](../../planos/02-mapspec-contrato.md) e incrementa
   `contract_version`. Não invente campo no `modelos.json`.

## Tarefas agentáveis

- [x] `shared/galeria/modelos.json` com os 5 modelos do MANIFEST (4 nascem `indisponivel`)
- [x] `shared/galeria/schema.json` — JSON Schema do arquivo acima
- [x] `shared/galeria/previews/` — PNG por modelo, extraídos de `Referencias_IMAP/Mapas/01/`
- [x] `shared/galeria/README.md` — como adicionar modelo (a receita acima, resumida)
- [x] `nucleo/mapasfacil_nucleo/galeria/catalogo.py` — carga + validação contra o schema
- [x] `nucleo/mapasfacil_nucleo/galeria/estado.py` — cálculo de `status` (MANIFEST × índice)
- [x] `nucleo/mapasfacil_nucleo/galeria/montar.py` — os 13 passos do algoritmo
- [x] `nucleo/mapasfacil_nucleo/__main__.py` — registrar os três métodos no roteador
- [x] `nucleo/mapasfacil_nucleo/erros.py` — `NU-230`…`NU-234` (via `ErroNucleo` nos módulos da galeria)
- [x] `app/src/paineis/Galeria.tsx` — grade, id `painel-galeria`
- [x] `app/src/paineis/GaleriaDetalhe.tsx` — mapeamento e toggles, id `painel-galeria-detalhe`
- [x] `app/src/componentes/CartaoModelo.tsx` — preview, chip de status, motivo
- [x] `nucleo/tests/test_galeria.py`

## Critérios de aceite

- [x] `python -m mapasfacil_nucleo stdio` responde `galeria.listar` com 5 modelos e
      `status` coerente com o MANIFEST (hoje: 1 `parcial`/`faltam_dados`, 4 `indisponivel`)
- [x] `galeria.montar_mapspec` do `dinamica_2026_retrato` contra a fixture da Harmonia produz um
      `MapSpec` que passa em `mapspec.validar` **sem erros**
- [x] Determinismo: rodar `montar_mapspec` 3× produz JSON idêntico exceto `id` (ULID) — teste
      compara com `id` removido
- [x] Pasta sem `ATP` → `NU-233`, com `requisitos_faltando: ["ATP"]`
- [x] `sobrescritas: {"camadas": [...]}` → `NU-232`
- [x] Modelo apontando para template inexistente → some de `galeria.listar` e loga `NU-231`
- [ ] O `MapSpec` de `galeria.montar_mapspec` e o produzido pelo agente para o mesmo pedido têm o
      mesmo `template`, as mesmas `camadas[].id` e o mesmo `elementos_layout`
      (`nucleo/tests/test_paridade_galeria_agente.py`, com o provedor em modo fake) — **adiado a M7/G10**
- [x] Clicar num cartão `indisponivel` não dispara requisição nenhuma; mostra o motivo

## Fora de escopo

- Editor visual de modelos dentro do app (criar template novo é trabalho de cartógrafo no ArcMap).
- Marketplace, download de modelos de terceiros, modelos do usuário sincronizados.
- Preview interativo com zoom no cartão (o preview é imagem estática; o zoom é no `painel-preview`).
- Modelos de outros perfis além de `harmonia` (o `perfil` já está no contrato, mas só há um).

## Anti-padrões

| Não faça | Por quê |
|---|---|
| Mostrar todos os modelos como clicáveis quando o template não está pronto | o usuário clica e falha; `status` existe para isso |
| Deixar a galeria montar `MapSpec` por caminho próprio, diferente do agente | dois caminhos divergem e a paridade some |
| Aceitar `MapSpec` parcial livre em `sobrescritas` | vira injeção de spec e mata a validação |
| Desenhar preview fake em vez de exportar do PDF real | o cartão promete um mapa que o motor não entrega |
| Chamar `mapa.gerar` sem `mapspec.validar` antes | queima uma geração inteira por erro evitável |
| Adicionar campo novo em `modelos.json` para contornar limitação do `MapSpec` | mudança de contrato disfarçada; vai em `planos/02` |
| Mandar o catálogo inteiro da galeria para o LLM | AP-06; o agente recebe só o item selecionado |
