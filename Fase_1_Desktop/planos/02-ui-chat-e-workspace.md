# F1-02 — Interface, chat e workspace de pasta

## Objetivo

Especificar a interface do app: os painéis, o comportamento do chat estilo Cursor, a árvore da
pasta conectada, a galeria como segunda entrada, o preview do mapa sendo construído e todos os
estados vazios/erro. O visual (tokens, tipografia, animações) vive em
[F1-16](16-design-system-dark.md); a galeria em [F1-15](15-galeria-de-modelos.md); o histórico de
conversas em [F1-17](17-persistencia-de-conversas.md); o login em [F1-14](14-auth-e-conta.md).
Este documento é o que amarra os quatro num layout.

## Estado atual vs alvo

| Item | Atual | Alvo |
|---|---|---|
| `Fase_1_Desktop/app/` | **M3 fechado** — C1–C11, `pnpm typecheck/test/build` verdes (71 testes) | app Electron + React completo (falta conteúdo M4/M6/M7) |
| Componentes de UI | **shell + workspace + paleta** — `AppShell`, `TopoApp`, `Divisor`, `BarraProgressoJob`, `Workspace`, `DoctorResumo`, `EstadoVazio`, `PaletaComandos`, `Preferencias`; chat, galeria e preview seguem vazios | tabela de IDs abaixo |
| Eventos que a UI consome | **só `job.progresso`** é emitido pelo núcleo, e é o único consumido | 8 eventos ([F1-01](01-arquitetura.md)) |

Quem continuar depois do M3 começa pela galeria (M4 / bloco D); o shell, a ponte, o workspace,
a paleta e os asserts visuais já fecharam — ver [`../app/README.md`](../app/README.md).

## Dependências

| Precisa de | Estado |
|---|---|
| Núcleo respondendo NDJSON | **existe** (17 métodos) |
| `job.progresso` emitido | **existe** (A9, núcleo v0.4.0) |
| Backend de identidade | ausente — bloqueia a tela de login |
| `shared/galeria/modelos.json` | ausente — bloqueia o painel da galeria |

## Stack

| Camada | Escolha | Por quê |
|---|---|---|
| Shell | Electron | janela nativa, tray, diálogo de pasta, auto-update, Credential Manager, `shell.openExternal` para o OAuth |
| UI | React 19 + TypeScript | ecossistema de chat/streaming maduro |
| Estilo | CSS Modules + tokens próprios ([F1-16](16-design-system-dark.md)) | o design system é próprio; framework de utilitário genérico empurra para o visual de dashboard que o produto evita |
| Estado | Zustand | simples; o estado pesado vive no núcleo |
| Preview de PDF | `pdf.js` | render local, sem servidor |
| Ícones | `lucide-react` | consistente; **nunca** emoji |
| Testes de UI | Vitest + Testing Library + `axe-core` | os DoD de [F1-16](16-design-system-dark.md) são asserts |

Electron e não Tauri: Tauri traria Rust como terceira linguagem (já temos TS e Python) e o ganho
de tamanho não paga o atrito de build no Windows.

## Layout

