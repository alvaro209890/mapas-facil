# F1-02 — Interface, chat e workspace de pasta

A experiência é a de um agente de programação (Cursor, Codex, Claude Code) aplicada à
cartografia: **conecte uma pasta e converse**.

## Stack

| Camada | Escolha | Por quê |
|---|---|---|
| Shell | Electron | janela nativa, tray, diálogo de pasta, auto-update, Credential Manager |
| UI | React 19 + TypeScript | ecossistema de chat/streaming maduro |
| Estilo | Tailwind + shadcn/ui | componentes prontos, tema claro/escuro |
| Estado | Zustand | simples; o estado pesado vive no núcleo |
| Preview de PDF | `pdf.js` | render local, sem servidor |
| Ícones | lucide-react | — |

Electron e não Tauri: Tauri traria Rust como terceira linguagem (já temos TS e Python) e o ganho
de tamanho não paga o atrito de build no Windows.

## Layout

Três painéis redimensionáveis. O do meio é o principal e nunca some.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Mapas Fácil          Fazenda Harmonia · Vila Rica/MT        ⚙  ?  ─ □ ✕     │
├───────────────┬────────────────────────────────────┬─────────────────────────┤
│ WORKSPACE     │  CHAT                              │  MAPA                   │
│               │                                    │                         │
│ 📁 Harmonia   │  ┌──────────────────────────────┐  │  ┌───────────────────┐  │
│               │  │ você                          │  │  │                   │  │
│ ▾ Arquivo Pro…│  │ faz a Dinâmica 2026           │  │  │   preview PDF     │  │
│   ▪ ATP.shp   │  └──────────────────────────────┘  │  │                   │  │
│     1 feição  │                                    │  │                   │  │
│     3.823,90ha│  Ana                               │  └───────────────────┘  │
│   ▪ AVN.shp   │  ▸ ler_recibo_car        1,2 s ✓   │                         │
│   ▪ AC.shp    │    Fazenda Harmonia                │  ✓ 14 HARD              │
│   ▪ AUAS.shp  │    MT102042/2017 · 3.823,9033 ha   │  ⚠ 1 SOFT               │
│ ▪ CAR….pdf    │  ▸ indexar_pasta         0,4 s ✓   │     S01 retângulo do    │
│ ▾ Mapas/      │  ▸ consultar_sema        4,1 s ✓   │        minimapa 0,3 mm  │
│   ▪ Dinam….pdf│    tipologia: 2 classes            │                         │
│               │  ▸ criar_mapa                      │  ARQUIVOS               │
│ ─────────────  │  ▸ gerar_mapa           68 s ✓    │  Dinamica_2026.mxd  📂  │
│ ArcMap 10.8 ✓ │                                    │  Dinamica_2026.pdf  📂  │
│ DeepSeek    ✓ │  Pronto. Escala 1:60.000.          │  Quantitativos.xlsx 📂  │
│ SEMA authkey✓ │  ⚠ 7,4 ha de AUAS fora da ATP.     │                         │
│ Planet      ✓ │                                    │  VERSÕES                │
│               │                                    │  ● v1  ○ v2  ○ v3       │
│               │  [ escreva ou arraste um arquivo ] │                         │
└───────────────┴────────────────────────────────────┴─────────────────────────┘
```

### Painel esquerdo — workspace

- Árvore da pasta conectada, com **metadados inline**: feições, CRS, área em ha. É o que
  diferencia de um explorador de arquivos comum — o técnico vê o número sem abrir nada.
- Ícone de alerta em arquivo com problema (`.prj` ausente, geometria inválida, área divergente).
- Rodapé com o **doctor resumido**: ArcMap, chave DeepSeek, authkey SEMA, chave Planet, templates.
  Verde/amarelo/vermelho, clicável para o diagnóstico completo.
- Botão "conectar outra pasta" e lista de projetos recentes.

### Painel central — chat

- Streaming token a token.
- **Tool calls visíveis**, colapsadas por padrão, com duração e status. Expandir mostra
  argumentos e resultado — é o que dá confiança de que o agente olhou os dados de verdade.
- Avisos em destaque, com o número (`7,4 ha`), nunca genéricos.
- Arrastar arquivo para o chat: `.zip`, PDF de recibo, **print de mapa de referência**.
- `Esc` cancela o turno; job em andamento continua e pode ser cancelado à parte.

### Painel direito — mapa

- Preview do PDF gerado, com zoom.
- Painel de conformidade: HARD/SOFT, cada check clicável para explicação.
- Lista de arquivos gerados, com "abrir" e "mostrar na pasta".
- **Linha do tempo de versões**: v1, v2, v3… clicar troca o preview; o diff aparece no chat.

## Conectar uma pasta

```
1. Usuário escolhe a pasta (diálogo nativo)
2. A pasta entra na allowlist do fsguard  ← única forma de autorizar I/O
3. Núcleo indexa: shapefiles, .zip, PDFs, imagens, .mxd
4. Detecta e lê o recibo do CAR automaticamente
5. Identifica o papel de cada shapefile (nome → alias → heurística → pergunta)
6. Watcher liga
7. O agente abre a conversa com o que encontrou
```

Mensagem de abertura, gerada sem custo de IA (é template preenchido pelo núcleo):

```
Conectei em Analise_de_área-Julio Barbosa_4_Harmonia.

