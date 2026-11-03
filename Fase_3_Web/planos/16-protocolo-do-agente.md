# W-16 — Protocolo do agente implementador

Você é um agente de codificação trabalhando no Windows do Álvaro (`C:\GIS\mapas-facil`), com
acesso ao server-desktop por `ssh sd` e à tailnet. Este arquivo diz **como** trabalhar; os
outros planos dizem **o quê**.

## Antes de começar qualquer sessão

1. Leia [`../../AGENT_BRIEF.md`](../../AGENT_BRIEF.md), [W-00](00-visao-e-decisoes.md),
   [W-01](01-arquitetura.md), [W-14](14-roadmap-marcos.md) e o plano do marco. Se o marco mexe em
   mapa (W7, W9, W10, W11), leia também [W-17](17-conhecimento-das-skills.md) — as lições das skills
   de MXD do Hermes e do Claude já dizem onde o ArcMap e os dados do SIMCAR armam ciladas.
2. Leia o estado da frota no **Segundo Cérebro** antes de assumir caminho, porta ou URL:
   `ssh sd 'cat /home/server/Downloads/Segundo-Cerebro/INDEX.md'` e
   `ssh sd 'cat /home/server/Downloads/Segundo-Cerebro/02-projetos/mapas-facil.md'`
   (+ `01-infra/portas.md`, `01-infra/servidor.md` quando for mexer no server).
3. `git status` e `git log -5`. Se houver mudança não commitada que **não é sua**, não toque nem
   inclua no seu commit (outro agente pode estar no meio de algo).
4. Rode as verificações rápidas de realidade:
   ```bash
   cd Fase_1_Desktop/nucleo && pytest -q            # núcleo verde antes de você mexer
   cd Fase_1_Desktop/app && pnpm test               # desktop verde
   ```
5. Confira no [W-15](15-checklist-implementacao.md) o que já está marcado e se o marco anterior
   fechou. Não comece marco com dependência aberta.

## Durante

- **Um marco por vez**, uma tarefa por commit sempre que possível. Commit pequeno, mensagem no
  padrão do repo (`feat(servidor): …`, `fix(nucleo): …`, `docs(fase3): …`, `test(web): …`).
- Branch: siga o que o Álvaro pedir. Sem pedido, a convenção do repo é commit direto no `main`
  (`AGENT_BRIEF.md` §Convenções) — mas **não** faça push sem ordem explícita.
- Identificadores, campos JSON, métodos e mensagens em **português** (convenção do repo); IDs ULID;
  datas ISO UTC com `Z`; hectare com 4 casas.
- Toda regra cartográfica nova vai para o **núcleo**, nunca para o servidor ou para a web (D23).
- Todo evento novo entra no vocabulário (`protocolo.py::EVENTOS`) **e** no plano no mesmo commit.
- Todo código de erro novo segue a tabela de prefixos de [W-01](01-arquitetura.md).
- Ao copiar componente do desktop, cabeçalho de proveniência com o hash.
- Se um plano estiver errado (arquivo que não existe, contrato que não fecha), **corrija o plano
  no mesmo commit** e explique na mensagem. Plano que mente é pior que plano nenhum (AP-15).
- Se precisar de algo que exige `sudo`, credencial, login na Cloudflare ou decisão de produto:
  **pare e pergunte** ao Álvaro com o comando exato/as opções. Nunca peça nem leia senha; nunca
  abra `servidor.env`/`auth.json` para ler valor.

## Proibições absolutas

| Não | Por quê |
|---|---|
| Commitar segredo, `secrets.local.json`, `servidor.env`, `.mxd` com `authkey` | AP-03 — rode `python ferramentas/chaves_mxd.py verificar` antes de todo commit que toque `.mxd` |
| Versionar recibo do CAR, shapefile de cliente, PDF com CPF | AP-09, D35 |
| Editar `.mxd` de cliente ou template no lugar | regra de ouro do vault (`mxd-formato-binario`) |
| Descompilar DLL da Esri sem autorização (P10), ou pôr no repo/vault código, pseudocódigo ou dump vindo do ArcMap | licença do ArcMap + repo público; o REA no Windows é para **observar** o ArcMap (Frida nas APIs do Windows, captura de processo) — ver [W-08](08-motor-mxd-binario.md) §Laboratório |
| Rodar ArcPy/ArcMap no servidor | D24 |
| Animação sem evento real | AP-07 |
| Tocar túnel, porta ou unit de outro serviço da frota | vault `01-infra/*` |
| Religar serviço da frota mascarado no incidente de 15–16/10 | vault `01-infra/incidente-invasao-frota-2026-10-15.md` |
| Mandar mensagem (WhatsApp, e-mail) em nome do Álvaro | regra global do Álvaro |
| Marcar `[x]` sem o teste do critério de aceite verde | AP-15 |
| Escrever estimativa de prazo | AP-13 |

## Ao fechar uma tarefa

1. Testes do critério de aceite verdes (cole a saída resumida no relatório).
2. `[x]` no [W-15](15-checklist-implementacao.md) + linha da gap analysis se mudou de estado.
3. Se fechou um marco: tabela de estado no [`../README.md`](../README.md) e no `AGENT_BRIEF.md`.

## Ao fechar um marco — relatório de rodada

Crie `docs/fase3-rodada-AAAA-MM-DD-<marco>.md`:

```markdown
# Fase 3 — <marco> — AAAA-MM-DD

## Feito
- W?-?? <o quê> — commit <hash>

## Verificado (comandos e resultado)
- `pytest …` → N passed
- …

## Não feito / pendente (com motivo)
- …

## Decisões tomadas (e quem decidiu)
- …

## Riscos e o que o próximo agente precisa saber
- …
```

Depois, **Segundo Cérebro** (regra do Álvaro: "se valeu gravar na memória do agente, vale
refletir no `.md` do projeto"): atualize `02-projetos/mapas-facil.md` com o estado do marco, pelo
protocolo do vault:

```bash
ssh sd 'cd /home/server/Downloads/Segundo-Cerebro && VAULT_AUTOR=<seu nome> ./ferramentas/lock.sh 02-projetos/mapas-facil.md'
# patch cirúrgico (nunca reescrever o arquivo inteiro), com "(autor: <nome> | AAAA-MM-DD)"
ssh sd 'cd /home/server/Downloads/Segundo-Cerebro && VAULT_AUTOR=<seu nome> ./ferramentas/lock.sh commit "mapas-facil: fase 3 <marco>"'
```

Entrada no topo do `06-changelog.md` quando o marco muda algo visível (deploy, URL, porta).
Nunca force lock ativo de outro agente.

## Quando parar e perguntar (lista fechada)

- O que você encontrou no código ou nos dados **contraria** uma das decisões já tomadas (D22–D39,
  P1–P10 em [W-00](00-visao-e-decisoes.md) §Decisões tomadas). As decisões em si **não** se
  perguntam de novo.
- Um spike do W10 falhou e o plano B muda o que o usuário recebe.
- Um check novo reprova mapas do acervo que o escritório considera corretos (pode ser o check
  que está errado).
- O preflight acusou algo que precisa de `sudo` ou de conta externa.
- Qualquer coisa que exija apagar dado no server.

## Como saber que a Fase 3 acabou

[W-14](14-roadmap-marcos.md) §Definição de "pronto".
