# F1-01 — Arquitetura do app desktop

**Fonte da verdade dos contratos internos da Fase 1.** Se outro plano da fase divergir, este
ganha. O `MapSpec` e o padrão visual vêm dos planos comuns
([`../../planos/02-mapspec-contrato.md`](../../planos/02-mapspec-contrato.md),
[`../../planos/01-padrao-imap-harmonia.md`](../../planos/01-padrao-imap-harmonia.md)) e não são
redefinidos aqui.

## Os três processos

```
┌──────────────────────────── PC do usuário — Windows 10/11 ────────────────────────────┐
│                                                                                        │
│  ┌──────────────────────────┐        ┌─────────────────────────────────────────────┐   │
│  │  Electron — main         │        │  Electron — renderer (React)                │   │
│  │  • janela, menus, tray   │◀──IPC─▶│  • árvore da pasta   • chat + streaming     │   │
│  │  • diálogo de pasta      │        │  • preview do mapa   • painel do MapSpec    │   │
│  │  • Credential Manager    │        │  • histórico de versões  • doctor           │   │
│  │  • auto-update           │        └─────────────────────────────────────────────┘   │
│  └───────────┬──────────────┘                                                          │
│              │ stdio JSON-RPC (NDJSON, uma linha por mensagem)                          │
│  ┌───────────▼────────────────────────────────────────────────────────────────────┐   │
│  │  NÚCLEO — Python 3.12 (sidecar, empacotado com o app)                           │   │
│  │  ┌──────────┬──────────┬───────────┬───────────┬──────────┬──────────────────┐ │   │
│  │  │workspace │  camadas │  mapspec  │  motores  │  agente  │  cofre / doctor  │ │   │
│  │  │index+watch│ wfs/wms │ validacao │ mxd·pdf   │ deepseek │  keyring         │ │   │
│  │  │          │ clip     │           │ xlsx·png  │ tools    │                  │ │   │
│  │  └──────────┴──────────┴───────────┴─────┬─────┴──────────┴──────────────────┘ │   │
│  └────────────────────────────────────────┬─┴──────────────────────────────────────┘   │
│                                            │ subprocess, payload em arquivo JSON        │
│  ┌─────────────────────────────────────────▼──────────────────────────────────────┐   │
│  │  Python 2.7 do ArcMap  —  arcpy_job.py                                          │   │
│  │  abre template · repõe fontes · extent/escala · textos · exporta PDF            │   │
│  │  (só quando há ArcMap; roda sempre com timeout)                                 │   │
│  └────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                        │
│  Saída:  <pasta do projeto>/Mapas/  ·  <pasta do projeto>/MXD/  ·  .../SHP/            │
└────────────────────────────────────────────────────────────────────────────────────────┘
        │                          │                         │
        ▼                          ▼                         ▼
  api.deepseek.com        geo.sema.mt.gov.br         tiles.planet.com
  (chat, chave do        (WFS/WMS + authkey)          (basemap)
   usuário)              + IBAMA, FUNAI, IBGE…
```

### Por que três processos e não um

| Alternativa | Por que não |
|---|---|
| Tudo em Node | o ecossistema geo maduro é Python: `shapely`, `pyproj`, `fiona`, `rasterio`, `PyMuPDF`, `openpyxl`, `matplotlib`. Reescrever em JS é meses de trabalho e perda de precisão |
| Tudo em Python (PySide6) | chat com streaming, diff, preview e árvore de arquivos no nível do Cursor custa muito mais em Qt |
| Núcleo como servidor HTTP local | abre porta na máquina do usuário — superfície de ataque e conflito de porta. stdio não tem nenhum dos dois |

### Regras de fronteira (invioláveis)

1. **O renderer nunca toca o disco do usuário diretamente.** Toda leitura e escrita passa pelo
   núcleo, que valida contra a allowlist do workspace.
2. **O núcleo nunca executa string vinda de fora.** Sem `eval`, sem `exec`, sem
   `subprocess(shell=True)`. O único subprocesso é o Python do ArcMap, com argumentos fixos.
3. **A IA nunca gera código.** Ela chama tools tipadas que produzem e editam `MapSpec`.
4. **Segredo nunca sai do processo principal do Electron** a não ser para o núcleo, sob demanda,
   e nunca é logado.
5. **O núcleo é a única coisa que sabe geo.** O renderer só desenha o que recebe.

## Protocolo Electron ↔ núcleo

NDJSON sobre stdin/stdout: uma mensagem JSON por linha, sem framing extra. `stderr` é log.

