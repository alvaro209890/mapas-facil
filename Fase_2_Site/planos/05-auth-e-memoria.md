# F2-05 — Identidade, auth e memória de projeto

> **Atenção, agente:** este é o **único documento da Fase 2 que a Fase 1 exige**. O app desktop
> não abre sem login (D10), e o serviço de identidade descrito aqui é dependência bloqueante do
> marco M5 de [F1-12](../../Fase_1_Desktop/planos/12-roadmap.md). Tudo o mais nesta pasta continua
> "depois da Fase 1 validada".

## Objetivo

Especificar o serviço de identidade que autentica o app desktop com Google e emite os tokens de
sessão, e — separadamente, para depois — a memória de projeto que dá ao site o que o desktop não
tem sozinho. As duas metades têm prioridades diferentes: **identidade é agora; memória é depois.**

## Estado atual vs alvo

| Item | Atual | Alvo |
|---|---|---|
| `Fase_2_Site/backend/` | só `README.md` — **sem código** | FastAPI com `/auth/*` e `/health` |
| `Fase_2_Site/web/` | só `README.md` — **sem código** | site com `/login` |
| Tunnel `mapasfacil-api.cursar.space` | **não criado** | tunnel dedicado, systemd |
| Cliente OAuth Google | **não criado** | Web application, com a redirect URI abaixo |
| Postgres | **não provisionado** | 3 tabelas de identidade na v1 |
| Memória de projeto | ausente | depois do M11 |

## Dependências

| Precisa de | Estado |
|---|---|
| Este PC com Cloudflare Tunnel funcionando (outros sistemas já usam) | disponível |
| Postgres local | a provisionar |
| Projeto no Google Cloud com OAuth consent screen | a criar |
| [F1-14](../../Fase_1_Desktop/planos/14-auth-e-conta.md) — o lado cliente | ausente |

## Decisões

| # | Decisão | Alternativa descartada |
|---|---|---|
| D10 | Identidade **própria, neste PC**, exposta pelo tunnel dedicado | Firebase Auth; Clerk/Auth0 |
| D12 | Redirect do desktop por loopback `127.0.0.1` (RFC 8252) | `mapasfacil://` como primário |
| D18 | Autenticado = **ilimitado** na v1 | quota, paywall, medição para cobrar |
| D20 | Conversas do desktop são **local-only**; espelho na conta é Fase 2 e opt-in | sync automático |

D10 tem custo assumido: o login depende deste PC e do tunnel estarem no ar. O app tolera o
backend fora do ar enquanto o `access_token` vale (12 h), mas um login **novo** falha com
`AUTH-020`. Se isso se mostrar inaceitável no piloto, a revisão é migrar a identidade para um
provedor gerenciado — não afrouxar o login.

## Contratos — identidade

### Configuração

| Env (systemd, permissão 600) | Uso |
|---|---|
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | OIDC com o Google |
| `JWT_PRIVATE_KEY` / `JWT_PUBLIC_KEY` | assinatura EdDSA (Ed25519) do `access_token` |
| `DATABASE_URL` | Postgres local |
| `SITE_BASE` / `API_BASE` | `https://mapasfacil.cursar.space` / `https://mapasfacil-api.cursar.space` |
| `IP_HASH_SALT` | sal do `ip_hash` |

Redirect URI registrada no Google: **apenas**
`https://mapasfacil-api.cursar.space/auth/google/callback`. O loopback do desktop **não** é
registrado no Google — quem redireciona para o loopback é o nosso backend. É isso que permite ter
um único cliente OAuth para todas as instalações.

### Rotas

