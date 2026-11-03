# W6 — trilha B (web): camada de API

*(início em 2026-11-03)*

## Feito

**W6-02 — `web/src/api/`**, com testes em Vitest (24 testes no web, 4 arquivos):

| Arquivo | O que faz | Provas |
|---|---|---|
| `cliente.ts` | `fetch` com `credentials: "include"`, `X-MF-CSRF` em POST/PUT/PATCH/DELETE, parse do corpo de erro `{erro:{codigo,mensagem,porque,o_que_fazer}}` em `ErroHttp`, 401 avisando a store de sessão **uma vez**, falha de rede virando `REDE` em vez de código `SV-xxx`, `204 → undefined` | 10 testes (`cliente.test.ts`) |
| `eventos.ts` | um `EventSource` por projeto (`event mf`, `withCredentials`), descarte de `seq ≤ último` (reconexão sem aplicar duas vezes), evento quebrado não derruba a tela, estados `conectado`/`reconectando`/`offline` com limite de 30 s | 9 testes (`eventos.test.ts`) |
| `tipos.ts` | tipos de projeto, versão, validação, sessão, erro, evento, mensagem, sugestão + vocabulário dos eventos | 4 testes (`tipos.test.ts`) |

`tipos.test.ts` é **guarda de contrato**: lê `servidor/mapasfacil_servidor/eventos/vocabulario.py`
e compara com `EVENTOS_NUCLEO`/`EVENTOS_SERVIDOR` do TypeScript. Se um dos lados ganhar evento
novo e o outro não, o teste do web falha — foi assim que descobri que meu vocabulário inicial
tinha `nucleo.res` no lado errado e faltava `workspace.mudou`.

## Comandos e resultados

    cd Fase_3_Web/web
    pnpm test       → 4 arquivos, 24 testes, 0 falhas
    pnpm typecheck  → exit 0 (TS estrito + exactOptionalPropertyTypes)
    pnpm build      → built in 872ms

## Pendências e riscos

- **W6-01** (copiar tokens, fontes, motion e os componentes de chat com proveniência) ainda não
  foi feito: é o próximo passo e é o que destrava as telas.
- **W6-03** (stores) depende do W6-01; `api/ponteWeb.ts` nasce junto, porque é o adaptador que
  substitui `chamar()` pelas rotas REST.
- TS estrito com `exactOptionalPropertyTypes` é chato de propósito: `ErroApi` e os campos do
  `ErroHttp` precisam declarar `| undefined` explicitamente. Melhor descobrir aqui do que na tela.
