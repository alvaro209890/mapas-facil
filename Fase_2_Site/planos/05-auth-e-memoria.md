# F2-05 — Identidade na nuvem e memória de projeto (adiado)

> **Atenção, agente:** este documento **não** é a v1 do site e **não** bloqueia a Fase 1.
> Login do app = conta **local** — [F1-14](../../Fase_1_Desktop/planos/14-auth-e-conta.md).
> Site v1 = **só distribuição** — [F2-00](00-visao-e-escopo.md) (D21). **Não** implemente
> Google OAuth, `/login` no Next.js, nem backend de identidade para “fechar” o site ou o M5.

## Objetivo

Reservar, para **depois** (se o produto pedir), um serviço de conta na nuvem e memória de
projeto entre máquinas. Hoje isso está **adiado**. A v1 do site **não** inclui login.

## Estado atual vs alvo

| Item | Atual | Alvo agora |
|---|---|---|
| Login no app desktop | **feito** (F1-14) | permanece local |
| Login no site | **proibido na v1** (D21) | sem rotas de auth |
| Conta nuvem / sync | ausente | só se reabrir este plano pós-piloto |
| `backend/` identidade | só README | continua fora ([F2-02](02-backend-api.md)) |

## Dependências

| Precisa de | Estado |
|---|---|
| D21 — site = distribuição | vigente |
| Piloto M11 / pedido explícito de sync entre PCs | futuro |
| F1-14 | **não** depende deste arquivo |

## Decisões

| # | Decisão | Nota |
|---|---|---|
| D10 | Conta desktop = e-mail + senha **local** | F2-05 não bloqueia |
| D18 | Autenticado = ilimitado | sem quota/planos |
| D20 | Conversas local-only; espelho nuvem opt-in e **adiado** | sync automático proibido |
| D21 | Site v1 sem login | distribuição apenas |

## O que este plano NÃO manda fazer

- Backend FastAPI de identidade
- Site `/login` ou “Entrar com Google”
- PKCE / tokens de conta no desktop apontando para o site
- Tunnel `mapasfacil-api` “porque auth precisa”
- Qualquer UI de conta no Next.js da v1

## Memória de projeto (futuro — não implementar)

Se reaberto no futuro, o backend *poderia* guardar metadados de imóvel, versões de MapSpec,
artefatos com consentimento, etc. **Não** desenhar tabelas agora. Preferência: shapes sensíveis
ficam no desktop.

A Fase 2 futura **não** substituiria `contas.sqlite` / `chats.sqlite` locais; no máximo espelho
opt-in (D20).

## Tarefas agentáveis

### Agora

- [x] Confirmar: nenhuma tarefa deste arquivo bloqueia site v1 nem M5
- [ ] Implementar landing **sem** auth — [F2-04](04-frontend-site.md)

### Só se o produto pedir conta nuvem

- [ ] Reabrir desenho (provedor, sync, LGPD) em plano novo ou revisão explícita
- [ ] Só então `backend/` + rotas

## Critérios de aceite (enquanto adiado)

- [ ] Site v1 sem `/login` / `/signup`
- [ ] Nenhum endpoint de upload de conversa na v1 (D20)
- [ ] `grep -rniE "quota|paywall|assinatura|billing|plano_limite"` sem restrição de produto (D18)
- [ ] Desktop continua offline sem o site

## Fora de escopo

- SSO, times, organizações, convites
- Cobrança, trial, quota
- Substituir conta local por conta obrigatória na nuvem

## Anti-padrões

| Não faça | Por quê |
|---|---|
| Tratar este plano como pré-requisito do site ou do M5 | D10 / D21 |
| “Entrar com Google” no site porque um plano antigo citava | obsoleto |
| Sync automático de chats | D20 |
| Tabela de plano/quota “para o futuro” | AP-05 / D18 |

## Pendências

| # | Questão | Recomendação |
|---|---|---|
| P1 | O piloto vai pedir a mesma conta em dois PCs? | Só então desenhar nuvem |
| P2 | Recuperação de senha local | Honestidade na UI do app; reset = recriar conta local |
