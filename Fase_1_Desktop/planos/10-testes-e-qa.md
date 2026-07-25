# F1-10 — Testes e QA

## O problema central

A parte mais importante do produto — o `.mxd` gerado pelo ArcPy — **não pode rodar no CI**:
exige Windows, ArcMap licenciado e Python 2.7. Um sistema de testes que ignore isso testa tudo
menos o que importa.

A resposta é dividir o produto em **anéis** por testabilidade e ser explícito sobre qual anel
cada teste cobre.

```
┌──────────────────────────────────────────────────────────────┐
│ ANEL 1 — puro, roda em qualquer lugar          ~70% do código │
│ MapSpec, validação, geo, quantitativos, catálogo, fsguard,    │
│ parser de recibo, tabela PNG, xlsx, renderizador nativo       │
├──────────────────────────────────────────────────────────────┤
│ ANEL 2 — precisa de rede ou fixture pesada     ~15%           │
│ clientes WFS/WMS/REST/GML, cache, agente (com fake)           │
├──────────────────────────────────────────────────────────────┤
│ ANEL 3 — precisa de Windows                    ~10%           │
│ empacotamento, Credential Manager, caminhos, instalador       │
├──────────────────────────────────────────────────────────────┤
│ ANEL 4 — precisa de ArcMap licenciado          ~5%            │
│ arcpy_job.py, T1, golden images do ArcMap                     │
└──────────────────────────────────────────────────────────────┘
```

CI comum (Linux) roda o anel 1 e o anel 2 com fakes. Um *runner* Windows roda 3 e 2 com rede real.
O anel 4 é **manual, com checklist**, a cada release.

## `fsguard` — a suíte mais importante do repositório

É a defesa contra a ameaça A2. Testes obrigatórios, cada um com caso positivo e negativo:

| Caso | Esperado |
|---|---|
| Caminho dentro do workspace | autorizado |
| `..\..\Windows\System32` | recusado |
| Caminho absoluto de outra pasta | recusado |
| Symlink apontando para fora | recusado (mesmo para leitura) |
| Junction do Windows apontando para fora | recusado |
| UNC `\\servidor\share` | recusado |
| Unidade diferente (`D:\`) quando o workspace é `C:\` | recusado |
| Nome reservado (`CON`, `NUL`, `AUX`, `COM1`, `LPT9`) | recusado |
| Caractere inválido (`<>:"|?*`) | recusado |
| Caminho com mais de 260 caracteres | recusado sem prefixo `\\?\` |
| Escrita fora de `Mapas/`, `MXD/`, `SHP/`, `_extraido/` | recusado |
| Leitura em qualquer lugar do workspace | autorizado |
| Caminho com acento e espaço | autorizado |
| Caminho normalizado de formas diferentes (`.\a\..\b`) | mesmo resultado |

Cobertura exigida: **100% de linha e de ramo** neste módulo. É o único do projeto com essa
exigência.

## Anel 1 — testes puros

### `MapSpec` e validação

- Schema aceita o exemplo canônico e rejeita cada invariante violada, uma a uma.
- Camada fora do catálogo → `NU-210`.
- Escala fora da lista → `NU-220`.
- CRS geográfico em `crs` → recusado.
- Filtro com operador fora da allowlist → recusado.
- Filtro com campo que não existe no `.dbf` → recusado.
- Diff entre duas versões produz a lista esperada de operações.
- `parent_id` inexistente → recusado.

### Geo

- Zona UTM pelo centroide: imóvel a 54,5°W → 21S; a 53,5°W → 22S; **exatamente** em 54°W → regra
  documentada e testada.
- Área de um quadrado conhecido em UTM bate com o valor analítico (tolerância 0,01%).
- Área em CRS geográfico → erro, nunca número.
- Geometria inválida corrigida, com contagem.
- `union` antes de `intersection` não conta sobreposição duas vezes.
- `TOTAL GERAL` == soma das células arredondadas, em 20 fixtures.
- Distância até TI/UC bate com valor calculado independentemente.

### Parser de recibo do CAR

- Recibo real da Harmonia → nome, município, CAR, áreas corretas.
- Rótulo quebrado em duas linhas é remontado.
- Matrícula e Posse distinguidas.
- **CPF não aparece na saída** — teste explícito.
- PDF corrompido → erro tratado, não exceção.

### Shapefile

- `.prj` ausente → aviso, CRS adivinhado.
- `.dbf` em latin-1, utf-8 e cp1252 → texto correto nos três.
- bbox lido do cabeçalho bate com o calculado pelas geometrias.
- Anel aberto detectado e fechado.

### Renderizador nativo

Regressão visual com golden images, tolerância 0,3% de pixels:

- Perfil retrato com 4 camadas + tabela.
- Perfil paisagem com camada temática sólida.
- Grade DMS em três extents diferentes.
- Minimapa com e sem malha do IBGE.
- Mapa sem basemap (fundo branco).

CI publica esperado/obtido/diff como artefato quando falha.

### Tabela e planilha

- PNG gerado tem ≥ 600 dpi efetivos.
- Faixa verde na última linha quando `total_geral`.
- `.xlsx` abre no openpyxl e no LibreOffice headless.
- Aba `Conferência` bate declarado × calculado.

## Anel 2 — rede

### Fake do provedor de IA

Grava e reproduz conversas reais (`vcr`-style). Roda no CI sem chave nem custo.

- Sequência de tools esperada por pedido.
- Tool inexistente → `IA-020`.
- Teto de 12 rodadas respeitado.
- Streaming parcial interrompido → estado consistente.

### Clientes geo

Contra respostas gravadas dos serviços reais:

| Teste | Fixture |
|---|---|
| WFS 2.0 GetFeature JSON | resposta real da SEMA |
| Fallback para WFS 1.0 | resposta da FUNAI |
| Paginação `startIndex` falhando | erro real `Cannot do natural order…` |
| `INTERSECTS` devolvendo menos que BBOX | o caso de 2026-07-10 (27 de 75 feições) |
| WMS HTTP 200 com XML de erro | resposta real |
| GML do INCRA | resposta real |
| Malha IBGE gzip | resposta real comprimida |
| PAMGIA ArcGIS REST | resposta real |

Um teste semanal ("*canary*") roda contra os serviços **de verdade** e avisa quando um endpoint
ou nome de layer mudou — foi assim que `Geoportal:TIPOLOGIA` sumiu sem ninguém perceber.

### Cache

- TTL respeitado por tema.
- Offline usa cache expirado e reporta a idade.
- Camada sem cache entra vazia e aciona `S09` sem abortar o job.

## Anel 3 — Windows

Runner Windows no CI (self-hosted ou GitHub Actions `windows-latest`):

- Núcleo empacotado sobe e responde `doctor.rodar`.
- `fsguard` com caminhos reais do Windows (UNC, junction, nome reservado).
- Credential Manager: gravar, ler existência, apagar.
- Caminho com acento e espaço em todo o pipeline.
- Instalador instala, roda e desinstala limpo.
- Doctor detecta ausência de ArcMap corretamente.
- **T2 completo**: gerar `.mxd` por patch numa máquina sem ArcMap, reabrir como OLE, conferir
  extent, escala, textos e definition query.

O T2 rodar no CI é o que impede que o caminho sem ArcMap apodreça — ele é testável, ao contrário
do T1.

## Anel 4 — ArcMap (manual)

Checklist a cada release, na máquina de referência (Windows 11 + ArcMap 10.8.1). O roteiro está
no [smoke test do motor](04-motor-mxd.md#smoke-test-manual-máquina-com-arcmap).

Registro obrigatório: quem rodou, quando, versão do app, e o `validacao.json` de cada mapa
anexado ao release.

## Fixtures

| Fixture | Conteúdo |
|---|---|
| `harmonia/` | a pasta real da análise: ATP, AVN, AC, AUAS, recibo do CAR. **É o fixture principal** |
| `sem_prj/` | shapefile sem `.prj` |
| `dbf_latin1/` | `.dbf` com acento em latin-1 |
| `geometria_invalida/` | polígono auto-interseccionado |
| `duas_zonas/` | imóvel cruzando 54°W |
| `zip_simcar/` | `.zip` como o SIMCAR entrega |
| `zip_malicioso/` | entrada com `..` (anti zip slip) |
| `mapspecs/` | 20 specs válidos e 20 inválidos, um por invariante |
| `pdfs_modelo/` | os 21 do acervo, para paridade |
| `print_referencia/` | prints em várias qualidades, para o analisador de visão |

O fixture da Harmonia é o mais valioso do projeto: é um caso real completo, com resultado
conhecido (os 19 PDFs) e números conferidos (`ATP 3.823,9140 · AVN 2.833,7541 · AC 483,8562 ·
AUAS 491,2631`).

## Definition of Done

Uma tarefa está pronta quando:

- [ ] Testes do anel correspondente passam
- [ ] Cobertura não caiu; `fsguard` continua em 100%
- [ ] Se mexeu em layout: golden images atualizadas **e revisadas visualmente**
- [ ] Se mexeu no `MapSpec`: schema, planos comuns e planos de fase atualizados no mesmo PR
- [ ] Se mexeu em catálogo: data de verificação atualizada
- [ ] Erro novo tem código na tabela de [erros](01-arquitetura.md#códigos-de-erro)
- [ ] Mensagem de erro diz o que aconteceu, por quê e o que fazer
- [ ] Nenhum segredo em log — `chaves_mxd.py verificar` e gitleaks limpos

## Bug bar

| Severidade | Definição | Bloqueia release? |
|---|---|---|
| S1 | Perda de dado do usuário; escrita fora do workspace; vazamento de chave | **sim** |
| S2 | `.mxd` ou PDF errado sem aviso; check HARD passando quando deveria falhar | **sim** |
| S3 | Falha reprodutível numa etapa, com mensagem clara | sim, se não houver contorno |
| S4 | Cosmético; aviso impreciso; lentidão | não |

Um check HARD que passa quando deveria falhar é S2 e não S3: o produto inteiro se apoia no verde.

## Pendências

| # | Questão |
|---|---|
| P1 | Runner Windows: GitHub Actions ou máquina própria? Actions não tem ArcMap de qualquer forma |
| P2 | Golden images no repositório inflam o git. Git LFS ou artefato de release? |
| P3 | O canary semanal contra serviços reais precisa de authkey no CI — como guardar |
| P4 | O fixture da Harmonia tem dado de cliente real. Anonimizar ou manter fora do repositório público? |
| P5 | Evals de IA custam dinheiro; definir cadência e orçamento |
