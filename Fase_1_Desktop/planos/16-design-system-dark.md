# F1-16 — Design system dark e animações da IA em trabalho

## Objetivo

O app tem de parecer um instrumento técnico premium, não um dashboard genérico: tema escuro por
padrão, tipografia com personalidade, superfícies calmas, e **animações que representam trabalho
real** — cada uma amarrada a um evento do sidecar ou do agente. Este documento define os tokens,
os componentes nomeados, os estados de animação e o DoD visual verificável. Ele é a fonte da
verdade visual da **interface**; o visual do **mapa** continua sendo
[`planos/01-padrao-imap-harmonia.md`](../../planos/01-padrao-imap-harmonia.md).

## Estado atual vs alvo

| Item | Atual | Alvo |
|---|---|---|
| Tokens, tema, fontes | **existem e são consumidos** (C3/C4) pelo renderer (C1/C5) | `app/src/estilos/tokens.css` + fontes embarcadas |
| Eventos NDJSON que alimentam animação | **`job.progresso`, `chat.delta`, `chat.tool`, `job.artefato_parcial`, `workspace.mudou` emitidos** | falta só `mapspec.atualizado` |
| `job.artefato_parcial` (preview em construção) | **implementado** (M8) — 4 tipos, caminho relativo | `nucleo/.../artefatos.py` + emissão no pipeline |
| `prefers-reduced-motion` | **respeitado** em `tokens.css` (≤ 80 ms, só opacidade/cor) | respeitado |

**Regra de honestidade:** enquanto o núcleo não emitir um evento, a animação correspondente
**não existe na UI**. Não substitua por spinner infinito nem por progresso simulado por
`setInterval` (AP-07). Se a etapa não é observável, mostre estado estático ("gerando…") sem barra
de porcentagem.

## Dependências

| Precisa de | Estado |
|---|---|
| M3 — shell Electron + React | **parcial** — `AppShell` e `barra-progresso-job` prontos (C1–C6) |
| Emissor de `job.progresso` no núcleo | **existe** (A9, núcleo v0.4.0) |
| `chat.delta` / `chat.tool` | **existem** (M7) |
| `job.artefato_parcial` | **existe** (M8) — contrato abaixo |

## Contratos — tokens

### Cor (tema escuro, default)

`app/src/estilos/tokens.css`, no `:root`. Tema claro em `[data-tema="claro"]`, opcional e nunca
default (D15 / AP-08).

```css
:root {
  /* superfícies — frias, sem preto puro */
  --mf-bg:            #0B0E11;
  --mf-superficie-1:  #12161B;   /* painéis */
  --mf-superficie-2:  #181D24;   /* cartões, mensagens */
  --mf-superficie-3:  #1F262F;   /* hover, campos */
  --mf-borda:         #262E38;
  --mf-borda-forte:   #38424F;

  /* texto */
  --mf-texto:         #E8EDF2;
  --mf-texto-2:       #A6B2C0;
  --mf-texto-3:       #6C7A8A;   /* metadados, timestamps */

  /* acento — jade; escolhido por não colidir com a semântica do mapa
     (amarelo = perímetro, verde hachurado = AVN, magenta = AC, laranja = AUAS) */
  --mf-acento:        #35C79A;
  --mf-acento-forte:  #57E0B4;
  --mf-acento-fraco:  rgba(53, 199, 154, 0.14);

  /* semântica de status */
  --mf-ok:            #35C79A;
  --mf-aviso:         #E8A33D;
  --mf-erro:          #F2555A;
  --mf-info:          #5AA9E6;

  /* raio e sombra — uma sombra, nunca pilha de sombras */
  --mf-raio-1: 6px;  --mf-raio-2: 10px;  --mf-raio-3: 14px;
  --mf-sombra: 0 1px 2px rgba(0,0,0,.4), 0 8px 24px rgba(0,0,0,.24);

  /* espaçamento — base 4 */
  --mf-e1: 4px; --mf-e2: 8px; --mf-e3: 12px; --mf-e4: 16px;
  --mf-e5: 24px; --mf-e6: 32px; --mf-e7: 48px;
}
```

Proibições de cor, verificáveis por lint de CSS:

| Proibido | Motivo |
|---|---|
| `#000000` como fundo de painel | preto puro em OLED serrilha o texto e mata a hierarquia |
| Gradiente roxo/violeta de marca | clichê de IA genérica |
| `box-shadow` com mais de duas camadas | ruído; use borda de 1 px |
| Cor solta fora dos tokens em componente | impede o tema claro e a auditoria de contraste |
| Emoji como ícone de interface | ícone é `lucide-react`; emoji fica para conteúdo do usuário |