| Método | Rota | Auth | Corpo → Resposta |
|---|---|---|---|
| `GET` | `/health` | pública | `{ok:true, versao}` — **a única rota sem auth fora do fluxo OAuth** |
| `GET` | `/auth/desktop/start` | PKCE | `?client_id&state&code_challenge&code_challenge_method=S256&redirect_uri` → 302 para `SITE_BASE/login` |
| `GET` | `/auth/google/callback` | PKCE | `?code&state` → 302 para o `redirect_uri` de loopback com `?code=<code_app>&state` |
| `POST` | `/auth/desktop/token` | PKCE | `{code, code_verifier, client_id}` → `{access_token, refresh_token, expires_in, token_type, conta}` |
| `POST` | `/auth/refresh` | token no corpo | `{refresh_token}` → mesmo formato; **rotaciona** |
| `POST` | `/auth/logout` | Bearer | `{refresh_token}` → `204` |
| `GET` | `/auth/me` | Bearer | → `{id, email, nome, avatar_url, criado_em, plano:"v1_ilimitado"}` |

Validações obrigatórias em `/auth/desktop/start`:

- `redirect_uri` **tem** de casar `^http://127\.0\.0\.1:\d{1,5}/callback$`. Qualquer outra coisa →
  `400`. Sem isso, o serviço vira open redirect.
- `code_challenge_method` tem de ser `S256`. `plain` é rejeitado.
- `client_id` ∈ allowlist (`mapasfacil-desktop`).

### Tokens

| Token | Forma | TTL | Rotação |
|---|---|---|---|
| `code_app` | opaco, 32 bytes aleatórios | **60 s**, uso único | — |
| `access_token` | JWT EdDSA; claims `sub`, `email`, `iat`, `exp`, `iss`, `aud` | **12 h** | — |
| `refresh_token` | opaco, 32 bytes, **hash SHA-256 no banco** | **60 dias** | rotativo: usar invalida o anterior |

Reuso de um `refresh_token` já rotacionado = sinal de vazamento → **revoga toda a família de
sessões daquela conta** e responde `401`. Detecção de replay padrão; implemente desde o começo,
é barato.

O TTL de 12 h do `access_token` é o que define o comportamento offline do app (D11): sem rede e
com token expirado, `mapa.gerar` recusa com `AUTH-030`
([F1-14](../../Fase_1_Desktop/planos/14-auth-e-conta.md)).

### Esquema Postgres (v1 — só identidade)

```sql
CREATE TABLE contas (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  google_sub    TEXT UNIQUE NOT NULL,          -- 'sub' do id_token; NUNCA o email como chave
  email         TEXT NOT NULL,
  nome          TEXT,
  avatar_url    TEXT,
  criado_em     TIMESTAMPTZ NOT NULL DEFAULT now(),
  ultimo_login  TIMESTAMPTZ,
  ativa         BOOLEAN NOT NULL DEFAULT true
);

CREATE TABLE sessoes (
  id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  conta_id           UUID NOT NULL REFERENCES contas(id) ON DELETE CASCADE,
  refresh_hash       TEXT NOT NULL UNIQUE,      -- sha256 do refresh_token
  familia_id         UUID NOT NULL,             -- rotação: mesma família = mesma cadeia
  substituida_por    UUID REFERENCES sessoes(id),
  criada_em          TIMESTAMPTZ NOT NULL DEFAULT now(),
  expira_em          TIMESTAMPTZ NOT NULL,
  revogada_em        TIMESTAMPTZ,
  user_agent         TEXT,
  ip_hash            TEXT                        -- sha256(ip + sal); nunca o IP em claro
);

CREATE TABLE codigos_desktop (
  code_hash      TEXT PRIMARY KEY,               -- sha256 do code_app
  conta_id       UUID NOT NULL REFERENCES contas(id) ON DELETE CASCADE,
  code_challenge TEXT NOT NULL,
  redirect_uri   TEXT NOT NULL,
  state          TEXT NOT NULL,
  criado_em      TIMESTAMPTZ NOT NULL DEFAULT now(),
  expira_em      TIMESTAMPTZ NOT NULL,
  usado_em       TIMESTAMPTZ
);

CREATE INDEX idx_sessoes_conta   ON sessoes(conta_id, revogada_em);
CREATE INDEX idx_sessoes_familia ON sessoes(familia_id);
CREATE INDEX idx_codigos_expira  ON codigos_desktop(expira_em);
```

