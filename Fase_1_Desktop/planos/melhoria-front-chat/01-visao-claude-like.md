# 01 — Visão alvo (chat estilo Claude)

## Experiência em uma frase

O assistente **trabalha em público**: mostra o que leu/fez em cartões curtos e retráteis, escreve trechos formatados entre as ações, e o usuário manda texto **ou** arquivos/imagens pelo mesmo composer — sem parecer um terminal de log.

## Fluxo alvo (turno)

```
[usuário]  mensagem (+ chips de anexos se houver)
[assistente]
  ▸ Raciocínio (opcional, colapsado)          ← BlocoRaciocinio
  ▸ Usou 3 ferramentas · 0,4 s          ▾    ← GrupoTools (colapsado)
      ├ listar_arquivos {...}  1 ms ✓
      ├ inspecionar_shapefile  12 ms ✓
      └ ler_recibo_car         220 ms ✓
  texto markdown formatado…                   ← BolhaMensagem
  ▸ Usou 1 ferramenta · 68 s            ▾    ← outro grupo / item
  mais texto markdown…
  [ações: copiar]                             ← opcional fase posterior
[composer]  [+]  textarea multilinha  [enviar]
```

Referência visual: print Claude — **uma linha** por ação (“Editado X, usado Y”), chevron para expandir, texto limpo entre ações, composer arredondado integrado ao dark.

## Princípios

1. **Densidade honesta** — tools existem e são auditáveis; default = colapsado, não escondido.
2. **Timeline, não painéis paralelos** — a ordem na tela = ordem dos eventos.
3. **Formatação de resposta = produto** — markdown não é “nice to have”; sem ele o técnico não lê tabelas de área.
4. **Composer é superfície de trabalho** — anexo e paste são first-class; não modal separado na v1.
5. **Tokens existentes** — reusar `--mf-*`; não inventar tema roxo/glow/pills genéricos.
6. **Honestidade de animação (AP-07)** — nada de spinner infinito; estado vem de evento.

## Anatomia visual (alvo)

### Bolha assistente
- Fundo `--mf-superficie-2`, borda esquerda `--mf-acento` (já existe).
- Conteúdo via renderer markdown (não `pre-wrap` cru).
- Tipografia: UI para prosa; mono só em código / nomes de tool / paths.

### Grupo de tools (retrátil)
- **Colapsado:** ícone ✓/◐/✕ + resumo humano (`Usou N ferramentas` ou nomes curtos) + duração total + chevron.
- **Expandido:** lista das tools; cada uma ainda expansível para args + `resultadoResumo`.
- Agrupamento: tools **consecutivas** sem texto entre elas viram **um** grupo. Texto no meio quebra o grupo (intercalação Claude).

### Raciocínio
- Card fino, tipografia `--mf-texto-2`, colapsado por padrão.
- Rótulo: “Raciocínio” / “Pensando…” enquanto streama.
- Se o provedor **não** emitir thinking: não inventar texto; manter só `IndicadorPensando` no início do turno.

### Composer
- Container único arredondado (`--mf-raio-3`), borda `--mf-borda`, hover/focus `--mf-borda-forte` / acento suave.
- Esquerda: botão `+` (file picker).
- Centro: textarea auto-grow (min 2 / max ~8 linhas).
- Direita: enviar (ícone ou botão compacto); vira **Parar** durante o turno.
- Acima do textarea (dentro do container): chips de anexos com preview/thumbnail + remover.
- Paste de imagem → vira anexo `image/png|jpeg|webp` no rascunho.

### Scrollbar
- Track quase invisível (`--mf-superficie-1`), thumb `--mf-borda-forte` → hover `--mf-texto-3`.
- Aplicar em `.conversa` e, se possível, regra global suave para painéis com overflow (workspace/galeria) — mesma família visual.

## O que deliberadamente **não** copiar do Claude/Cursor

| Evitar | Motivo |
|---|---|
| Barra de branch/PR/`Criar PR` no rodapé | Produto é GIS, não IDE |
| Diff `+N −M` nas tools | Tools GIS não são edits de arquivo (salvo futuro); usar duração + ✓ |
| Microfone / seletor de modelo no composer v1 | Fora do escopo; modelo já é fixo no núcleo |
| Cards decorativos / badges flutuantes | F1-16 / regras de design do repo |

## Critério “parece Claude?”

Um revisor abre um turno com 8+ tools e:

1. Na vista default **não** vê 8 barras; vê ≤2 grupos colapsados + texto formatado.
2. Expande um grupo e audita args/resultado.
3. Vê texto **entre** grupos se o agente escreveu entre chamadas.
4. Scrollbar não “grita” branco.
5. Cola um PNG no composer e vê chip antes de enviar.