### Tipografia (D15)

Três famílias, **embarcadas no pacote** (`app/src/estilos/fontes/`), servidas por `@font-face`
com `font-display: block`. Nenhuma requisição a CDN — o app precisa abrir offline e não vaza
navegação do usuário.

| Papel | Família | Licença | Uso |
|---|---|---|---|
| Display / marca | **Space Grotesk** | OFL | nome do produto, títulos de tela, números grandes de destaque |
| Interface / corpo | **IBM Plex Sans** | OFL | tudo o mais |
| Monoespaçada | **IBM Plex Mono** | OFL | hectares, coordenadas, códigos de erro, JSON do `MapSpec`, logs |

```css
:root {
  --mf-fonte-display: "Space Grotesk", ui-sans-serif, sans-serif;
  --mf-fonte-ui:      "IBM Plex Sans", ui-sans-serif, sans-serif;
  --mf-fonte-mono:    "IBM Plex Mono", ui-monospace, monospace;

  --mf-fs-hero:  40px/1.1;   /* marca no login e no onboarding */
  --mf-fs-t1:    22px/1.25;
  --mf-fs-t2:    17px/1.3;
  --mf-fs-corpo:  14px/1.55;
  --mf-fs-peq:    12px/1.45;
  --mf-fs-micro:  11px/1.4;

  --mf-tracking-display: -0.02em;
}
```

Regras vinculantes:

- **Nunca** use `Inter`, `Roboto`, `Arial`, `Helvetica` ou `system-ui` como primeira opção da
  pilha. Elas só aparecem como fallback depois das embarcadas.
- Todo número em hectare usa `--mf-fonte-mono` com `font-variant-numeric: tabular-nums`, formato
  pt-BR e 4 casas (`3.823,9033`). Colunas de números **alinham**.
- O nome do produto aparece em `--mf-fs-hero` na primeira viewport do login e do onboarding — é o
  sinal hero da marca. Em nenhum outro lugar.

### Movimento

```css
:root {
  --mf-dur-1: 120ms;  /* hover, foco */
  --mf-dur-2: 180ms;  /* entrada de item, colapso */
  --mf-dur-3: 260ms;  /* troca de painel, crossfade de preview */
  --mf-dur-4: 420ms;  /* transição de tela (login → app) */

  --mf-ease-saida:  cubic-bezier(.2,.8,.2,1);
  --mf-ease-ambos:  cubic-bezier(.4,0,.2,1);
  --mf-ease-entrada: cubic-bezier(.4,0,1,1);
}

@media (prefers-reduced-motion: reduce) {
  :root { --mf-dur-1: 0ms; --mf-dur-2: 0ms; --mf-dur-3: 0ms; --mf-dur-4: 0ms; }
  /* transições de opacidade sobrevivem, limitadas a 80ms; nada translada, nada escala */
}
```

O Electron precisa espelhar a preferência do sistema: `nativeTheme` e a media query já cobrem
Windows ("Mostrar animações no Windows" em Facilidade de Acesso).

## Contratos — eventos que alimentam as animações

### Já especificados, ainda não emitidos

| Evento | Dados | Quem emite | Estado |
|---|---|---|---|
| `job.progresso` | `{etapa, pct, item?}` | `motores/gerar.py` | **implementado** (A9) — emitido ao concluir cada etapa |
| `job.log` | `{linha}` | núcleo | a implementar |
| `chat.delta` | `{texto}` | agente | a implementar (M7) |
| `chat.tool` | `{trace_id, tool, fase:"inicio"\|"fim", args_resumo?, resultado_resumo?, ms?, ok?}` | agente | a implementar (M7) |
| `mapspec.atualizado` | `{id, versao, diff}` | núcleo | a implementar |
| `aviso` | `{codigo, mensagem}` | núcleo | a implementar |

`item` é novo em `job.progresso` e existe para a animação de construção: quando a etapa é
`resolvendo_camadas_locais` ou `baixando_externas`, `item` traz o `camadas[].id` que acabou de
ficar pronto.

### Contrato — `job.artefato_parcial`

**Implementado no M8.** Vocabulário e validação em `nucleo/mapasfacil_nucleo/artefatos.py`;
emissão pelo `RastreadorProgresso`, que já é o canal de eventos do job:

```json
{"v":1,"id":"01J…","tipo":"evt","evento":"job.artefato_parcial",
 "dados":{"tipo":"camada","camada_id":"avn","caminho":"SHP/AVN.shp","etapa":"resolvendo_camadas_locais","ordem":30}}

{"v":1,"id":"01J…","tipo":"evt","evento":"job.artefato_parcial",
 "dados":{"tipo":"tabela_png","caminho":"recursos/tabela_quantitativos.png","etapa":"gerando_tabela"}}

{"v":1,"id":"01J…","tipo":"evt","evento":"job.artefato_parcial",
 "dados":{"tipo":"preview_png","caminho":"Mapas/.preview/parcial_07.png","etapa":"aplicando_layout","pct":70}}
```

| `tipo` | Significado | Origem no núcleo |
|---|---|---|
| `camada` | shapefile materializado em `SHP/` | `camadas/materializar.py` |
| `tabela_png` | PNG da tabela pronto | `quantitativos/png_tabela.py` |
| `preview_png` | rasterização intermediária do mapa | `motores/nativo.py`, ao fim de cada etapa de desenho |
| `pdf` | PDF final | `motores/gerar.py` |

Regras: caminho **sempre relativo à pasta do projeto**; nunca caminho absoluto (vaza disco do
usuário) — `artefatos.montar_dados` recusa absoluto e `..`, e a UI descarta o evento se algum
passar (`ehJobArtefatoParcial`). O renderer lê o arquivo **pelo núcleo**, nunca direto (regra de
fronteira 1 de [F1-01](01-arquitetura.md)): o método é **`artefato.ler`**, que devolve
`{caminho, mime, tamanho, base64}` para PNG/JPG dentro do workspace, com teto de 8 MB.

As rasterizações intermediárias saem em `Mapas/.preview/parcial_NN.png` (`artefatos.PASTA_PREVIEW`),
a 72 dpi — é preview, não entrega. Sem canal de eventos, nada é rasterizado: `gerar_mapa` chamado
como biblioteca não paga por imagem que ninguém vê.

**Fase 1 continua valendo:** quando ainda não chegou `preview_png`, o `painel-preview` mostra o
*esqueleto de camadas* derivado do `MapSpec` e acende cada linha quando `job.progresso` traz o
`item` correspondente. Isso é progresso real, com granularidade menor — não é loader falso.

## Layout principal e IDs de componente

IDs estáveis. Testes de UI e este documento referenciam por eles; renomear exige atualizar os
dois lugares no mesmo commit.

```
┌─ topo-app ──────────────────────────────────────────────────────────────────────────┐
│ marca  ·  breadcrumb-projeto            conta-menu   doctor-chip   janela-controles  │
├─ barra-chats ─┬─ painel-workspace ─┬─ painel-chat ────────────┬─ painel-direito ─────┤
│ + novo chat   │ 📁 Harmonia        │  mensagens               │ [abas]               │
│ ──────────    │ ▾ Arquivo Projeto  │  ┌───────────────────┐   │  preview · galeria   │
│ busca-chats   │   ▪ ATP.shp        │  │ msg-usuario       │   │  · mapspec · checks  │
│ ──────────    │     1 feição       │  └───────────────────┘   │                      │
│ Dinâmica 2026 │     3.823,9033 ha  │  ┌───────────────────┐   │  painel-preview      │
│ Tipologia…    │   ▪ AVN.shp        │  │ msg-agente        │   │  ┌────────────────┐  │
│ Embargos…     │   ▪ AUAS.shp       │  │  cartao-tool ×N   │   │  │                │  │
│               │ ▾ Mapas/           │  │  bloco-raciocinio │   │  │  mapa em       │  │
│               │                    │  └───────────────────┘   │  │  construção    │  │
│               │ ────────────────   │  ┌───────────────────┐   │  └────────────────┘  │
│               │ doctor-resumo      │  │ barra-progresso-  │   │  linha-versoes       │
│               │ ArcMap ✓ IA ✓      │  │ job (10 etapas)   │   │  ◀ v1  v2  v3 ▶      │
│               │ SEMA ✓ Planet ✓    │  └───────────────────┘   │  lista-artefatos     │
│               │                    │  [ campo-entrada    ] ▶  │                      │
└───────────────┴────────────────────┴──────────────────────────┴──────────────────────┘
```

