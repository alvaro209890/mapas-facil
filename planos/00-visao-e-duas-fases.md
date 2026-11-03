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

> **Nota (2026-11-03):** existe uma **Fase 3** — app web com login e chat de IA, backend no
> server-desktop — em [`../Fase_3_Web/`](../Fase_3_Web/README.md), com as decisões D22–D39 no fim
> deste arquivo. As duas fases descritas abaixo continuam valendo como estão; a Fase 3 não
> substitui nenhuma das duas.

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
| Conta | **login obrigatório** com **e-mail + senha local** (SQLite neste PC); depois de autenticado, **sem limite de uso** (D10 revisada, D18). Sem Google |
| Funciona offline? | **Sim, por completo** com sessão local: gera mapa com shapes locais e cache. Sem login → modo leitura (D11). Sem chave DeepSeek: galeria/modo determinístico |
| Depende da Fase 2? | **Não**. Site = só distribuição (D21). Conta nuvem ([F2-05](../Fase_2_Site/planos/05-auth-e-memoria.md)) adiada |
| Motor de `.mxd` | ArcPy quando há ArcMap; **patch de template** quando não há |

### Fase 2 — Site de distribuição do produto

[`../Fase_2_Site/`](../Fase_2_Site/README.md)

Site **público** só para **distribuir** o Mapas Fácil: vitrine, requisitos e download do
instalador Windows. **Não** tem login, **não** cria conta e **não** gera mapa. Conta e mapas
ficam no [app desktop](../Fase_1_Desktop/README.md) (D10, D21).

| Aspecto | Decisão |
|---|---|
| Stack v1 | Next.js (landing/marketing) em `Fase_2_Site/web/` |
| Backend v1 | **ausente** — sem FastAPI/Postgres para distribuição |
| Onde publica | `mapasfacil.cursar.space` no PC servidor (tunnel/host dedicado; sem tocar tunnels existentes) |
| Depende da Fase 1? | Aponta para o instalador (M10); não reusa núcleo geo no site |
| Gera mapa / `.mxd` / PDF? | **Não** — só o desktop |

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

- **Conta obrigatória local**: criar/entrar com e-mail e senha salvos neste PC (SQLite), sem
  Google e sem backend; sem limites de uso depois de autenticado
  ([F1-14](../Fase_1_Desktop/planos/14-auth-e-conta.md)).
- **Galeria de modelos** com preview real e montagem determinística de `MapSpec` — a porta que
  funciona sem chave de IA ([F1-15](../Fase_1_Desktop/planos/15-galeria-de-modelos.md)).
- **Interface escura** com tipografia embarcada e animações amarradas a eventos reais do núcleo
  ([F1-16](../Fase_1_Desktop/planos/16-design-system-dark.md)).
- **Histórico de conversas local**, reabrível, com busca e ramificação
  ([F1-17](../Fase_1_Desktop/planos/17-persistencia-de-conversas.md)).
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

- Site público de **distribuição**: landing, requisitos, download do instalador (ou “em breve”
  até o M10), contato/links ([F2-00](../Fase_2_Site/planos/00-visao-e-escopo.md)).
- Publicação em `mapasfacil.cursar.space` no PC servidor, **sem** alterar tunnels de outros
  sistemas ([F2-06](../Fase_2_Site/planos/06-deploy-tunnel-neste-pc.md)).

### Fora da Fase 2 v1 (continua só no desktop ou adiado)

- Login / criar conta no site — conta é local no app ([F1-14](../Fase_1_Desktop/planos/14-auth-e-conta.md)).
- Gerar mapa, PDF, `.mxd` ou “mapa por CAR” no browser.
- Chat web, projetos na nuvem, memória entre máquinas, ponte de jobs ([F2-05](../Fase_2_Site/planos/05-auth-e-memoria.md) adiado).
- FastAPI + Postgres + consultas WFS no site.

### Fora da v1, e por quê (tabela vinculante)

Incluir qualquer item desta tabela exige alterar **este documento** e
[`../Fase_1_Desktop/planos/00-visao-e-escopo.md`](../Fase_1_Desktop/planos/00-visao-e-escopo.md)
no mesmo commit.

