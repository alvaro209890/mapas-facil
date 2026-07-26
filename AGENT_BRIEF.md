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
| `Fase_1_Desktop/nucleo` pytest (anel 1) | **não** — FakeProvedor; ~238 pass | verde |
| `Fase_1_Desktop/app` Vitest | **não** | ~81 pass |
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
#   → definição + chamadores: job.progresso é emitido (A9); os outros 7 eventos, não
cd Fase_1_Desktop/nucleo && pytest -q      # anel 1 deve ficar verde (~238)
cd Fase_1_Desktop/app && pnpm test         # shell + galeria + chats + chat + visual/axe (~81)
```

## O que existe hoje (2026-07-26, núcleo v0.4.0 + M6)

| Camada | Estado | Onde |
|---|---|---|
| Planos e contratos | escritos; esta rodada os reescreveu para agentes | `planos/`, `Fase_1_Desktop/planos/`, `Fase_2_Site/planos/` |
| `MapSpec` schema `contract_version: 2` | existe e valida | `shared/schemas/mapspec.schema.json` |
| Catálogo de camadas (41) | existe | `shared/catalog/camadas.json` |
| MANIFEST de templates | 1 `parcial` (`dinamica_retrato`), 4 `a_preparar` | `shared/templates/MANIFEST.json` |
| Acervo de referência | 6 acervos, 84 PDFs + 61 `.mxd`, organizados em `Mapas/01–06` | [`Referencias_IMAP/README.md`](Referencias_IMAP/README.md) |
| Sidecar Python NDJSON | **32 métodos** (galeria + chat histórico + `chat.enviar`/`cancelar`) | `Fase_1_Desktop/nucleo/` |
| Emissão de `job.progresso` (10 etapas) | **fechada** (A9, v0.4.0) — único evento com emissor | `nucleo/.../progresso.py`, `motores/gerar.py` |
| App Electron | **M3 fechado** (C1–C11) + **galeria M4** + **barra de chats M6** | [`Fase_1_Desktop/app/README.md`](Fase_1_Desktop/app/README.md) |
| Galeria de modelos | **fechada** — `galeria.listar/detalhar/montar_mapspec`, 5 modelos, previews reais | [`shared/galeria/`](shared/galeria/) |
| Persistência de conversas | **fechada** (M6) — `chats.sqlite` WAL+FTS5, redator, 10 `chat.*`, `barra-chats` | `nucleo/.../conversas/`, `app/src/paineis/BarraChats.tsx` |
| Agente DeepSeek | **parcial** (M7) — orquestrador, cancelamento, 24/27 tools reais, `PainelChat` com “Parar”; faltam as 3 tools que dependem de R21/F1-07 e o VCR | `nucleo/.../agente/`, `app/src/paineis/PainelChat.tsx` |
| `fsguard` | fechado, 100% de cobertura | `mapasfacil_nucleo/fsguard.py` |
| PDF nativo + overlay da tabela | estrutural (sem paridade visual Harmonia) | `motores/nativo.py` |
| Quantitativos + `.xlsx` + PNG + Conferência | fechados | `quantitativos/` |
| `mapspec.diff`, diff raster de PDF | fechados | `mapspec/diff.py`, `validacao/comparar_pdf.py` |
| Motor `.mxd` | **parcial**: T2 copia template preparado; T1 é esqueleto | `motores/patch_mxd.py`, `motores/arcpy_ponte.py` |
| CI anel 1 (Linux) | verde | `.github/workflows/nucleo.yml` |

## O que NÃO existe (não invente que existe)

- Preview em construção (M8) e motion A2/A3/A5 ainda incompletos.
- Watcher de pasta: `workspace.mudou` não é emitido; reindexar é botão explícito, não tempo real.
- Menus e tray do Electron (só diálogo de pasta + IPC).
- Eventos NDJSON ainda sem emissor: `job.log`, `job.artefato_parcial`, `workspace.mudou`,
  `mapspec.atualizado`, `aviso`. Emitidos: `job.progresso`, `chat.delta`, `chat.tool`.
- Tools do agente ainda sem implementação, por dependência que não existe (respondem `IA-022`
  com o motivo): `consultar_sema` e `distancia_ate` (esperam `camada.resolver`, R21) e
  `analisar_referencia` (espera o fluxo de visão, F1-07). As outras 24 são reais.
- Autenticação, conta, site de login, backend de identidade (gate AUTH-030 em `chat.enviar` adiado).
- Cliente WFS/WMS em runtime, cofre/Credential Manager, instalador.
- Visão / `analisar_referencia` (F1-07).
- Qualquer código da Fase 2 além do que M5 exigir.

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
          ├─▶ M5  Conta e autenticação        (exige F2-05 no ar)
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
| M5 — Auth | não | **sim** | [F1-14](Fase_1_Desktop/planos/14-auth-e-conta.md), [F2-05](Fase_2_Site/planos/05-auth-e-memoria.md) |
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
| R01 | App Electron + React com 4 painéis nomeados | [F1-02](Fase_1_Desktop/planos/02-ui-chat-e-workspace.md) | **parcial** — M3+M4+M6+M7: shell/workspace/galeria/chats/chat; preview espera M8 | `app/src/paineis/` |
| R02 | Ponte NDJSON Electron ↔ sidecar | [F1-01](Fase_1_Desktop/planos/01-arquitetura.md) | **feito** | `app/electron/nucleo/ponte.ts` |
| R02 | Dark theme default + tokens CSS | [F1-16](Fase_1_Desktop/planos/16-design-system-dark.md) | **feito** (C3) — `data-tema="escuro"` vem do `index.html` e é reafirmado em `main.tsx` | `app/src/estilos/tokens.css`, `app/src/estado/tema.ts` |
| R03 | Tipografia embarcada (Space Grotesk / IBM Plex) | [F1-16](Fase_1_Desktop/planos/16-design-system-dark.md) | **feito** (C4) — woff2 + OFL versionados, zero CDN | `app/src/estilos/fontes/` |
| R04 | ≥3 animações amarradas a evento real | [F1-16](Fase_1_Desktop/planos/16-design-system-dark.md) | **parcial** — tokens de motion e `useReducedMotion` existem; só **A4** (progresso do job) está ligada a evento. A2 e A3 dependem de `chat.delta`/`chat.tool` (M7) | `app/src/motion/`, `app/src/componentes/BarraProgressoJob.tsx` |
| R05 | Emissão de `job.progresso` com as 10 etapas | [F1-01](Fase_1_Desktop/planos/01-arquitetura.md) | **feito** (A9, v0.4.0) — `pct` monotônico 3→100, `item` nas camadas locais | `nucleo/.../progresso.py`, `motores/gerar.py`, `protocolo.py` |
| R06 | Evento `job.artefato_parcial` (preview em construção) | [F1-16](Fase_1_Desktop/planos/16-design-system-dark.md) §Contrato novo | **ausente — contrato só especificado** | `nucleo/.../motores/gerar.py`, `protocolo.py` |
| R07 | Galeria de modelos (catálogo + UI + montagem de MapSpec) | [F1-15](Fase_1_Desktop/planos/15-galeria-de-modelos.md) | **feito** (M4) — 5 modelos, previews reais, UI no painel direito | `shared/galeria/`, `app/src/paineis/Galeria*.tsx` |
| R08 | `galeria.listar` / `galeria.detalhar` / `galeria.montar_mapspec` | [F1-15](Fase_1_Desktop/planos/15-galeria-de-modelos.md) | **feito** (M4) — `NU-230`…`NU-234`; só `dinamica_2026_retrato` sai de `indisponivel` | `nucleo/.../galeria/` |
| R09 | Login obrigatório Google via site → app | [F1-14](Fase_1_Desktop/planos/14-auth-e-conta.md) | **ausente** | `app/electron/auth/`, `Fase_2_Site/backend/` |
| R10 | Backend de identidade + site de login | [F2-05](Fase_2_Site/planos/05-auth-e-memoria.md) | **ausente** | `Fase_2_Site/backend/`, `Fase_2_Site/web/` |
| R11 | Tokens no Windows Credential Manager | [F1-14](Fase_1_Desktop/planos/14-auth-e-conta.md) | **ausente** | `app/electron/cofre.ts` |
| R12 | Gate de sessão em `mapa.gerar` (`AUTH-030`) | [F1-14](Fase_1_Desktop/planos/14-auth-e-conta.md) | **ausente** | `nucleo/.../sessao.py`, `motores/gerar.py` |
| R13 | Persistência local de conversas (SQLite) | [F1-17](Fase_1_Desktop/planos/17-persistencia-de-conversas.md) | **feito** (M6) — WAL+FTS5, redator na entrada, 10 `chat.*` | `nucleo/.../conversas/` |
| R14 | Sidebar de chats: buscar/renomear/arquivar/apagar/ramificar | [F1-17](Fase_1_Desktop/planos/17-persistencia-de-conversas.md) | **feito** (M6) — lista + busca + filtro pasta; menu de contexto parcial (apagar) | `app/src/paineis/BarraChats.tsx` |
| R15 | Cliente DeepSeek streaming + tool calling | [F1-06](Fase_1_Desktop/planos/06-agente-eng-florestal.md) | **feito** (G1) — DeepSeek + FakeProvedor | `nucleo/.../agente/deepseek.py` |
| R15b | Tools tipadas do agente (G5) | [F1-06](Fase_1_Desktop/planos/06-agente-eng-florestal.md) §Catálogo | **parcial** — 24/27 reais e versionadas; 3 travadas em R21/F1-07 | `nucleo/.../agente/tools.py`, `agente/edicao.py` |
| R16a | Orçamento de contexto (`limites.py`) | [F1-06](Fase_1_Desktop/planos/06-agente-eng-florestal.md) §Orçamento | **feito** (G2) | `nucleo/.../agente/limites.py` |
| R16 | Pipeline de compressão de contexto | [F1-06](Fase_1_Desktop/planos/06-agente-eng-florestal.md) §Orçamento | **feito** (G3) | `nucleo/.../agente/contexto.py` |
| R17 | VCR/fake do provedor no CI | [F1-06](Fase_1_Desktop/planos/06-agente-eng-florestal.md), [F1-10](Fase_1_Desktop/planos/10-testes-e-qa.md) | **parcial** — FakeProvedor; VCR HTTP pendente | `nucleo/.../agente/fake.py` |
| R18 | Assert: request ao LLM sem WKT e sem CPF | [F1-06](Fase_1_Desktop/planos/06-agente-eng-florestal.md) §Testes | **feito** (G9) | `nucleo/tests/test_contexto_vazamento.py` |
| R19 | `mapa.cancelar` e `chat.cancelar` | [F1-01](Fase_1_Desktop/planos/01-arquitetura.md) | **parcial** — `chat.cancelar` feito (grava parcial com `cancelada`, fecha o stream, botão “Parar” na UI); `mapa.cancelar` ausente | `nucleo/.../agente/orquestrador.py`, `app/src/paineis/PainelChat.tsx` |
| R20 | Cofre (`cofre.definir`/`existe`/`testar`) | [F1-03](Fase_1_Desktop/planos/03-nucleo-python.md) | **ausente** | `nucleo/.../cofre.py` |
| R21 | `catalogo.listar` e `camada.resolver` (WFS runtime) | [F1-03](Fase_1_Desktop/planos/03-nucleo-python.md) | **ausente** | `nucleo/.../camadas/` |
| R22 | Motor T1 (ArcPy real) | [F1-04](Fase_1_Desktop/planos/04-motor-mxd.md) | **parcial** (esqueleto) | `nucleo/.../scripts/arcpy_job.py` |
| R23 | B1: template `dinamica_retrato` completo + offsets | [F1-13](Fase_1_Desktop/planos/13-checklist-implementacao.md) | **parcial** | `shared/templates/MANIFEST.json` |
| R24 | Paridade visual Harmonia (< 0,3% raster) | [F1-09](Fase_1_Desktop/planos/09-validacao-conformidade.md) | **ausente** (infra pronta, baseline não passa) | `nucleo/.../motores/nativo.py` |
| R25 | Instalador Windows assinado | [F1-11](Fase_1_Desktop/planos/11-empacotamento-instalador.md) | **ausente** | `Fase_1_Desktop/app/build/` |

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
| AP-14 | Abrir porta HTTP no PC do usuário para o sidecar | o transporte é stdio NDJSON; a única porta é o loopback efêmero do OAuth |
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
| "faz o login" | F1-14 → F2-05 → `planos/05-seguranca-e-segredos.md` |
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
