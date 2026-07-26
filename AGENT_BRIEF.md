# AGENT_BRIEF — como um agente de IA deve usar estes planos

Este repositório é documentação executável. O consumidor é um **agente de codificação** (Cursor,
Claude Code, Codex, cloud agent), não um leitor humano. Leia este arquivo inteiro antes de tocar
em qualquer coisa.

## Chave DeepSeek para desenvolvimento e testes (M7)

Neste PC de desenvolvimento a chave de **teste** já está em `secrets.local.json` (gitignored),
campo `deepseek_api_key`. **Não copie o valor para arquivos versionados** — viola AP-03.

| O quê | Valor / onde |
|---|---|
| Arquivo local | `secrets.local.json` na raiz do repositório |
| Campo | `deepseek_api_key` |
| Template público (vazio) | `secrets.example.json` |
| Endpoint | `https://api.deepseek.com/chat/completions` |
| Modelos planejados | `deepseek-v4-pro` (chat + tools), `deepseek-v4-flash` (título, `compact_summary`) |
| Quem lê hoje | `doctor.py` + `agente/chave.py` → `chat.enviar` |
| Cliente HTTP | **feito** — `agente/deepseek.py` (SSE) + `FakeProvedor` no CI |

### Testes que dependem da chave (estado 2026-07-26)

| Suíte | Precisa da chave ao vivo? | Resultado neste PC |
|---|---|---|
| `Fase_1_Desktop/nucleo` pytest (anel 1) | **não** — FakeProvedor; ~457 pass | verde |
| `Fase_1_Desktop/app` Vitest | **não** | ~124 pass |
| `test_agente*.py` (agente, tools, orquestrador) / vazamento / paridade galeria | **não** — fake | verde |
| Smoke live | **sim** — `ferramentas/deepseek_smoke.py` | opcional |

**Conclusão:** o CI não usa a chave real. A chave serve para smoke local e turnos reais no app.

Smoke da chave (fora do CI, não versiona segredo):

```bash
python3 ferramentas/deepseek_smoke.py
```

Para testar manualmente (curl, script isolado, implementação futura do G1):

```bash
python3 -c "import json; print(json.load(open('secrets.local.json'))['deepseek_api_key'])"
```

Ao implementar o cliente, ler a chave só do cofre local (`secrets.local.json` em dev;
Credential Manager em produção — ver [F1-11](Fase_1_Desktop/planos/11-empacotamento-instalador.md)).
Nunca hardcodar, nunca logar, nunca enviar ao renderer Electron. Detalhe de privacidade do
prompt: [`planos/05-seguranca-e-segredos.md`](planos/05-seguranca-e-segredos.md) (§o que vai
para a DeepSeek).

## Regra zero

**Nenhum plano descreve código que já existe, a não ser onde diz explicitamente que existe.**
Cada plano tem uma seção `Estado atual vs alvo`. Se ela diz `ausente`, não presuma que há stub,
pasta ou função. Se diz `parcial`, leia a nota — ela lista o que falta.

Verificações rápidas de realidade (rode antes de planejar):

```bash
ls Fase_1_Desktop/app                      # M3 fechado: C1–C11 (shell, workspace, paleta, visual)
ls shared/galeria                          # M4: modelos.json + previews
ls Fase_1_Desktop/nucleo/mapasfacil_nucleo # sidecar Python real, v0.4.0
grep -rn "envelope_evt\|Emissor" --include=*.py Fase_1_Desktop/nucleo/mapasfacil_nucleo
#   → definição + chamadores: os 8 eventos do vocabulário têm emissor
cd Fase_1_Desktop/nucleo && pytest -q      # anel 1 deve ficar verde (~457)
cd Fase_1_Desktop/app && pnpm test         # shell + galeria + chats + chat + motion + login (~124)
```

## O que existe hoje (2026-07-26, núcleo v0.4.0 + M6)

