# W-04 — Ponte servidor ↔ núcleo e o "modo servidor" do núcleo

## Objetivo

Fazer o servidor hospedar o núcleo `mapasfacil_nucleo` **sem mudar o que ele é**: um processo
filho por projeto, falando o mesmo NDJSON por stdio que o Electron fala, com um "modo servidor"
mínimo que troca as três coisas que só fazem sentido no PC do usuário — cofre no keyring, sessão
local e diretórios do APPDATA.

## Estado atual vs alvo

| Item | Hoje | Alvo |
|---|---|---|
| Quem fala com o núcleo | `Fase_1_Desktop/app/electron/nucleo/ponte.ts` (Electron main) | + `Fase_3_Web/servidor/mapasfacil_servidor/ponte/` (Python asyncio) |
| Protocolo | `protocolo.py`: envelopes `req`/`res`/`evt`, `PROTOCOLO_VERSAO`, ULID | **igual** |
| Cofre | `cofre.py` → keyring (Credential Manager / Secret Service); dev: `secrets.local.json` | modo servidor: lê env injetada pela ponte |
| Sessão | `sessao.py` + gate `AUTH-030` em `mapa.gerar`, `chat.enviar`, … | modo servidor: sessão vem de `MAPASFACIL_SESSAO_SERVIDOR` |
| Dirs de dados | `dados.py`, `conversas/banco.py`, `contas/banco.py` com ordem de resolução por env | **já resolvem por env** — a ponte só injeta |
| Concorrência de geração | um usuário, um job | `MF_MAX_JOBS` vagas por `flock` entre processos |
| Watcher de pasta (`workspace/watcher.py`) | ligado | desligado em modo servidor (a entrada é imutável) |

## Dependências

[W-01](01-arquitetura.md). Bloqueia W3–W8.

## Contratos

### Modo servidor no núcleo (W1)

Ativado por `MAPASFACIL_MODO=servidor`. Uma função só decide: `config.modo_servidor() -> bool`.
Nada mais no núcleo testa a env diretamente.

| Ponto | Arquivo | Comportamento em modo servidor |
|---|---|---|
| Cofre | `cofre.py` | `obter(nome)` lê `MAPASFACIL_DEEPSEEK_API_KEY`, `MAPASFACIL_SEMA_AUTHKEY`, `MAPASFACIL_PLANET_API_KEY`; `cofre.definir` → `NU-060` "cofre é do servidor"; nunca toca keyring |
| Sessão | `sessao.py` | `sessao.estado` = autenticado com `usuario_id = MAPASFACIL_SESSAO_SERVIDOR`; `conta.*` e `sessao.definir` → `AUTH-090` (novo) "conta é do servidor" |
| Provisão automática de chaves | `agente/provisao.py` | desligada (D33) |
| Watcher | `workspace/watcher.py` | não inicia |
| Projeto | `workspace/servico.py` | ao abrir, lê `.servidor/projeto.json` → `folha` padrão e `nome` entram na memória de trabalho do agente (`tools.py::montar_memoria_trabalho`) |
| Pasta de saída | `galeria/montar.py`, `agente/tools.py::tool_criar_mapa` | `saida.pasta = "Mapas/v%03d" % versao` (em vez de sufixo `_vN` na `Mapas/`) |
| Vaga de geração | `jobs.py` (ou `motores/gerar.py` na entrada) | **antes de `validando_spec`**: `flock` em `MAPASFACIL_VAGAS_DIR/vaga-{0..N-1}.lock`; sem vaga → `job.log "aguardando vaga (2 mapas sendo gerados)"` a cada 10 s e espera; cancelamento libera a espera. A vaga é liberada ao fim do job (sucesso, erro ou cancelamento) e pelo próprio SO se o processo morrer |
| Doctor | `doctor.py` | reporta `modo: "servidor"`, `arcmap: "não se aplica"`, `motor_mxd: "binario"` |
| Motor `.mxd` | `motores/gerar.py` | nunca escolhe `arcpy`; escolhe `binario` (W10) ou nenhum |

Teste de fronteira `tests/test_modo_servidor.py`: com a env ligada, nenhuma chamada a `keyring`,
nenhum acesso a `APPDATA`/`XDG_DATA_HOME`, nenhum `subprocess` de Python 2.7.

### Ponte (W2) — `servidor/mapasfacil_servidor/ponte/`

#### `worker.py` — um processo

```python
class Worker:
    projeto_id: str
    estado: Literal["iniciando", "pronto", "ocupado", "encerrando", "caido"]
    async def iniciar(self) -> None          # spawn + handshake (doctor.rodar curto ou ping)
    async def chamar(self, metodo: str, params: dict, *, timeout_s: float,
                     ao_evento: Callable[[dict], Awaitable[None]]) -> dict   # res.resultado ou ErroNucleo
    async def cancelar(self, req_id: str) -> None
    async def encerrar(self, *, motivo: str) -> None   # SIGTERM, espera 10 s, SIGKILL
```

