# F1-01 — Arquitetura do app desktop

## Objetivo

Fixar os contratos internos da Fase 1: quais processos existem, quem fala com quem, qual o
protocolo, onde cada estado vive e quais são os códigos de erro. **Fonte da verdade dos contratos
internos da Fase 1** — se outro plano da fase divergir, este ganha. O `MapSpec` e o padrão visual
vêm dos planos comuns ([`../../planos/02-mapspec-contrato.md`](../../planos/02-mapspec-contrato.md),
[`../../planos/01-padrao-imap-harmonia.md`](../../planos/01-padrao-imap-harmonia.md)) e não são
redefinidos aqui.

## Estado atual vs alvo

| Peça | Atual | Alvo |
|---|---|---|
| Sidecar Python NDJSON | **existe**, v0.4.0, 17 métodos | 40+ métodos (tabela abaixo) |
| Emissão de eventos | **parcial** — `job.progresso` emitido (A9); os outros 7 sem chamador | 8 eventos emitidos |
| Electron main + renderer | **parcial** — main, preload e ponte NDJSON existem; renderer ainda não | shell completo |
| Ponte ArcPy (py 2.7) | esqueleto | T1 funcional |
| Cofre / Credential Manager (BYOK) | **ausente** | chaves DeepSeek/SEMA/Planet — **não** senha de conta |
| Conta local (e-mail + senha) | **feito** (M5) | [F1-14](14-auth-e-conta.md) — SQLite Argon2id; **sem** Google/F2-05 |
| Persistência de conversas | **ausente** | `chats.sqlite` ([F1-17](17-persistencia-de-conversas.md)) |

## Os quatro processos

```
┌──────────────────────── PC do usuário — Windows 10/11 ─────────────────────────────────┐
│                                                                                        │
│  ┌──────────────────────────┐        ┌─────────────────────────────────────────────┐   │
│  │  Electron — main         │        │  Electron — renderer (React)                │   │
│  │  • janela, menus, tray   │◀──IPC─▶│  • árvore da pasta   • chat + streaming     │   │
│  │  • diálogo de pasta      │        │  • galeria           • preview do mapa      │   │
│  │  • Credential Manager    │        │  • sidebar de chats  • painel do MapSpec    │   │
│  │    (só chaves BYOK)      │        │  • histórico de versões  • doctor           │   │
│  │  • IPC auth (conta local)│        │  • tela-login (e-mail + senha)              │   │
│  │  • auto-update           │  │     └─────────────────────────────────────────────┘   │
│  └───────────┬──────────────┘  │                                                       │
│              │ stdio NDJSON    │ HTTPS (só main; token nunca cruza para o renderer)     │
│  ┌───────────▼─────────────────┼──────────────────────────────────────────────────┐   │
│  │  NÚCLEO — Python 3.12 (sidecar, empacotado com o app)                           │   │
│  │  ┌──────────┬─────────┬──────────┬─────────┬─────────┬─────────┬─────────────┐ │   │
│  │  │workspace │ camadas │ mapspec  │ galeria │ motores │ agente  │ conversas   │ │   │
│  │  │índice    │ wfs/wms │ validação│ catálogo│ mxd·pdf │ deepseek│ sqlite      │ │   │
│  │  │watch     │ clip    │ diff     │ montar  │ xlsx·png│ contexto│ fts         │ │   │
│  │  └──────────┴─────────┴──────────┴─────────┴────┬────┴─────────┴─────────────┘ │   │
│  │   fsguard · sessao · cofre · doctor · erros     │                              │   │
│  └─────────────────────────────────────────────────┼──────────────────────────────┘   │
│                                                    │ subprocess, payload em JSON       │
│  ┌─────────────────────────────────────────────────▼──────────────────────────────┐   │
│  │  Python 2.7 do ArcMap  —  arcpy_job.py                                          │   │
│  │  abre template · repõe fontes · extent/escala · textos · exporta PDF            │   │
│  │  (só quando há ArcMap; roda sempre com timeout)                                 │   │
│  └────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                        │
│  Saída:  <pasta do projeto>/Mapas/  ·  /MXD/  ·  /SHP/   ·   %APPDATA%\MapasFacil\     │
└────────────────────────────────────────────────────────────────────────────────────────┘
        │                    │                    │                     │
        ▼                    ▼                    ▼                     ▼
  api.deepseek.com   geo.sema.mt.gov.br    tiles.planet.com    mapasfacil-api.cursar.space
  (chat, BYOK)       (WFS/WMS + authkey)   (basemap)           (identidade — só o main)
```

