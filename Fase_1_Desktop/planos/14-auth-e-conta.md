# F1-14 — Conta e autenticação do app desktop

## Objetivo

O app Windows exige login. O fluxo é: o app abre o navegador padrão → o usuário entra com Google
no site do Mapas Fácil → o backend de identidade emite um par de tokens → o app recebe o token
por *redirect* de loopback e o guarda no Windows Credential Manager. Uma vez autenticado, o
usuário tem **acesso ilimitado na v1**: sem quota, sem paywall, sem rate limit de produto, sem
feature flag de cobrança. A conta existe para identidade e continuidade, não para cobrar.

## Estado atual vs alvo

| Item | Atual | Alvo |
|---|---|---|
| Fluxo de login no app | **ausente** | Authorization Code + PKCE com redirect de loopback |
| Backend de identidade | **ausente** | FastAPI neste PC, exposto por `mapasfacil-api.cursar.space` ([F2-05](../../Fase_2_Site/planos/05-auth-e-memoria.md)) |
| Site de login | **ausente** | `mapasfacil.cursar.space/login` |
| Armazenamento de token | **ausente** (nem cofre existe) | Windows Credential Manager, escrito só pelo processo main do Electron |
| Gate de sessão no núcleo | **ausente** | `sessao.definir` + recusa de `mapa.gerar` com `AUTH-030` |
| Códigos `AUTH-xxx` | **ausentes** da tabela de erros | definidos aqui e replicados em [F1-01](01-arquitetura.md#códigos-de-erro) |

## Dependências

| Precisa de | Estado | Onde |
|---|---|---|
| M3 — Shell Electron (janela, main process, IPC) | ausente | [F1-02](02-ui-chat-e-workspace.md) |
| F2-05 — backend de identidade **no ar** | ausente | [F2-05](../../Fase_2_Site/planos/05-auth-e-memoria.md) |
| Cliente OAuth Google configurado | ausente | console Google Cloud, ver §Configuração |
| Cofre (Credential Manager) | ausente | [F1-03](03-nucleo-python.md#cofre) — o cofre do app é o **mesmo** módulo |

**D10 tem uma consequência que o agente precisa aceitar:** o backend de identidade vive em
`Fase_2_Site/`, mas **é dependência bloqueante da Fase 1**. É a única parte da Fase 2 que sobe
antes do piloto. Não interprete "Fase 2 vem depois" como permissão para adiar o login.

## Decisões que fecham este plano

| # | Decisão | Alternativa descartada |
|---|---|---|
| D10 | Backend de identidade **próprio, neste PC**, exposto por tunnel dedicado | Firebase Auth (menos código, mas outra conta e outro plano de dados); Clerk/Auth0 (custo e dependência SaaS) |
| D11 | Sem sessão válida, `mapa.gerar` é **bloqueado** (`AUTH-030`); o app fica em modo leitura | carência offline de 30 dias (mais amigável, mas mais estado para auditar) |
| D12 | Redirect do desktop por **loopback** `http://127.0.0.1:<porta efêmera>/callback` (RFC 8252) | `mapasfacil://` como primário — fica só como fallback registrado pelo instalador |
| D18 | v1 autenticada é **ilimitada** | quota por conta, paywall, trial |

### D11 em detalhe — o que "sessão válida" significa

`sessão válida` = existe `access_token` **não expirado** no Credential Manager.

- `access_token`: JWT, TTL **12 h**. Escolhido para o técnico em campo passar um dia inteiro sem
  rede depois de abrir o app conectado.
- `refresh_token`: opaco, TTL **60 dias**, rotativo, revogável no servidor.
- Offline com `access_token` válido → o app funciona **inteiro**, inclusive `mapa.gerar`.
- Offline com `access_token` expirado → `mapa.gerar`, `galeria.montar_mapspec` e `chat.enviar`
  recusam com `AUTH-030`. Continuam permitidos: abrir pasta, inspecionar shapefile, ler recibo,
  abrir e ler conversas antigas, ver mapas já gerados.

Isto **revisa o critério de aceite 6 antigo** da [F1-00](00-visao-e-escopo.md) ("sem internet, o
app gera o mapa com cache"): agora vale "sem internet **e com sessão válida em cache**". A troca
foi decidida com o dono do produto; está registrada como D11 e é revisável em D11-a se o piloto
reclamar (a revisão seria aumentar o TTL, não remover o gate).

**Honestidade sobre o gate:** ele é de produto, não de segurança contra o dono da máquina. Quem
controla o Windows consegue burlá-lo. Não gaste esforço endurecendo isso; gaste em `fsguard`.

## Contratos

### Configuração (sem segredo no repositório)

| Nome | Onde vive | Exemplo |
|---|---|---|
| `MAPASFACIL_AUTH_BASE` | `app/config/ambiente.json` (público) | `https://mapasfacil-api.cursar.space` |
| `MAPASFACIL_SITE_BASE` | idem | `https://mapasfacil.cursar.space` |
| `MAPASFACIL_CLIENT_ID` | idem — client público de desktop, **sem secret** (PKCE) | `mapasfacil-desktop` |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | **só no backend**, env do systemd | ver [F2-05](../../Fase_2_Site/planos/05-auth-e-memoria.md) |

Um client desktop **não tem client secret**. Se um agente for tentado a colocar um, é PKCE que
está faltando, não o secret.

### Fluxo completo (sequência)

```
App (Electron main)          Navegador padrão        Backend identidade        Google
   │                                │                        │                   │
 1 │ gera code_verifier (43–128)    │                        │                   │
   │ code_challenge = S256(verifier)│                        │                   │
   │ state = ULID                   │                        │                   │
 2 │ sobe servidor loopback         │                        │                   │
   │ 127.0.0.1:<porta efêmera>      │                        │                   │
 3 ├───── shell.openExternal ──────▶│                        │                   │
   │   GET {SITE}/login?client_id&state&code_challenge       │                   │
   │        &redirect_uri=http://127.0.0.1:PORTA/callback    │                   │
 4 │                                ├─ "Entrar com Google" ─▶│                   │
 5 │                                │                        ├── OIDC authorize ▶│
 6 │                                │◀────────── consentimento e login ──────────┤
 7 │                                │                        │◀── code ──────────┤
 8 │                                │                        │ troca code→id_token
   │                                │                        │ valida iss/aud/exp
   │                                │                        │ upsert conta
   │                                │                        │ emite code_app (60 s)
 9 │                                │◀─ 302 redirect_uri?code=code_app&state ─────┤
10 │◀─ GET /callback?code&state ────┤                        │                   │
   │  confere state; fecha loopback │                        │                   │
11 ├──── POST /auth/desktop/token {code, code_verifier, client_id} ─────────────▶ │
12 │◀─── {access_token, refresh_token, expires_in, conta} ───────────────────────┤
13 │ grava no Credential Manager    │                        │                   │
14 │ envia sessao.definir ao núcleo (SEM token)              │                   │
15 │ renderer recebe evento auth.mudou {estado:"conectado"}  │                   │
```

Passos que um agente costuma errar e aqui são obrigatórios:

1. **`state` conferido no passo 10.** Diferente → `AUTH-040`, aborta, não troca o código.
2. **Loopback em `127.0.0.1`, nunca `localhost`.** Resolução de `localhost` pode ir para `::1` e
   quebrar em máquinas com IPv6 mal configurado.
3. **Porta efêmera** (`server.listen(0)`), nunca fixa. Porta fixa colide e vira vetor.
4. **O servidor loopback aceita exatamente uma requisição** em `/callback` e fecha. Timeout de
   **5 min** sem callback → `AUTH-022`, fecha o servidor.
5. **A página de retorno é local**, servida pelo próprio loopback: HTML estático "pode fechar
   esta aba". Não redirecione o navegador de volta para o site.

### Endpoints consumidos pelo app

Contrato completo (incluindo o lado servidor) em
[F2-05](../../Fase_2_Site/planos/05-auth-e-memoria.md). O app usa só estes quatro:

| Método | Rota | Corpo | Resposta |
|---|---|---|---|
| `POST` | `/auth/desktop/token` | `{code, code_verifier, client_id}` | `{access_token, refresh_token, expires_in, token_type:"Bearer", conta}` |
| `POST` | `/auth/refresh` | `{refresh_token}` | mesmo formato; **o refresh antigo é invalidado** (rotação) |
| `POST` | `/auth/logout` | `{refresh_token}` | `204` |
| `GET` | `/auth/me` | header `Authorization: Bearer` | `{id, email, nome, avatar_url, criado_em, plano}` |

`conta` e `/auth/me` devolvem `plano: "v1_ilimitado"` — campo existe para telemetria futura e
**nunca** deve ser lido para restringir função nenhuma na v1 (AP-05).

### Renovação

```
a cada 30 min, e no boot, e antes de mapa.gerar:
   access_token expira em > 10 min ?  → nada a fazer
   expira em <= 10 min ou expirado ?  → POST /auth/refresh
        200 → grava novo par; auth.mudou {estado:"conectado"}
        401/403 → apaga o par; auth.mudou {estado:"expirado"}; AUTH-011
        rede falhou → mantém o par; auth.mudou {estado:"offline"}; NÃO apaga nada
```

Rede falhando **nunca** apaga o refresh token. Só `401`/`403` do servidor apaga.

### Onde os tokens ficam

| Segredo | Local | Quem escreve | Quem lê |
|---|---|---|---|
| `access_token` | Credential Manager, alvo `MapasFacil/access_token` | Electron **main** | Electron main |
| `refresh_token` | Credential Manager, alvo `MapasFacil/refresh_token` | Electron main | Electron main |
| `code_verifier` | **memória do main**, apagado após o passo 12 | main | main |
| conta (id, email, nome) | `%APPDATA%\MapasFacil\config.json` | main | main + renderer |

Invioláveis:

- Token **nunca** cruza o IPC para o renderer. O renderer recebe `{estado, conta}` e nada mais.
- Token **nunca** entra no NDJSON do sidecar. O núcleo sabe se há sessão, não qual é.
- Token **nunca** aparece em log — o redator de URL/headers cobre `Authorization` e `Bearer`.
- Se o Credential Manager falhar (perfil corrompido, política de grupo), **não** caia para arquivo
  em texto: erro `AUTH-050` com instrução. Fallback silencioso para disco é AP-03.

### IPC (main ↔ renderer)

| Canal | Direção | Payload |
|---|---|---|
| `auth:entrar` | renderer → main | `{}` — dispara o fluxo |
| `auth:sair` | renderer → main | `{esquecer_este_pc?: boolean}` |
| `auth:estado` | renderer → main (invoke) | `{}` → `{estado, conta?, expira_em?}` |
| `auth:mudou` | main → renderer (evento) | `{estado, conta?, expira_em?, erro?}` |

`estado` ∈ `desconectado` \| `conectando` \| `conectado` \| `offline` \| `expirado`.

`auth:sair` com `esquecer_este_pc: false` (default) revoga a sessão e **preserva o histórico
local de conversas** — D14. Com `true`, apaga também `chats.sqlite` e `config.json`, com
confirmação de texto digitado ("APAGAR").

### Métodos NDJSON novos no núcleo

| Método | Params | Retorno | Nota |
|---|---|---|---|
| `sessao.definir` | `{estado, conta_id?, expira_em?}` | `{ok:true}` | chamado pelo main a cada `auth:mudou`. **Não recebe token** |
| `sessao.estado` | `{}` | `{estado, conta_id?, expira_em?}` | leitura |

Gate no núcleo: `mapa.gerar`, `galeria.montar_mapspec`, `chat.enviar` e
`quantitativos.exportar_xlsx` conferem `sessao.estado`. Se `estado != "conectado"` **e**
`expira_em` no passado → erro `AUTH-030`. `workspace.*`, `car.ler_recibo`, `mapspec.validar`,
`zip.*`, `doctor.rodar`, `chat.listar_conversas` e `chat.abrir_conversa` **não** têm gate.

### Códigos de erro `AUTH-xxx`

| Código | Significado | O que a UI faz |
|---|---|---|
| `AUTH-001` | Nunca houve login neste PC | tela de boas-vindas com "Entrar com Google" |
| `AUTH-010` | `access_token` expirado, refresh disponível | renova em silêncio; sem UI |
| `AUTH-011` | `refresh_token` expirado ou revogado | volta para a tela de login, explicando |
| `AUTH-020` | Backend inalcançável (DNS, tunnel fora do ar) | banner "servidor de conta indisponível"; se há token válido, o app **segue funcionando** |
| `AUTH-021` | Backend respondeu 5xx | igual a `AUTH-020` + botão "tentar de novo" |
| `AUTH-022` | Timeout de 5 min sem callback | fecha o loopback; "o login não foi concluído" |
| `AUTH-030` | Operação exige sessão válida e não há | bloqueia a ação, explica, oferece "Entrar" |
| `AUTH-040` | `state` divergente no callback (possível CSRF) | aborta, registra em log, pede novo login |
| `AUTH-041` | `code_app` expirado ou já usado | "o login demorou demais, tente de novo" |
| `AUTH-050` | Credential Manager indisponível | erro com instrução; **sem** fallback em arquivo |
| `AUTH-051` | Conta desativada no servidor | mensagem com contato |
| `AUTH-060` | Relógio do sistema fora de sincronia > 5 min | "acerte o relógio do Windows" — JWT `exp` fica inutilizável |

Todos entram na tabela de erros de [F1-01](01-arquitetura.md#códigos-de-erro).

## Estados da UI

| Estado | Primeira viewport | Resto do app |
|---|---|---|
| `desconectado` | tela de login em tela cheia: nome do produto como sinal hero, um botão "Entrar com Google", nota "acesso completo, sem limites" | inacessível |
| `conectando` | mesma tela, botão em estado de espera, texto "concluindo no navegador…" + link "abrir de novo" | inacessível |
| `conectado` | app normal | tudo liberado |
| `offline` | app normal + chip discreto "offline" no rodapé, ao lado do doctor | tudo liberado enquanto o token vale |
| `expirado` | faixa no topo: "sua sessão expirou — entre de novo para gerar mapas" | leitura liberada; geração recusa com `AUTH-030` |

A tela de login segue os tokens de [F1-16](16-design-system-dark.md): fundo `--mf-bg`, marca em
Space Grotesk no tamanho `--mf-fs-hero`, sem ilustração genérica, sem gradiente roxo.

## Tarefas agentáveis

### Backend (pré-requisito — ver F2-05 para o detalhe)

- [ ] `Fase_2_Site/backend/` com FastAPI, rotas `/auth/*` e `/health`
- [ ] Tabelas `contas`, `sessoes`, `codigos_desktop` (schema em F2-05)
- [ ] Deploy via systemd + tunnel dedicado, **sem tocar nos tunnels existentes**

### App — processo main

- [ ] `app/electron/auth/pkce.ts` — `gerar_verifier()`, `desafio_s256()`
- [ ] `app/electron/auth/loopback.ts` — servidor efêmero, uma requisição, timeout 5 min
- [ ] `app/electron/auth/fluxo.ts` — orquestra os passos 1–14 do diagrama
- [ ] `app/electron/auth/tokens.ts` — leitura/escrita no Credential Manager; nunca em disco
- [ ] `app/electron/auth/renovacao.ts` — timer de 30 min + renovação sob demanda
- [ ] `app/electron/ipc/auth.ts` — os quatro canais da tabela de IPC
- [ ] `app/electron/log/redator.ts` — remove `Authorization`, `Bearer`, `code`, `refresh_token`

### App — renderer

- [ ] `app/src/telas/Login.tsx` — id de painel `tela-login`
- [ ] `app/src/estado/auth.ts` — store Zustand com `estado`, `conta`
- [ ] `app/src/componentes/FaixaSessao.tsx` — faixa de `expirado` e chip de `offline`
- [ ] Guarda de rota: qualquer painel que não seja `tela-login` exige `estado === "conectado" | "offline"`

### Núcleo

- [ ] `nucleo/mapasfacil_nucleo/sessao.py` — estado em memória + `sessao.definir`/`sessao.estado`
- [ ] Gate `AUTH-030` em `mapa.gerar`, `galeria.montar_mapspec`, `chat.enviar`, `quantitativos.exportar_xlsx`
- [ ] `nucleo/mapasfacil_nucleo/erros.py` — família `AUTH-`

## Critérios de aceite

Verificáveis por outro agente, sem contexto humano:

- [ ] `pytest nucleo/tests/test_sessao.py` — `mapa.gerar` sem sessão devolve
      `{"ok":false,"erro":{"codigo":"AUTH-030"}}`; com `estado:"conectado"` e `expira_em` futuro, gera
- [ ] `pytest nucleo/tests/test_sessao.py::test_metodos_sem_gate` — `workspace.abrir`,
      `mapspec.validar`, `car.ler_recibo` funcionam com `estado:"desconectado"`
- [ ] Teste de integração do main (`app/electron/auth/__tests__/fluxo.test.ts`) com backend
      fake: fluxo completo devolve `estado:"conectado"` e grava dois alvos no cofre mockado
- [ ] `state` divergente → o teste espera `AUTH-040` e **nenhuma** chamada a `/auth/desktop/token`
- [ ] Refresh com `401` apaga o par; refresh com `ECONNREFUSED` **não** apaga (dois testes distintos)
- [ ] `grep -rn "access_token\|refresh_token" app/src/` não retorna nada — o renderer não conhece token
- [ ] Rodar o app com o backend desligado e token válido em cache: gera mapa normalmente,
      chip "offline" visível
- [ ] Adiantar o relógio 13 h e reabrir o app sem rede: `mapa.gerar` recusa com `AUTH-030`;
      abrir pasta e ler conversas continuam funcionando
- [ ] Nenhum log de sessão inteira contém `eyJ` (prefixo de JWT) — `grep -c "eyJ" %APPDATA%\MapasFacil\logs\*` = 0

## Fora de escopo

- Cadastro por e-mail e senha, magic link, provedores além do Google.
- SSO corporativo, SAML, organizações, times, papéis.
- Cobrança, planos, trial, quota, medição de uso para faturar.
- Sincronizar conversas, `MapSpec` ou arquivos para o servidor (é Fase 2 e é opt-in — D20).
- Recuperação de conta, exclusão de conta pelo app (faz-se pelo site, na Fase 2).
- Multi-conta simultânea no mesmo app.

## Anti-padrões

| Não faça | Por quê |
|---|---|
| Client secret embutido no app | um binário distribuído não guarda segredo; é para isso que existe PKCE |
| Token em `localStorage`, `sessionStorage` ou arquivo JSON | renderer comprometido = conta comprometida |
| Porta de loopback fixa | colisão e vetor de ataque local |
| Apagar o refresh token quando a rede falha | o usuário perde a sessão por causa de um Wi-Fi ruim |
| Usar `plano` para liberar/bloquear função | AP-05 / D18: v1 autenticada é ilimitada |
| Fallback de cofre para arquivo em texto | AP-03 |
| Bloquear leitura do workspace por falta de sessão | o técnico precisa abrir a pasta e conferir dados mesmo expirado |
| Pedir login de novo a cada abertura do app | o refresh de 60 dias existe justamente para isso |
