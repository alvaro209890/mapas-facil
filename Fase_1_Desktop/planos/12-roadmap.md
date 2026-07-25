# F1-12 — Roadmap

Milestones da Fase 1 em ordem **desktop-first**: documentação → núcleo → motor `.mxd` → UI →
agente → conformidade Harmonia → instalador → piloto com usuário real. Cada marco tem critério de
saída objetivo — não se avança com "quase pronto".

A Fase 2 (site/backend) **não entra neste roadmap**. Ela começa só depois do M7 validado.

## Visão geral

```
M0 docs ──▶ M1 núcleo ──▶ M2 MXD ──▶ M3 UI ──▶ M4 agente ──▶ M5 Harmonia ──▶ M6 instalador ──▶ M7 piloto
  │            │            │          │           │              │                │              │
  └────────────┴────────────┴──────────┴───────────┴──────────────┴────────────────┴──────────────┘
                              MapSpec + fsguard são a fundação de tudo
```

| Marco | Nome curto | Depende de |
|---|---|---|
| M0 | Documentação e contratos | — |
| M1 | Núcleo + MapSpec + fsguard | M0 |
| M2 | Motor `.mxd` | M1 |
| M3 | UI e workspace | M1 |
| M4 | Agente | M1, M3 |
| M5 | Conformidade Harmonia | M2, M4 |
| M6 | Instalador | M1–M5 |
| M7 | Piloto | M6 |

M3 e M2 podem avançar em paralelo depois do M1. M4 precisa da UI (chat). M5 é integração
completa. M6 só começa quando M5 passa.

---

## Kickoff

Checklist dia a dia da implementação: [`13-checklist-implementacao.md`](13-checklist-implementacao.md).
Atualize as caixas no mesmo PR da tarefa.

## M0 — Documentação e contratos

**Objetivo:** congelar o que será construído antes de escrever código de produção. Evitar o erro
do NexoGeo — `.mxd` prometido e nunca especificado.

**Entregáveis:**

- Planos F1-00 a F1-13 revisados e consistentes entre si
- [`02-mapspec-contrato.md`](../../planos/02-mapspec-contrato.md) com schema JSON e exemplo canônico
- [`01-padrao-imap-harmonia.md`](../../planos/01-padrao-imap-harmonia.md) com os 14 HARD + 11 SOFT
- Acervo em `Referencias_IMAP/Mapas/01` (verdade) + `02` (Trevisol) + DOC MXD Harmonia
- `shared/`: catálogo de camadas, perfil visual, manifesto de templates com `sha256`
- Fixtures mínimos: `harmonia/` (ou equivalente anonimizado), `mapspecs/` válidos e inválidos
- `secrets.example.json`; chaves fora dos `.mxd` versionados

**Critério de saída:**

- [x] Planos F1 e comuns reestruturados; acervo 01/02 documentado
- [x] Nenhum plano menciona backend/site como pré-requisito da Fase 1
- [ ] Schema do `MapSpec` valida o exemplo canônico e rejeita 10 invariantes documentadas
- [ ] Manifesto de templates lista cada `.mxd` da v1 com `sha256`
- [ ] Dois revisores (ou dois agentes) leem F1-01 e F1-04 sem achar contradição

**Dependências:** nenhuma.

---

## M1 — Núcleo + MapSpec + fsguard

**Objetivo:** sidecar Python funcional, sem Electron, que valida `MapSpec`, indexa pasta, resolve
camadas locais e respeita a allowlist de disco. É a fundação de tudo.

**Entregáveis:**

- `nucleo/` com JSON-RPC NDJSON (stdio)
- `fsguard` com 100% de cobertura de linha e ramo
- Validador de `MapSpec` (schema + catálogo + invariantes)
- `workspace.abrir`, `workspace.inspecionar`, `mapspec.validar`
- Parser do recibo do CAR (CPF descartado na entrada)
- Leitura de shapefile, cálculo de área em UTM, quantitativos básicos
- Renderizador nativo de PDF (matplotlib) — um mapa simples de ponta a ponta
- Suíte de testes anel 1 no CI Linux

**Critério de saída:**

- [ ] `pytest` anel 1 verde no CI
- [ ] `fsguard`: todos os casos de [`10-testes-e-qa.md`](10-testes-e-qa.md) passam
- [ ] `mapspec.validar` rejeita camada fora do catálogo (`NU-210`) e escala inválida (`NU-220`)
- [ ] Recibo da Harmonia parseado corretamente; CPF ausente na saída
- [ ] Um `MapSpec` mínimo gera PDF nativo + `validacao.json` sem ArcMap
- [ ] CLI de dev: `python -m nucleo doctor` funciona