```json
{"v":1,"id":"01J8X…","tipo":"req","metodo":"workspace.abrir","params":{"caminho":"C:\\…"}}
{"v":1,"id":"01J8X…","tipo":"res","ok":true,"resultado":{"arquivos":[…]}}
{"v":1,"id":"01J8X…","tipo":"evt","evento":"job.progresso","dados":{"etapa":"exportando_pdf","pct":80}}
{"v":1,"id":"01J8X…","tipo":"res","ok":false,"erro":{"codigo":"NU-041","mensagem":"…"}}
```

`id` é ULID. `evt` é emitido no meio de uma requisição longa e usa o `id` dela.

### Métodos

| Método | Params | Retorno |
|---|---|---|
| `workspace.abrir` | `{caminho}` | índice da pasta + doctor resumido |
| `workspace.reindexar` | `{caminho?}` | índice atualizado |
| `workspace.inspecionar` | `{arquivo}` | CRS, campos, feições, bbox, área, validade |
| `car.ler_recibo` | `{pdf}` | dados do imóvel |
| `zip.listar` / `zip.extrair` | `{arquivo}` | conteúdo / caminho extraído |
| `catalogo.listar` | `{tema?}` | camadas, estilos e templates disponíveis |
| `camada.resolver` | `{fonte, bbox, crs}` | caminho do shapefile materializado |
| `mapspec.validar` | `{mapspec}` | lista de erros e avisos, sem gerar nada |
| `mapa.gerar` | `{mapspec}` | artefatos + `validacao.json`; emite `job.progresso` |
| `mapa.cancelar` | `{job_id}` | mata o subprocesso ArcPy |
| `planilha.gerar` | `{quantitativos, saida}` | caminho do `.xlsx` |
| `chat.enviar` | `{projeto, mensagem, anexos?}` | stream de `evt` com deltas e tool calls |
| `chat.cancelar` | `{turno_id}` | aborta o turno |
| `visao.analisar_referencia` | `{imagem\|zip}` | `MapSpec` proposto |
| `doctor.rodar` | `{}` | diagnóstico completo |
| `cofre.definir` / `cofre.testar` | `{chave, valor}` | ok/erro — **nunca** devolve o valor |

### Eventos

| Evento | Quando |
|---|---|
| `workspace.mudou` | watcher detectou alteração na pasta |
| `chat.delta` | pedaço de texto da resposta |
| `chat.tool` | tool chamada / resultado |
| `mapspec.atualizado` | nova versão, com diff |
| `job.progresso` | etapa e percentual |
| `job.log` | linha de log técnico |
| `aviso` | avisos não fatais (camada vazia, cache velho, área divergente) |

## Ciclo de vida de um mapa

```
 1. Usuário abre a pasta          → workspace.abrir → índice + doctor
 2. Núcleo lê o recibo do CAR     → nome, município, CAR, áreas
 3. Usuário pede o mapa no chat
 4. Agente chama tools:
       estado_do_projeto → ler_recibo_car → listar_camadas
       → consultar_sema  → criar_mapa → adicionar_camada ×N
       → definir_tabela  → validar_mapspec → gerar_mapa
 5. Núcleo valida o MapSpec contra schema + catálogo (rejeita, não corrige)
 6. Resolve camadas: shapefile local; WFS por bbox + clip; materializa em SHP/
 7. Calcula quantitativos em UTM; gera o PNG da tabela
 8. Motor de mapa:
       ArcMap presente? → subprocesso Python 2.7 → .mxd + .pdf
       ausente?         → patch de template → .mxd ; renderizador nativo → .pdf
 9. Valida a saída (14 HARD + 11 SOFT) → validacao.json
10. Renderer mostra preview, checks e os arquivos gerados
11. "muda a cor da AVN" → nova versão do MapSpec → arquivos _v2, anteriores intactos
```

### Etapas reportadas em `job.progresso`

| # | Etapa | Peso |
|---|---|---|
| 1 | `validando_spec` | 3% |
| 2 | `resolvendo_camadas_locais` | 7% |
| 3 | `baixando_externas` | 20% |
| 4 | `calculando_quantitativos` | 10% |
| 5 | `gerando_tabela` | 5% |
| 6 | `preparando_template` | 10% |
| 7 | `aplicando_layout` | 15% |
| 8 | `salvando_mxd` | 5% |
| 9 | `exportando_pdf` | 15% |
| 10 | `validando_saida` | 10% |

## Estado e armazenamento local

