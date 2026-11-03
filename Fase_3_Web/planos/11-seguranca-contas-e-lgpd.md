# W-11 — Segurança, contas e LGPD

## Objetivo

O site fica na internet e guarda dado de imóvel rural (geometria, CAR, nome de propriedade) e
chaves do escritório. Este plano fixa contas, sessões, permissões, segredos, tratamento de dado
pessoal e o modelo de ameaças — e conecta com o que já foi decidido em
[`../../planos/05-seguranca-e-segredos.md`](../../planos/05-seguranca-e-segredos.md) e com o
incidente de 15–16/10/2026 da frota.

## Estado atual vs alvo

| Item | Hoje | Alvo |
|---|---|---|
| Contas | locais por PC (`contas/`, Argon2id, `contas.sqlite`) | no servidor, **cadastro aberto** sem confirmação de e-mail; admin bloqueia (D27) |
| Sessão | IPC local | cookie HttpOnly + CSRF |
| Segredos | keyring do Windows / `secrets.local.json` em dev | `$MF_RAIZ/segredos/servidor.env` (600), injetado nos workers |
| CPF | descartado pelo parser do recibo (AP-09) | idem + varredura automática em banco/log/evento |
| Link público | `analises.cursar.space` sem senha (decisão de 2026-07-29) | a Fase 3 **não** publica nada sem login (P6) |

## Dependências

W3 (rotas e banco). Revisão final antes do W12.

## Contratos

### Contas

```sql
CREATE TABLE usuarios (
  id            TEXT PRIMARY KEY,
  email         TEXT NOT NULL UNIQUE COLLATE NOCASE,
  nome          TEXT NOT NULL,
  papel         TEXT NOT NULL CHECK (papel IN ('usuario','admin')),
  senha_hash    TEXT NOT NULL,          -- Argon2id (mapasfacil_nucleo.contas.senha)
  trocar_senha  INTEGER NOT NULL DEFAULT 1,
  ativo         INTEGER NOT NULL DEFAULT 1,
  criado_em     TEXT NOT NULL,
  ultimo_acesso TEXT
);
CREATE TABLE sessoes (
  id_hash     TEXT PRIMARY KEY,         -- sha256 do token (o token em si só existe no cookie)
  usuario_id  TEXT NOT NULL REFERENCES usuarios(id),
  csrf        TEXT NOT NULL,
  criada_em   TEXT NOT NULL,
  expira_em   TEXT NOT NULL,            -- deslizante: +30 dias a cada uso, teto 90 dias da criação
  ip_prefixo  TEXT,                     -- /24 (IPv4) ou /48 (IPv6), para a tela "sessões ativas"
  agente      TEXT                      -- user-agent truncado em 120
);
CREATE TABLE auditoria (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  em         TEXT NOT NULL,
  usuario_id TEXT,
  acao       TEXT NOT NULL,             -- cadastrou, entrou, falhou_login, saiu, criou_usuario, bloqueou, desbloqueou, redefiniu_senha, abriu_projeto_alheio, apagou_projeto, baixou_pacote
  alvo       TEXT,                      -- id do projeto/usuário
  detalhe    TEXT                       -- JSON curto, sem dado pessoal
);
```

- Criação (D27, P2): **cadastro aberto** em `POST /auth/cadastrar` — nome, e-mail, senha; sem
  confirmação de e-mail; a conta nasce `ativo=1`, `trocar_senha=0`, `papel='usuario'` e já sai
  com sessão. O admin também cria pela CLI `python -m mapasfacil_servidor conta criar --email …
  --nome … [--admin]` (senha temporária impressa uma vez, `trocar_senha=1`) e por
  `POST /admin/usuarios`. Admin inicial: no boot, a conta cujo e-mail é `MF_ADMIN_EMAIL` (só no
  `servidor.env`, nunca no repo público) vira `admin`.
- E-mail: normalizado (minúsculas, sem espaços), validado por forma (`SV-013`); único (`SV-012`).
- Senha: mínimo 10 caracteres, recusa as 10.000 mais comuns (lista embarcada em
  `auth/senhas_comuns.txt`), recusa igual ao e-mail (`SV-010`).
- **Bloquear** (`ativo=0`, pela tela de admin ou CLI `conta bloquear`) apaga todas as sessões da
  conta na hora; login de conta bloqueada → `403 SV-003`; os projetos dela ficam intactos.
- Única trava contra abuso do cadastro: o bloqueio pelo admin (decisão do Álvaro em 03/11 — sem
  captcha, sem confirmação de e-mail, sem fila por conta). O limitador de tentativas de **login**
  continua: ele protege a senha das contas, não limita uso.

### Sessão e CSRF