**Dependências:** M0 (schema, catálogo, fixtures).

---

## M2 — Motor `.mxd`

**Objetivo:** gerar `.mxd` editável no ArcMap **e** pelo patch de template quando não há ArcMap.
É o coração do produto e a parte que o NexoGeo não entregou.

**Entregáveis:**

- `arcpy_job.py` (Python 2.7, payload JSON, timeout)
- Caminho ArcMap: repor fontes, extent, escala, textos, definition query, exportar PDF
- Caminho patch (T2): manipulação OLE do template sem `arcpy`
- Materialização de camadas em `SHP/` com nomes que o template espera
- Troca de município (definition query) e recentro do minimapa
- Smoke test manual documentado (anel 4)
- T2 no CI Windows: gerar `.mxd` sem ArcMap, reabrir como OLE

**Critério de saída:**

- [ ] Com ArcMap 10.8: `Dinamica_2026.mxd` da pasta Harmonia abre sem `!` vermelho
- [ ] Sem ArcMap: T2 gera `.mxd` estruturalmente correto (extent, escala, textos, query)
- [ ] PDF do ArcMap e PDF nativo existem; diferença documentada
- [ ] `arcpy_job.py` nunca recebe acento em `argv` — payload só em arquivo JSON UTF-8
- [ ] Timeout mata subprocesso travado (`AG-020`)
- [ ] Nenhum texto de análise anterior no mapa gerado (prep para check `S11`)

**Dependências:** M1 (validação, camadas, quantitativos, fsguard).

---

## M3 — UI e workspace

**Objetivo:** app Electron com três painéis (pasta, chat, preview), conectado ao núcleo via
JSON-RPC. Sem agente ainda — botões e comandos manuais bastam.

**Entregáveis:**

- Electron main + renderer React
- Árvore da pasta com watcher
- Painel de preview (PNG do PDF gerado)
- Painel de `MapSpec` (JSON legível + diff entre versões)
- Doctor na sidebar (ArcMap? templates? chaves?)
- IPC seguro: renderer nunca toca disco nem segredos
- Fluxo: abrir pasta → validar spec → gerar mapa → ver checks

**Critério de saída:**

- [ ] Abrir a pasta Harmonia mostra ATP, AVN, AC, AUAS e o recibo
- [ ] Gerar mapa por botão (sem IA) produz arquivos em `Mapas/` e preview na UI
- [ ] `job.progresso` aparece com as 10 etapas
- [ ] Doctor mostra status de ArcMap, templates e chaves (sem exibir valores)
- [ ] Renderer não consegue ler arquivo fora do workspace (teste manual)
- [ ] Histórico de versões do MapSpec navegável (◀ v1 v2 ▶)

**Dependências:** M1 (núcleo rodando). Pode avançar em paralelo com M2.

---

## M4 — Agente

**Objetivo:** chat com streaming e tools tipadas que produzem `MapSpec` — não código. DeepSeek V4
Pro com chave do usuário (BYOK).

**Entregáveis:**

- `chat.enviar` com stream de `chat.delta` e `chat.tool`
- Tools: `estado_do_projeto`, `ler_recibo_car`, `listar_camadas`, `consultar_sema`,
  `criar_mapa`, `adicionar_camada`, `definir_tabela`, `validar_mapspec`, `gerar_mapa`
- Integração Credential Manager (via main process)
- Modo determinístico sem IA (template fixo)
- Fake do provedor (VCR) para CI
- Guard rails: teto de 12 rodadas, tool inexistente → `IA-020`

**Critério de saída:**

- [ ] "Faz a Dinâmica 2026 dessa pasta" na Harmonia gera os três arquivos sem intervenção
- [ ] Tools visíveis no chat (estilo Cursor)
- [ ] Sem chave DeepSeek: modo determinístico gera a série com aviso
- [ ] Com chave: streaming funciona; cancelamento de turno limpa estado
- [ ] Nenhuma tool executa código arbitrário — só `MapSpec` declarativo
- [ ] Testes VCR do anel 2 verdes no CI

**Dependências:** M1 (núcleo, validação), M3 (UI de chat). Motor `.mxd` (M2) necessário para
geração real, mas o agente pode ser testado com PDF nativo antes do M2 fechar.

---

## M5 — Conformidade Harmonia

**Objetivo:** série IMAP completa da Harmonia com 14 checks HARD verdes e paridade visual com os
PDFs-modelo. É o marco que prova que o produto funciona de verdade.

**Entregáveis:**