```
%APPDATA%\MapasFacil\
├─ config.json              preferências, projetos recentes, allowlist de pastas
├─ projetos\<hash>\
│  ├─ conversas.sqlite      mensagens, tool calls, uso de tokens
│  ├─ mapspecs.sqlite       append-only: id, versao, parent_id, spec, valido
│  └─ jobs.sqlite           jobs, etapas, artefatos, validacao
└─ logs\                    rotacionado, 7 dias

%LOCALAPPDATA%\MapasFacil\
├─ cache\                   WFS, WMS, tiles, malha IBGE  (TTL por tema)
└─ tmp\<job_id>\            trabalho do ArcPy; limpo ao final

Windows Credential Manager  deepseek_api_key · sema_authkey · planet_api_key
```

SQLite e não JSON: histórico de conversa e de versões cresce, precisa de consulta por data e de
escrita concorrente entre o watcher e o chat. Um arquivo por projeto mantém tudo junto do
contexto e torna trivial "apagar este projeto".

`mapspecs` é **append-only**: editar cria linha nova com `parent_id`. Histórico de versões sai
de graça, e "por que este mapa ficou assim" tem resposta.

## Segurança de sistema de arquivos — `fsguard`

O componente mais importante do núcleo, e o de suíte de testes mais densa.

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

Testes obrigatórios em [`10-testes-e-qa.md`](10-testes-e-qa.md).

## Códigos de erro

Prefixo por camada, número estável. O código aparece na UI e no log — é o que o usuário cola no
suporte.

| Faixa | Camada | Exemplos |
|---|---|---|
| `NU-0xx` | núcleo / workspace | `NU-001` pasta não existe · `NU-010` caminho fora da allowlist · `NU-020` shapefile sem `.prj` |
| `NU-1xx` | camadas / rede | `NU-101` WFS timeout · `NU-110` WMS devolveu XML · `NU-120` camada vazia após clip |
| `NU-2xx` | `MapSpec` | `NU-201` schema inválido · `NU-210` camada fora do catálogo · `NU-220` escala não permitida |
| `AG-0xx` | ambiente ArcGIS | `AG-001` ArcMap não encontrado · `AG-010` licença indisponível · `AG-020` timeout do ArcPy · `AG-030` template com `sha256` diferente |
| `AG-1xx` | geração | `AG-101` fonte quebrada no `.mxd` · `AG-110` PDF em branco · `AG-120` elemento obrigatório ausente no template |
| `IA-0xx` | agente | `IA-001` chave ausente · `IA-010` provedor indisponível · `IA-020` tool inexistente · `IA-030` limite de turnos |
| `UI-0xx` | app | `UI-001` núcleo não subiu · `UI-010` versão do núcleo incompatível |

## Matriz de ambiente

| Ambiente | `.mxd` | `.pdf` | Fidelidade | Motor |
|---|---|---|---|---|
| ArcMap 10.6–10.8 + licença | sim | ArcMap | referência | `arcpy.mapping` |
| ArcMap sem licença | **sim** (patch) | nativo | alta no `.mxd`, média no PDF | patch + matplotlib |
| ArcGIS Pro 3.x apenas | não¹ | Pro | alta no PDF | `arcpy.mp` |
| Sem ArcGIS | **sim** (patch) | nativo | alta no `.mxd`, média no PDF | patch + matplotlib |

¹ Pro 3.x não salva `.mxd` — não existe `saveAsMXD`, e "Save As ArcMap Document" foi removido da
interface. Num PC só-Pro, o `.mxd` sai pelo caminho de patch, não pelo `arcpy.mp`.

**O caminho de patch é o que torna o produto viável fora de máquinas com ArcMap** e é a diferença
central em relação ao plano anterior. Detalhe em [`04-motor-mxd.md`](04-motor-mxd.md).

## Versionamento e compatibilidade

| Componente | Versionado por |
|---|---|
| App (Electron) | semver, canal `stable`/`beta` |
| Núcleo Python | empacotado junto do app; `versao_nucleo` conferida no boot |
| `MapSpec` | `contract_version` |
| Templates | `MANIFEST.json` com `sha256` por arquivo |
| Catálogo | `catalog_version` + data de verificação |

App e núcleo sobem juntos (mesmo instalador), então não há matriz de compatibilidade entre eles —
só a checagem de sanidade no boot (`UI-010`).

## Pendências

| # | Questão |
|---|---|
| P1 | Empacotar o Python: PyInstaller *onedir* (~120 MB, inicia rápido) vs *onefile* (menor, extrai a cada boot) |
| P2 | Auto-update do Electron com o núcleo dentro: substituir o `.exe` inteiro ou só o diff |
| P3 | Multi-projeto simultâneo — uma instância do núcleo por projeto ou uma só com contexto por projeto |
| P4 | Se o núcleo morrer no meio de um job, o Electron deve retomar ou marcar como falho |
| P5 | Tamanho do instalador com Python + libs geo + Electron; meta < 250 MB |
