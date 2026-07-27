# 06 — Inventário de arquivos

Referência do que foi criado e modificado na execução de 2026-07-27.

## Criar

| Path | Fase |
|---|---|
| `app/src/estilos/scrollbar.css` | 1 |
| `app/src/componentes/BolhaMarkdown.tsx` (+ `.module.css`) | 2 |
| `app/src/componentes/GrupoTools.tsx` (+ `.module.css`) | 3 |
| `app/src/componentes/BlocoRaciocinio.tsx` (+ `.module.css`) | 5 |
| `app/src/componentes/CampoEntrada.tsx` (+ `.module.css`) | 6 |
| `app/src/chat/timeline.ts` (redutor puro `aplicarEventoTimeline`) | 4 |
| `app/tests/timeline.test.ts` | 4 |
| `app/tests/campo-entrada.test.tsx` | 6 |

## Modificar

| Path | Fase | O quê |
|---|---|---|
| `app/src/main.tsx` | 1 | import scrollbar |
| `app/src/paineis/PainelChat.tsx` | 3–6 | timeline, markdown, CampoEntrada, tool_traces |
| `app/src/paineis/PainelChat.module.css` | 1–6 | composer some; overflow/scroll |
| `app/src/componentes/CartaoTool.tsx` (+ css) | 3 | expand + resultado |
| `app/tests/painel-chat.test.tsx` | 3–4 | asserts novos |
| `app/package.json` | 2 | `react-markdown`, `remark-gfm` |

## Possível núcleo (só se Fase 0 exigir)

| Path | Quando |
|---|---|
| handlers `chat.enviar` / anexos | payload UI ≠ contrato |
| `agente/deepseek.py` / eventos | emitir raciocínio (Fase 5) |
| `conversas/repositorio.py` | Camada B blocos (follow-up) |

## Não tocar nesta onda

- `BarraChats.*`, `Workspace.*`, `Galeria.*`, `TopoApp.*`, `AppShell.tsx` (exceto se slot do rodapé do chat precisar de 1 linha)
- `dist/`, `node_modules/`, instalador

## Specs relacionadas (leitura)

- `planos/02-ui-chat-e-workspace.md` — comportamento chat
- `planos/16-design-system-dark.md` — A1/A3, IDs, tokens
- `planos/17-persistencia-de-conversas.md` — anexos + tool_traces
- `planos/06-agente-eng-florestal.md` — traces reais