| ID | Componente | Arquivo |
|---|---|---|
| `topo-app` | barra superior; marca, projeto, conta, doctor | `app/src/layout/TopoApp.tsx` |
| `barra-chats` | histórico de conversas, busca, novo chat | `app/src/paineis/BarraChats.tsx` |
| `painel-workspace` | árvore da pasta com metadados inline | `app/src/paineis/Workspace.tsx` |
| `painel-chat` | conversa estilo Cursor | `app/src/paineis/Chat.tsx` |
| `cartao-tool` | uma tool call: nome, args resumidos, duração, resultado | `app/src/componentes/CartaoTool.tsx` |
| `bloco-raciocinio` | streaming do raciocínio, colapsável | `app/src/componentes/BlocoRaciocinio.tsx` |
| `barra-progresso-job` | 10 etapas de `mapa.gerar` | `app/src/componentes/BarraProgressoJob.tsx` |
| `painel-direito` | abas: preview, galeria, mapspec, checks | `app/src/paineis/PainelDireito.tsx` |
| `painel-preview` | mapa em construção / PDF final | `app/src/paineis/Preview.tsx` |
| `painel-galeria` | grade de modelos ([F1-15](15-galeria-de-modelos.md)) | `app/src/paineis/Galeria.tsx` |
| `painel-mapspec` | JSON legível + diff entre versões | `app/src/paineis/MapSpecView.tsx` |
| `painel-checks` | HARD/SOFT com explicação | `app/src/paineis/Conformidade.tsx` |
| `linha-versoes` | ◀ v1 v2 v3 ▶ | `app/src/componentes/LinhaVersoes.tsx` |
| `doctor-resumo` / `doctor-chip` | estado do ambiente, discreto | `app/src/componentes/Doctor*.tsx` |
| `campo-entrada` | textarea + anexos + enviar/cancelar | `app/src/componentes/CampoEntrada.tsx` |
| `tela-login` | primeira viewport, marca hero ([F1-14](14-auth-e-conta.md)) | `app/src/telas/Login.tsx` |

Painéis redimensionáveis com estado persistido em `config.json`. `painel-chat` nunca some.
Alvo de janela: **1280×800 ou maior**. Mobile e tablet não são alvo (AP: não gaste tempo com
breakpoints de telefone).

## As animações, uma a uma

Cada animação declara o **evento real** que a liga e a que a desliga. Sem evento → sem animação.

### A1 — Pensando (`bloco-raciocinio`)

| Aspecto | Definição |
|---|---|
| Liga | turno enviado (`chat.enviar` despachado) |
| Desliga | primeiro `chat.delta` de texto visível |
| Forma | três pontos em `--mf-texto-3` com opacidade oscilando 0,35 ↔ 1, 1.400 ms, defasagem de 160 ms; ao lado, o rótulo "pensando" em `--mf-fs-peq` |
| Por que assim | DeepSeek com raciocínio alto leva 10–40 s; sem sinal o app parece travado |
| Reduced-motion | pontos estáticos, só o rótulo |

### A2 — Streaming de tokens (`painel-chat`)

| Aspecto | Definição |
|---|---|
| Liga | `chat.delta` |
| Desliga | fim do turno |
| Forma | texto acrescentado no fim, sem re-render do bloco inteiro; cursor de 2 px em `--mf-acento` piscando 1 Hz; autoscroll só se o usuário está a ≤ 48 px do fim |
| Proibido | animar cada caractere com `transition`; simular digitação com atraso artificial quando o texto já chegou inteiro |

### A3 — Tool aparecendo (`cartao-tool`)

| Aspecto | Definição |
|---|---|
| Liga | `chat.tool` com `fase:"inicio"` |
| Atualiza | `chat.tool` com `fase:"fim"` |
| Forma | cartão entra com `translateY(6px) → 0` + opacidade 0 → 1 em `--mf-dur-2` / `--mf-ease-saida`; enquanto pendente, o ícone da tool gira 1 volta a cada 1.200 ms; ao terminar, o giro para, aparece a duração em `--mf-fonte-mono` (`1,2 s`) e um `✓`/`✕` |
| Conteúdo | nome da tool + args resumidos (uma linha, ≤ 80 caracteres) + resultado resumido; expandir mostra o objeto completo |
| Falha | borda esquerda em `--mf-erro`, código do erro em mono |

### A4 — Progresso do job (`barra-progresso-job`)

