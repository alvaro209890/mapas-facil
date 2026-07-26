# F1-12 — Roadmap

## Objetivo

Ordenar os marcos da Fase 1 por **dependência técnica**, com critério de saída objetivo em cada
um. Não se avança com "quase pronto", e não há estimativa em dias ou semanas — a ordem é o
grafo de dependências, não um calendário.

A Fase 2 (site/backend geo) **não entra neste roadmap**. Conta do app = **local** ([F1-14](14-auth-e-conta.md));
[F2-05](../../Fase_2_Site/planos/05-auth-e-memoria.md) é pós-M11 e **não** bloqueia o M5.

## Snapshot (2026-07-26)

| Faixa | Marcos | Estado |
|---|---|---|
| Fechado sem ArcMap | M0, M1A, M3, M4, M5, M6, M7, M8 (+ F1-07, A9–A13, polish) | **feito** |
| Parcial / próximo | **M2** (motor `.mxd`) | exige Windows + ArcMap |
| Não iniciado | **M9** → **M10** → **M11** | Harmonia, instalador, piloto |
| Depois | Fase 2 | após M11 |

Backlog desktop **sem** ArcMap: esgotado. Detalhe vivo:
[`../../AGENT_BRIEF.md`](../../AGENT_BRIEF.md#snapshot--o-que-falta-2026-07-26).

**No PC Windows:** execute [`../GUIA_WINDOWS.md`](../GUIA_WINDOWS.md) (M2 → M9 → M10 → M11).

## Grafo

```
M0 docs ──▶ M1 núcleo ──┬──▶ M2 motor .mxd ─────────────────────────────┐
                        │                                               │
                        └──▶ M3 shell + design system ──┬──▶ M4 galeria │
                                                        │               │
                                                        ├──▶ M5 conta local ─┤
                                                        │               │
                                                        └──▶ M6 chats ──┴──▶ M7 agente
                                                                              │
                                                                              ▼
                                                                        M8 motion/preview
                                                                              │
                                            M2 + M8 ──────────────────────▶ M9 Harmonia
                                                                              │
                                                                              ▼
                                                                        M10 instalador
                                                                              │
                                                                              ▼
                                                                          M11 piloto
```

| Marco | Nome curto | Depende de | Exige ArcMap? | Exige rede? |
|---|---|---|---|---|
| M0 | Documentação e contratos | — | não | não |
| M1 | Núcleo + `MapSpec` + `fsguard` | M0 | não | não |
| M2 | Motor `.mxd` | M1 | **sim** (T1); T2 não | não |
| M3 | Shell Electron + design system dark | M1 | não | não |
| M4 | Galeria + geração determinística | M3 | não | não |
| M5 | Conta local (e-mail + senha) | M3 | não | **não** |
| M6 | Persistência de conversas | M3 | não | não |
| M7 | Agente DeepSeek + compressão | M4, M6 | não | sim (fake no CI) |
| M8 | Motion e preview de construção | M7 | não | não |
| M9 | Conformidade Harmonia | M2, M8 | **sim** para paridade T1 | sim |
| M10 | Instalador | M1–M9 | não | não |
| M11 | Piloto | M10 | depende do piloto | sim |

**Um agente sem Windows e sem ArcMap fecha M3, M4, M5, M6, M7 e M8 inteiros.** Só M2, M9 (para a
paridade T1) e partes de M10/M11 exigem a máquina do usuário.

### Mapeamento com a numeração antiga

Planos e commits anteriores a esta rodada usavam outra numeração. Equivalência:

| Antigo | Novo |
|---|---|
| M3 — UI e workspace | **M3** (agora inclui design system) |
| M4 — Agente | **M7** |
| M5 — Conformidade Harmonia | **M9** |
| M6 — Instalador | **M10** |
| M7 — Piloto | **M11** |

M4, M5, M6 e M8 são novos.

---

## M0 — Documentação e contratos

**Objetivo:** congelar o que será construído antes de escrever código de produção, em formato
executável por agente.

**Critério de saída:**

- [x] Planos F1 e comuns reestruturados; acervo 01/02 documentado
- [x] Nenhum plano menciona backend/site como pré-requisito da Fase 1, **exceto** o serviço de
      identidade (D10), que está declarado como tal
- [x] `AGENT_BRIEF.md` com estado real, ordem de marcos, gap analysis e anti-padrões
- [x] Planos de auth, galeria, design system e persistência de conversas escritos com DoD
- [ ] Schema do `MapSpec` valida o exemplo canônico e rejeita 10 invariantes documentadas
- [ ] Manifesto de templates lista cada `.mxd` da v1 com `sha256`
- [ ] Dois agentes leem F1-01 e F1-04 sem achar contradição

---

## M1 — Núcleo + `MapSpec` + `fsguard`

**Objetivo:** sidecar Python funcional, sem Electron, que valida `MapSpec`, indexa pasta, resolve
camadas locais e respeita a allowlist de disco.

**Estado: bloco A fechado, bloco B parcial (v0.4.0).** Detalhe em
[13-checklist-implementacao.md](13-checklist-implementacao.md).

**Critério de saída:**

- [x] `pytest` anel 1 verde no CI
- [x] `fsguard`: todos os casos de [`10-testes-e-qa.md`](10-testes-e-qa.md) passam, 100% de cobertura
- [x] `mapspec.validar` rejeita camada fora do catálogo (`NU-210`) e escala inválida (`NU-220`)
- [x] Recibo da Harmonia parseado corretamente; CPF ausente na saída
- [x] Um `MapSpec` mínimo gera PDF nativo + `validacao.json` sem ArcMap
- [x] CLI de dev: `python -m mapasfacil_nucleo doctor` funciona
- [ ] **`mapa.gerar` emite `job.progresso` nas 10 etapas** (hoje `envelope_evt` não tem chamador)
- [ ] `mapa.cancelar` mata a árvore de processos
- [ ] `cofre.definir` / `existe` / `testar` implementados, sem devolver valor

---

## M2 — Motor `.mxd`

**Objetivo:** gerar `.mxd` editável no ArcMap **e** pelo patch de template quando não há ArcMap.
É o coração do produto e a parte que o NexoGeo não entregou.

**Critério de saída:**

- [ ] Com ArcMap 10.8: `Dinamica_2026.mxd` da pasta Harmonia abre sem `!` vermelho
- [ ] Sem ArcMap: T2 gera `.mxd` estruturalmente correto (extent, escala, textos, query)
- [ ] PDF do ArcMap e PDF nativo existem; diferença documentada
- [ ] `arcpy_job.py` nunca recebe acento em `argv` — payload só em arquivo JSON UTF-8
- [ ] Timeout mata subprocesso travado (`AG-020`)
- [ ] `dinamica_retrato` sai de `parcial` para `pronto` no MANIFEST, com offsets calibrados
- [ ] Nenhum texto de análise anterior no mapa gerado (prep para o check `S11`)

**Dependências:** M1. Pode avançar em paralelo com M3–M8.

---

## M3 — Shell Electron + design system dark

**Objetivo:** app Electron com os quatro painéis, tokens de tema, tipografia embarcada e ponte
NDJSON com o núcleo. Sem agente e sem auth ainda — a galeria e os botões vêm no M4.

**Entregáveis:** [F1-02](02-ui-chat-e-workspace.md) e [F1-16](16-design-system-dark.md).

**Critério de saída:**

- [ ] `Fase_1_Desktop/app/` existe, versionada, com build reproduzível (`pnpm build`)
- [ ] Abrir a pasta Harmonia mostra ATP, AVN, AC, AUAS e o recibo, com áreas em pt-BR 4 casas
- [ ] Tema escuro por padrão: `dataset.tema === "escuro"` numa instalação limpa
- [ ] Fontes embarcadas; `grep -rn "fonts.googleapis\|cdn\." app/src/` vazio
- [ ] `job.progresso` (do M1) aparece na `barra-progresso-job` com as 10 etapas em português
- [ ] Doctor mostra ArcMap, templates e chaves (booleanos, sem valores)
- [ ] Renderer não lê arquivo fora do workspace — teste espera `NU-010`
- [ ] `axe-core` sem violação de contraste nas telas vazia e com job
- [ ] Reduced-motion respeitado (nada acima de 80 ms)

**Dependências:** M1. Paralelo com M2.

---

## M4 — Galeria + geração determinística

**Objetivo:** o usuário gera a série inteira **sem IA e sem login de outro serviço**, escolhendo
um modelo na galeria. É o caminho de teste em CI e o fallback de todo o produto.

**Entregáveis:** [F1-15](15-galeria-de-modelos.md).

**Critério de saída:**

- [x] `shared/galeria/modelos.json` + schema + previews reais extraídos de `Referencias_IMAP/Mapas/01/`
- [x] `galeria.listar` devolve status coerente com o MANIFEST e com o índice da pasta
- [x] `galeria.montar_mapspec` do `dinamica_2026_retrato` passa em `mapspec.validar` sem erros
- [x] Determinismo: 3 execuções produzem JSON idêntico (exceto ULID)
- [x] Pasta sem `ATP` → `NU-233` com `requisitos_faltando`
- [x] `sobrescritas` fora da allowlist → `NU-232`
- [x] Clicar num cartão `indisponivel` não dispara requisição
- [ ] Fluxo completo pela UI: galeria → montar → validar → gerar → preview
      (montar na UI fechado; validar/gerar/preview dependem de auth M5 + motor + M8)

**Dependências:** M3.

---

## M5 — Conta local (e-mail + senha)

**Objetivo:** login obrigatório com **e-mail e senha** salvos em SQLite **neste PC**, gate de
sessão no núcleo. Sem Google, sem site, sem backend. **Acesso ilimitado depois de autenticado**
(D18). Funciona **offline**.

**Entregáveis:** [F1-14](14-auth-e-conta.md). ([F2-05](../../Fase_2_Site/planos/05-auth-e-memoria.md)
não faz parte deste marco.)

**Critério de saída:**

- [x] `contas.sqlite` com hash Argon2id; senha **nunca** em claro nem no renderer
- [x] Criar conta → sair → entrar de novo com o mesmo e-mail/senha
- [x] “Lembrar neste PC”: reabrir o app já `conectado` sem redigitar
- [x] Senha errada → `AUTH-002` (mensagem genérica)
- [x] E-mail duplicado → `AUTH-070`
- [x] `mapa.gerar` sem sessão → `AUTH-030`; `workspace.abrir` funciona sem sessão
- [x] Sem rede (airplane mode): criar/entrar/gerar funcionam (tudo local)
- [x] Nenhum fluxo Google / OAuth / `openExternal` de login
- [x] `grep -rn "quota\|rate_limit\|paywall\|trial" app/ nucleo/` sem restrição de produto

**Dependências:** só M3.

**Estado: fechado em 2026-07-26** (Bloco E).

---

## M6 — Persistência de conversas

**Objetivo:** histórico local reabrível, com busca, renomear, arquivar, apagar e ramificar.

**Entregáveis:** [F1-17](17-persistencia-de-conversas.md).

**Critério de saída:**

- [x] `chats.sqlite` criado e migrado no boot; `schema_versao = 1`
- [x] Criar conversa → fechar o app → reabrir → histórico íntegro com tool traces
- [x] Conversa de 200 mensagens abre com 30 mensagens + `total: 200` (teto 800 ms no CI)
- [x] Busca acentuada ↔ sem acento funciona (FTS5 `remove_diacritics 2`)
- [x] CPF escrito no chat não aparece no arquivo (`grep -a` vazio)
- [x] `chat.ramificar` cria conversa com `parent_conversation_id`
- [ ] Logout sem "esquecer este PC" preserva o banco (espera M5)
- [x] Pacote `conversas/` sem cliente HTTP

**Dependências:** M3. Independente de M5 (chats criados antes do login têm `conta_id` nulo).

**Estado: fechado em 2026-07-26** (Bloco F).

---

## M7 — Agente DeepSeek + compressão de contexto

**Objetivo:** chat com streaming e tools tipadas que produzem `MapSpec` — não código — com
orçamento de contexto respeitado.

**Entregáveis:** [F1-06](06-agente-eng-florestal.md).

**Critério de saída:**

- [x] `pytest` do agente verde **sem rede e sem chave** (FakeProvedor + VCR)
- [x] O agente usa `usar_modelo_da_galeria` e **não** `criar_mapa` quando há modelo
- [x] Paridade galeria↔chat no `template`, `camadas[].id` e `elementos_layout`
- [x] 13ª rodada de tool → `IA-030` com mensagem clara
- [x] Fixture de 120 turnos: payload ≤ 60.000 tokens, verbatim limitado, `compact_summary` presente
- [x] Teste de vazamento: sem WKT, sem CPF, sem `C:\Users\`, sem `PLAK`, sem `authkey`
- [x] Cancelar turno encerra o request e grava a mensagem parcial
- [x] Sem chave: `IA-001` e a UI aponta a galeria; nenhum request sai
- [x] Cassetes VCR (passos + SSE) em `tests/agente/cassetes/`
- [x] MapSpec vivo persistido em `chats/mapspecs/<id>.json`

**Nota:** as 3 tools que respondiam `IA-022` no fechamento do M7 (`consultar_sema`, `distancia_ate`,
`analisar_referencia`) ficaram reais depois — A13 (R21) e F1-07 fecharam as três; não bloquearam
o critério de fechamento do M7 na época.

**Dependências:** M4 (a galeria é a fonte de template) e M6 (onde o transcript vive).

**Estado: fechado em 2026-07-26** (Bloco G).

---

## M8 — Motion e preview de construção do mapa

**Objetivo:** as animações que fazem o produto parecer um instrumento, todas amarradas a evento
real. Inclui o contrato novo `job.artefato_parcial` no núcleo.

**Entregáveis:** [F1-16](16-design-system-dark.md) §A1–A6.

**Critério de saída:**

- [x] `job.artefato_parcial` emitido pelo núcleo nos quatro tipos (`camada`, `tabela_png`,
      `preview_png`, `pdf`), com caminho **relativo**
- [x] ≥ 3 animações provadas por teste com evento injetado (streaming, tool, progresso, artefato)
- [x] `grep -rn "setInterval" app/src/motion/ app/src/componentes/Barra*` vazio
- [x] `painel-preview` troca do esqueleto para a rasterização real com crossfade
- [x] Reduced-motion continua verde depois de todas as animações entrarem
- [~] Nenhum spinner sem evento correspondente — coberto por teste (cada animação tem o caso
      "antes do evento não existe"); a revisão manual entra na release

As microinterações A6 de watcher de pasta e de troca de versão fecharam depois deste marco, em
A12 (`workspace.mudou`) e H6 (`mapspec.atualizado`) — nenhuma foi simulada antes de o evento
existir (AP-07).

**Dependências:** M7 (para `chat.delta`/`chat.tool`) e M1 (para `job.progresso`).

---

## M9 — Conformidade Harmonia

**Objetivo:** série IMAP completa da Harmonia com 14 checks HARD verdes e paridade visual com os
PDFs-modelo. É o marco que prova que o produto funciona de verdade.

**Critério de saída:**

- [ ] 19 mapas da Harmonia em < 10 minutos (com ArcMap) ou tempo documentado sem ArcMap
- [ ] 100% dos checks HARD passam em todos os mapas
- [ ] Diferença raster < 0,3% contra os PDFs-modelo
- [ ] `.mxd` abre no ArcMap de **outro PC**
- [ ] "Muda a cor da AVN" gera `_v2` sem apagar v1
- [ ] Check `S11` (texto herdado) passa em todos os mapas
- [ ] `validacao.json` declara `confianca: "arcpy"` ou `"estrutural"` honestamente

**Dependências:** M2 (motor) e M8 (fluxo completo pela UI).

---

## M10 — Instalador

**Objetivo:** transformar o app em `.exe` instalável, assinado, com auto-update.

**Critério de saída:**

- [ ] Instalação limpa em Windows 11 sem Python pré-instalado
- [ ] T2 completo passa após instalação (máquina sem ArcMap)
- [ ] Login funciona a partir da build instalada (loopback + `mapasfacil://` de fallback registrado)
- [ ] Instalador < 250 MB (P5) ou desvio justificado
- [ ] Auto-update de N para N+1 funciona
- [ ] Desinstalação limpa; `%APPDATA%\MapasFacil\` preservado ou removido conforme a escolha do usuário
- [ ] Critérios de [`11-empacotamento-instalador.md`](11-empacotamento-instalador.md) atendidos

**Dependências:** M1–M9. M9 é bloqueante — não se empacota um gerador que não passa na Harmonia.

---

## M11 — Piloto

**Objetivo:** um técnico de GIS real (não o desenvolvedor) produz uma análise completa com o
instalador, sem suporte presencial.

**Critério de saída:**

- [ ] Piloto instala **e faz login** sozinho em < 15 minutos
- [ ] Primeiro mapa válido sem ajuda do desenvolvedor
- [ ] Análise completa em imóvel novo do piloto (não a Harmonia)
- [ ] Zero bugs S1 ou S2 abertos
- [ ] Feedback incorporado ou registrado como pendência pós-v1
- [ ] Critérios de aceite de [`00-visao-e-escopo.md`](00-visao-e-escopo.md) verificados um a um

**Dependências:** M10.

---

## O que fica depois do M11

| Item | Quando |
|---|---|
| Fase 2 completa (site, mapa por CAR, memória de projeto) | após M11 validado |
| Sync opcional de conversas para a conta | Fase 2, opt-in (D20) |
| Certificado EV (se o piloto usou OV) | se o SmartScreen ainda assusta |
| ArcGIS Pro como gerador de PDF alternativo | demanda do piloto |
| Linux/macOS | fora da v1 por design |
| Cobrança e limites de uso | **depois** da validação; hoje é AP-05 |
| Rotação das chaves vazadas nos `.mxd` | pendência de segurança, independente do roadmap |

## Riscos do roadmap

| Risco | Marco afetado | Mitigação |
|---|---|---|
| `arcpy` trava em subprocesso | M2, M9 | timeout, API mínima comprovada, caminho T2 |
| M2 demora e bloqueia tudo | M9, M10 | T2 avança em paralelo; PDF nativo desbloqueia M3–M8 |
| Conta local corrompida / SQLite ilegível | M5 | `AUTH-050` com instrução; não cair para senha em `config.json` |
| Auth vira porta de entrada para cobrança "só um limitezinho" | escopo | D18 e AP-05 são vinculantes; mudar exige alterar F1-00 e planos comuns |
| Animação implementada antes do evento existir | M3, M8 | AP-07; o critério de saída do M3 exige o evento do M1 |
| Galeria virar enfeite e o chat montar tudo do zero | M4, M7 | teste de paridade é critério de saída do M7 |
| Contexto do agente estourar em pasta real | M7 | orçamento e compressão são critério de saída, com fixture de 120 turnos |
| Instalador > 250 MB | M10 | auditoria de deps na decisão P1 (onedir) |
| Escopo vira "NexoGeo 2" | qualquer | a tabela "Fora da v1" em [`00-visao-e-escopo.md`](00-visao-e-escopo.md) é vinculante |