- Validador de saída (`validacao.json` com HARD/SOFT)
- Série completa: Dinâmica (retrato) + temáticos (paisagem) + quantitativos
- Tabela PNG ≥ 600 dpi + `Quantitativos.xlsx`
- Comparação raster com os 21 PDFs-modelo (tolerância < 0,3%)
- Edição conversacional com versionamento (`_v2`, anteriores intactos)
- Modo "olha esse print/zip e faz igual" (visão)
- Bloqueio em falha HARD; aviso em SOFT

**Critério de saída:**

- [ ] 19 mapas da Harmonia em < 10 minutos (com ArcMap) ou tempo documentado sem ArcMap
- [ ] 100% dos checks HARD passam em todos os mapas
- [ ] Diferença raster < 0,3% contra PDFs-modelo
- [ ] `.mxd` abre no ArcMap de **outro PC** (camadas resolvem ou um passo óbvio)
- [ ] "Muda a cor da AVN" gera `_v2` sem apagar v1
- [ ] Check `S11` (texto herdado) passa em todos os mapas
- [ ] `validacao.json` declara `confianca: "arcpy"` ou `"estrutural"` honestamente

**Dependências:** M2 (motor), M4 (agente para fluxo conversacional). M3 para preview.

---

## M6 — Instalador

**Objetivo:** transformar o app de "clone o repo e rode" em `.exe` instalável, assinado, com
auto-update. Um técnico instala em 15 minutos e produz o primeiro mapa.

**Entregáveis:**

- PyInstaller onedir do núcleo (decisão P1)
- `electron-builder` + NSIS
- Credential Manager integrado na build de produção
- Auto-update (`electron-updater` + `latest.yml`)
- Assinatura Authenticode (ou exceção documentada para piloto)
- `sha256.txt` na release
- Testes anel 3 no CI Windows

**Critério de saída:**

- [ ] Instalação limpa em Windows 11 sem Python pré-instalado
- [ ] T2 completo passa após instalação (máquina sem ArcMap)
- [ ] Instalador < 250 MB (P5) ou desvio justificado
- [ ] Auto-update de N para N+1 funciona
- [ ] Desinstalação limpa
- [ ] Critérios de [`11-empacotamento-instalador.md`](11-empacotamento-instalador.md) atendidos

**Dependências:** M1–M5 (produto funcional antes de empacotar). M5 é bloqueante — não se
empacota um gerador que não passa na Harmonia.

---

## M7 — Piloto

**Objetivo:** um técnico de GIS real (não o desenvolvedor) produz uma análise completa com o
instalador, sem suporte presencial. Valida o critério de sucesso da v1.

**Entregáveis:**

- Build `stable` assinada distribuída a 1–3 usuários piloto
- Roteiro de onboarding (15 min do download ao primeiro mapa)
- Canal de feedback (issue, formulário ou chat direto)
- Registro do smoke test ArcMap (anel 4) anexado à release
- Lista de bugs encontrados, classificados por severidade (S1–S4)

**Critério de saída:**

- [ ] Piloto instala sozinho em < 15 minutos
- [ ] Primeiro mapa válido sem ajuda do desenvolvedor
- [ ] Análise completa (não só Harmonia) em imóvel novo do piloto
- [ ] Zero bugs S1 ou S2 abertos
- [ ] Feedback do piloto incorporado ou registrado como pendência pós-v1
- [ ] Critérios de aceite de [`00-visao-e-escopo.md`](00-visao-e-escopo.md) verificados

**Dependências:** M6 (instalador). Acesso a máquina piloto com ou sem ArcMap (testar os dois
cenários se possível).

---

## O que fica depois do M7

| Item | Quando |
|---|---|
| Fase 2 (site, backend, tunnel) | após M7 validado |
| Certificado EV (se piloto usou OV) | se SmartScreen ainda assusta |
| ArcGIS Pro como gerador de PDF alternativo | demanda do piloto |
| Linux/macOS | fora da v1 por design |
| Cobrança | após validação com usuários reais |
| Rotação das chaves vazadas nos `.mxd` | pendência de segurança, independente do roadmap |

## Riscos do roadmap

| Risco | Marco afetado | Mitigação |
|---|---|---|
| `arcpy` trava em subprocesso | M2, M5 | timeout, API mínima comprovada, caminho T2 |
| M2 demora e bloqueia tudo | M5, M6 | T2 (patch) avança em paralelo; PDF nativo desbloqueia M3/M4 |
| Instalador > 250 MB | M6 | auditoria de deps na decisão P1 (onedir) |
| Piloto não tem ArcMap | M7 | caminho sem ArcMap já testado no M6; expectativa alinhada |
| Escopo vira "NexoGeo 2" | qualquer | tabela "Fora da v1" em [`00-visao-e-escopo.md`](00-visao-e-escopo.md) é vinculante |