- Token: `secrets.token_urlsafe(32)`; cookie `mf_sessao`, `HttpOnly; Secure; SameSite=Lax;
  Path=/`; no banco só o `sha256`.
- CSRF: valor por sessão, devolvido em `GET /auth/eu`, exigido em `X-MF-CSRF` nas mutações;
  comparação em tempo constante.
- `Origin`/`Referer` das mutações tem de ser `MF_URL_PUBLICA` (`403 SV-021` senão).
- CORS: fechado (o SPA é servido pelo mesmo host; nenhuma origem externa).
- Anti-abuso de login (não é quota, D18): 10 falhas por e-mail ou por IP em 15 min → `429
  SV-005` com `tentar_em_s`; contador em memória + tabela `auditoria`.

### Permissões

| Recurso | Dono | Outro usuário | Admin |
|---|---|---|---|
| Projeto, mensagens, versões, arquivos, eventos | tudo | `404 SV-031` | leitura (P4), registrada em `auditoria` como `abriu_projeto_alheio` |
| Upload | dono | `404` | — |
| Usuários, auditoria, saúde | — | `403 SV-032` | tudo |

Verificação de dono em **toda** rota de projeto, por dependência FastAPI única
(`exige_projeto(id, modo="leitura"|"escrita")`). Teste `test_permissoes.py` percorre a lista de
rotas do app (introspecção do router) e falha se alguma rota com `{id}` não usa a dependência.

### Segredos

| Segredo | Onde | Quem lê |
|---|---|---|
| Chave do Mapas Fácil no 9Router, SEMA `authkey`, Planet (DeepSeek só se usar o provedor alternativo) | `$MF_RAIZ/segredos/servidor.env`, dono `server`, modo `0600` | o servidor no boot; repassa só para o env do worker |
| Token do túnel Cloudflare do app | arquivo de credencial do `cloudflared` (fora do repo), `0600` | `cloudflared` |

- **Novos**: chaves criadas para este serviço depois do incidente de 15–16/10/2026; nunca copiar
  `.env` de outro projeto nem reaproveitar token antigo (AW-08). O vault guarda só ponteiros
  (`01-infra/onde-vivem-os-segredos.md`), nunca valores.
- O boot recusa subir se `servidor.env` tiver permissão mais aberta que `0600` (`SV-000`).
- O `.mxd` entregue passa por `chaves_mxd.py verificar` (H18); o `.mxd` de **entrada** tem a
  chave removida antes de o núcleo ler (W-02 §Verificação).
- Logs: filtro de redação no servidor e no stderr dos workers: `sk-[A-Za-z0-9]{20,}`,
  `authkey=[^&\s]+`, `api_key`, CPF (`\d{3}\.?\d{3}\.?\d{3}-?\d{2}`), CNPJ.

### LGPD

| Dado | Pessoal? | Tratamento |
|---|---|---|
| E-mail e nome do usuário | sim | finalidade: acesso; apagado ao excluir conta |
| CPF/CNPJ do proprietário (no recibo) | sim | **nunca persistido**: o parser descarta; o PDF do recibo fica só dentro de `entrada.zip`/`entrada/` do projeto, que só o dono acessa |
| Nome do imóvel, CAR, geometria | é dado do cliente do escritório (pode identificar pessoa) | fica no projeto; não vai para log técnico (log usa `projeto_id`), não vai ao LLM em WKT (AP-06) |
| Conteúdo do chat | pode conter | fica no `chats.sqlite` do projeto; redator do núcleo (`conversas/redator.py`) roda antes de gravar |

- Exclusão: projeto na lixeira 30 dias (P3) → `limpar-lixeira` apaga a pasta inteira e as linhas.
  Excluir usuário: projetos dele vão para a lixeira do admin (não somem sem decisão).
- Backup ([W-12](12-deploy-servidor-e-operacao.md)) cifrado e com a mesma retenção.
- Varredura automática `python -m mapasfacil_servidor varrer-pii` (diária, timer): procura CPF
  em `mapasfacil.sqlite`, `eventos.ndjson` e logs. Achou ⇒ alerta no log + saída ≠ 0 (o timer
  registra falha); nunca imprime o valor achado, só arquivo e linha.

### Modelo de ameaças (o que cada controle cobre)

