# Melhoria do front — chat desktop (estilo Claude)

**Executado em 2026-07-27.** Esta pasta preserva o diagnóstico, os contratos e o roteiro usados
na implementação em `Fase_1_Desktop/app/` e no suporte mínimo de anexos do núcleo.

Entregue:

- timeline live intercalada, markdown GFM e histórico com `tool_traces`;
- grupos e tools retráteis, incluindo argumentos e resultado;
- raciocínio dedicado via `chat.raciocinio` quando o provedor emitir, sem fallback inventado;
- composer com picker, drag-drop, colar imagem, preview e limite de 20 MB;
- persistência local do anexo e scrollbar dark global baseada em `--mf-*`.

## Por que esta pasta existe

O chat funciona (streaming, tools, cancelar, perguntas), mas a UI parece “lista técnica crua”:

1. **Scrollbar branca nativa** — contraste alto no tema escuro, sem estilização.
2. **Tools em lista flat** — uma linha por tool, sempre aberta, ocupa a tela inteira.
3. **Fluxo não intercalado** — texto do assistente num bloco; tools todas abaixo (não `tool → texto → tool → texto`).
4. **Sem markdown** — respostas com tabelas/`**negrito**` aparecem como texto cru.
5. **Raciocínio inexistente** — só `IndicadorPensando` (3 dots); não há balão colapsável de thinking.
6. **Composer básico** — textarea + Enviar; sem anexo, sem colar imagem, visual datado.

O alvo visual de referência é o fluxo Claude/Cursor: cartões de ação **retráteis**, mensagem bem formatada, raciocínio colapsável, composer moderno com anexos.

## Documentos

| Arquivo | Conteúdo |
|---|---|
| [00-diagnostico-atual.md](00-diagnostico-atual.md) | O que existe hoje, lacunas vs F1-02/F1-16/F1-17, prints |
| [01-visao-claude-like.md](01-visao-claude-like.md) | UX alvo, princípios, o que **não** mudar |
| [02-modelo-timeline.md](02-modelo-timeline.md) | Modelo de blocos intercalados (estado + eventos) |
| [03-componentes.md](03-componentes.md) | Componentes novos/refatorados (tools, markdown, raciocínio, scrollbar) |
| [04-composer-anexos.md](04-composer-anexos.md) | Barra de entrada moderna + anexos + paste de imagem |
| [05-fases-implementacao.md](05-fases-implementacao.md) | Fases ordenadas, DoD, testes, riscos |

## Relação com planos existentes

Isto **não substitui** F1-02 / F1-16 / F1-17 — **fecha gaps** que esses planos já pediam e o código ainda não entregou:

| Spec antiga | Pedido | Código hoje |
|---|---|---|
| F1-02 / F1-16 §A3 | `cartao-tool` colapsável, expandir args/resultado | linha sempre aberta; `resultadoResumo` nunca renderizado |
| F1-16 §A1 | `bloco-raciocinio` colapsável | só `IndicadorPensando` |
| F1-02 / F1-16 | `CampoEntrada.tsx` com anexos | form inline em `PainelChat` |
| F1-17 | `tool_traces` + `anexos/` no histórico | backend grava; UI **ignora** |
| F1-16 | markdown / tipografia de mensagem | `<p>` com `pre-wrap`, sem parser |

Esta pasta adiciona o que faltava na spec antiga: **timeline intercalada** (o salto visual principal vs Claude) e **polish de scrollbar/composer**.

## Ordem sugerida de execução (resumo)

1. **Scrollbar + polish CSS** — ganho imediato, risco zero.
2. **Markdown nas bolhas** — respostas legíveis.
3. **Tools retráteis (grupo + expand)** — corta o “muro” de linhas.
4. **Timeline de blocos** — `tool → texto → tool → texto` ao vivo e no histórico.
5. **Bloco de raciocínio** — se o provedor emitir thinking; senão UI pronta + fallback ao indicador.
6. **Composer + anexos + paste** — amarra ao contrato `chat.enviar` / F1-17.

Detalhe e DoD: [05-fases-implementacao.md](05-fases-implementacao.md).

## Escopo explícito

**Dentro:** painel de chat (`PainelChat` + componentes filhos + CSS do scroll da conversa + composer).

**Fora desta onda (não misturar):** redesign da `BarraChats`, `Workspace`, `Galeria`, `TopoApp`, instalador, motor de mapa. Só tocar o necessário para o chat parecer Claude.
