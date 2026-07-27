# F2-01 — Arquitetura do site de distribuição

## Objetivo

Descrever como o site da Fase 2 se encaixa no produto: um front Next.js público que explica o
Mapas Fácil e aponta para o instalador do desktop. Sem agente WebSocket, sem hub de jobs, sem
API geo na v1 (D21).

## Estado atual vs alvo

| Item | Atual | Alvo |
|---|---|---|
| Documento | legado (Vercel + Render + agente WS) | este texto (D7 + D21) |
| Artefatos | `web/` e `backend/` só README | `web/` = Next.js; `backend/` **fora da v1** |
| Fronteira com Fase 1 | legado misturava MapSpec/RPC | site só linka o instalador ([F2-03](03-integracao-fase1.md)) |

## Dependências

| Precisa de | Plano |
|---|---|
| Escopo D21 | [F2-00](00-visao-e-escopo.md) |
| Visão comum | [`../../planos/00-visao-e-duas-fases.md`](../../planos/00-visao-e-duas-fases.md) |
| Conta (só desktop) | [F1-14](../../Fase_1_Desktop/planos/14-auth-e-conta.md) |

## Contratos

### Diagrama

```
Visitante
   │
   ▼
mapasfacil.cursar.space     (Next.js — Fase_2_Site/web/)
   │  landing / requisitos / download / contato
   │
   └──▶ instalador Windows (.exe)     (artefato M10 da Fase 1)
              │
              ▼
         App desktop
              ├── login / criar conta (local)
              └── gera mapa / .mxd / PDF
```

### Fronteiras invioláveis

1. O site **não** autentica usuários.
2. O site **não** recebe `MapSpec`, não dispara job e não consulta WFS/SEMA.
3. O site **não** importa o núcleo Python da Fase 1 em runtime.
4. Dados de cliente **nunca** sobem pelo site na v1.
5. `backend/` (FastAPI/Postgres) **não** faz parte do deploy v1.

### Domínios

| Host | Conteúdo v1 |
|---|---|
| `mapasfacil.cursar.space` | site Next.js |
| `mapasfacil-api.cursar.space` | **não usado** na v1 de distribuição (reservado se no futuro houver API) |

### Variáveis (site)

| Var | Obrigatória | Uso |
|---|---|---|
| `NEXT_PUBLIC_DOWNLOAD_URL` | não | URL do instalador; vazia → UI “em breve” |
| `NEXT_PUBLIC_CONTACT_EMAIL` | não | mailto na página de contato |
| `NEXT_PUBLIC_REPO_URL` | não | link do repositório |

Nenhum segredo no front (AP-03).

## Tarefas agentáveis

- [ ] Substituir o texto legado pelo D21 — **feito** (este documento)
- [ ] Scaffold `Fase_2_Site/web/` (Next.js) conforme [F2-04](04-frontend-site.md) — **próxima rodada**
- [ ] Manter `Fase_2_Site/backend/` só com README “fora da v1” — [F2-02](02-backend-api.md)

## Critérios de aceite

- [ ] Nenhum diagrama ou tabela neste plano descreve agente WS, fila de mapa ou login no site
- [ ] `backend/` não aparece como dependência de deploy da landing
- [ ] Download aponta só para artefato da Fase 1 (ou placeholder)

## Fora de escopo

- Conta nuvem, sync, chat web ([F2-05](05-auth-e-memoria.md))
- API FastAPI, Postgres, WFS no servidor
- Pareamento desktop ↔ nuvem

## Anti-padrões

| Não faça | Por quê |
|---|---|
| Restaurar o hub WebSocket de agentes do texto legado | D21 |
| Exigir Postgres para servir HTML estático | desnecessário |
| Colocar chave DeepSeek ou SEMA no site | AP-03; produto é BYOK no desktop |
| Tratar `mapasfacil-api` como obrigatório na v1 | API fora da v1 |

## Relação com o legado

O corpo anterior deste arquivo (Render + Vercel + `agent/` WS) é **obsoleto**. Não use como
especificação. Histórico fica no git.