**`google_sub` é a chave, não o email.** O email pode mudar; o `sub` não. Usar email como chave é
o erro clássico que mistura contas.

Nenhuma tabela de plano, quota ou uso na v1. Se um agente criar `assinaturas`, `limites` ou
`consumo`, está violando D18/AP-05.

### Códigos de erro (espelhados no app)

| HTTP | Código | Situação |
|---|---|---|
| 400 | `AUTH-040` | `state` ausente/divergente, `redirect_uri` inválida, `code_challenge_method` ≠ S256 |
| 400 | `AUTH-041` | `code_app` expirado, já usado, ou `code_verifier` não confere |
| 401 | `AUTH-011` | `refresh_token` inválido, expirado ou revogado (inclui replay) |
| 401 | `AUTH-010` | `access_token` expirado |
| 403 | `AUTH-051` | conta desativada |
| 5xx | `AUTH-021` | erro interno; o app degrada para "offline" se tiver token válido |

## Segurança da superfície

- HTTPS obrigatório (o tunnel termina TLS).
- **Todas** as rotas autenticadas exceto `/health` e as três do fluxo OAuth (protegidas por
  PKCE + `state` + expiração de 60 s).
- CORS restrito a `SITE_BASE`. O app desktop chama `/auth/desktop/token` pelo processo main, não
  por navegador — não precisa estar no CORS.
- Rate limit **de abuso**, não de produto: `/auth/desktop/token` e `/auth/refresh` limitados por
  IP para conter força bruta. Isso **não** contraria D18/AP-05 — AP-05 proíbe limitar
  *funcionalidade de usuário autenticado*, não proteger endpoint de autenticação contra ataque.
- Cabeçalhos: `Content-Security-Policy`, `X-Content-Type-Options`, `Referrer-Policy`,
  `Strict-Transport-Security`.
- Log **sem** token, sem `code`, sem IP em claro. O redator cobre `Authorization`, `Bearer`,
  `refresh_token`, `code`.
- Segredos só em `EnvironmentFile` do systemd com permissão `600`.
- Tunnel **dedicado**: `saldopro-config.yml` e `/etc/cloudflared/config.yml` dos outros sistemas
  ficam **intocados** (D7).

## Memória de projeto (depois do M11 — não implemente agora)

O que o backend guardaria por usuário/projeto, quando a Fase 2 começar de verdade:

| Dado | Persistência | Sensível? |
|---|---|---|
| Metadados do imóvel (nome, CAR, município, área) | Postgres | baixo |
| Histórico de conversas e tool calls | Postgres, **opt-in** (D20) | médio |
| Versões de `MapSpec` | Postgres, append-only | baixo |
| Artefatos PDF/PNG gerados | disco neste PC | médio |
| Shapefiles do cliente | **só com consentimento**; preferência = ficar no desktop | alto |

Regra: se o usuário só usa o site para "mapa por CAR" a partir de dados públicos/SEMA, não é
necessário upload de shape. Upload é opt-in e apagável.

### Relação com a Fase 1

O desktop guarda conversas em `%APPDATA%\MapasFacil\chats\chats.sqlite`
([F1-17](../../Fase_1_Desktop/planos/17-persistencia-de-conversas.md)). A Fase 2 **não substitui**
esse armazenamento local; ofereceria um espelho **opcional**. Na v1 esse espelho **não existe**
(D20) — não há endpoint de upload de conversa, e criar um é fora de escopo.

## Tarefas agentáveis

### Agora (bloqueia o M5 da Fase 1)