| Aspecto | Definição |
|---|---|
| Liga | `job.progresso` |
| Desliga | resposta final de `mapa.gerar` |
| Forma | barra segmentada com as **10 etapas** de [F1-01](01-arquitetura.md#etapas-reportadas-em-jobprogresso); segmento concluído preenche em `--mf-dur-2`; segmento ativo tem varredura de luz de 1.600 ms; nome da etapa em português ao lado, com o `item` quando existe (`baixando externas · lim_municipios_mt`) |
| Proibido | barra indeterminada quando há `pct`; `pct` interpolado por timer entre eventos |

### A5 — Mapa sendo construído (`painel-preview`)

A animação-assinatura do produto. **Duas fases, e o plano é explícito sobre qual existe quando.**

| Fase | Requer | Comportamento |
|---|---|---|
| **Fase 1 — esqueleto** (M4/M7, sem contrato novo) | `job.progresso` com `item` | o preview mostra a pilha de camadas do `MapSpec`, em ordem de desenho, cada uma cinza; quando `item` bate com o `camadas[].id`, a linha acende em `--mf-acento` (opacidade 0,3 → 1 em `--mf-dur-2`). Molduras da tabela, do minimapa e da legenda acendem nas etapas correspondentes |
| **Fase 2 — artefato real** (M8, **feita**) | `job.artefato_parcial` | cada `preview_png` entra com crossfade de `--mf-dur-3` sobre a anterior (duas camadas empilhadas); `tabela_png` anuncia a tabela pronta; `camada` acende a linha correspondente mesmo sem `item`; `pdf` marca o estado final |

A Fase 2 nunca é simulada: sem `preview_png` o painel fica na Fase 1, e a imagem só aparece depois
que `artefato.ler` devolve os bytes. O contorno real por camada (desenhar o shapefile
materializado no palco) fica para quando o preview virar render vetorial — hoje o `camada` acende
a linha da pilha, que é o que o dado sustenta.

### A6 — Microinterações

| Interação | Forma | Evento |
|---|---|---|
| Abrir pasta | itens da árvore entram com opacidade + `translateY(4px)`, defasagem 24 ms, **máximo 12 itens** animados; o resto aparece direto | resposta de `workspace.abrir` |
| Seleção na galeria | cartão vai a `scale(1.02)` e ganha borda `--mf-acento` em `--mf-dur-1`; preview do painel direito faz crossfade | clique |
| Troca de versão `◀ v1 v2 ▶` | crossfade do preview em `--mf-dur-3`; as linhas do diff que mudaram piscam uma vez em `--mf-acento-fraco` | `mapspec.atualizado` ou clique |
| Arquivo novo na pasta | linha entra na árvore com realce que decai em 2 s | `workspace.mudou` |
| Doctor mudou de estado | chip troca de cor em `--mf-dur-2`, sem chamar atenção | `doctor.rodar` |
| Cancelar turno (`Esc`) | cursor some, cartões pendentes viram "cancelado" em `--mf-texto-3` | `chat.cancelar` |

## Acessibilidade

- Contraste **AA** para todo texto sobre `--mf-bg`, `--mf-superficie-1` e `--mf-superficie-2`.
  `--mf-texto-3` só para texto ≥ 12 px que não carrega informação única.
- Estado **nunca** só por cor: check HARD/SOFT tem ícone + texto; tool falhada tem `✕` + código.
- Foco visível em todos os interativos: contorno de 2 px em `--mf-acento`, deslocado 2 px.
- Navegação completa por teclado; ordem de tabulação segue a ordem visual dos painéis.
- Leitor de tela: `painel-chat` é `role="log"` com `aria-live="polite"`; `barra-progresso-job` é
  `role="progressbar"` com `aria-valuenow`; `cartao-tool` anuncia início e fim uma vez cada.
- Atalhos: `Ctrl+O` pasta · `Ctrl+N` novo chat · `Ctrl+Enter` enviar · `Esc` cancelar turno ·
  `Ctrl+K` paleta · `Ctrl+F` buscar em chats · `Ctrl+,` preferências · `F1` doctor.

## Tarefas agentáveis

- [x] `app/src/estilos/tokens.css` — todos os tokens acima, `:root` escuro + `[data-tema="claro"]`
- [x] `app/src/estilos/fontes/` — Space Grotesk, IBM Plex Sans, IBM Plex Mono (woff2) + `@font-face`
- [x] `app/src/estilos/reset.css`
- [x] `app/src/motion/tokens.ts` — durações e easings espelhando o CSS, para animação em JS
- [x] `app/src/motion/useReducedMotion.ts`
- [ ] Componentes da tabela de IDs, um arquivo por linha
- [x] `nucleo/mapasfacil_nucleo/motores/gerar.py` — **emitir `job.progresso`** nas 10 etapas,
      com `item` nas etapas de camada
- [ ] `nucleo/mapasfacil_nucleo/protocolo.py` — registrar `job.artefato_parcial` no vocabulário
- [ ] `nucleo/mapasfacil_nucleo/motores/gerar.py` — emitir `job.artefato_parcial` (M8)
- [~] `app/src/estado/eventos.ts` — assinatura pronta + `peso`/`pctAoConcluir`; o store existe só para `job.progresso` (`app/src/estado/progressoJob.ts`)
- [x] `app/tests/visual/` — tema default, contraste AA/tokens + axe, reduced-motion ≤ 80 ms,
      layout 1280×800, hectares mono (`tests/visual/*.test.tsx`)

## Critérios de aceite (DoD visual verificável)

Cada item é um comando ou assert, não uma opinião:

- [x] **Dark é o default:** app recém-instalado, sem `config.json`, abre com
      `document.documentElement.dataset.tema === "escuro"`
      (`app/tests/visual/tema-default.test.tsx`)
- [x] `--mf-bg` no tema escuro resolve para `#0b0e11` (mesmo assert)
- [x] `grep -rniE "inter|roboto|arial|helvetica|system-ui" app/src/estilos/tokens.css` só aparece
      **depois** de uma família embarcada na pilha
- [x] `grep -rn "https://fonts\.\|cdn\." app/src/` não retorna nada — zero requisição externa de fonte
- [~] **≥ 3 animações ligadas a estado real**, provadas por teste com eventos NDJSON injetados:
      A2 (streaming), A3 (tool), A4 (progresso). **A4 está provada**
      (`app/tests/barra-progresso-job.test.tsx`); A2 e A3 esperam `chat.delta`/`chat.tool` (M7).
      Cada teste emite o evento fake e assere a classe ou o atributo resultante — nenhum usa
      timer sozinho
- [x] `grep -rn "setInterval" app/src/motion/ app/src/componentes/Barra*` não retorna nada
      (progresso não é simulado)
- [ ] **Preview reage à geração:** teste emite `job.progresso` com `item:"avn"` e assere que a
      linha `preview-camada-avn` mudou de estado
- [x] **Reduced motion:** com `prefers-reduced-motion: reduce`, nenhum elemento tem
      `animation-duration` ou `transition-duration` maior que 80 ms
      (`app/tests/visual/reduced-motion.test.tsx`)
- [~] Contraste: pares de token WCAG AA + `axe-core` sem violação (exceto color-contrast no jsdom)
      em app vazio / com job / com erro — `app/tests/visual/contraste.test.tsx`; login é M5
- [~] Janela de 1280×800 não produz scroll horizontal — `app/tests/visual/layout-e-numeros.test.tsx`
- [x] Nenhum emoji em componente de interface: `grep -rnP "[\x{1F300}-\x{1FAFF}]" app/src/componentes/` vazio
- [x] Números em hectare renderizam em `--mf-fonte-mono` com `tabular-nums` —
      `app/tests/visual/layout-e-numeros.test.tsx`

## Fora de escopo

- Temas customizáveis pelo usuário além de escuro/claro.
- Ilustrações, mascote, onboarding animado longo.
- Responsividade para telefone e tablet.
- Animação de transição entre rotas com biblioteca pesada de física.
- Skeleton screens genéricos onde já existe evento de progresso real.

## Anti-padrões

| Não faça | Por quê |
|---|---|
| Spinner infinito enquanto o núcleo não reporta nada | AP-07: mente sobre o estado do sistema |
| `pct` interpolado por timer entre dois `job.progresso` | inventa progresso que não existe |
| "Digitação" artificial de texto já recebido | atrasa o usuário para parecer inteligente |
| Glow roxo, blur pesado, vidro fosco em tudo | clichê e custa GPU no PC do técnico |
| Animar 300 itens da árvore ao abrir uma pasta grande | trava; o limite é 12 |
| Tema claro como default, ou `@media (prefers-color-scheme)` decidindo sozinho | AP-08/D15: escuro é o default do produto |
| Ícone por emoji | inconsistente entre versões do Windows |
| Cor fora dos tokens dentro de um componente | quebra tema claro e auditoria de contraste |
| Fingir a Fase 2 do A5 antes do `job.artefato_parcial` existir | AP-07 |