- Spawn: `asyncio.create_subprocess_exec(MF_PYTHON_NUCLEO, "-m", "mapasfacil_nucleo",
  cwd=<raiz do projeto>, env=<env mínima>, stdin=PIPE, stdout=PIPE, stderr=PIPE,
  start_new_session=True)`. Env mínima = só as variáveis da tabela de [W-01](01-arquitetura.md)
  + `PATH`, `LANG=C.UTF-8`, `PYTHONIOENCODING=utf-8`, `HOME`. **Não** herdar o ambiente do
  servidor inteiro (vazaria `MF_*`).
- Leitura de stdout linha a linha (`readline`, limite de 16 MiB por linha — maior → `SV-230`
  e o worker é reiniciado). Cada linha → `protocolo.parsear_linha` (importável: é utilitário puro).
- `tipo:"evt"` → `ao_evento` da requisição dona do `id`; evento com `id` desconhecido (assíncrono,
  ex.: `viewport.foco` da indexação) → callback de projeto.
- `tipo:"res"` → resolve o futuro do `id`.
- stderr → log técnico do servidor (`logs/workers/<projeto_id>.log`, rotação 5 × 10 MB), **com
  redação** de padrões de CPF e de chave (`sk-…`, `authkey=`) antes de gravar.
- Timeout de requisição: `MF_TIMEOUT_REQ_S`; estourou → `mapa.cancelar`/`chat.cancelar`, espera
  30 s, senão encerra o worker → `SV-220`.
- Morte do processo (EOF no stdout) → todas as requisições pendentes falham com `SV-221`,
  evento `worker.estado {estado:"caido"}`; o próximo pedido reinicia.

#### `pool.py` — muitos processos

