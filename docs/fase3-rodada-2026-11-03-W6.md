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

## W6-01 — design system e componentes herdados

Copiado de `Fase_1_Desktop/app/src/` para `web/src/` **com cabeçalho de proveniência** em cada
arquivo:

| Origem | Destino | O quê |
|---|---|---|
| `estilos/tokens.css`, `reset.css`, `scrollbar.css` | `web/src/estilos/` | tokens do tema escuro e base |
| `estilos/fontes/` | `web/src/estilos/fontes/` | Space Grotesk + IBM Plex (woff2) e as **licenças OFL** |
| `componentes/` | `web/src/herdados/` | BolhaMarkdown, BlocoRaciocinio, IndicadorPensando, CartaoPergunta, CartaoTool, GrupoTools, CampoEntrada, LinhaVersoes (+ `.module.css`) |
| `chat/timeline.ts` | `web/src/herdados/timeline.ts` | redução de eventos do turno em blocos |

Diferenças assumidas (e só elas): os imports de `../estado/*` passaram a apontar para
`herdados/tipos.ts`, que declara **apenas tipos** — a web não herda as stores do desktop (W6-03
vai escrever as suas). Dependências novas no `package.json`, com versão exata:
`lucide-react 0.469.0`, `react-markdown 10.1.0`, `remark-gfm 4.0.1`.

Dois ajustes que o TypeScript estrito do web exigiu e o desktop não:

- `src/tipos/estilos.d.ts` declara `*.module.css` (sem isso, TS2307 em todo componente);
- em `LinhaVersoes`, `versoes[indiceExibido]` é `VersaoMapspec | undefined` de verdade
  (`noUncheckedIndexedAccess`) — agora há guarda explícita antes de desenhar o cartão de diff.

`main.tsx` passou a importar na ordem **fontes → tokens → reset → scrollbar → base**.

Comandos: `pnpm test` → **5 arquivos, 32 testes**; `pnpm typecheck` → exit 0;
`pnpm build` → 822 ms. O teste `herdados.test.tsx` não checa "copiei os arquivos": ele
**renderiza** bolha markdown com tabela, cartão de tool, grupo de tools, cartão de pergunta com
opções clicáveis e o bloco de raciocínio, além de acumular dois deltas no mesmo bloco da timeline
e cancelar tool pendente no fim do turno.