| Fora da v1 | Motivo |
|---|---|
| **Cobrança, planos, trial** | a v1 valida o produto, não o modelo de negócio |
| **Quota, rate limit de produto, feature flag de cobrança** | D18: autenticado = ilimitado. Rate limit de *abuso* nos endpoints de auth não conta |
| **Sync de conversas para a nuvem** | ~~D20: local-only~~ — **revisto pela Fase 3 (D26)**: na web as conversas vivem no servidor; o desktop continua local-only e não há sync entre os dois |
| **Login / mapa / chat no site** | ~~D21: site = distribuição; produto = desktop~~ — **revisto pela Fase 3 (D22, D34)**: a landing da Fase 2 continua só distribuição, mas o **app web** ganha hostname próprio (`mapasfacil-app.cursar.space`) com login, chat e geração de mapa |
| **Marketplace/compartilhamento de modelos de galeria** | modelo novo exige template preparado no ArcMap |
| **Multi-conta simultânea, times, organizações** | uma conta por instalação |
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
| D7 | Publicar Fase 2 no PC servidor + tunnel/host **dedicado** (`mapasfacil.cursar.space`); sem reusar tunnels existentes. API geo neste PC **não** é requisito da v1 do site (D21) *(recontextualizada 2026-07-27)* | 2026-07-25 | Render/Vercel como primário; reusar tunnel existente |
| D21 | Fase 2 v1 = **site de distribuição** (landing + download). Sem login no site; sem gerar mapa no site | 2026-07-27 | site com chat, mapa por CAR, conta nuvem e backend geo na v1 |
| D8 | Acesso à SEMA só por WFS/WMS + recibo PDF | 2026-07-25 | API técnica do SIMCAR (sessão única); scraping do portal público (frágil) |
| D9 | Repositório público, chaves fora dos `.mxd` | 2026-07-25 | privar o repo; reescrever o histórico |

### D10–D20 — conta, interface, galeria e contexto (2026-07-25)

Fechadas com o dono do produto na rodada que reescreveu os planos para agentes. Cada uma tem a
alternativa descartada registrada, para que nenhum agente reabra a discussão sozinho.

| # | Decisão | Alternativa descartada | Plano dono |
|---|---|---|---|
| D10 | **Login obrigatório** com **e-mail + senha**, conta **local** em SQLite neste PC. Sem Google/OAuth/backend na v1. [F2-05](../Fase_2_Site/planos/05-auth-e-memoria.md) **não** bloqueia a Fase 1 *(revisada 2026-07-26)* | Google via site + F2-05 bloqueante; Firebase/Clerk/Auth0 | [F1-14](../Fase_1_Desktop/planos/14-auth-e-conta.md) |
| D11 | Sem sessão **local** válida, `mapa.gerar` é **bloqueado** (`AUTH-030`); o app fica em modo leitura. Sessão não depende de rede *(revisada 2026-07-26)* | JWT 12 h + refresh remoto; carência offline artificial | [F1-14](../Fase_1_Desktop/planos/14-auth-e-conta.md) |
| D12 | Auth **sem** porta HTTP/loopback OAuth no PC. Senha só no main/núcleo (hash Argon2id); renderer nunca vê senha/hash *(revisada 2026-07-26)* | PKCE + loopback `127.0.0.1` como fluxo primário; Google OAuth | [F1-14](../Fase_1_Desktop/planos/14-auth-e-conta.md) |
| D13 | Conversas num **banco SQLite único** em `%APPDATA%\MapasFacil\chats\chats.sqlite`, agrupadas por `workspace_fingerprint` | um banco por projeto (sidebar só via chats do workspace aberto); JSON por conversa (busca e paginação manuais) | [F1-17](../Fase_1_Desktop/planos/17-persistencia-de-conversas.md) |
| D14 | **Logout não apaga** o histórico local; existe ação separada "Sair e esquecer este PC" | apagar no logout (usuário perde trabalho ao trocar de conta) | [F1-17](../Fase_1_Desktop/planos/17-persistencia-de-conversas.md) |
| D15 | **Tema escuro por padrão**; tipografia Space Grotesk (display) + IBM Plex Sans (UI) + IBM Plex Mono (números), **embarcadas** | Inter/Roboto/system (genérico); serifada editorial; tema claro default | [F1-16](../Fase_1_Desktop/planos/16-design-system-dark.md) |
| D16 | **Galeria** em `shared/galeria/modelos.json`, versionada por `galeria_version`; galeria e chat produzem **o mesmo** `MapSpec` pelo mesmo código | galeria como atalho de UI que monta spec por conta própria | [F1-15](../Fase_1_Desktop/planos/15-galeria-de-modelos.md) |
| D17 | **Compressão de contexto obrigatória**: memória de trabalho + últimos 8 turnos verbatim + resumo por `deepseek-v4-flash`; `MapSpec` por diff | mandar índice e spec completos a cada turno (estoura contexto e custo) | [F1-06](../Fase_1_Desktop/planos/06-agente-eng-florestal.md) |
| D18 | **v1 autenticada é ilimitada**: sem quota, paywall, rate limit de produto ou feature flag de cobrança | trial/limite "só para começar" | [F1-14](../Fase_1_Desktop/planos/14-auth-e-conta.md) |
| D19 | Eventos de construção parcial (`job.artefato_parcial`) são **contrato novo a implementar** no núcleo (M8). Até lá, a animação usa só `job.progresso` — **nunca** loader falso | simular progresso na UI enquanto o núcleo não reporta | [F1-16](../Fase_1_Desktop/planos/16-design-system-dark.md) |
| D20 | Conversas **local-only** na v1; espelho na conta é **adiado** e opt-in (não é a v1 do site) | sync automático para a conta | [F1-17](../Fase_1_Desktop/planos/17-persistencia-de-conversas.md) |
| D21 | Site Fase 2 v1 = **distribuição** (landing + download); sem login e sem mapa no site | chat/mapa/conta nuvem no site na v1 | [F2-00](../Fase_2_Site/planos/00-visao-e-escopo.md) |