- `obter(projeto_id) -> Worker`: reusa ou inicia; se já há `MF_MAX_WORKERS` vivos, encerra o
  **ocioso há mais tempo**; se todos estão ocupados, espera até 60 s → `SV-211` ("servidor cheio,
  tente em instantes").
- Varredura a cada 60 s: encerra quem está ocioso há `MF_WORKER_OCIOSO_S`.
- Um turno de chat por projeto (fila de 1): segundo `chat.enviar` com o primeiro em curso → `SV-210`.
- Desligamento do servidor: `encerrar` todos com `motivo="desligando"`; jobs em curso recebem
  cancelamento (o usuário vê "o servidor reiniciou durante a geração — mande de novo").

#### `allowlist.py` — o que o servidor pode pedir ao núcleo

| Método | Quem chama | Observação |
|---|---|---|
| `workspace.abrir` | ponte | `pasta` é **sempre** a raiz do projeto, montada pelo servidor; nunca vem do navegador |
| `workspace.inspecionar`, `workspace.reindexar` | ponte | — |
| `chat.criar_conversa`, `chat.abrir_conversa`, `chat.carregar_anteriores`, `chat.enviar`, `chat.cancelar` | API de mensagens | uma conversa principal por projeto (D25) |
| `chat.renomear` | API (renomear projeto) | o título da conversa acompanha o nome do projeto |
| `mapa.gerar`, `mapa.cancelar` | API ("gerar de novo esta versão") | o agente também chama por tool, dentro do `chat.enviar` |
| `analise.executar` | tool do agente / botão "Série completa" | — |
| `mapspec.validar`, `mapspec.diff` | API de versões | — |
| `quantitativos.calcular`, `quantitativos.exportar_xlsx`, `quantitativos.renderizar_png` | tool / API | — |
| `galeria.listar`, `galeria.detalhar`, `galeria.montar_mapspec` | sugestões do chat | — |
| `catalogo.listar` | API (painel "camadas disponíveis") | — |
| `doctor.rodar` | `/admin/saude` | só admin |
| **bloqueados** | — | `cofre.*`, `conta.*`, `sessao.*`, `chat.apagar`, `chat.arquivar`, `chat.ramificar`, `chat.gravar_mensagem`, `artefato.ler` (o servidor lê arquivo direto, com a allowlist de prefixos), `camada.resolver` direto |

Método fora da allowlist → `SV-201` **antes** de chegar ao worker. Teste
`test_allowlist.py` lista os métodos do núcleo (pelo `grep` do registro de métodos no
`__main__`/dispatcher) e falha se aparecer método novo sem classificação explícita.

#### `fake_nucleo.py` — núcleo falso para testes

Executável Python (`python -m mapasfacil_servidor.ponte.fake_nucleo --roteiro <arquivo>`) que
fala o protocolo real e reproduz um **roteiro** NDJSON gravado: responde `workspace.abrir`,
emite eventos de um job completo com os atrasos gravados, responde `chat.enviar` com deltas.
Roteiros em `servidor/tests/roteiros/*.ndjson`, gravados de execuções reais do núcleo com o
`imovel_ficticio.zip` (W7-10). É o que deixa W3–W8 testáveis sem GDAL, rede ou IA.

### Registro de versão (ponte → banco)

Quando a requisição `mapa.gerar` (ou o `chat.enviar` que chamou a tool `gerar_mapa`) termina com
artefatos, a ponte:

1. lê o `validacao.json` da versão e os artefatos de `Mapas/vNNN/`;
2. grava `versoes` (com `conforme` = todos os HARD ok) e atualiza `projetos.versao_atual` e
   `miniatura` (o `preview_png` final);
3. emite `versao.criada`.

A ponte **não** decide conformidade: só copia o que o núcleo escreveu.

## Tarefas agentáveis

### W1 — núcleo

- [ ] **W1-02** `config.py::modo_servidor()`; teste.
- [ ] **W1-03** `cofre.py`: ramo de env em modo servidor; `cofre.definir` → `NU-060`.
- [ ] **W1-04** `sessao.py` + gates: sessão do servidor; `AUTH-090` para `conta.*`/`sessao.definir`.
- [ ] **W1-05** `agente/provisao.py`: não roda em modo servidor.
- [ ] **W1-06** `workspace/watcher.py`: não inicia em modo servidor.
- [ ] **W1-07** `workspace/servico.py`: lê `.servidor/projeto.json`; `tools.py::montar_memoria_trabalho` inclui `folha` e nome do projeto.
- [ ] **W1-08** Saída por versão (`Mapas/vNNN/`) só em modo servidor — `galeria/montar.py`, `tools.py::tool_criar_mapa`, `analise/executar.py` (série vai em `Mapas/vNNN/serie/`).
- [ ] **W1-09** Vagas por `flock` em `jobs.py`/`motores/gerar.py` + `analise/executar.py`; `job.log` de espera; cancelamento libera.
- [ ] **W1-10** `doctor.py`: campos do modo servidor.
- [ ] **W1-11** `motores/gerar.py`: em modo servidor nunca `arcpy`.
- [ ] **W1-12** `MapSpec` v3: `shared/schemas/mapspec.schema.json` com `folha` obrigatório, `contract_version: 3`; `mapspec/validar.py` migra v2 → v3 lendo `formato_pagina` do template no MANIFEST; `shared/contract_version.json`; `planos/02-mapspec-contrato.md` atualizado; testes antigos de v2 continuam passando pela migração.
- [ ] **W1-13** `tests/test_modo_servidor.py` (fronteira: sem keyring, sem APPDATA, sem py2.7).

### W2 — servidor

- [ ] **W2-01** `ponte/worker.py` (spawn, leitura, timeouts, morte, redação de stderr).
- [ ] **W2-02** `ponte/pool.py` (teto, ociosidade, fila de 1 turno por projeto, desligamento).
- [ ] **W2-03** `ponte/allowlist.py` + `test_allowlist.py`.
- [ ] **W2-04** `ponte/fake_nucleo.py` + 3 roteiros iniciais: `indexar_ok`, `dinamica_ok`, `dinamica_falha_hard`.
- [ ] **W2-05** Registro de versão no banco ao fim de geração.
- [ ] **W2-06** Teste de integração com o **núcleo real** (marcado `@pytest.mark.nucleo_real`, roda no server e no CI Linux que já instala o núcleo): abrir o `imovel_ficticio.zip`, `mapspec.validar`, `quantitativos.calcular`.

## Critérios de aceite

- [ ] Matar o worker com `kill -9` no meio de um job: o navegador recebe `worker.estado caido` e `nucleo.res {ok:false, erro:{codigo:"SV-221"}}`; a próxima mensagem sobe um worker novo e funciona.
- [ ] 7 projetos abertos com `MF_MAX_WORKERS=6`: o sétimo encerra o mais ocioso e sobe; nenhum job em curso é morto.
- [ ] 3 gerações simultâneas com `MF_MAX_JOBS=2`: a terceira mostra "aguardando vaga" e começa quando uma termina; o palco dela fica em espera (sem animação falsa).
- [ ] `grep -rn "keyring" ` não é atingido em execução de modo servidor (teste com `monkeypatch` que explode ao importar `keyring`).
- [ ] `stderr` de worker com um CPF fictício injetado aparece redigido no log.
- [ ] O desktop continua igual: `pytest` do núcleo inteiro verde sem `MAPASFACIL_MODO`.

## Fora de escopo

- Workers em outra máquina (por exemplo, o Windows com ArcMap) — se um dia for preciso, é um
  `Worker` remoto pela tailnet com o mesmo protocolo; não na Fase 3.
- Afinidade de CPU/cgroups.

## Anti-padrões

- Importar `mapasfacil_nucleo.agente`/`motores` dentro do processo do servidor (AW-01).
- Herdar `os.environ` inteiro no worker.
- Repassar `params` do navegador direto para o núcleo (AW-02) — cada rota monta os `params`.
- `print` no núcleo fora do protocolo (polui o stdout; o CI já pegou isso com o deprecation do `fitz`).
