# 03 — Componentes (tools, markdown, raciocínio, scrollbar)

## Inventário alvo

| ID / peça | Arquivo alvo | Origem |
|---|---|---|
| `grupo-tools` | `app/src/componentes/GrupoTools.tsx` (+ css) | **novo** — resume N `CartaoTool` |
| `cartao-tool` | `app/src/componentes/CartaoTool.tsx` | **refatorar** — colapsável, mostrar resultado |
| `bloco-raciocinio` | `app/src/componentes/BlocoRaciocinio.tsx` | **novo** (spec F1-16) |
| `bolha-markdown` | `app/src/componentes/BolhaMarkdown.tsx` | **novo** |
| `campo-entrada` | `app/src/componentes/CampoEntrada.tsx` | **novo** (extrair de `PainelChat`) |
| `indicador-pensando` | `IndicadorPensando.tsx` | manter como fallback pré-primeiro-evento |
| scrollbar | `app/src/estilos/scrollbar.css` (+ import em `main.tsx`) | **novo** |
| orquestração | `PainelChat.tsx` | renderiza timeline |

## 1. Scrollbar dark

Arquivo sugerido: `app/src/estilos/scrollbar.css`

```css
/* WebKit (Electron/Chromium) */
* {
  scrollbar-width: thin;                 /* Firefox */
  scrollbar-color: var(--mf-borda-forte) transparent;
}
*::-webkit-scrollbar { width: 10px; height: 10px; }
*::-webkit-scrollbar-track { background: transparent; }
*::-webkit-scrollbar-thumb {
  background: var(--mf-borda-forte);
  border-radius: 8px;
  border: 2px solid transparent;
  background-clip: content-box;
}
*::-webkit-scrollbar-thumb:hover { background: var(--mf-texto-3); background-clip: content-box; }
```

Escopo: global leve **ou** só `.conversa` / painéis com overflow — preferir global thin nos overflow containers para o print não voltar branco em outro painel.

DoD: print do chat com tema escuro **não** mostra track branco sólido.

## 2. `GrupoTools` (card retrátil)

### Colapsado (default)
- Ícone status agregado (✓ se todos ok; ✕ se algum falhou; ◐ se pendente).
- Texto: `N ferramentas` ou, se N≤3, nomes unidos por vírgula.
- Duração total (`sum(ms)` das finalizadas).
- Chevron.
- `aria-expanded`.

### Expandido
- Lista vertical dos `CartaoTool` (gap `--mf-e1`).
- Cada tool: linha resumo; click/chevron interno abre args + `resultadoResumo` (monospace, truncável com “mostrar tudo”).

### Agrupamento
- Feito pelo redutor de timeline (`tipo: "tools"`), não por heurística visual solta.

## 3. `CartaoTool` — mudanças

| Antes | Depois |
|---|---|
| Sempre aberto | Resumo + expand |
| Só args truncados | Args + resultado ao expandir |
| Sem click | `<button>` ou `<details>` acessível |
| Fora do histórico | Também renderizado a partir de `tool_traces` |

Manter `data-tool`, `data-fase`, `data-ok` para testes visuais existentes.

## 4. `BolhaMarkdown`

Dependência sugerida: `react-markdown` + `remark-gfm` (tabelas GFM — críticas para áreas ha).

Regras de segurança:
- **Sem** `rehype-raw` / HTML cru.
- Links: `rel="noreferrer"`; no Electron, preferir abrir via shell externo se já houver helper.
- Código inline/bloco com `--mf-fonte-mono`.
- Tabelas: scroll horizontal interno se estreitas; não estourar o painel.

Streaming: renderizar markdown parcial (aceitar tabelas incompletas; bibliotecas lidam ou mostrar texto até fechar fence).

CSS: classes `.md p`, `.md table`, `.md code`, `.md ul` no module — tipografia calma, sem “card dentro de card”.

## 5. `BlocoRaciocinio`

```
<details> / botão
  header: Brain/ícone + "Raciocínio" + chevron
  body: texto streaming (texto-2, fs menor)
```

Default: **colapsado** quando o turno termina; **aberto** opcional enquanto `streaming` e usuário não fechou (preferência: colapsado sempre após 1º delta de texto útil — calibrar no uso).

Se não houver evento de thinking no provedor:
- Não criar bloco vazio.
- Manter `IndicadorPensando` só enquanto `enviando && blocos.length === 0`.

Investigação pré-implementação (checklist em fase 4): ler `agente/deepseek.py` / eventos se já existe campo `reasoning` / `reasoning_content`. Se não, UI fica pronta e o núcleo ganha emissor depois (`chat.raciocinio` ou flag no delta).

## 6. Ações da mensagem (fase posterior, opcional)

Copiar markdown bruto — botão discreto sob a última bolha do turno. Não bloquear as fases 1–5.

## 7. Motion

Reusar tokens `mf-surgir` / `--mf-dur-*`. Entrada de novo grupo tools: fade curto. Respeitar `prefers-reduced-motion`.