### Por que essa divisão

| Alternativa | Por que não |
|---|---|
| Tudo em Node | o ecossistema geo maduro é Python: `shapely`, `pyproj`, `fiona`, `rasterio`, `PyMuPDF`, `openpyxl`, `matplotlib`. Reescrever em JS custa meses e perde precisão |
| Tudo em Python (PySide6) | chat com streaming, diff, preview e árvore de arquivos no nível do Cursor custa muito mais em Qt |
| Núcleo como servidor HTTP local | abre porta na máquina do usuário — superfície de ataque e conflito de porta. stdio não tem nenhum dos dois (AP-14) |
| Auth só no renderer | senha/hash vazariam; auth passa pelo main → núcleo (NDJSON), renderer só vê `{estado, conta}` |

### Regras de fronteira (invioláveis)

1. **O renderer nunca toca o disco do usuário diretamente.** Toda leitura e escrita passa pelo
   núcleo, que valida contra a allowlist do workspace.
2. **O núcleo nunca executa string vinda de fora.** Sem `eval`, sem `exec`, sem
   `subprocess(shell=True)`. O único subprocesso é o Python do ArcMap, com argumentos fixos.
3. **A IA nunca gera código.** Ela chama tools tipadas que produzem e editam `MapSpec`.
4. **Segredo nunca sai do processo main do Electron.** Token de sessão e chave BYOK ficam no
   Credential Manager; o renderer recebe booleanos e estados, nunca valores.
5. **O núcleo é a única coisa que sabe geo.** O renderer só desenha o que recebe.
6. **O núcleo não faz requisição de identidade.** Ele recebe `sessao.definir` com estado e
   validade, sem token ([F1-14](14-auth-e-conta.md)).

## Protocolo Electron ↔ núcleo

NDJSON sobre stdin/stdout: uma mensagem JSON por linha, sem framing extra. `stderr` é log.

```json
{"v":1,"id":"01J8X…","tipo":"req","metodo":"workspace.abrir","params":{"caminho":"C:\\…"}}
{"v":1,"id":"01J8X…","tipo":"res","ok":true,"resultado":{"arquivos":[…]}}
{"v":1,"id":"01J8X…","tipo":"evt","evento":"job.progresso","dados":{"etapa":"exportando_pdf","pct":80}}
{"v":1,"id":"01J8X…","tipo":"res","ok":false,"erro":{"codigo":"NU-041","mensagem":"…"}}
```

`id` é ULID. `evt` é emitido no meio de uma requisição longa e usa o `id` dela.

### Métodos — o que existe e o que falta

Verificável: `grep -n "registrar\|criar_roteador" nucleo/mapasfacil_nucleo/__main__.py`.

| Método | Params | Retorno | Estado |
|---|---|---|---|
| `ping` | `{}` | `{pong:true}` | **existe** |
| `doctor.rodar` | `{}` | diagnóstico | **existe** (stub fora do Windows) |
| `workspace.abrir` | `{caminho}` | índice + recibo + doctor resumido | **existe** |
| `workspace.reindexar` | `{caminho?}` | índice atualizado | **existe** |
| `workspace.inspecionar` | `{arquivo}` | CRS, campos, feições, bbox, área | **existe** |
| `car.ler_recibo` | `{pdf}` | dados do imóvel (sem CPF) | **existe** |
| `zip.listar` / `zip.extrair` | `{arquivo}` | conteúdo / caminho | **existe** |
| `mapspec.validar` | `{mapspec}` | erros e avisos, sem gerar | **existe** |
| `mapspec.diff` | `{de, para}` | operações | **existe** |
| `mapa.gerar` | `{mapspec, comparar_baseline?}` | artefatos + `validacao.json` | **existe** (não emite evento) |
| `quantitativos.calcular` | `{mapspec\|camadas}` | matriz classe × ha | **existe** |
| `quantitativos.exportar_xlsx` | `{quantitativos, saida}` | caminho do `.xlsx` | **existe** |
| `quantitativos.renderizar_png` | `{quantitativos, saida}` | caminho do PNG ≥ 600 dpi | **existe** |
| `validacao.comparar_pdf` | `{a, b, tolerancia?}` | diferença raster | **existe** |
| `template.listar` / `template.verificar` | `{id?}` | MANIFEST + `sha256_ok` | **existe** |
| `mapa.cancelar` | `{job_id}` | mata o subprocesso ArcPy | **falta** |
| `catalogo.listar` | `{tema?}` | camadas, estilos, templates | **falta** |
| `camada.resolver` | `{fonte, bbox, crs}` | shapefile materializado | **falta** |
| `cofre.definir` / `cofre.existe` / `cofre.testar` | `{chave, valor?}` | ok/erro — **nunca** o valor | **falta** |
| `sessao.definir` / `sessao.estado` | `{estado, conta_id?, expira_em?}` | estado | **falta** — [F1-14](14-auth-e-conta.md) |
| `galeria.listar` / `galeria.detalhar` / `galeria.montar_mapspec` | ver [F1-15](15-galeria-de-modelos.md) | — | **falta** |
| `chat.enviar` | `{conversation_id, mensagem, anexos?}` | stream de `evt` | **falta** |
| `chat.cancelar` | `{turno_id}` | aborta o turno | **falta** |
| `chat.criar_conversa` · `listar_conversas` · `abrir_conversa` · `carregar_anteriores` · `renomear` · `arquivar` · `apagar` · `ramificar` · `buscar` | ver [F1-17](17-persistencia-de-conversas.md) | — | **falta** |
| `visao.analisar_referencia` | `{imagem\|zip}` | `MapSpec` proposto | **falta** |

