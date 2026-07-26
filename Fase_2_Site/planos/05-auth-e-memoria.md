# F2-05 — Identidade na nuvem e memória de projeto (Fase 2)

> **Atenção, agente (revisão 2026-07-26):** este documento **NÃO bloqueia mais a Fase 1**.
> O login do app desktop é **conta local com e-mail e senha** em SQLite — ver
> [F1-14](../../Fase_1_Desktop/planos/14-auth-e-conta.md) (D10 revisada). **Não implemente
> Google OAuth, site de login nem backend de identidade para fechar o M5.**
>
> Este arquivo descreve o que a **Fase 2** pode oferecer depois do piloto (M11): conta na nuvem
> (opcional), espelho de projetos e memória entre máquinas. Até lá, trate tudo abaixo como
> **adiado**.

## Objetivo

Especificar — para **depois do M11** — um serviço de identidade/nuvem e a memória de projeto que
o site teria e o desktop sozinho não tem. A identidade do **desktop na v1** já está fechada em
F1-14 (local). As duas metades aqui têm a mesma prioridade: **depois da Fase 1 validada**.

## Estado atual vs alvo

| Item | Atual | Alvo (Fase 2, pós-M11) |
|---|---|---|
| Login do app desktop (M5) | **especificado em F1-14** — e-mail+senha local | **não depende deste plano** |
| `Fase_2_Site/backend/` | só `README.md` — **sem código** | FastAPI com rotas de conta/nuvem (desenho a reabrir) |
| `Fase_2_Site/web/` | só `README.md` — **sem código** | site de engenharia / vitrine |
| Conta Google / OAuth | **descartada para o M5** | eventual provedor na nuvem é decisão **nova**, não herança automática do plano antigo |
| Memória de projeto entre PCs | ausente | opt-in (D20) |

## Dependências

| Precisa de | Estado |
|---|---|
| Fase 1 validada até M11 (piloto) | em andamento |
| [F1-14](../../Fase_1_Desktop/planos/14-auth-e-conta.md) — conta **local** do desktop | a implementar no M5 (sem este arquivo) |

## Decisões

| # | Decisão | Nota |
|---|---|---|
| **D10** *(revisada 2026-07-26)* | Conta do desktop = **e-mail + senha local** (F1-14). F2-05 **não** é dependência da Fase 1 | Google + tunnel dedicado como login do app foram descartados |
| D18 | Autenticado = **ilimitado** na v1 | vale para conta local e, se existir, conta nuvem |
| D20 | Conversas do desktop são **local-only**; espelho na conta é Fase 2 e opt-in | sync automático proibido na v1 |

## O que este plano NÃO manda fazer agora

- Backend FastAPI de identidade para desbloquear o app
- Site `/login` com botão Google
- PKCE, loopback OAuth, Credential Manager de `access_token`/`refresh_token` de conta
- Tunnel `mapasfacil-api.cursar.space` “porque o M5 precisa”

Quem for implementar **M5** lê só [F1-14](../../Fase_1_Desktop/planos/14-auth-e-conta.md).

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
([F1-17](../../Fase_1_Desktop/planos/17-persistencia-de-conversas.md)) e contas em
`%APPDATA%\MapasFacil\contas\contas.sqlite` ([F1-14](../../Fase_1_Desktop/planos/14-auth-e-conta.md)).
A Fase 2 **não substitui** esse armazenamento local; ofereceria um espelho **opcional**. Na v1
esse espelho **não existe** (D20).

## Conta na nuvem (rascunho futuro — não implementar no M5)

Se no futuro o produto quiser a mesma conta em vários PCs, isso será um **plano novo** (ou revisão
explícita deste), escolhendo provedor (e-mail+senha no servidor, OAuth, etc.). O desenho antigo
com Google OIDC + PKCE + loopback ficou **obsoleto para o login do desktop**; não copie da
memória do chat nem de commits antigos sem releitura da D10 revisada.

## Tarefas agentáveis

### Agora

- [ ] **Nenhuma** tarefa de identidade neste arquivo bloqueia o M5. Implemente F1-14.

### Depois do M11

- [ ] Reabrir desenho de conta na nuvem (se o piloto pedir sync entre PCs)
- [ ] Memória de projeto, mapa por CAR, ponte com o desktop, vitrine pública
- [ ] `Fase_2_Site/backend/` + `web/` conforme o desenho **então** vigente

## Critérios de aceite (Fase 2 — futuros)

- [ ] Nenhum endpoint de upload de conversa na v1 (D20)
- [ ] `grep -rniE "quota|paywall|assinatura|billing|plano_limite"` sem restrição de produto (D18)
- [ ] Conta desktop continua funcionando **offline** mesmo se o site/backend futuro cair

## Fora de escopo (v1 / M5)

- Qualquer implementação deste arquivo para “fechar auth do app”
- SSO corporativo, organizações, times, papéis, convites
- Planos, cobrança, quota, trial
- Substituir `contas.sqlite` local por conta obrigatória na nuvem

## Anti-padrões

| Não faça | Por quê |
|---|---|
| Tratar este plano como pré-requisito do M5 | D10 revisada; login é F1-14 local |
| Reintroduzir “Entrar com Google” no app porque um plano antigo citava | obsoleto para o desktop |
| Sync automático de chats para a nuvem | D20 / AP-12 |
| Criar tabela de plano/quota “para o futuro” | AP-05 / D18 |

## Pendências

| # | Questão | Recomendação |
|---|---|---|
| P1 | O piloto vai pedir a mesma conta em dois PCs? | Só então desenhar conta nuvem; até lá local basta |
| P2 | Recuperação de senha local | Na v1: honestidade na UI (só neste PC); reset = apagar/recriar conta local |
