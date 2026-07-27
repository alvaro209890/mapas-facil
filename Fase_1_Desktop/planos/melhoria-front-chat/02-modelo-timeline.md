# 02 — Modelo de timeline (intercalação)

## Problema

Hoje:

```ts
streaming: string
tools: EstadoTool[]
```

Render: `[texto streaming][lista tools]`.  
Claude precisa: `[bloco][bloco][bloco]…` na ordem dos eventos.

## Modelo proposto

```ts
type BlocoTurno =
  | { tipo: "texto"; id: string; markdown: string; streaming?: boolean }
  | { tipo: "tools"; id: string; tools: EstadoTool[]; colapsado?: boolean }
  | { tipo: "raciocinio"; id: string; texto: string; streaming?: boolean; colapsado?: boolean }
  | { tipo: "pergunta"; id: string; dados: DadosChatPergunta };

type TurnoAoVivo = {
  conversationId: string;
  blocos: BlocoTurno[];
};
```

Histórico (após `chat.abrir_conversa`):

```ts
type MensagemChat = {
  message_id?: string;
  papel: "usuario" | "assistente" | string;
  conteudo: string;
  seq?: number;
  cancelada?: boolean;
  tool_traces?: EstadoTool[];   // JÁ vem do núcleo — passar a consumir
  anexos?: AnexoResumo[];       // quando UI/núcleo expuserem
};
```

Para mensagens antigas **sem** timestamps por delta: se só houver `conteudo` + `tool_traces[]`, renderizar:

1. grupo de tools (se houver traces)  
2. texto markdown  

Isso já melhora o histórico. Intercalação fina no histórico só existe se no futuro o núcleo gravar **blocos ordenados** (fase opcional — ver abaixo).

## Redutor live (eventos → blocos)

Regras:

| Evento | Ação no array `blocos` |
|---|---|
| thinking delta (se existir) | append/atualiza bloco `raciocinio` aberto; senão cria um |
| `chat.delta` (texto) | se último bloco é `texto` streaming → concatena; senão push novo `texto` |
| `chat.tool` fase `inicio` | se último bloco é `tools` → adiciona tool; senão push novo `tools` |
| `chat.tool` fase `fim` | atualiza tool pelo `trace_id` dentro do bloco `tools` que a contém |
| `chat.pergunta` | push/`replace` bloco `pergunta` |
| fim do turno (`chat.enviar` resolve) | `carregar()`; limpar turno ao vivo |

Pseudocódigo:

```
ao delta(texto):
  se ultimo?.tipo === "texto" && ultimo.streaming:
    ultimo.markdown += texto
  senão:
    blocos.push({ tipo:"texto", markdown:texto, streaming:true })

ao tool(inicio):
  se ultimo?.tipo === "tools":
    ultimo.tools.push(nova)
  senão:
    blocos.push({ tipo:"tools", tools:[nova] })
```

Isso produz naturalmente: `tools → texto → tools → texto`.

## Persistência — duas camadas

### Camada A (obrigatória nesta onda) — só frontend

- Live: timeline correta.
- Histórico: `tool_traces` + `conteudo` (tools depois texto, ou tools antes texto — escolher **tools → texto** como default estável, documentado).
- Sem migração de banco.

### Camada B (opcional / follow-up núcleo)

Gravar `blocos_json` na mensagem assistente (ou tabela `message_blocks`) com ordem real.

Só vale se DeepSeek/orquestrador emitir texto **entre** tools com frequência. Avaliar depois da Camada A em uso real.

## Componente de render

```
TurnoAssistente
  for bloco in blocos:
    raciocinio → <BlocoRaciocinio />
    tools      → <GrupoTools />
    texto      → <BolhaMarkdown />
    pergunta   → <CartaoPergunta />
```

`PainelChat` deixa de renderizar `streaming` e `tools` como irmãos soltos; passa a renderizar `blocos`.

## Compatibilidade de testes

- Manter `aplicarEventoTool` puro (já testado).
- Novo: `aplicarEventoTimeline(blocos, evento) → blocos` com testes unitários de intercalação.
- Atualizar `tests/painel-chat.test.tsx` para assertir ordem DOM (`data-bloco`).

## IDs estáveis (a11y / testes)

| Elemento | `id` / `data-*` |
|---|---|
| lista de blocos do turno | `data-turno="ao-vivo"` |
| bloco | `data-bloco={tipo}` + `data-bloco-id` |
| grupo tools | `id="grupo-tools-{id}"` |
| raciocínio | `id="bloco-raciocinio"` (já reservado em F1-16) |
| composer | `id="campo-entrada"` (manter) |
