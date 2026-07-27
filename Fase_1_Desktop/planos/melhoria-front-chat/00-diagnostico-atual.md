# 00 — Diagnóstico atual (código + prints)

## Prints que motivam o plano

| Print | Problema visível |
|---|---|
| Chat com ~12 tools em fila | Cada tool é uma barra completa; a conversa vira log técnico |
| Scrollbar branca grossa | Track/thumb nativos do SO/Electron sem CSS dark |
| Resposta “olhe novamente” | Parede de texto misturando narrativo + passos; sem estrutura |
| Referência Claude | Tools em **uma linha retrátil** entre trechos de texto; composer limpo |

## Onde vive o chat hoje

| Peça | Path | Estado |
|---|---|---|
| Painel | `app/src/paineis/PainelChat.tsx` + `.module.css` | lista flat: msgs → streaming → tools → pergunta → pensando |
| Tools | `app/src/componentes/CartaoTool.tsx` + `.module.css` | 1 cartão/trace, **não** expansível, **não** agrupado |
| Pensando | `app/src/componentes/IndicadorPensando.tsx` | 3 dots; **não** é balão de raciocínio |
| Pergunta | `app/src/componentes/CartaoPergunta.tsx` | ok; manter |
| Composer | embutido em `PainelChat` | textarea + Enviar/Parar |
| Tokens | `app/src/estilos/tokens.css` | tema escuro `--mf-*` ok |
| Markdown | — | **ausente** (sem `react-markdown` no `package.json`) |
| Scrollbar custom | — | **ausente** em todo `app/src` |

## Modelo de estado atual (o gargalo)

```
PainelChat
  mensagens: MensagemChat[]     // só {papel, conteudo} — sem tool_traces na UI
  streaming: string             // TODOS os deltas concatenados num único buffer
  tools: EstadoTool[]           // TODAS as tools do turno numa lista paralela
```

Ordem de render **fixa** no JSX (não cronológica):

1. bolhas históricas  
2. bolha de streaming (se houver texto)  
3. **todas** as tools  
4. pergunta / avisos / pensando  

Resultado: impossível parecer Claude enquanto `streaming` for uma string e `tools` um array paralelo.

## Backend já entrega o que a UI joga fora

| Dado | Backend | UI |
|---|---|---|
| `tool_traces` por mensagem em `chat.abrir_conversa` | sim (`repositorio.py`) | **ignorado** — `carregar()` só lê `mensagens` texto |
| `chat.enviar` com `anexos?` | contrato F1-17 / núcleo | UI **não envia** |
| `resultadoResumo` no evento `chat.tool` | chega no estado live | **nunca renderizado** |
| Thinking / reasoning do provedor | DeepSeek V4: verificar se há campo dedicado nos deltas | hoje só `chat.delta` de texto |

## Checklist de dor (mapeado ao print)

- [ ] Scrollbar dark (`.conversa` e painéis com `overflow: auto`)
- [ ] Tools colapsadas num card (resumo “N ferramentas · Xs”) com expand por item
- [ ] Fluxo intercalado live + histórico
- [ ] Markdown (tabelas, listas, negrito, código inline)
- [ ] Balão de raciocínio retrátil (quando houver conteúdo)
- [ ] Composer moderno: `+` anexo, paste imagem, chips de preview, arrastar arquivo
- [ ] Autoscroll inteligente (só se usuário está perto do fim — spec F1-02 já pedia ≤48px)

## O que **não** está quebrado (não redesenhar)

- Shell 4 colunas / divisores  
- Streaming via eventos NDJSON  
- Cancelar turno / Esc  
- `CartaoPergunta`  
- Tokens `--mf-*` e tipografia Space Grotesk / IBM Plex  
- Persistência de conversas no núcleo  