### Eventos

**Emitidos hoje:** `job.progresso` (A9), `chat.delta` e `chat.tool` (M7), `job.artefato_parcial`
(M8). O vocabulário é fechado em `protocolo.EVENTOS` — emitir nome fora da lista levanta erro, em
vez de virar evento órfão que nenhuma UI consome. A mecânica é a mesma:
`protocolo.Emissor` + `Roteador.despachar(mensagem, emitir)` + registro com `com_eventos=True`.
Quem implementar os outros eventos reaproveita esse canal.

| Evento | Dados | Quando | Estado |
|---|---|---|---|
| `job.progresso` | `{etapa, pct, item?}` | durante `mapa.gerar` | **existe** (A9) — emitido ao concluir cada etapa; `pct` acumulado e monotônico |
| `job.log` | `{linha}` | log técnico do job | falta |
| `job.artefato_parcial` | `{tipo, caminho, etapa, camada_id?, ordem?, pct?}` | artefato intermediário pronto | **existe** (M8) — 4 tipos, caminho relativo; ver [F1-16](16-design-system-dark.md) |
| `workspace.mudou` | `{mudancas:[]}` | watcher detectou alteração | falta |
| `chat.delta` | `{texto}` | pedaço da resposta | **existe** (M7) |
| `chat.tool` | `{trace_id, tool, fase, args_resumo?, resultado_resumo?, ms?, ok?}` | tool chamada/concluída | **existe** (M7) |
| `mapspec.atualizado` | `{id, versao, diff}` | nova versão | falta |
| `aviso` | `{codigo, mensagem}` | avisos não fatais | falta |

### Etapas reportadas em `job.progresso`

| # | Etapa | Peso | Emite `item`? |
|---|---|---|---|
| 1 | `validando_spec` | 3% | não |
| 2 | `resolvendo_camadas_locais` | 7% | **sim** — `camadas[].id` |
| 3 | `baixando_externas` | 20% | **sim** — `camadas[].id` |
| 4 | `calculando_quantitativos` | 10% | não |
| 5 | `gerando_tabela` | 5% | não |
| 6 | `preparando_template` | 10% | não |
| 7 | `aplicando_layout` | 15% | não |
| 8 | `salvando_mxd` | 5% | não |
| 9 | `exportando_pdf` | 15% | não |
| 10 | `validando_saida` | 10% | não |

## Sequência — login local (resumo; detalhe em F1-14)

```
renderer              main                         núcleo (contas.sqlite)
   │ auth:criar/entrar │                              │
   ├──────────────────▶│ NDJSON conta.criar|entrar ──▶│ Argon2id + sessão local
   │                   │◀── {conta, sessao} ──────────┤
   │◀ auth:mudou ──────┤                              │
   │  {conectado}      ├── sessao.definir {estado, conta_id} (sem senha)
```

O renderer **nunca** vê senha nem `senha_hash`. O gate de `mapa.gerar` é `sessao.estado`
(D11, `AUTH-030`). Sem rede.

## Sequência — gerar um mapa pela galeria (sem IA)

