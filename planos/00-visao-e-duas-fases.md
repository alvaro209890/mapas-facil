# 00 — Visão, escopo e as duas fases

## O problema

A produção cartográfica de uma consultoria ambiental em Mato Grosso é repetitiva, cara e
inconsistente. O ciclo real, documentado na análise **Fazenda Harmonia** (julho/2026, 19 mapas):

1. Copiar os `.mxd` de uma análise anterior do mesmo município.
2. Reprojetar os shapefiles do CAR do imóvel novo para UTM e **gravá-los com o nome que o
   template espera** (`Fazenda_Santa_Clara.shp`, `SIEGEF.shp`, `Fazendas_Unidas.shp`…), porque é
   assim que o ArcMap reencontra os dados.
3. Repontar as fontes, remover camadas mortas da análise anterior, corrigir typos herdados
   (`Área concolidada`, `Dadosr:`).
4. Recentrar cada mapa no imóvel — em **UTM** para a série Dinâmica, em **Web Mercator** para os
   temáticos, senão o mapa sai em branco.
5. Trocar a *definition query* da camada de municípios (`"nome" = 'Vila Rica'`), apagar
   matrículas e distâncias herdadas, recentrar o retângulo do minimapa.
6. Calcular áreas em hectare por classe, gerar a imagem da tabela de quantitativos, trocar o
   `PICTURE_ELEMENT`.
7. Calcular a distância até a TI e a UC mais próximas e reposicionar a linha tracejada.
8. Exportar 19 PDFs, conferir cada um em PNG, juntar num `Mapas_unidos.pdf`.

Foram **dois dias de trabalho** com scripts sob medida (`adapt_dinamica.py`, `adapt_tematico.py`,
`adapt_bloco2.py`, `fix_minimap_rect.py`, `calc_geo.py`, `gen_tabela_quantitativos.py`), e o
resultado ainda precisou de uma correção de 19 mapas porque o retângulo do minimapa estava
0,4 cm fora do lugar em todos.

Esse trabalho se repete inteiro a cada imóvel novo. É esse ciclo que o Mapas Fácil automatiza.

## A proposta

Um **agente de engenharia florestal** que conversa em linguagem natural, olha a pasta do projeto
do usuário e entrega os mapas da série IMAP — `.mxd` abrível no ArcMap, `.pdf` pronto para
entrega e `.xlsx` de quantitativos — com o padrão garantido por validação automática, não por
disciplina humana.

O modelo mental é o de um agente de programação (Cursor, Codex, Claude Code), trocando código
por cartografia: **você aponta uma pasta e conversa.**

```
Você:  "faz a Dinâmica 2026 dessa pasta"
Ana:   li o recibo do CAR: Fazenda Harmonia, MT102042/2017, Vila Rica/MT, 3.823,90 ha
       achei ATP.shp, AVN.shp, AREA_CONSOLIDADA.shp, AUAS.shp
       consultei o SIMCAR: tipologia Floresta 2.584,86 / Cerrado 1.224,02
       → Dinamica_2026.mxd + Dinamica_2026.pdf + Quantitativos.xlsx
       escala 1:60.000 · 14 checks HARD ok · 1 aviso: AUAS 7,4 ha fora da ATP

Você:  "a vegetação nativa tá muito escura, deixa mais clara e tira a tabela"
Ana:   → versão 2, mesmos arquivos com sufixo _v2, os anteriores intactos
```

## As duas fases

O produto tem duas metades, com prioridades **muito** diferentes. Elas vivem em pastas separadas
neste repositório e podem ser desenvolvidas por pessoas/agentes diferentes.

### Fase 1 — App desktop Windows (o produto principal)

[`../Fase_1_Desktop/`](../Fase_1_Desktop/README.md)

Aplicativo nativo Windows, chat estilo Cursor/Codex, conectado a uma **pasta do PC**. É onde
está todo o valor: é ele que gera `.mxd`, `.pdf` e `.xlsx`, lê o recibo do CAR, consulta a SEMA,
calcula quantitativos e conversa com o usuário.

| Aspecto | Decisão |
|---|---|
| Stack | Electron + React (UI) + sidecar Python (geo, `.mxd`, planilha) |
| IA | **DeepSeek V4 Pro**, chave do próprio usuário (BYOK), guardada no Windows Credential Manager |
| Funciona offline? | Sim para o essencial. Sem internet: gera mapa com os shapes locais e o cache; sem chave DeepSeek: modo determinístico por template |
| Depende da Fase 2? | **Não.** É um produto completo sozinho |
| Motor de `.mxd` | ArcPy quando há ArcMap; **patch de template** quando não há |

### Fase 2 — Site de engenharia florestal e mapas

[`../Fase_2_Site/`](../Fase_2_Site/README.md)

Site com backend rodando **neste PC** (Linux, Cuiabá-MT), exposto por Cloudflare Tunnel
dedicado. Dá ao produto o que o desktop não tem: espaço de trabalho persistente com memória,
histórico de projetos entre máquinas, mapas por número de CAR sem instalar nada, e uma vitrine
pública.