| Camada | Estado | Onde |
|---|---|---|
| Planos e contratos | escritos; esta rodada os reescreveu para agentes | `planos/`, `Fase_1_Desktop/planos/`, `Fase_2_Site/planos/` |
| `MapSpec` schema `contract_version: 2` | existe e valida | `shared/schemas/mapspec.schema.json` |
| Catálogo de camadas (41) | existe | `shared/catalog/camadas.json` |
| MANIFEST de templates | 1 `parcial` (`dinamica_retrato`), 4 `a_preparar` | `shared/templates/MANIFEST.json` |
| Acervo de referência | 6 acervos, 84 PDFs + 61 `.mxd`, organizados em `Mapas/01–06` | [`Referencias_IMAP/README.md`](Referencias_IMAP/README.md) |
| Sidecar Python NDJSON | **45 métodos** (galeria + chat + conta/sessão M5 + `artefato.ler` + `catalogo.listar`/`camada.resolver` A13) | `Fase_1_Desktop/nucleo/` |
| Clientes de camada em runtime | **fechado — 41/41 camadas, os 4 tipos do catálogo**: `wms_wfs` (A13), `arcgis_rest`, `wfs_gml` (reprojeta do EPSG nativo) e `wms_raster` (imagem, `tipo_saida="raster"`); cache TTL por tema; `NU-101/102/110/111/112/120/130/140` | `nucleo/.../camadas/{catalogo,http,wfs,rest_arcgis,gml_incra,wms,clip,cache,resolver}.py` |
| Eventos NDJSON com emissor | **os 8 do vocabulário** — `job.progresso` (A9), `chat.delta`/`chat.tool` (M7), `job.artefato_parcial` (M8), `workspace.mudou` (A12), `mapspec.atualizado` (H6), **`job.log` e `aviso`** | `nucleo/.../progresso.py`, `artefatos.py`, `agente/orquestrador.py`, `agente/tools.py`, `workspace/watcher.py`, `motores/gerar.py` |
| App Electron | **M3 fechado** + **galeria M4** + **conta local M5** + **chats M6** + **chat M7** + **motion/preview M8** | [`Fase_1_Desktop/app/README.md`](Fase_1_Desktop/app/README.md) |
| Galeria de modelos | **fechada** — `galeria.listar/detalhar/montar_mapspec`, 5 modelos, previews reais | [`shared/galeria/`](shared/galeria/) |
| Conta local | **fechada** (M5) — e-mail+senha Argon2id, `contas.sqlite`, `tela-login`, gate `AUTH-030` | `nucleo/.../contas/`, `sessao.py`, `app/src/telas/Login.tsx` |
| Persistência de conversas | **fechada** (M6) — `chats.sqlite` WAL+FTS5, redator, 10 `chat.*`, `barra-chats` | `nucleo/.../conversas/`, `app/src/paineis/BarraChats.tsx` |
| Agente DeepSeek | **fechado** (M7) — orquestrador, VCR/cassetes, MapSpec em disco, **27/27 tools reais** (F1-07 fechou `analisar_referencia`) | `nucleo/.../agente/`, `app/src/paineis/PainelChat.tsx` |
| Visão de referência (F1-07) | **determinístico fechado** (imagem/PDF/`.mxd`/`.zip`); modelo de visão pronto mas **sem confirmação** de qual DeepSeek tem visão (P1) — degrada com `IA-060` até alguém confirmar | `nucleo/.../agente/visao/` |
| `fsguard` | fechado, 100% de cobertura | `mapasfacil_nucleo/fsguard.py` |
| PDF nativo + overlay da tabela | estrutural (sem paridade visual Harmonia) | `motores/nativo.py` |
| Quantitativos + `.xlsx` + PNG + Conferência | fechados | `quantitativos/` |
| `mapspec.diff`, diff raster de PDF | fechados | `mapspec/diff.py`, `validacao/comparar_pdf.py` |
| Motor `.mxd` | **parcial**: T2 copia template preparado; T1 é esqueleto | `motores/patch_mxd.py`, `motores/arcpy_ponte.py` |
| CI anel 1 (Linux) | verde | `.github/workflows/nucleo.yml` |

## O que NÃO existe (não invente que existe)