```
renderer                     núcleo
   │ galeria.listar ────────────▶│ lê modelos.json × MANIFEST × índice
   │◀── modelos + status ────────┤
   │ galeria.montar_mapspec ────▶│ 13 passos determinísticos
   │◀── {mapspec, avisos} ───────┤
   │ mapspec.validar ───────────▶│ schema + catálogo + invariantes
   │◀── {erros:[], avisos:[]} ───┤
   │ mapa.gerar ────────────────▶│ gate de sessão → job
   │◀── evt job.progresso ×N ────┤   (anima barra-progresso-job e painel-preview)
   │◀── evt job.artefato_parcial ┤   (M8)
   │◀── res {artefatos, validacao}
```

## Sequência — um turno de chat

```
renderer                 núcleo/agente                    DeepSeek
   │ chat.enviar ───────────▶│ grava mensagem (redator de CPF)
   │                         │ monta contexto comprimido (F1-06)
   │                         ├────── request (stream) ───────▶│
   │◀── evt chat.delta ×N ───┤◀───── deltas ──────────────────┤
   │◀── evt chat.tool ───────┤ executa tool no núcleo
   │                         ├────── resultado da tool ──────▶│   (até 12 rodadas — IA-030)
   │◀── evt mapspec.atualizado
   │◀── res {mensagem, mapspec_id, versao, tokens}
   │                         │ grava mensagem + tool_traces em chats.sqlite
```

`Esc` no renderer → `chat.cancelar` → o núcleo aborta o request HTTP, grava a mensagem parcial com
`cancelada: 1` e devolve resposta normal com `cancelado: true`.

## Pipeline de contexto do agente (resumo; detalhe em F1-06)

```
   índice do workspace ─┐
   recibo do CAR ───────┤
   quantitativos ───────┼─▶ memória de trabalho  (<= 1.200 tokens, recalculada quando o índice muda)
   MapSpec atual ───────┘

   transcript completo ──▶ últimos 8 turnos verbatim
                           + compact_summary (<= 800 tokens, deepseek-v4-flash)

   MapSpec ──────────────▶ turno 1: completo · demais: mapspec.diff
   galeria ──────────────▶ só o item selecionado
   tools ────────────────▶ resumo tipado, <= 2.000 tokens por resultado

                     ▼
        teto de entrada por turno: 60.000 tokens
        estourou? → compacta → resume → recusa com IA-040
```

## Estado e armazenamento local

```
%APPDATA%\MapasFacil\
├─ config.json              preferências, projetos recentes, allowlist, conta (sem senha)
├─ contas\
│  └─ contas.sqlite         contas locais (e-mail + senha_hash Argon2id) + sessoes_locais  ← F1-14
├─ chats\
│  ├─ chats.sqlite          TODAS as conversas, mensagens, tool_traces, FTS   ← D13
│  └─ anexos\<conversation_id>\
├─ projetos\<fingerprint>\
│  ├─ mapspecs.sqlite       append-only: id, versao, parent_id, spec, valido
│  └─ jobs.sqlite           jobs, etapas, artefatos, validacao
└─ logs\                    rotacionado, 7 dias, com redator aplicado

%LOCALAPPDATA%\MapasFacil\
├─ cache\                   WFS, WMS, tiles, malha IBGE  (TTL por tema)
└─ tmp\<job_id>\            trabalho do ArcPy; limpo ao final

Windows Credential Manager / keyring do SO
   MapasFacil/deepseek_api_key · MapasFacil/sema_authkey · MapasFacil/planet_api_key
   (BYOK apenas — **não** guarda senha de conta; senha vai hasheada em contas.sqlite)```

**D13 revoga o desenho anterior** de `projetos\<hash>\conversas.sqlite`: as conversas vivem num
banco único global, para a sidebar listar chats de todos os workspaces (comportamento Cursor).
`mapspecs` e `jobs` continuam por projeto — eles são específicos da pasta e somem com ela.

`mapspecs` é **append-only**: editar cria linha nova com `parent_id`. Histórico de versões sai de
graça, e "por que este mapa ficou assim" tem resposta.

## Segurança de sistema de arquivos — `fsguard`

O componente mais importante do núcleo, e o de suíte de testes mais densa. **Já existe, fechado,
com 100% de cobertura de linha e ramo.**

```python
def resolver(caminho: str, workspace: Path, escrita: bool) -> Path:
    """Resolve e autoriza um caminho, ou levanta CaminhoNaoAutorizado."""
```

Regras:

1. `realpath` antes de qualquer comparação — resolve `..`, `.` e **symlink**.
2. O resultado tem de estar sob uma das pastas autorizadas do workspace.
3. Escrita só nas subpastas de saída (`Mapas/`, `MXD/`, `SHP/`, `_extraido/`).
4. Rejeita: caminho UNC (`\\servidor\share`), unidade diferente da do workspace, nome reservado
   do Windows (`CON`, `PRN`, `AUX`, `NUL`, `COM1`…`LPT9`), caractere `<>:"|?*`, componente com
   mais de 255 caracteres, caminho final acima de 260 caracteres sem prefixo `\\?\`.
5. Nunca segue symlink que sai do workspace, mesmo para leitura.

`%APPDATA%\MapasFacil\` **não** é workspace: o acesso a `chats.sqlite` e `config.json` passa por
um resolvedor separado, restrito a essa árvore, sem allowlist dinâmica.

## Códigos de erro

Prefixo por camada, número estável. O código aparece na UI e no log — é o que o usuário cola no
suporte.

| Faixa | Camada | Exemplos |
|---|---|---|
| `NU-0xx` | núcleo / workspace | `NU-001` pasta não existe · `NU-010` caminho fora da allowlist · `NU-020` shapefile sem `.prj` |
| `NU-1xx` | camadas / rede | `NU-101` WFS timeout · `NU-110` WMS devolveu XML · `NU-120` camada vazia após clip |
| `NU-2xx` | `MapSpec` | `NU-201` schema inválido · `NU-210` camada fora do catálogo · `NU-220` escala não permitida |
| `NU-23x` | **galeria** | `NU-230` modelo inexistente · `NU-231` template ausente/`sha256` divergente · `NU-232` sobrescrita fora da allowlist · `NU-233` requisito obrigatório ausente · `NU-234` `modelos.json` inválido |
| `AG-0xx` | ambiente ArcGIS | `AG-001` ArcMap não encontrado · `AG-010` licença indisponível · `AG-020` timeout do ArcPy · `AG-030` template com `sha256` diferente |
| `AG-1xx` | geração | `AG-101` fonte quebrada no `.mxd` · `AG-110` PDF em branco · `AG-120` elemento obrigatório ausente |
| `IA-0xx` | agente | `IA-001` chave ausente · `IA-010` provedor indisponível · `IA-020` tool inexistente · `IA-030` limite de rodadas · `IA-040` contexto excedido após compressão · `IA-041` teto de tokens da conversa · `IA-050` resposta truncada por `max_tokens` |
| `AUTH-0xx` | conta e sessão local | `AUTH-001` sem login · `AUTH-002` e-mail/senha incorretos · `AUTH-003` senha fraca · `AUTH-030` operação exige sessão · `AUTH-050` falha no SQLite · `AUTH-070` e-mail já cadastrado — tabela completa em [F1-14](14-auth-e-conta.md) |
| `UI-0xx` | app | `UI-001` núcleo não subiu · `UI-010` versão do núcleo incompatível · `UI-020` projeto recente não está mais na lista |

## Matriz de ambiente

| Ambiente | `.mxd` | `.pdf` | Fidelidade | Motor |
|---|---|---|---|---|
| ArcMap 10.6–10.8 + licença | sim | ArcMap | referência | `arcpy.mapping` |
| ArcMap sem licença | **sim** (patch) | nativo | alta no `.mxd`, média no PDF | patch + matplotlib |
| ArcGIS Pro 3.x apenas | não¹ | Pro | alta no PDF | `arcpy.mp` |
| Sem ArcGIS | **sim** (patch) | nativo | alta no `.mxd`, média no PDF | patch + matplotlib |

¹ Pro 3.x não salva `.mxd` — não existe `saveAsMXD`, e "Save As ArcMap Document" foi removido da
interface. Num PC só-Pro, o `.mxd` sai pelo caminho de patch, não pelo `arcpy.mp`.

**O caminho de patch é o que torna o produto viável fora de máquinas com ArcMap.** Detalhe em
[`04-motor-mxd.md`](04-motor-mxd.md).

## Versionamento e compatibilidade

| Componente | Versionado por |
|---|---|
| App (Electron) | semver, canal `stable`/`beta` |
| Núcleo Python | empacotado junto do app; `versao_nucleo` conferida no boot |
| `MapSpec` | `contract_version` (hoje **2**) |
| Templates | `MANIFEST.json` com `sha256` por arquivo |
| Catálogo | `catalog_version` + data de verificação |
| Galeria | `galeria_version` |
| Banco de conversas | `schema_versao` + migrações versionadas |

App e núcleo sobem juntos (mesmo instalador), então não há matriz de compatibilidade entre eles —
só a checagem de sanidade no boot (`UI-010`).

## Tarefas agentáveis

- [x] `nucleo/mapasfacil_nucleo/motores/gerar.py` — emitir `job.progresso` nas 10 etapas
- [x] `nucleo/mapasfacil_nucleo/__main__.py` — canal de eventos no roteador
- [ ] `nucleo/mapasfacil_nucleo/sessao.py` — `sessao.definir` / `sessao.estado` + gate
- [ ] `nucleo/mapasfacil_nucleo/cofre.py` — Credential Manager; `existe`/`testar` nunca devolvem valor
- [ ] `nucleo/mapasfacil_nucleo/workspace/watcher.py` — debounce 500 ms + `workspace.mudou`
- [ ] `nucleo/mapasfacil_nucleo/jobs.py` — `mapa.cancelar` com `taskkill /T /F`
- [x] `app/electron/main.ts`, `app/electron/nucleo/ponte.ts` — spawn, NDJSON, reinício *(sem teste executado)*
- [x] `app/electron/ipc/` — canais tipados; nenhum expõe caminho absoluto sem passar pelo núcleo
- [x] `app/src/estado/eventos.ts` — assinatura dos 8 eventos

## Critérios de aceite

- [x] `python -m mapasfacil_nucleo stdio` + `mapa.gerar` na fixture Harmonia emite **as 10 etapas**
      em linhas `tipo:"evt"` com `evento:"job.progresso"`, `pct` monotônico de 3 a 100 — mais um
      evento por camada nas etapas com `item`, então o total é ≥ 10
      (`tests/test_job_progresso.py::test_mapa_gerar_emite_as_dez_etapas_em_ordem`)
- [x] `grep -rn "envelope_evt" nucleo/mapasfacil_nucleo/` retorna a definição **e ao menos um chamador**
- [ ] `mapa.cancelar` durante um job mata a árvore de processos: nenhum `python.exe` órfão
      (`tasklist` antes/depois no teste do anel 3)
- [ ] `sessao.estado` = `desconectado` faz `mapa.gerar` devolver `AUTH-030` e `workspace.abrir` funcionar
- [ ] `grep -rn "access_token\|api_key" app/src/` vazio — segredo não chega ao renderer
- [ ] Matar o núcleo no meio de um job: o app mostra `UI-001`, oferece reiniciar, e a conversa
      continua íntegra ao reabrir (está em `chats.sqlite`)
- [ ] Nenhuma porta TCP aberta pelo sidecar: `netstat -ano | findstr <pid do núcleo>` vazio

## Fora de escopo

- Núcleo como servidor HTTP ou WebSocket local (AP-14).
- Múltiplas instâncias do núcleo por projeto (ver P3).
- Comando remoto vindo do backend para o desktop (ameaça A7; a ponte da Fase 2 transporta
  `MapSpec`, revalidado localmente).
- Plugin/extensão de terceiros no núcleo.

## Anti-padrões

| Não faça | Por quê |
|---|---|
| Expor caminho absoluto no NDJSON de volta ao renderer | vaza estrutura do disco e viola a fronteira 1 |
| Emitir evento com `pct` que anda para trás | a barra de progresso passa a mentir |
| Fazer o núcleo chamar o backend de identidade | fronteira 6; token acabaria no sidecar |
| Guardar segredo em `config.json` | é lido pelo renderer; vai para o Credential Manager |
| Criar método NDJSON sem código de erro na tabela acima | o usuário recebe erro sem nome |
| Bloquear o loop NDJSON com trabalho pesado sem emitir progresso | o app parece travado |

## Pendências

| # | Questão | Recomendação |
|---|---|---|
| P1 | Empacotar o Python: PyInstaller *onedir* vs *onefile* | **onedir** — inicia 3–5 s mais rápido; ver [F1-11](11-empacotamento-instalador.md) |
| P2 | Auto-update com o núcleo dentro: `.exe` inteiro ou diff | `.exe` inteiro na v1; diff é otimização |
| P3 | Multi-projeto: uma instância do núcleo por projeto ou uma com contexto | **uma instância**, contexto por requisição — o banco de conversas já é global |
| P4 | Núcleo morre no meio de um job: retomar ou marcar falho | **marcar falho** e oferecer "gerar de novo"; retomada exige checkpoint que não vale o custo |
| P5 | Tamanho do instalador com Python + libs geo + Electron | meta < 250 MB; ver [F1-11](11-empacotamento-instalador.md) |
