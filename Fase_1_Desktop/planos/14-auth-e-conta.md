# F1-14 — Conta e autenticação do app desktop

## Objetivo

O app exige **conta local** antes de gerar mapas. A pessoa **cria conta com e-mail e senha**; os
dados ficam **só neste PC**, num banco SQLite do app. **Não há login Google**, OAuth, site de
login nem backend de identidade na v1. Depois de autenticada, a conta tem **acesso ilimitado**
(D18): sem quota, paywall, rate limit de produto ou feature flag de cobrança. A conta existe para
identificar quem usa o PC e amarrar histórico/`conta_id`, não para cobrar nem sincronizar nuvem.

## Estado atual vs alvo

| Item | Atual | Alvo |
|---|---|---|
| Fluxo de login no app | **feito** — `tela-login` criar/entrar | criar conta / entrar com e-mail + senha na `tela-login` |
| Provedor Google / OAuth / PKCE | **descartado** | **fora da v1** (D10 revisada 2026-07-26) |
| Backend de identidade / site | **ausente** e **não bloqueia** M5 | Fase 2 opcional (espelho/nuvem) — [F2-05](../../Fase_2_Site/planos/05-auth-e-memoria.md) |
| Armazenamento da conta | **feito** | SQLite local `%APPDATA%\MapasFacil\contas\contas.sqlite` |
| Hash de senha | **feito** (Argon2id) | Argon2id (ou equivalente forte); **nunca** senha em claro |
| Gate de sessão no núcleo | **feito** | `sessao.definir` + `AUTH-030` em `mapa.gerar` (e irmãos) |
| Códigos `AUTH-xxx` | **feitos** nos handlers | definidos aqui e em [F1-01](01-arquitetura.md#códigos-de-erro) |

## Dependências

| Precisa de | Estado | Onde |
|---|---|---|
| M3 — Shell Electron (janela, main, IPC) | **fechado** | [F1-02](02-ui-chat-e-workspace.md) |
| SQLite / padrão de banco local | **feito** (padrão M6) | [F1-17](17-persistencia-de-conversas.md) |
| F2-05 — backend de identidade | **não é dependência** do M5 | [F2-05](../../Fase_2_Site/planos/05-auth-e-memoria.md) — adiado |

**Revisão D10 (2026-07-26):** o dono do produto removeu Google + servidor de identidade como
pré-requisito da Fase 1. M5 fecha **inteiro no desktop**, offline, sem tunnel e sem Fase 2.

## Decisões que fecham este plano

| # | Decisão | Alternativa descartada |
|---|---|---|
| **D10** *(revisada 2026-07-26)* | Login obrigatório com **e-mail + senha**, conta **local** em SQLite neste PC. Sem Google, sem OAuth, sem backend de identidade na v1 | Google via site + F2-05 bloqueante; Firebase/Clerk/Auth0 |
| **D11** *(revisada)* | Sem sessão local válida, `mapa.gerar` (e irmãos) → `AUTH-030`; modo leitura liberado. Sessão **não depende de rede** | token JWT 12 h + refresh remoto; carência offline artificial |
| **D12** *(revisada)* | **Sem** porta HTTP / loopback OAuth no PC do usuário para login. Senha só no main/núcleo; renderer nunca vê hash nem senha | PKCE + loopback `127.0.0.1` (RFC 8252) como fluxo primário |
| D18 | v1 autenticada é **ilimitada** | quota por conta, paywall, trial |

### D11 em detalhe — o que "sessão válida" significa

`sessão válida` = existe conta local e um login bem-sucedido nesta instalação, com sessão ativa
em memória (e, se “lembrar neste PC”, reaberta no boot a partir do SQLite **sem** pedir senha de
novo até “Sair”).

- Offline → o app funciona **inteiro** com sessão local (não há servidor para consultar).
- Sem conta / desconectado / senha errada → `mapa.gerar`, `galeria.montar_mapspec`, `chat.enviar`
  e `quantitativos.exportar_xlsx` recusam com `AUTH-030`. Continuam permitidos: abrir pasta,
  inspecionar shapefile, ler recibo, abrir e ler conversas, ver mapas já gerados.
- “Sair” (D14) **não apaga** chats; “Sair e esquecer este PC” apaga sessão + pode apagar
  `contas.sqlite` / `chats.sqlite` / `config.json` com confirmação digitada (`APAGAR`).

**Honestidade sobre o gate:** é de produto, não de segurança contra o dono da máquina. Quem
controla o Windows consegue burlá-lo. Não endureça o gate; endureça `fsguard` e o hash da senha.

## Contratos

### Banco local `contas.sqlite`

Caminho: `%APPDATA%\MapasFacil\contas\contas.sqlite` (Linux/dev: sob `MAPASFACIL_DADOS` /
userData do Electron — mesmo padrão de `chats.sqlite`).

```sql
CREATE TABLE contas (
  id              TEXT PRIMARY KEY,           -- ULID
  email           TEXT NOT NULL COLLATE NOCASE UNIQUE,
  nome            TEXT,
  senha_hash      TEXT NOT NULL,              -- Argon2id (PHC string); NUNCA texto claro
  criado_em       TEXT NOT NULL,              -- ISO-8601 Z
  ultimo_login_em TEXT,
  ativa           INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE sessoes_locais (
  id              TEXT PRIMARY KEY,           -- ULID opaco
  conta_id        TEXT NOT NULL REFERENCES contas(id) ON DELETE CASCADE,
  criada_em       TEXT NOT NULL,
  expira_em       TEXT,                       -- NULL = até “Sair”; senão ISO-8601 Z
  lembrar_neste_pc INTEGER NOT NULL DEFAULT 1
);
```

Regras:

- E-mail normalizado: trim + minúsculas antes de gravar/buscar.
- Senha mínima: **8 caracteres**; recusar senha igual ao e-mail.
- `senha_hash` **nunca** sai do processo que autentica (núcleo ou main). Renderer recebe só
  `{id, email, nome}`.
- Uma instalação pode ter várias contas; só **uma sessão ativa** por vez.
- Sem tabela de plano/quota/consumo (D18 / AP-05).

### Métodos NDJSON (núcleo)

| Método | Params | Retorno | Nota |
|---|---|---|---|
| `conta.criar` | `{email, senha, nome?}` | `{conta:{id,email,nome}, sessao:{estado:"conectado",…}}` | falha se e-mail já existe (`AUTH-070`) |
| `conta.entrar` | `{email, senha, lembrar_neste_pc?}` | idem | senha errada → `AUTH-002` (mensagem genérica) |
| `conta.sair` | `{esquecer_este_pc?: boolean}` | `{ok:true}` | ver D14 |
| `conta.estado` | `{}` | `{estado, conta?}` | leitura |
| `sessao.definir` | `{estado, conta_id?, expira_em?}` | `{ok:true}` | uso interno / main; **sem senha** |
| `sessao.estado` | `{}` | `{estado, conta_id?, expira_em?}` | leitura |

Gate no núcleo: `mapa.gerar`, `galeria.montar_mapspec`, `chat.enviar` e
`quantitativos.exportar_xlsx` exigem `estado == "conectado"`. Sem sessão → `AUTH-030`.
`workspace.*`, `car.ler_recibo`, `mapspec.validar`, `zip.*`, `doctor.rodar`,
`chat.listar_conversas` e `chat.abrir_conversa` **não** têm gate.

### IPC (main ↔ renderer)

| Canal | Direção | Payload |
|---|---|---|
| `auth:criar` | renderer → main | `{email, senha, nome?}` — main encaminha ao núcleo; **não loga senha** |
| `auth:entrar` | renderer → main | `{email, senha, lembrar_neste_pc?}` |
| `auth:sair` | renderer → main | `{esquecer_este_pc?: boolean}` |
| `auth:estado` | renderer → main (invoke) | `{}` → `{estado, conta?}` |
| `auth:mudou` | main → renderer (evento) | `{estado, conta?, erro?}` |

`estado` ∈ `desconectado` \| `conectando` \| `conectado`.

(Os estados `offline` / `expirado` do desenho antigo com JWT remoto **não se aplicam** à conta
local; se a sessão “lembrar” expirar, volta a `desconectado`.)

### Códigos de erro `AUTH-xxx`

| Código | Significado | O que a UI faz |
|---|---|---|
| `AUTH-001` | Nenhuma conta / nunca logou neste PC | tela de boas-vindas: criar conta ou entrar |
| `AUTH-002` | E-mail ou senha incorretos | mensagem genérica (não revelar qual campo falhou) |
| `AUTH-003` | Senha fraca / não atende política | explica o mínimo (8 caracteres, ≠ e-mail) |
| `AUTH-030` | Operação exige sessão e não há | bloqueia a ação, oferece “Entrar” |
| `AUTH-050` | Falha ao abrir/gravar `contas.sqlite` | erro com instrução; sem fallback inseguro |
| `AUTH-070` | E-mail já cadastrado neste PC | oferece “Entrar” em vez de criar |
| `AUTH-071` | Conta desativada localmente | mensagem clara |

Códigos antigos de OAuth (`AUTH-010`…`AUTH-022`, `AUTH-040`, `AUTH-041`, `AUTH-060`) ficam
**reservados / obsoletos na v1 local** — não implementar fluxo que os exija. Se a Fase 2 trouxer
conta na nuvem no futuro, aí sim podem voltar num plano novo — não neste.

Todos os códigos ativos entram na tabela de [F1-01](01-arquitetura.md#códigos-de-erro).

## Estados da UI

| Estado | Primeira viewport | Resto do app |
|---|---|---|
| `desconectado` | `tela-login`: criar conta **ou** entrar (e-mail + senha); nota “acesso completo, sem limites · dados só neste PC” | inacessível para geração |
| `conectando` | mesma tela, botão em espera | inacessível |
| `conectado` | app normal | tudo liberado |

A tela segue [F1-16](16-design-system-dark.md): fundo `--mf-bg`, marca `--mf-fs-hero`, sem
ilustração genérica, **sem** botão “Entrar com Google”.

## Tarefas agentáveis

### Núcleo

- [x] `nucleo/mapasfacil_nucleo/contas/` — esquema SQL, repositório, hash Argon2id, migração `001`
- [x] Métodos `conta.criar` / `conta.entrar` / `conta.sair` / `conta.estado`
- [x] `nucleo/mapasfacil_nucleo/sessao.py` — estado em memória + `sessao.definir` / `sessao.estado`
- [x] Gate `AUTH-030` em `mapa.gerar`, `galeria.montar_mapspec`, `chat.enviar`, `quantitativos.exportar_xlsx`
- [x] Família `AUTH-` via `ErroNucleo` nos handlers
- [x] No boot: se existe `sessoes_locais` com `lembrar_neste_pc` e não expirada → restaura sessão

### App — main + renderer

- [x] `conta.*` via IPC `nucleo:chamar` (`estado/auth.ts`); senha não fica no store
- [x] `app/src/telas/Login.tsx` — id `tela-login` (criar + entrar)
- [x] `app/src/estado/auth.ts` — store com `estado`, `conta` (sem senha)
- [x] Guarda de rota: sem sessão → `tela-login` (`App.tsx`)

### Testes

- [x] `pytest nucleo/tests/test_conta_local.py`
- [x] `pytest nucleo/tests/test_sessao.py`
- [x] Assert: arquivo `contas.sqlite` **não** contém a senha em claro
- [x] `app/tests/login.test.tsx`
## Critérios de aceite

- [ ] Criar conta → fechar app → reabrir com “lembrar” → `estado:"conectado"` sem digitar de novo
- [ ] Entrar com senha errada → `AUTH-002`; hash no banco inalterado
- [ ] `mapa.gerar` sem sessão → `AUTH-030`; `workspace.abrir` funciona
- [ ] Sem rede (airplane mode) → criar/entrar/gerar funcionam
- [ ] Nenhum botão/fluxo Google, OAuth, PKCE ou `openExternal` para login
- [ ] `grep -rn "quota\|rate_limit\|paywall\|trial" app/ nucleo/` sem restrição de produto
- [ ] Logout sem “esquecer” preserva `chats.sqlite` (D14)

## Fora de escopo

- Google, Apple, Microsoft, magic link, SSO, SAML, organizações, times, papéis.
- Backend / site / tunnel de identidade (Fase 2; **não bloqueia** este plano).
- Sincronizar conta ou conversas para a nuvem (D20).
- Recuperação de senha por e-mail remoto (v1: só neste PC; “esqueci” = criar outra conta local
  ou reset manual do banco — documentar na UI com honestidade).
- Multi-sessão simultânea de várias contas na mesma janela.
- Cobrança, planos, trial, quota.

## Anti-padrões

| Não faça | Por quê |
|---|---|
| Guardar senha em claro ou em `config.json` | comprometimento trivial; use Argon2id no SQLite |
| Mandar senha/`senha_hash` ao renderer via IPC | renderer comprometido = conta comprometida |
| Logar e-mail+senha juntos ou senha em qualquer log | AP-03 / privacidade |
| Reintroduzir Google/OAuth “porque o plano antigo dizia” | D10 revisada; este arquivo manda |
| Criar dependência de F2-05 / rede para o M5 | M5 é 100% local |
| Usar `plano` para liberar/bloquear função | AP-05 / D18 |
| Bloquear leitura do workspace sem sessão | técnico precisa inspecionar pasta mesmo desconectado |
| Porta HTTP local “só para auth” | D12 / AP-14 — auth é NDJSON + IPC, sem socket |