### D22–D39 — Fase 3: app web com chat de IA (2026-11-03)

Fechadas com o Álvaro na rodada de planejamento da Fase 3. O texto completo, com o contexto e as
respostas P1–P10, está em
[`../Fase_3_Web/planos/00-visao-e-decisoes.md`](../Fase_3_Web/planos/00-visao-e-decisoes.md).
A coluna **Revisa** diz o que cada uma muda deste documento — nada além disso é revisado.

| # | Decisão | Revisa |
|---|---|---|
| D22 | Existe uma **Fase 3**: app web com login + chat de IA que cria/edita mapas, backend no server-desktop. A landing de distribuição (Fase 2) continua; o desktop (Fase 1) continua | D21 (só para o app web; a landing segue D21) |
| D23 | O backend **não reimplementa regra geo**: hospeda o núcleo `mapasfacil_nucleo` como processo filho por projeto, no mesmo NDJSON por stdio que o Electron usa | — |
| D24 | No servidor, `.mxd` só sai do **motor binário** (patch de template + `mxd_binario`); ArcMap/ArcPy **nunca** rodam no servidor | AP-01 do `AGENT_BRIEF.md` |
| D25 | **Um projeto = um mapa** (ou uma série). O projeto nasce com `folha` (A4–A0) e `orientacao`; a entrada é **um** `.zip`; há **uma** conversa principal | — |
| D26 | Projetos, conversas e versões da Fase 3 ficam **no servidor**; o desktop continua local-only | D20 e AP-12, só para a Fase 3 |
| D27 | **Cadastro aberto** (nome, e-mail, senha com Argon2id), sem confirmação de e-mail; a única trava é o admin bloquear a conta. Sem OAuth | F2-05 (adiado) → W-11 |
| D28 | Metadados do backend em **SQLite WAL**, um processo uvicorn. Postgres só se houver mais de uma instância | — |
| D29 | Eventos para o navegador por **SSE** com replay por `Last-Event-ID`; comandos por `POST`. Sem WebSocket na v1 | — |
| D30 | Toda animação do palco é **consequência de evento real**; o vocabulário ganha `viewport.foco`, `camada.renderizada` e `layout.elemento` | reforça AP-07 |
| D31 | Folhas maiores que A4 = **perfil A4 medido escalado por igual** (mesma razão √2); nenhum layout novo é inventado | H02 vira H02 (A4) + H15 (folha do `MapSpec`) |
| D32 | Templates `.mxd` por folha são **fabricados uma vez no Windows** e entram no servidor com `sha256` no MANIFEST; o servidor só remonta | — |
| D33 | A IA do servidor é o **9Router central da VPS** (`http://100.104.255.35:20128/v1`), `ag/gemini-3.8-flash-high`, `reasoning_effort: high`, com chave própria do Mapas Fácil. A **visão usa o mesmo modelo** (`MAPASFACIL_MODELO_VISAO`) | BYOK do desktop continua só no desktop |
| D34 | Hostname do app: **`mapasfacil-app.cursar.space`** (um nível — o certificado `*.cursar.space` não cobre dois níveis); API no mesmo host em `/api/v1` | D21 (só para o app web) |
| D35 | Dado de cliente **nunca** entra no git; testes usam ZIPs sintéticos de `Fase_3_Web/fixtures/` | reforça AP-03/AP-09 |
| D36 | O `MapSpec` sobe para `contract_version: 3` com bloco obrigatório `folha`; v2 é migrado na leitura | [`02-mapspec-contrato.md`](02-mapspec-contrato.md) |
| D37 | **Pacote sempre liberado**: PDF, XLSX e o pacote ArcMap (`.zip` com `MXD/`, `SHP/`, `Mapas/`) sem validação manual. Check HARD falho marca a versão "não conforme" e a IA explica — **não** bloqueia download; G4 é teste de desenvolvimento | AP "HARD bloqueia a entrega" |
| D38 | Enquadramento = **"zoom na camada"** como no ArcMap (medido na Análise PH): faixa útil, margem, escala redonda para cima, a mesma escala na série, sem lista fixa | H05 e a lista fixa de escalas |
| D39 | Regras do escritório no núcleo: série Dinâmica só com AC/AVN/tabela em 2000, 2008 e atual; imagem por ano (SEMA até 2015, Planet de outubro a partir de 2016); AC/AVN em hachura sobre satélite; nenhum texto cobre linha de shapefile | — |

### Como um agente lê estas decisões

Uma decisão fechada **não é sugestão**. Se a implementação parecer pedir o contrário, o caminho é
registrar a divergência como pendência no plano dono e perguntar — não decidir sozinho no código.
Os anti-padrões derivados destas decisões estão em
[`../AGENT_BRIEF.md`](../AGENT_BRIEF.md#anti-padrões--vinculantes-para-qualquer-agente-implementador).