| # | Ameaça | Controle |
|---|---|---|
| T1 | Senha vazada / força bruta | Argon2id, anti-abuso de login, troca obrigatória, sessão revogável |
| T2 | CSRF a partir de outro site | SameSite=Lax + token CSRF + checagem de `Origin` |
| T3 | Usuário vendo projeto alheio (IDOR) | dependência única de dono + teste de introspecção |
| T4 | ZIP malicioso (zip-slip, bomba, symlink) | `importacao/extrair.py` ([W-02](02-projeto-folha-e-upload.md)) |
| T5 | Prompt injection no conteúdo do `.zip` (nome de camada, texto do recibo pedindo "ignore as regras") | a IA só edita `MapSpec` validado por schema (AP-02); tools devolvem resumo tipado; nenhuma tool executa comando, abre URL arbitrária ou escreve fora de `PASTAS_ESCRITA` |
| T6 | Path traversal em download | allowlist de prefixos + normalização + `..` recusado (`SV-401/402`) |
| T7 | Vazamento de chave em `.mxd` entregue | H18 |
| T8 | Esgotamento do server (muitos jobs/uploads) | `MF_MAX_WORKERS`, `MF_MAX_JOBS`, limites de upload, timeout por requisição |
| T9 | Comprometimento de outro serviço da frota alcançando este | backend só em `127.0.0.1`; usuário de sistema `server` sem sudo para o serviço; segredos próprios; nada compartilhado com outros `.env` |
| T11 | Estranho cria conta (cadastro aberto) e usa o servidor e a IA | **risco aceito pelo Álvaro em 03/11**: o admin bloqueia a conta; a chave do 9Router é dedicada ao Mapas Fácil (uso visível e revogável sem afetar a frota); `MF_MAX_JOBS` limita o que roda junto; auditoria registra `cadastrou` e `entrou` |
| T10 | Dependência maliciosa no build (supply chain — houve commits maliciosos no GeoForest em 16/10) | versões exatas travadas (`package-lock`/`pnpm-lock`, `requirements` com hash), **sem** auto-pull no server, deploy só por comando manual do Álvaro ou do agente com o commit conferido ([W-12](12-deploy-servidor-e-operacao.md)) |

## Tarefas agentáveis

- [ ] **W3-20** Tabelas `usuarios`, `sessoes`, `auditoria` na migração 0001.
- [ ] **W3-21** `auth/senhas.py` (reuso do núcleo + lista comum), `auth/sessoes.py`, `auth/csrf.py`, `auth/limitador.py`.
- [ ] **W3-22** Dependências `exige_sessao`, `exige_admin`, `exige_projeto`; `test_permissoes.py` por introspecção.
- [ ] **W3-23** CLI `conta criar|listar|bloquear|desbloquear|redefinir`.
- [ ] **W3-25** `POST /auth/cadastrar` (D27) + `SV-003/012/013` + promoção do `MF_ADMIN_EMAIL` no boot.
- [ ] **W3-24** Redação de logs (servidor e workers) + teste.
- [ ] **W12-20** `varrer-pii` + timer.
- [ ] **W12-21** Checagem de permissão do `servidor.env` no boot.
- [ ] **W12-22** Revisão final: rodar `/security-review` (ou revisão equivalente) sobre `Fase_3_Web/servidor` antes do piloto.

## Critérios de aceite

- [ ] `test_permissoes.py`: toda rota com `{id}` protegida; usuário B recebe 404 nos projetos de A; admin lê e a auditoria registra.
- [ ] Mutação sem `X-MF-CSRF` → 403; com `Origin` estranho → 403.
- [ ] 11ª tentativa de login errado em 15 min → 429.
- [ ] Cadastro novo entra direto; o mesmo e-mail de novo → 409 `SV-012`; conta bloqueada pelo admin perde a sessão aberta na hora e o login devolve 403 `SV-003`.
- [ ] Importar o `imovel_ficticio.zip` (que tem CPF fictício no recibo) e rodar `varrer-pii` → zero achados.
- [ ] `servidor.env` com `0644` → o servidor não sobe e diz por quê.

## Fora de escopo

- 2FA (pode vir depois; o desenho de sessão não impede).
- SSO/OAuth (D27).
- Criptografia em repouso do HD inteiro (é decisão de infraestrutura do server, não do app).

## Anti-padrões

- Responder 403 para projeto alheio (confirma que existe).
- Logar corpo de requisição.
- Guardar senha temporária no banco em claro "para mostrar depois".


### Tarjamento prévio de imagem para visão de IA (W11-13 / D42)
Antes de qualquer imagem rasterizada da folha ser despachada para o provedor de visão de IA (Gemini via 9Router), a função `tarjar_imagem_para_visao` detecta e aplica tarjas pretas opacas cobrindo:
- Todo número com padrão de CPF (`\d{3}\.\d{3}\.\d{3}-\d{2}` ou 11 dígitos sequenciais);
- Todo número com padrão de CNPJ;
- Nomes de proprietários extraídos do recibo CAR.
Nenhum dado pessoal é transmitido para servidores externos de IA.