- Menus e tray do Electron (só diálogo de pasta + IPC).
- Crossfade de **imagem do mapa** por versão do MapSpec: o núcleo não gera PNG por versão (só por
  etapa de `mapa.gerar`); `linha-versoes` crossfadeia o card de diff/resumo, não uma imagem — ver
  nota em [16-design-system-dark.md §A6](Fase_1_Desktop/planos/16-design-system-dark.md#a6--microinterações).
- Tools do agente que respondem `IA-022`: **nenhuma hoje** — `TOOLS_COM_DEPENDENCIA_PENDENTE`
  está vazio. `consultar_sema`/`distancia_ate` saíram em A13; `analisar_referencia` saiu em F1-07.
- Modelo de visão confirmado (P1 de F1-07): o cliente (`agente/visao/provedor.py`) e o pipeline
  determinístico existem, mas ninguém confirmou que um modelo DeepSeek da conta enxerga imagem —
  toda chamada real degrada com `IA-060` até isso ser confirmado. O determinístico (medidas de
  imagem, texto de PDF, strings de `.mxd`, inventário de `.zip`) funciona sem depender disso.
- OCR embarcado (Tesseract) para print sem chave de visão — decisão deliberada de não pagar os
  +40 MB (F1-07 P2); sem chave, o print fica só na análise determinística (sem texto lido).
- Conta na nuvem / site de login (F2-05) — **adiado pós-M11**; não bloqueia a Fase 1.
- Instalador Windows (M10) — nada de empacotamento neste repositório ainda.
- Qualquer código da Fase 2 (site/backend/nuvem) — F2-05 é pós-M11 e **não** é exigido pelo M5.

## Ordem de implementação (dependências, nunca calendário)

Estimativa em dias/semanas é **proibida** neste repositório. A ordem abaixo é de dependência
técnica. Detalhe por marco: [`Fase_1_Desktop/planos/12-roadmap.md`](Fase_1_Desktop/planos/12-roadmap.md).

```
M1 núcleo ✅parcial
   │
   ├─▶ M2  Motor .mxd            (exige ArcMap para T1)
   │
   └─▶ M3  Shell + Design System dark
          │
          ├─▶ M4  Galeria de modelos + geração determinística
          ├─▶ M5  Conta local (e-mail + senha em SQLite)
          │
          └─▶ M6  Persistência de conversas
                 │
                 └─▶ M7  Agente DeepSeek + compressão de contexto
                        │
                        └─▶ M8  Motion + preview de construção do mapa
                               │
              M2 ──────────────┴─▶ M9  Conformidade Harmonia
                                      │
                                      └─▶ M10 Instalador ──▶ M11 Piloto
```

| Marco | Precisa de ArcMap? | Precisa de rede? | Plano de referência |
|---|---|---|---|
| M2 — Motor `.mxd` | **sim** (T1); T2 não | não | [F1-04](Fase_1_Desktop/planos/04-motor-mxd.md) |
| M3 — Shell + Design System | não | não | [F1-02](Fase_1_Desktop/planos/02-ui-chat-e-workspace.md), [F1-16](Fase_1_Desktop/planos/16-design-system-dark.md) |
| M4 — Galeria | não | não | [F1-15](Fase_1_Desktop/planos/15-galeria-de-modelos.md) |
| M5 — Auth local | não | **não** | [F1-14](Fase_1_Desktop/planos/14-auth-e-conta.md) (e-mail+senha SQLite; F2-05 **não** bloqueia) |
| M6 — Conversas | não | não | [F1-17](Fase_1_Desktop/planos/17-persistencia-de-conversas.md) |
| M7 — Agente | não | **sim** (fake no CI) | [F1-06](Fase_1_Desktop/planos/06-agente-eng-florestal.md) |
| M8 — Motion | não | não | [F1-16](Fase_1_Desktop/planos/16-design-system-dark.md) |
| M9 — Harmonia | **sim** para paridade T1 | sim | [F1-09](Fase_1_Desktop/planos/09-validacao-conformidade.md) |

**Um agente sem Windows/ArcMap pode fechar M3, M4, M5, M6, M7 e M8 inteiros.** Não fique
bloqueado esperando ArcMap.

## Como ler um plano

Todo plano reescrito nesta rodada segue a mesma forma. Procure estas seções, nesta ordem:

1. `Objetivo` — um parágrafo.
2. `Estado atual vs alvo` — a verdade operacional.
3. `Dependências`.
4. `Contratos` — JSON schema, métodos NDJSON, pastas, env vars, códigos de erro.
5. `Tarefas agentáveis` — checkboxes **com caminho de arquivo**.
6. `Critérios de aceite` — comandos/asserts que outro agente valida.
7. `Fora de escopo`.
8. `Anti-padrões`.

Se um plano de fase divergir de um plano comum (`planos/`), **o comum ganha** e a divergência é
corrigida no mesmo commit.

```
planos/01-padrao-imap-harmonia.md   ← vence em tudo que é visual do MAPA
planos/02-mapspec-contrato.md       ← vence em tudo que é formato de dado
planos/00-visao-e-duas-fases.md     ← vence em escopo e decisões D1–D20
        ↓
Fase_1_Desktop/planos/01-arquitetura.md   ← vence nos contratos internos da Fase 1
        ↓
demais planos de fase                     ← implementam; nunca redefinem
```

## Gap analysis — requisito → plano → estado → arquivo a editar

Tabela viva. Um agente que fecha um item **atualiza a linha no mesmo commit**.

| # | Requisito | Plano que manda | Estado do código | Arquivo/pasta a criar ou editar |
|---|---|---|---|---|
| R01 | App Electron + React com 4 painéis nomeados | [F1-02](Fase_1_Desktop/planos/02-ui-chat-e-workspace.md) | **feito** — M3+M4+M6+M7+M8: shell, workspace, galeria, chats, chat e `painel-preview` com abas | `app/src/paineis/` |
| R02 | Ponte NDJSON Electron ↔ sidecar | [F1-01](Fase_1_Desktop/planos/01-arquitetura.md) | **feito** | `app/electron/nucleo/ponte.ts` |
| R02 | Dark theme default + tokens CSS | [F1-16](Fase_1_Desktop/planos/16-design-system-dark.md) | **feito** (C3) — `data-tema="escuro"` vem do `index.html` e é reafirmado em `main.tsx` | `app/src/estilos/tokens.css`, `app/src/estado/tema.ts` |
| R03 | Tipografia embarcada (Space Grotesk / IBM Plex) | [F1-16](Fase_1_Desktop/planos/16-design-system-dark.md) | **feito** (C4) — woff2 + OFL versionados, zero CDN | `app/src/estilos/fontes/` |
| R04 | ≥3 animações amarradas a evento real | [F1-16](Fase_1_Desktop/planos/16-design-system-dark.md) | **feito** (M8+A12+H6) — A1–A6 completas: A1–A5 + realce de arquivo novo (`workspace.mudou`) + troca de versão (`mapspec.atualizado`) | `app/src/componentes/IndicadorPensando.tsx`, `CartaoTool.tsx`, `BarraProgressoJob.tsx`, `LinhaVersoes.tsx`, `app/src/paineis/Preview.tsx`, `Workspace.tsx` |
| R05 | Emissão de `job.progresso` com as 10 etapas | [F1-01](Fase_1_Desktop/planos/01-arquitetura.md) | **feito** (A9, v0.4.0) — `pct` monotônico 3→100, `item` nas camadas locais | `nucleo/.../progresso.py`, `motores/gerar.py`, `protocolo.py` |
| R06 | Evento `job.artefato_parcial` (preview em construção) | [F1-16](Fase_1_Desktop/planos/16-design-system-dark.md) §Contrato | **feito** (M8) — 4 tipos, caminho relativo, `artefato.ler` para o renderer | `nucleo/.../artefatos.py`, `leitor_artefato.py`, `motores/gerar.py`, `motores/nativo.py` |
| R07 | Galeria de modelos (catálogo + UI + montagem de MapSpec) | [F1-15](Fase_1_Desktop/planos/15-galeria-de-modelos.md) | **feito** (M4) — 5 modelos, previews reais, UI no painel direito | `shared/galeria/`, `app/src/paineis/Galeria*.tsx` |
| R08 | `galeria.listar` / `galeria.detalhar` / `galeria.montar_mapspec` | [F1-15](Fase_1_Desktop/planos/15-galeria-de-modelos.md) | **feito** (M4) — `NU-230`…`NU-234`; só `dinamica_2026_retrato` sai de `indisponivel` | `nucleo/.../galeria/` |
| R09 | Login obrigatório **e-mail + senha local** (SQLite) | [F1-14](Fase_1_Desktop/planos/14-auth-e-conta.md) | **feito** (M5) — Argon2id, `tela-login`, sem Google | `nucleo/.../contas/`, `app/src/telas/Login.tsx` |
| R10 | Conta na nuvem / site (Fase 2) | [F2-05](Fase_2_Site/planos/05-auth-e-memoria.md) | **adiado** — **não** bloqueia M5 | `Fase_2_Site/` (pós-M11) |
| R11 | Cofre BYOK (DeepSeek/SEMA/Planet) no OS keyring | [F1-03](Fase_1_Desktop/planos/03-nucleo-python.md), [F1-11](Fase_1_Desktop/planos/11-empacotamento-instalador.md) | **feito** (A11) — `keyring` (CM/Secret Service); Preferências grava; `secrets.local.json` ainda vale em dev | `nucleo/.../cofre.py`, `app/src/componentes/Preferencias.tsx` |
| R12 | Gate de sessão em `mapa.gerar` (`AUTH-030`) | [F1-14](Fase_1_Desktop/planos/14-auth-e-conta.md) | **feito** (M5) — também `galeria.montar_mapspec`, `chat.enviar`, `quantitativos.exportar_xlsx` | `nucleo/.../sessao.py` |
| R13 | Persistência local de conversas (SQLite) | [F1-17](Fase_1_Desktop/planos/17-persistencia-de-conversas.md) | **feito** (M6) — WAL+FTS5, redator na entrada, 10 `chat.*` | `nucleo/.../conversas/` |
| R14 | Sidebar de chats: buscar/renomear/arquivar/apagar/ramificar | [F1-17](Fase_1_Desktop/planos/17-persistencia-de-conversas.md) | **feito** — lista + busca + filtro pasta + **menu de contexto completo** (renomear/arquivar/desarquivar/ramificar/apagar) + filtro de arquivadas | `app/src/paineis/BarraChats.tsx` |
| R15 | Cliente DeepSeek streaming + tool calling | [F1-06](Fase_1_Desktop/planos/06-agente-eng-florestal.md) | **feito** (G1) — DeepSeek + FakeProvedor | `nucleo/.../agente/deepseek.py` |
| R15b | Tools tipadas do agente (G5) | [F1-06](Fase_1_Desktop/planos/06-agente-eng-florestal.md) §Catálogo | **feito** — 27/27 reais; A13 fechou `consultar_sema`/`distancia_ate`, F1-07 fechou `analisar_referencia` | `nucleo/.../agente/tools.py`, `agente/edicao.py` |
| R16a | Orçamento de contexto (`limites.py`) | [F1-06](Fase_1_Desktop/planos/06-agente-eng-florestal.md) §Orçamento | **feito** (G2) | `nucleo/.../agente/limites.py` |
| R16 | Pipeline de compressão de contexto | [F1-06](Fase_1_Desktop/planos/06-agente-eng-florestal.md) §Orçamento | **feito** (G3) | `nucleo/.../agente/contexto.py` |
| R17 | VCR/fake do provedor no CI | [F1-06](Fase_1_Desktop/planos/06-agente-eng-florestal.md), [F1-10](Fase_1_Desktop/planos/10-testes-e-qa.md) | **feito** (G8) — FakeProvedor + cassetes SSE/passos em `tests/agente/cassetes/` | `nucleo/.../agente/vcr.py`, `fake.py` |
| R18 | Assert: request ao LLM sem WKT e sem CPF | [F1-06](Fase_1_Desktop/planos/06-agente-eng-florestal.md) §Testes | **feito** (G9) | `nucleo/tests/test_contexto_vazamento.py` |
| R19 | `mapa.cancelar` e `chat.cancelar` | [F1-01](Fase_1_Desktop/planos/01-arquitetura.md) | **feito** — `chat.cancelar` + `mapa.cancelar` (`jobs.py`, `NU-050`, `taskkill` no Windows); loop NDJSON em thread | `nucleo/.../jobs.py`, `app/.../BarraProgressoJob.tsx` |
| R20 | Cofre (`cofre.definir`/`existe`/`testar`) | [F1-03](Fase_1_Desktop/planos/03-nucleo-python.md) | **feito** (A11) — valor nunca no stdio | `nucleo/.../cofre.py` |
| R21 | `catalogo.listar` e `camada.resolver` (clientes em runtime) | [F1-03](Fase_1_Desktop/planos/03-nucleo-python.md) | **feito** — A13 abriu com `wms_wfs`; o épico seguinte fechou `arcgis_rest`, `wfs_gml` e `wms_raster`. **41/41 camadas com cliente** | `nucleo/.../camadas/` |
| R22 | Motor T1 (ArcPy real) | [F1-04](Fase_1_Desktop/planos/04-motor-mxd.md) | **parcial** (esqueleto) | `nucleo/.../scripts/arcpy_job.py` |
| R23 | B1: template `dinamica_retrato` completo + offsets | [F1-13](Fase_1_Desktop/planos/13-checklist-implementacao.md) | **parcial** | `shared/templates/MANIFEST.json` |
| R24 | Paridade visual Harmonia (< 0,3% raster) | [F1-09](Fase_1_Desktop/planos/09-validacao-conformidade.md) | **ausente** (infra pronta, baseline não passa) | `nucleo/.../motores/nativo.py` |
| R25 | Instalador Windows assinado | [F1-11](Fase_1_Desktop/planos/11-empacotamento-instalador.md) | **ausente** | `Fase_1_Desktop/app/build/` |
| R26 | `analisar_referencia` — print/PDF/`.mxd`/`.zip` → MapSpec proposto | [F1-07](Fase_1_Desktop/planos/07-visao-print-e-zip.md) | **feito** (2026-07-26) — determinístico completo; modelo de visão pronto, P1 (nome do modelo DeepSeek com visão) em aberto | `nucleo/.../agente/visao/`, `agente/tools.py` |

## Anti-padrões — vinculantes para qualquer agente implementador

Violar qualquer um destes é motivo de rejeição do trabalho, mesmo que "funcione".

| # | Não faça | Por quê |
|---|---|---|
| AP-01 | Gerar `.mxd` em servidor Linux | `arcpy` é Windows-only; o servidor **nunca** promete `.mxd` |
| AP-02 | Deixar a IA escrever código, `arcpy`, SQL ou `definitionQuery` livre | ameaça A1/A4; o contrato é `MapSpec` declarativo validado por schema |
| AP-03 | Commitar segredo (chave, token, `secrets.local.json`, `.mxd` com `authkey`) | incidente 2026-07-25; rodar `ferramentas/chaves_mxd.py verificar` |
| AP-04 | Inventar camada, estilo ou template fora do catálogo/MANIFEST | validador rejeita; `NU-210` |
| AP-05 | Bloquear usuário autenticado com quota, paywall, rate limit ou feature flag de cobrança | **D18**: v1 autenticada é ilimitada |
| AP-06 | Enviar shapefile, PDF, `.mxd` ou geometria WKT bruta ao LLM | custo, privacidade e estouro de contexto; tools devolvem resumo tipado |
| AP-07 | Spinner/loader falso, desconectado de evento real do núcleo | animação só existe amarrada a `job.progresso`, `chat.delta`, `chat.tool` ou `job.artefato_parcial` |
| AP-08 | Hardcodar tema claro como default | **D15**: dark é o default; claro é opção |
| AP-09 | Gravar CPF em chat, transcript, log ou prompt — **ou versionar recibo do CAR** | LGPD; o parser descarta CPF na entrada, e os recibos do acervo estão no `.gitignore` porque o repo é público |
| AP-10 | Chamar o provedor de IA sem passar pelo pipeline de compressão | estoura contexto e custo; `IA-040` |
| AP-11 | Ler/escrever disco fora do `fsguard` | ameaça A2 |
| AP-12 | Sincronizar chats para nuvem na v1 | **D20**: local-only |
| AP-13 | Escrever estimativa em dias/semanas em plano | ordem é por dependência técnica |
| AP-14 | Abrir porta HTTP no PC do usuário para o sidecar **ou para login** | transporte é stdio NDJSON; auth local é IPC+SQLite (D12) — **sem** loopback OAuth |
| AP-15 | Marcar tarefa como feita sem atualizar a linha do gap analysis e o checklist F1-13 | o repositório mente e o próximo agente se perde |

## Convenções de código que os planos assumem

| Assunto | Convenção |
|---|---|
| Idioma | identificadores, métodos NDJSON, campos de JSON e mensagens de usuário em **português**; código-fonte segue o idioma do módulo existente |
| IDs | ULID em string para `id` de requisição, conversa, mensagem e `MapSpec` |
| Datas | ISO-8601 em UTC com sufixo `Z` |
| Números na UI | pt-BR, hectare com 4 casas (`3.823,9033`) |
| Erros | código estável (`NU-`, `AG-`, `IA-`, `UI-`, `AUTH-`) + o que aconteceu + por quê + o que fazer |
| Testes | anel 1 (puro) roda no CI Linux; anel 2 com fake; anel 3 Windows; anel 4 ArcMap manual |
| Commits | direto no `main`, sem PR (convenção deste repositório) |

## Onde começar, por tipo de tarefa

| Se te pediram… | Leia, nesta ordem |
|---|---|
| "faz a UI" | F1-02 → F1-16 → F1-01 (§IPC) → F1-15 |
| "faz o login" | F1-14 → `planos/05-seguranca-e-segredos.md` (F2-05 só se for conta **nuvem** pós-M11) |
| "faz a galeria" | F1-15 → `planos/02-mapspec-contrato.md` → F1-04 (§MANIFEST) |
| "faz o agente" | F1-06 → F1-17 → `planos/05-seguranca-e-segredos.md` (§o que vai para a DeepSeek) |
| "faz o chat salvar" | F1-17 → F1-01 (§estado local) |
| "faz o `.mxd`" | F1-04 → `Referencias_IMAP/MXD/DOCUMENTACAO_MXD_HARMONIA.md` → F1-13 |
| "melhora o PDF" | F1-05 → `planos/01-padrao-imap-harmonia.md` → F1-09 |
| "mexe no acervo de referência" | [`Referencias_IMAP/README.md`](Referencias_IMAP/README.md) → **rode `chaves_mxd.py limpar` antes de commitar** |

## Ao acrescentar material ao acervo de referência

Receita fechada. Todo `.mxd` que chega do escritório traz chave de API real embutida, e o
repositório é público.

1. Coloque em `Referencias_IMAP/Mapas/NN/` (número novo), com `MXD/` e `PDF/` dentro. **Não**
   crie pasta com nome de download (`OneDrive_*`) — elas foram dissolvidas em 2026-07-26.
2. Escreva o `README.md` do acervo: imóveis, município, inventário, e **o que ele resolve que os
   outros não resolvem**.
3. `python3 ferramentas/chaves_mxd.py limpar && python3 ferramentas/chaves_mxd.py verificar` —
   tem de dizer **"Seguro para commit"**. A varredura é recursiva; a pasta nova entra sozinha.
4. Recibo do CAR, documento de proprietário, qualquer PDF com CPF/CNPJ: **não versione**. O
   `.gitignore` já cobre `CAR - Recibo*.pdf`, mas confira.
5. Atualize a tabela de acervos em [`Referencias_IMAP/README.md`](Referencias_IMAP/README.md).