Quatro painéis. `painel-chat` é o principal e nunca some. Todos os IDs, e o arquivo de cada
componente, estão na tabela de [F1-16](16-design-system-dark.md#layout-principal-e-ids-de-componente).

```
┌─ topo-app ───────────────────────────────────────────────────────────────────────────────┐
│  MAPAS FÁCIL   Fazenda Harmonia · Vila Rica/MT              ◍ conta   ⚙ doctor   ─ □ ✕   │
├─ barra-chats ──┬─ painel-workspace ──┬─ painel-chat ─────────────┬─ painel-direito ───────┤
│ + novo chat    │ 📁 Harmonia         │  você                     │ preview │galeria│spec  │
│ 🔍 buscar      │                     │  faz a Dinâmica 2026      │ ┌────────────────────┐ │
│ ─────────────  │ ▾ Arquivo Projeto   │                           │ │                    │ │
│ HOJE           │   ▪ ATP.shp         │  Ana  ▸ pensando…         │ │  ▪ perímetro    ✓  │ │
│ ▸ Dinâmica 26  │     1 feição        │                           │ │  ▪ AUAS         ✓  │ │
│ ▸ Tipologia    │     3.823,9033 ha   │  ▸ ler_recibo_car  1,2s ✓ │ │  ▪ AVN          ◐  │ │
│ 7 DIAS         │   ▪ AVN.shp         │    Fazenda Harmonia       │ │  ▪ área consol. ○  │ │
│ ▸ Embargos     │     12 feições      │    MT102042/2017          │ │  ▫ tabela       ○  │ │
│ ▸ TI Kayapó    │   ▪ AUAS.shp        │  ▸ galeria.montar  0,3s ✓ │ │                    │ │
│                │ ▪ CAR-Emissao.pdf   │  ▸ validar_mapspec 0,1s ✓ │ └────────────────────┘ │
│                │ ▾ Mapas/            │  ▸ gerar_mapa      68s  ◐ │                        │
│                │   ▪ Dinamica.pdf    │                           │ ✓ 14 HARD  ⚠ 1 SOFT    │
│                │ ─────────────────   │  ▓▓▓▓▓▓▓▓▓░░░  aplicando  │ ◀ v1  ● v2  v3 ▶       │
│                │ ArcMap ✓ IA ✓       │  layout · 70%   [cancelar]│ Dinamica_2026.mxd   📂 │
│                │ SEMA ✓ Planet ✓     │                           │ Dinamica_2026.pdf   📂 │
│                │                     │ [ escreva ou arraste ] ▶  │ Quantitativos.xlsx  📂 │
└────────────────┴─────────────────────┴───────────────────────────┴────────────────────────┘
```

Painéis redimensionáveis, larguras persistidas em `config.json`. `barra-chats` e
`painel-workspace` são colapsáveis; `painel-chat` não. Janela mínima **1280×800**.

### `barra-chats`

Sidebar de conversas. Comportamento completo em [F1-17](17-persistencia-de-conversas.md).
Resumo: agrupada por data, busca por `Ctrl+F`, menu de contexto com renomear/arquivar/ramificar/
apagar, filtro "só desta pasta".

### `painel-workspace`

- Árvore da pasta conectada, com **metadados inline**: feições, CRS, área em ha. É o que
  diferencia de um explorador de arquivos comum — o técnico vê o número sem abrir nada.
- Números em `--mf-fonte-mono` com `tabular-nums`, formato pt-BR e 4 casas.
- Ícone de alerta em arquivo com problema (`.prj` ausente, geometria inválida, área divergente),
  com o motivo no `title`.
- Rodapé `doctor-resumo`: ArcMap, chave DeepSeek, authkey SEMA, chave Planet, templates.
  Verde/amarelo/vermelho **com ícone e texto**, clicável para o diagnóstico completo.
- Botão "conectar outra pasta" e lista de projetos recentes.

### `painel-chat`

- Streaming token a token (`chat.delta`), sem re-render do bloco inteiro.
- `bloco-raciocinio` colapsado por padrão, com o rótulo "pensando" enquanto não há delta de texto.
- **Tool calls visíveis** (`cartao-tool`), colapsadas por padrão, com duração e status. Expandir
  mostra argumentos e resultado — é o que dá confiança de que o agente olhou os dados de verdade.
- Avisos em destaque, **com o número** (`7,4 ha`), nunca genéricos.
- Arrastar arquivo para o chat: `.zip`, PDF de recibo, **print de mapa de referência**. O arquivo
  é copiado para `chats/anexos/` ([F1-17](17-persistencia-de-conversas.md)).
- `barra-progresso-job` aparece ancorada acima do `campo-entrada` enquanto há job, com as 10
  etapas nomeadas e botão cancelar.
- `Esc` cancela o turno; o job em andamento continua e é cancelado à parte (dois botões distintos,
  nunca o mesmo).

### `painel-direito` — abas

| Aba | Conteúdo |
|---|---|
| `painel-preview` | mapa em construção → PDF final; `linha-versoes` ◀ v1 v2 v3 ▶; lista de artefatos com "abrir" e "mostrar na pasta" |
| `painel-galeria` | grade de modelos ([F1-15](15-galeria-de-modelos.md)); vira a aba ativa quando não há mapa gerado |
| `painel-mapspec` | JSON legível, com diff entre versões em português |
| `painel-checks` | HARD/SOFT, cada check clicável para explicação |

Aba ativa por padrão: `painel-galeria` numa pasta sem mapa; `painel-preview` depois da primeira
geração.

### `painel-preview` — o mapa sendo construído

O comportamento em duas fases está especificado em
[F1-16 §A5](16-design-system-dark.md#a5--mapa-sendo-construído-painel-preview). Resumo para quem
implementa a UI:

| Momento | O que aparece |
|---|---|
| Sem job | preview do PDF da versão selecionada, com zoom (`pdf.js`) |
| Job iniciado | pilha de camadas do `MapSpec` em ordem de desenho, todas apagadas |
| `job.progresso` com `item` | a linha da camada correspondente acende |
| Etapas `gerando_tabela`, `aplicando_layout` | as molduras de tabela/minimapa/legenda acendem |
| `job.artefato_parcial` (M8) | o esqueleto é substituído por rasterização real, com crossfade |
| Job concluído | PDF final; `linha-versoes` ganha a versão nova |
| Job falhou | último estado congelado + cartão de erro com código |

**Não** desenhe barra de porcentagem antes de o núcleo emitir `job.progresso` (AP-07). Enquanto o
emissor não existir, o preview mostra "gerando…" estático.

## Conectar uma pasta

```
1. Usuário escolhe a pasta (diálogo nativo do Electron, no processo main)
2. A pasta entra na allowlist do fsguard  ← única forma de autorizar I/O
3. workspace.abrir → índice: shapefiles, .zip, PDFs, imagens, .mxd
4. Detecta e lê o recibo do CAR automaticamente
5. Identifica o papel de cada shapefile (nome → alias → heurística → pergunta)
6. Watcher liga (debounce 500 ms)
7. galeria.listar recalcula o status dos modelos com o índice novo
8. O app abre a conversa com o que encontrou
```

Mensagem de abertura, gerada **sem custo de IA** (é template preenchido pelo núcleo):

```
Conectei em Analise_de_área-Julio Barbosa_4_Harmonia.

Imóvel   Fazenda Harmonia · Vila Rica/MT · CAR MT102042/2017 · 3.823,9033 ha
Shapes   ATP (1) · AVN (12) · AREA_CONSOLIDADA (5) · AUAS (8)  — SIRGAS 2000, EPSG:4674
Saídas   Mapas/ (vazia) · MXD/ (vazia)

Modelos prontos para esta pasta: Dinâmica de uso do solo.
Escolha na galeria ao lado, ou me diga o que você quer.
```

## Watcher

- Observa a pasta com *debounce* de 500 ms.
- Reindexa só o que mudou e emite `workspace.mudou`.
- Arquivo novo relevante aparece no chat como **aviso do sistema**, não como mensagem do agente:
  *"apareceu `AUAS_corrigido.shp` (8 feições, 491,26 ha)"*.
- Arquivo removido que era usado por um `MapSpec` ativo vira alerta.
- Ignora: `.lock`, `~$*`, `.tmp`, e a própria pasta de saída durante um job.

## Estados vazios, carregamento e erro

| Situação | O que a UI mostra |
|---|---|
| Nunca logou | `tela-login` em tela cheia: marca em `--mf-fs-hero`, "Entrar com Google", nota "acesso completo, sem limites" |
| Sessão expirada | faixa no topo; leitura liberada; gerar recusa com `AUTH-030` e o botão vira "Entrar" |
| Backend de conta fora do ar, token válido | chip "offline" no rodapé; **app funciona inteiro** |
| Nenhuma pasta conectada | boas-vindas com "conectar pasta" + projetos recentes + galeria em modo vitrine (cartões `faltam_dados`) |
| Pasta sem shapefile | explica o que o app espera encontrar e oferece arrastar o `.zip` do SIMCAR |
| Sem chave DeepSeek | banner "configurar chave" + "usar a galeria" — o app **continua funcionando** |
| Sem ArcMap | banner informativo: "vou gerar o `.mxd` pelo caminho de template; o PDF sai pelo motor nativo" |
| Sem internet | banner de offline; camadas externas vêm do cache com idade |
| Job rodando | `barra-progresso-job` com a etapa nomeada, botão cancelar, log técnico colapsado |
| Job falhou | código do erro, o que aconteceu, o que fazer, botão "copiar diagnóstico" |
| Núcleo caiu | banner vermelho + botão reiniciar; a conversa não se perde (está em `chats.sqlite`) |

Regra de mensagem de erro: **o que aconteceu, por que, o que fazer.** Nunca só o código.

```
AG-020 · O ArcMap não respondeu em 150 s

O arcpy travou ao abrir o template. Isso costuma ser licença ou uma
instância do ArcMap aberta segurando o arquivo.

  → Feche o ArcMap e tente de novo
  → Ou gere sem ArcMap (o .mxd sai pelo caminho de template)

[ Tentar de novo ]  [ Gerar sem ArcMap ]  [ Copiar diagnóstico ]
```

## Acessibilidade e atalhos

| Atalho | Ação |
|---|---|
| `Ctrl+O` | conectar pasta |
| `Ctrl+N` | nova conversa |
| `Ctrl+F` | buscar nos chats |
| `Ctrl+Enter` | enviar |
| `Esc` | cancelar turno |
| `Ctrl+K` | paleta de comandos (gerar mapa da série, abrir pasta, doctor) |
| `Ctrl+,` | preferências |
| `F1` | doctor |

Contraste, foco, leitor de tela e `prefers-reduced-motion`: regras e asserts em
[F1-16 §Acessibilidade](16-design-system-dark.md#acessibilidade). Tema **escuro é o default**;
claro é opção, nunca o padrão (AP-08).

## Tarefas agentáveis

- [x] `Fase_1_Desktop/app/` — scaffold Electron + Vite + React 19 + TS + entrada do renderer
- [~] `app/electron/main.ts` — janela, ciclo da ponte e **diálogo de pasta** prontos; menus e tray faltam
- [x] `app/electron/nucleo/ponte.ts` — spawn do sidecar, NDJSON, reinício, `UI-001` *(7 testes)*
- [x] `app/src/layout/AppShell.tsx` — os quatro painéis, redimensionáveis e persistidos
- [x] `app/src/paineis/Workspace.tsx` — árvore com metadados inline (feições, CRS, ha pt-BR)
- [ ] `app/src/paineis/Chat.tsx` + `componentes/CartaoTool.tsx` + `BlocoRaciocinio.tsx`
- [x] `app/src/componentes/BarraProgressoJob.tsx` — 10 etapas nomeadas, `role="progressbar"`
- [ ] `app/src/paineis/Preview.tsx` — esqueleto de camadas + `pdf.js` + `linha-versoes`
- [ ] `app/src/paineis/PainelDireito.tsx` — abas
- [ ] `app/src/componentes/CampoEntrada.tsx` — textarea, anexos, enviar/cancelar
- [~] `app/src/componentes/EstadoVazio.tsx` — os casos com dado real; login/sessão/offline esperam M5
- [x] `app/src/paleta/PaletaComandos.tsx` — `Ctrl+K` (+ atalhos F1-02; preferências de tema)
- [ ] `app/tests/` — os asserts dos critérios de aceite

## Critérios de aceite

- [x] `pnpm test` verde (71) e `pnpm build` produz o bundle — rodados em `Fase_1_Desktop/app/`
- [~] Abrir a pasta Harmonia: `painel-workspace` mostra ATP, AVN, AC, AUAS e o recibo, com áreas
      em ha formatadas pt-BR com 4 casas — provado com a **fixture gerada pelo núcleo**
      (`app/tests/workspace.test.tsx`); falta o teste com a pasta Harmonia real, que exige o
      acervo local
- [ ] Gerar mapa pela galeria (sem IA) produz arquivos em `Mapas/` e o preview atualiza
- [x] Com `job.progresso` injetado, `barra-progresso-job` mostra as 10 etapas em português e
      `pct` monotônico; sem o evento, mostra "gerando…" **sem** barra
      (`app/tests/barra-progresso-job.test.tsx`)
- [ ] `Esc` cancela o turno e **não** cancela o job; o botão do job cancela só o job (dois testes)
- [ ] Renderer não consegue ler arquivo fora do workspace — teste tenta `../../Windows/System32`
      e espera `NU-010`
- [ ] `linha-versoes` navega v1↔v2 e troca o preview; o diff aparece no chat em português
- [~] `axe-core` sem violação nas telas existentes (app vazio, app com job, app com erro) —
      `app/tests/visual/contraste.test.tsx`; login espera M5
- [~] Janela 1280×800 sem scroll horizontal — assert em `app/tests/visual/layout-e-numeros.test.tsx`
      (jsdom; smoke de layout)
- [ ] Fechar e reabrir o app restaura larguras de painel, projeto recente e a conversa aberta

## Fora de escopo

- Responsividade para telefone/tablet (o alvo é desktop 1280×800+).
- Editor de shapefile, edição de geometria, medição no mapa.
- Abas ou múltiplas janelas de projeto (ver P2).
- Terminal embutido, editor de código, execução de script pelo usuário.
- Personalização de layout além de largura de painel.

## Anti-padrões

| Não faça | Por quê |
|---|---|
| Ler arquivo do usuário direto pelo renderer (`fs` no preload) | quebra a fronteira 1 e o `fsguard` |
| Barra de progresso sem evento de progresso | AP-07 |
| Emoji como ícone | AP: inconsistente entre versões do Windows |
| Mesmo botão para cancelar turno e cancelar job | o usuário perde 68 s de geração ao querer só parar o texto |
| Aviso genérico ("há inconsistências") | o produto avisa com o número: "7,4 ha de AUAS fora da ATP" |
| Esconder tool calls para "limpar" a interface | é justamente o que dá confiança no agente |
| Tema claro como default | AP-08 / D15 |
| Bloquear a UI enquanto o núcleo indexa | indexação é assíncrona, com esqueleto na árvore |

## Pendências

| # | Questão | Recomendação |
|---|---|---|
| P1 | Preview do `.mxd` sem ArcMap — só o PDF, ou render aproximado das camadas? | **render aproximado** já existe de graça: é o mesmo esqueleto do A5 |
| P2 | Múltiplos projetos abertos: abas ou janelas? | **fora da v1**; a `barra-chats` já cobre o troca-troca |
| P3 | Onde mostrar o custo acumulado de IA sem virar ansiedade | rodapé do `painel-chat`, só tokens da conversa atual; total no doctor |
| P4 | O `painel-direito` deve mostrar mapa ou tabela quando o pedido foi só quantitativos? | aba `painel-preview` mostra o PNG da tabela; o `.xlsx` entra na lista de artefatos |
