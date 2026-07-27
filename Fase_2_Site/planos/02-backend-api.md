# F2-02 — Backend e API

## Objetivo

Deixar explícito: na v1 de **distribuição** (D21), **não há backend** da Fase 2. Sem FastAPI,
sem Postgres, sem jobs, sem auth, sem WFS. A pasta `Fase_2_Site/backend/` existe só como
reserva documental.

## Estado atual vs alvo

| Item | Atual | Alvo v1 |
|---|---|---|
| Código em `backend/` | só `README.md` | continua só README — **sem** `pyproject.toml` / app |
| API geo / auth / jobs | legado (Render + WS) | **fora da v1** |
| Site | precisa de API? | **não** — Next.js serve a landing |

## Dependências

Nenhuma para a v1 do site. Conta nuvem futura: [F2-05](05-auth-e-memoria.md) (adiado).

## Decisão

| # | Decisão |
|---|---|
| D21 | Distribuição não exige API |
| — | `mapasfacil-api.cursar.space` **não** é provisionado na v1 |

Se no futuro o produto pedir conta nuvem ou API, este plano será **reaberto** com o formato
completo (Objetivo → Contratos → Tarefas). Até lá, **não** implementar FastAPI “por antecipação”
(AP-05 / D18: sem tabelas de quota; sem esqueleto de billing).

## Contratos (v1)

- Nenhum endpoint HTTP da Fase 2.
- Nenhum schema de banco da Fase 2.
- Health do site = o próprio Next.js respondendo na porta publicada.

## Tarefas agentáveis

### Agora (v1)

- [x] Documentar “backend fora da v1” (este arquivo)
- [x] README de `backend/` alinhado — ver pasta `../backend/README.md`
- [ ] **Não** criar `app/main.py`, Alembic, Docker de API nesta fase

### Só se F2-05 / produto pedir API no futuro

- [ ] Reabrir este plano com FastAPI + Postgres no PC servidor
- [ ] Rotas mínimas então vigentes (não copiar o legado WS às cegas)

## Critérios de aceite (v1)

- [ ] `ls Fase_2_Site/backend` não contém código de aplicação além do README
- [ ] Planos F2 não listam Postgres como pré-requisito do site
- [ ] Nenhuma menção operacional a hub WebSocket de agentes como caminho v1

## Fora de escopo

- Implementar API “só o health”
- Migrar o texto legado (fila, SSE de chat, agents.ws) para código
- Consultas SEMA no servidor por causa do site

## Anti-padrões

| Não faça | Por quê |
|---|---|
| Scaffold FastAPI “para já deixar pronto” | D21; YAGNI |
| Copiar endpoints `/v1/jobs` do legado | mapa só no desktop |
| Criar tabela `users` no site | login é F1-14 |

## Relação com o legado

O corpo anterior (hub WS, fila `jobs`, DeepSeek no backend, Render) é **obsoleto** para a v1.
