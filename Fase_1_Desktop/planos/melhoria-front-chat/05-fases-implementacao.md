# 05 — Fases de implementação e DoD

**Estado:** executado em 2026-07-27, fase a fase, com testes e build verdes.

## Fase 0 — Preparação (½ dia)

- [x] Confirmar contrato real de `chat.enviar` + `anexos` no núcleo (`servico.py` / schema).
- [x] Confirmar shape de `tool_traces` em `chat.abrir_conversa`.
- [x] Checar se DeepSeek/orquestrador emite reasoning (sim/não) → decide Fase 4.
- [x] Inventariar testes que quebram com refactor (`painel-chat`, `CartaoTool`, motion).

**DoD:** nota curta no PR/commit ou checklist marcado; sem UI ainda.

## Fase 1 — Scrollbar + polish mínimo (baixo risco)

- [x] `scrollbar.css` + import.
- [x] Revisar `.conversa` / overflow.
- [x] Autoscroll só se perto do fim (≤48px), conforme F1-02.

**DoD:** print do chat sem barra branca; testes existentes verdes.

## Fase 2 — Markdown nas bolhas

- [x] Dependência `react-markdown` + `remark-gfm`.
- [x] `BolhaMarkdown` para papel assistente (usuário pode ficar texto simples).
- [x] Estilos de tabela/lista/código nos tokens.

**DoD:** mensagem com `**ATP** | 3.823` renderiza negrito/tabela; sem XSS HTML.

## Fase 3 — Tools retráteis (ainda sem intercalação fina)

- [x] `GrupoTools` colapsado por padrão envolvendo a lista atual do turno.
- [x] `CartaoTool` expansível com `resultadoResumo`.
- [x] Histórico: consumir `tool_traces` ao abrir conversa (grupo + texto).

**DoD:** turno com 10 tools = **1** card colapsado na vista default; expand mostra as 10; reabrir conversa mostra traces.

## Fase 4 — Timeline intercalada

- [x] Tipo `BlocoTurno` + `aplicarEventoTimeline`.
- [x] `PainelChat` renderiza `blocos` ao vivo.
- [x] Testes de ordem: tool → delta → tool → delta.

**DoD:** com mock de eventos, DOM na ordem Claude; print real com texto entre grupos.

## Fase 5 — Raciocínio retrátil

- [x] `BlocoRaciocinio` (UI).
- [x] Se houver emissor: ligar evento.
- [x] Se **não** houver: UI morta + `IndicadorPensando` permanece; documentar gap no núcleo.

**DoD:** componente no inventário F1-16; colapsável; sem texto inventado.

## Fase 6 — Composer + anexos + paste

- [x] Extrair `CampoEntrada`.
- [x] Chips, `+`, drag-drop, paste imagem.
- [x] Wire `anexos` no `chat.enviar`.
- [x] Preview imagem; limite 20 MB; aviso se modelo sem visão.

**DoD:** colar PNG → chip → enviar → anexo no disco/`anexos` (ou path aceito pelo núcleo); testes Vitest do composer.

## Fase 7 — QA visual + regressão

- [x] `pnpm typecheck` / `test` / `build`.
- [x] axe nos novos componentes (padrão F1-16).
- [x] Passar checklist “parece Claude?” ([01-visao-claude-like.md](01-visao-claude-like.md)).
- [x] Atualizar referência cruzada em `Fase_1_Desktop/planos/README.md` (apontar esta pasta).

## Ordem e paralelismo

```
F1 (scrollbar) ──┐
F2 (markdown) ───┼──► F3 (tools card) ──► F4 (timeline) ──► F5 (raciocínio)
                 │                              │
                 └──────────────────────────────┴──► F6 (composer) pode ir em paralelo após F1
```

F6 não depende de F4; F4 depende de F3.

## Riscos

| Risco | Mitigação |
|---|---|
| Histórico sem ordem real tool/texto | Camada A estável (tools→texto); Camada B só se necessário |
| Markdown quebrando streaming parcial | testes com fences incompletos; fallback texto |
| Anexos: contrato divergente | Fase 0 lê o núcleo antes de inventar payload |
| Modelo sem visão + usuário cola print | copy honesta no chip (“anexo guardado; modelo atual é só texto”) |
| Refactor grande de `PainelChat` | fases; manter `aplicarEventoTool` puro |

## Fora de escopo (não puxar nesta onda)

- Redesign workspace/galeria/topo  
- Seletor de modelo / microfone  
- Diff estilo IDE nas tools  
- Camada B de persistência de blocos (salvo necessidade comprovada)  
- Tema claro polish (manter tokens; foco no escuro)

## Critério de pronto da onda

Usuário abre o app, manda um turno GIS pesado, e a UI:

1. não mostra muro de 12 linhas de tool;  
2. formata a resposta como documento legível;  
3. permite auditar tools sob demanda;  
4. aceita colar um print no composer;  
5. scrollbar não destoa do tema escuro.

Só então marcar esta pasta como **executada** (nota no README desta pasta + link no checklist F1-13 se aplicável).