| Aspecto | Decisão |
|---|---|
| Stack | Next.js (site) + FastAPI (backend) + Postgres |
| Onde roda | backend neste PC + tunnel `mapasfacil-api.cursar.space`; site em `mapasfacil.cursar.space` |
| Por que neste PC e não em nuvem | `sema.mt.gov.br` **bloqueia IP fora do Brasil**. Render/Vercel nem conseguem fazer GetFeature. Este PC está em MT |
| Depende da Fase 1? | Reusa o núcleo Python e o `MapSpec`, mas roda independente |
| Gera `.mxd`? | Não. Sem ArcMap no servidor, o site entrega PDF/PNG e **delega o `.mxd` ao desktop** |

### Por que nessa ordem

1. **O `.mxd` é o entregável que importa**, e ele só existe no Windows do usuário.
2. O NexoGeo Ambiental já provou a metade web (chat → `MapSpec` → PDF IMAP) e **falhou
   exatamente no `.mxd`**, que ficou como "quando ArcMap estiver disponível" e nunca saiu do
   papel. Inverter a prioridade é a lição principal.
3. A Fase 1 valida o produto com usuário real sem nenhuma infraestrutura.

## O que cada fase compartilha

Estes documentos e dados valem para as duas e vivem na raiz:

| Recurso | O que é |
|---|---|
| [`01-padrao-imap-harmonia.md`](01-padrao-imap-harmonia.md) | **fonte da verdade visual**: geometria de página medida, cores, checks |
| [`02-mapspec-contrato.md`](02-mapspec-contrato.md) | o JSON que descreve um mapa |
| [`03-wfs-e-servicos-geo.md`](03-wfs-e-servicos-geo.md) | receitas de WFS/WMS da SEMA, IBAMA, FUNAI, INCRA, MapBiomas |
| [`04-dados-camadas-e-car.md`](04-dados-camadas-e-car.md) | shapefiles locais, recibo do CAR, `.zip` do SIMCAR, cache |
| [`05-seguranca-e-segredos.md`](05-seguranca-e-segredos.md) | cofre de chaves, LGPD, o incidente das chaves nos `.mxd` |
| [`../shared/`](../shared/README.md) | catálogo de camadas, schema do `MapSpec`, perfil visual, templates |
| [`../Referencias_IMAP/`](../Referencias_IMAP/README.md) | 21 PDFs + 24 `.mxd` reais |

## Linhagem técnica

Nada aqui nasce do zero. Três sistemas do mesmo dono já resolveram partes do problema:

| Fonte | O que entra no Mapas Fácil |
|---|---|
| **[NexoGeo Ambiental](https://github.com/alvaro209890/NexoGeo-Ambiental)** | chat → `MapSpec` → PDF IMAP; renderizador matplotlib calibrado; parser do recibo do CAR (`core/recibo.py`); estilo de planilha (`core/xlsx_builder.py`); cliente DeepSeek; quantitativos por overlay. **O `.mxd` ficou incompleto** — é o que a Fase 1 resolve |
| **GeoForest-IA** | cliente WFS/WMS de produção: BBOX + clip local, `authkey` SEMA, fallback de paginação, PAMGIA do IBAMA, GML do INCRA, escritor de shapefile, regras de erro de geometria do SIMCAR |
| **Cerebro-Geo-IA** | catálogo de camadas e serviços, gotchas de campo (2026-07) |
| **Análise Fazenda Harmonia** | a receita real de adaptação de `.mxd`, com todas as armadilhas — o documento mais valioso do acervo |

## Escopo da v1

### Dentro (Fase 1)

- Chat com histórico, streaming e ferramentas visíveis, conectado a uma pasta do PC.
- Leitura automática da pasta: shapefiles, `.zip` do SIMCAR, recibo do CAR em PDF, prints.
- Geração de `.mxd` + `.pdf` + `.png` + `.xlsx` no padrão Harmonia.
- `.mxd` com **caminhos relativos** e camadas materializadas ao lado, para abrir em qualquer PC.
- Troca automática de município (definition query) e recentragem do minimapa.
- Consulta a WFS/WMS da SEMA, IBAMA, FUNAI, MapBiomas, INCRA, IBGE.
- Edição conversacional do mapa, cada edição gerando nova versão.
- Validação de conformidade com bloqueio quando um check HARD falha.
- Modo "olha esse print e faz igual": imagem ou `.zip` de referência → `MapSpec`.
- Doctor: diagnóstico do ambiente (ArcMap? Python 2.7? templates? fonte ESRI North? chaves?).
- Instalador Windows assinado.

### Dentro (Fase 2)

- Site com login, projetos persistentes e histórico entre máquinas.
- "Mapa por número do CAR": digita `MT102042/2017`, recebe o PDF sem instalar nada.
- Espaço de trabalho no backend com memória do projeto e dos imóveis do usuário.
- Ponte com o app desktop, para o `.mxd` ser gerado na máquina certa.
- Backend neste PC via Cloudflare Tunnel dedicado, **sem tocar nos tunnels existentes**.

### Fora, e por quê

| Fora da v1 | Motivo |
|---|---|
| Agente/app em Linux ou macOS | `arcpy` é Windows-only; o núcleo Python roda em Linux, mas sem `.mxd` |
| Edição de geometria (desenhar, cortar polígono) | é trabalho de GIS, não de cartografia — usa-se o ArcMap ou o QGIS |
| Pareceres, laudos e análises jurídicas | escopo do NexoGeo Ambiental e do GeoForest Oráculo |
| Escrita no SIMCAR (importar shape, processar geo) | domínio do GeoForest Oráculo; aqui é só leitura |
| Login em portal da SEMA | a sessão técnica do SIMCAR é **única**: o app logar derruba o técnico do navegador |
| ArcGIS Pro como caminho primário | Pro 3.x **não salva `.mxd`**; entra só como gerador de PDF alternativo |
| Suporte a QGIS (`.qgz`) | avaliar na v2 se houver demanda |
| Cobrança | depois da validação com usuários reais |

## Usuários

| Perfil | O que precisa | Como mede valor |
|---|---|---|
| Técnico de GIS / engenheiro florestal | série de mapas pronta, `.mxd` editável, sem retrabalho | horas por análise |
| Coordenador | consistência entre entregas de analistas diferentes | mapas devolvidos por erro de padrão |
| Cliente final (produtor rural) | PDF legível no padrão que já conhece | reclamações |

## Critérios de sucesso da v1

1. Uma análise completa (Dinâmica + temáticos + quantitativos) sai de uma pasta com o CAR em
   **menos de 10 minutos**, contra os dois dias da Harmonia.
2. 100% dos checks **HARD** passam em todos os mapas gerados.
3. O `.mxd` entregue **abre no ArcMap de outra pessoa** e todas as camadas resolvem — sem `!`
   vermelho, ou com um passo único e óbvio de vinculação.
4. Um técnico que nunca viu o sistema produz seu primeiro mapa válido em menos de 15 minutos,
   incluindo instalação.
5. Nenhum shapefile de cliente sai do PC dele sem consentimento explícito.
6. Reproduzir os 21 PDFs-modelo da Harmonia com diferença de raster < 0,3%.

## Riscos principais

| Risco | Impacto | Mitigação |
|---|---|---|
| **`arcpy` trava neste tipo de ambiente** — na máquina da Harmonia, `Describe`, `replaceDataSource`, cursores e `Project_management` davam *hang* infinito | crítico | motor usa só a API que comprovadamente funciona (`MapDocument`, `findAndReplaceWorkspacePaths`, `ListLayoutElements`, `ExportToPDF`); todo subprocesso com timeout; `ogr2ogr` para geometria. Ver [motor](../Fase_1_Desktop/planos/04-motor-mxd.md) |
| Usuário sem ArcMap | alto | caminho de patch de template + shapes homônimos; PDF pelo renderizador nativo |
| `arcpy` do ArcMap é Python 2.7 | alto | script isolado, comunicação por arquivo JSON UTF-8, nunca `argv` com acento |
| Templates `.mxd` precisam ser preparados e mantidos | alto | manifesto versionado com `sha256`, smoke test por template |
| Texto herdado de análise anterior vazando no mapa | médio | check `S11` varre todo `TEXT_ELEMENT` |
| IA inventar camada, estilo ou template inexistente | médio | validador rejeita `MapSpec` fora do catálogo |
| WFS da SEMA cair ou renomear layer | médio | cache local por bbox + descoberta fuzzy + catálogo versionado |
| Escopo virar "NexoGeo 2" | alto | a tabela "Fora da v1" é vinculante; incluir algo exige alterar este documento |

## Decisões tomadas

| # | Decisão | Data | Alternativas descartadas |
|---|---|---|---|
| D1 | **Desktop primeiro**, site depois | 2026-07-25 | site primeiro (foi o erro do NexoGeo) |
| D2 | Electron + React + sidecar Python | 2026-07-25 | Tauri (mais uma linguagem); PySide6 (chat muito mais trabalhoso) |
| D3 | DeepSeek V4 Pro com chave do usuário (BYOK) | 2026-07-25 | chave do dono no backend (acopla Fase 1 à Fase 2) |
| D4 | Suportar **com e sem ArcMap** | 2026-07-25 | exigir ArcMap (limita mercado); nunca usar ArcMap (perde fidelidade) |
| D5 | Perfil visual **Harmonia** como fonte da verdade | 2026-07-25 | perfil Trevisol; suportar os dois |
| D6 | `MapSpec` JSON validado por schema como contrato único | herdada | IA gerando código Python |
| D7 | Backend da Fase 2 **neste PC** + tunnel dedicado | 2026-07-25 | Render/Vercel (geo-block da SEMA); reusar tunnel existente (risco aos outros sistemas) |
| D8 | Acesso à SEMA só por WFS/WMS + recibo PDF | 2026-07-25 | API técnica do SIMCAR (sessão única); scraping do portal público (frágil) |
| D9 | Repositório público, chaves fora dos `.mxd` | 2026-07-25 | privar o repo; reescrever o histórico |