Imóvel   Fazenda Harmonia · Vila Rica/MT · CAR MT102042/2017 · 3.823,9033 ha
Shapes   ATP (1) · AVN (12) · AREA_CONSOLIDADA (5) · AUAS (8)  — SIRGAS 2000, EPSG:4674
Saídas   Mapas/ (vazia) · MXD/ (vazia)

Posso fazer a série Dinâmica, Tipologia, Embargos, Terras Indígenas ou Unidade de
Conservação. O que você quer primeiro?
```

## Watcher

- Observa a pasta com *debounce* de 500 ms.
- Reindexa só o que mudou.
- Arquivo novo relevante aparece no chat como aviso do sistema, não como mensagem do agente:
  *"apareceu `AUAS_corrigido.shp` (8 feições, 491,26 ha)"*.
- Arquivo removido que era usado por um `MapSpec` ativo vira alerta.
- Ignora: `.lock`, `~$*`, `.tmp`, e a própria pasta de saída durante um job.

## Estados vazios, carregamento e erro

| Situação | O que a UI mostra |
|---|---|
| Nenhuma pasta conectada | tela de boas-vindas com "conectar pasta" e os projetos recentes |
| Pasta sem shapefile | explica o que o app espera encontrar e oferece arrastar o `.zip` do SIMCAR |
| Sem chave DeepSeek | banner com "configurar chave" + botão "usar modo sem IA" — o app **continua funcionando** |
| Sem ArcMap | banner informativo: "vou gerar o `.mxd` pelo caminho de template; o PDF sai pelo motor nativo" |
| Sem internet | banner de offline; camadas externas vêm do cache com idade |
| Job rodando | barra de progresso com a etapa nomeada, botão cancelar, log técnico colapsado |
| Job falhou | código do erro, o que aconteceu, o que fazer, botão "copiar diagnóstico" |
| Núcleo caiu | banner vermelho + botão reiniciar; a conversa não se perde (está em SQLite) |

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
| `Ctrl+N` | nova conversa no projeto |
| `Ctrl+Enter` | enviar |
| `Esc` | cancelar turno |
| `Ctrl+K` | paleta de comandos (gerar mapa da série, abrir pasta, doctor) |
| `Ctrl+,` | preferências |
| `F1` | doctor |

- Navegação completa por teclado; foco visível.
- Contraste AA; a lista de checks não usa **só** cor (ícone + texto).
- Suporte a leitor de tela nos painéis de chat e de conformidade.
- Tema claro e escuro seguindo o sistema.

## Checklist de implementação

- [ ] Três painéis redimensionáveis, com estado persistido
- [ ] Árvore de pasta com metadados inline
- [ ] Doctor resumido no rodapé + tela completa
- [ ] Chat com streaming e tool calls expansíveis
- [ ] Arrastar `.zip`/PDF/imagem para o chat
- [ ] Preview de PDF com zoom
- [ ] Painel de conformidade com explicação por check
- [ ] Linha do tempo de versões com diff
- [ ] Watcher com debounce e aviso de arquivo novo
- [ ] Todos os estados vazios/erro da tabela
- [ ] Paleta de comandos
- [ ] Atalhos e navegação por teclado
- [ ] Tema claro/escuro

## Pendências

| # | Questão |
|---|---|
| P1 | Preview do `.mxd` sem ArcMap — só o PDF, ou tentar um render aproximado das camadas? |
| P2 | Múltiplos projetos abertos: abas ou janelas? |
| P3 | Onde mostrar o custo acumulado de IA sem virar ansiedade |
| P4 | O painel direito deve mostrar mapa ou tabela quando o pedido foi só quantitativos? |