- [ ] `Fase_2_Site/backend/pyproject.toml` + FastAPI mínimo com `/health`
- [ ] `backend/auth/oidc_google.py` — troca de código, validação de `iss`/`aud`/`exp`/`nonce`
- [ ] `backend/auth/rotas.py` — as 7 rotas da tabela
- [ ] `backend/auth/tokens.py` — JWT EdDSA, refresh rotativo, detecção de replay
- [ ] `backend/db/migracoes/001_identidade.sql` — as 3 tabelas
- [ ] `backend/log/redator.py`
- [ ] `Fase_2_Site/web/` — página `/login` com botão Google (estática basta na v1)
- [ ] `deploy/mapasfacil-api.service` + config do tunnel dedicado
- [ ] `backend/tests/test_auth.py`

### Depois do M11

- [ ] Memória de projeto, mapa por CAR, ponte com o desktop, vitrine pública

## Critérios de aceite

- [ ] `GET /health` responde 200 sem auth; **qualquer** outra rota fora do fluxo OAuth responde
      401 sem Bearer — teste varre `app.routes` e falha se uma rota nova ficar pública
- [ ] Fluxo completo com Google mockado: `start` → `callback` → `token` devolve o par de tokens e
      cria uma linha em `contas` e uma em `sessoes`
- [ ] `redirect_uri = "https://evil.com/callback"` → `400` / `AUTH-040`
- [ ] `code_challenge_method = "plain"` → `400`
- [ ] `code_app` usado duas vezes → segunda vez `AUTH-041`
- [ ] `code_app` após 61 s → `AUTH-041`
- [ ] `code_verifier` errado → `AUTH-041`
- [ ] Refresh rotativo: o token antigo passa a falhar com `AUTH-011`
- [ ] **Replay:** usar um refresh já rotacionado revoga a família inteira — a sessão nova também
      deixa de funcionar
- [ ] Conta identificada por `google_sub`: mudar o email da conta Google não cria conta nova
- [ ] `grep -rniE "quota|paywall|assinatura|billing|plano_limite" backend/` não encontra
      restrição de produto; o único rate limit é o de abuso nos endpoints de auth, comentado como tal
- [ ] Log de um fluxo completo não contém JWT (`grep -c "eyJ"` = 0), nem `code=`, nem IP em claro
- [ ] `systemctl status mapasfacil-api` ativo e a configuração dos outros tunnels inalterada
      (`diff` vazio em `/etc/cloudflared/` e no `saldopro-config.yml`)

## Fora de escopo

- Cadastro por e-mail/senha, magic link, outros provedores.
- SSO corporativo, organizações, times, papéis, convites.
- Planos, cobrança, quota, trial, medição de uso para faturar (D18).
- Sync de conversas do desktop (D20).
- Recuperação/exclusão de conta pelo app (é pelo site, depois).
- Sessão web longa — na v1 o site existe só para a tela de login.

## Anti-padrões

| Não faça | Por quê |
|---|---|
| Registrar o loopback do desktop como redirect URI no Google | obrigaria um cliente OAuth por instalação; o nosso backend é quem redireciona |
| Usar email como chave da conta | email muda; `google_sub` não |
| Guardar `refresh_token` em claro no banco | vazamento do dump = todas as sessões |
| Aceitar qualquer `redirect_uri` | open redirect e roubo de código |
| Criar tabela de plano/quota "para o futuro" | AP-05 / D18: futuro que restringe hoje é restrição hoje |
| Deixar rota nova pública "por enquanto" | o teste de varredura de rotas existe para isso |
| Reaproveitar o tunnel de outro sistema | D7; risco aos sistemas existentes |
| Logar o IP em claro | LGPD; guarde `sha256(ip + sal)` |

## Pendências

| # | Questão | Recomendação |
|---|---|---|
| P1 | Se este PC cair, ninguém faz login novo | monitorar `/health`; se virar problema no piloto, revisar D10 para provedor gerenciado |
| P2 | Sal do `ip_hash`: por instalação ou global | global no env, rotacionável |
| P3 | Consent screen do Google em "testing" limita a 100 usuários | suficiente para o piloto; publicar antes de distribuir |
| P4 | Quem apaga `codigos_desktop` expirados | job periódico: `DELETE WHERE expira_em < now() - interval '1 day'` |
