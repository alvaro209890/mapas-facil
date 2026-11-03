# W-07 — Motion: o palco do mapa

## Objetivo

Substituir o "spinner com barra" por um **palco** que mostra o trabalho real do núcleo: a câmera
desce do estado ao município e ao imóvel, as camadas vetoriais acendem uma a uma na ordem em
que ficam prontas, o mosaico de satélite entra recortado, e no fim a câmera recua para a
**folha**, que se monta peça por peça (moldura, mapa, grade, título, norte, minimapa, legenda,
metadados, tabela, logo) até virar o PDF final. **Toda** mudança no palco é causada por um evento
do núcleo (AP-07, D30). Sem evento, o palco fica parado — e diz o porquê ("aguardando vaga",
"baixando camadas da SEMA…").

## Estado atual vs alvo

| Item | Hoje (desktop M8) | Alvo |
|---|---|---|
| Feedback de job | `BarraProgressoJob` (10 etapas) + `Preview.tsx` com crossfade de PNG por etapa | barra de etapas (mantida) + palco com 3 modos |
| Eventos | `job.progresso`, `job.artefato_parcial` | + `viewport.foco`, `camada.renderizada`, `layout.elemento` ([W-03](03-api-http-e-eventos.md)) |
| Tokens de motion | `src/motion/tokens.ts`, `useReducedMotion.ts` | estendidos com os tokens da tabela abaixo |

## Dependências

W5 (SSE), W6 (tela do projeto), W7-núcleo (eventos novos e GeoJSON de palco — tarefas W7-01…05
de [W-03](03-api-http-e-eventos.md)).

## Contratos

### Anatomia do palco (`web/src/palco/`)

```
Palco.tsx
├── CamadaMapa      (MapLibre GL, canvas WebGL)      modo "mapa"
│   ├── fonte "bases"     → UF e município (GET /bases/…)
│   ├── fonte "camadas"   → uma source GeoJSON por camada_id (GET /palco/{job}/…)
│   └── fonte "raster"    → image source do basemap recortado (PNG + bbox_4326)
├── CamadaFolha     (SVG + motion, em mm reais)      modo "folha"
│   ├── <rect> da folha na proporção do formato
│   ├── um <g> por layout.elemento (caixa + recorte PNG ou desenho vetorial simples)
│   └── o "mapa" da folha é um snapshot do canvas MapLibre (toDataURL) encaixado no quadro
├── CamadaResultado (PDF final como imagem: preview_png da versão)   modo "resultado"
├── Legendinha      (rótulo da câmera: "Querência/MT", escala, etapa em curso)
└── BarraEtapas     (BarraProgressoJob herdada, compacta, no rodapé do palco)
```

Modos e transições (máquina de estados em `palco/coreografia.ts`):

```
          viewport.foco(estado|municipio|imovel)
 ocioso ─────────────────────────────────────▶ mapa ──── viewport.foco(folha) ───▶ folha
   ▲                                            │                                   │
   │                                            │ camada.renderizada (acende)       │ layout.elemento (encaixa)
   │                                            ▼                                   ▼
   └──────── nucleo.res / versao.criada ◀──── resultado ◀── job.artefato_parcial{pdf} ┘
```

- `ocioso`: sem job. Mostra o resultado da versão aberta (se houver) ou o imóvel parado com o
  perímetro aceso (estado depois da indexação).
- `mapa`: câmera e camadas.
- `folha`: montagem do layout.
- `resultado`: a folha montada faz crossfade (240 ms) para o PNG do PDF real; a linha de versões
  ganha a bolinha nova com um pulso.

### Coreografia

Tokens novos em `web/src/motion/tokens.ts` (somam-se aos do desktop):

| Token | Valor | Uso |
|---|---|---|
| `voo.estado_ms` | 1600 | `flyTo` para a UF (zoom-out → UF) |
| `voo.municipio_ms` | 1800 | UF → município |
| `voo.imovel_ms` | 2200 | município → imóvel (o mais cinematográfico: `curve: 1.6`, `essential: false`) |
| `voo.enquadramento_ms` | 900 | ajuste fino até o extent escolhido |
| `voo.min_ms` / `voo.max_ms` | 500 / 2400 | limites quando a fila comprime |
| `camada.acende_ms` | 520 | opacidade 0 → alvo + traço do contorno se desenhando (`line-dasharray` animado) |
| `camada.intervalo_min_ms` | 180 | intervalo mínimo entre dois acendimentos |
| `raster.revela_ms` | 700 | máscara circular do centro do imóvel para fora |
| `folha.recuo_ms` | 1100 | câmera "sobe" e o mapa encolhe até o quadro da folha (transição mapa → folha) |
| `elemento.entra_ms` | 360 | cada elemento: escala 0,96 → 1 + opacidade, spring leve |
| `elemento.intervalo_min_ms` | 120 | entre elementos |
| `resultado.crossfade_ms` | 240 | folha montada → PNG real |

Regras por evento:

| Evento | O que o palco faz | Duração |
|---|---|---|
| `viewport.foco` `estado` | `fitBounds(bbox, {padding: 8%})` com `flyTo`; mostra contorno da UF (traço se desenhando) e o rótulo | `voo.estado_ms` |
| `viewport.foco` `municipio` | voa ao bbox do município; contorno do município em laranja (cor do minimapa do padrão) | `voo.municipio_ms` |
| `viewport.foco` `imovel` | voa ao bbox do imóvel (padding 18%); a UF e o município esmaecem a 25% | `voo.imovel_ms` |
| `camada.renderizada` (vetor) | `GET` do GeoJSON (com `AbortController`); adiciona source + layers com o `estilo` do evento; anima opacidade e traço; o rótulo mostra "Área de vegetação nativa · 812,4410 ha" por 1,2 s. `padrao: "hachura"` (AC/AVN sobre satélite nas dinâmicas — [W-17](17-conhecimento-das-skills.md) §3) vira `fill-pattern` gerado em canvas (linhas a 45° na cor do estilo, fundo transparente), para o palco mostrar o mesmo que o PDF | `camada.acende_ms` |
| `camada.renderizada` (raster) | image source no `bbox_4326`; revela com máscara; camadas vetoriais sobem para cima dele | `raster.revela_ms` |
| `viewport.foco` `enquadramento` | ajusta ao extent final e desenha, por 800 ms, a moldura do quadro do mapa na proporção `quadro_mm` (o usuário vê "o que vai caber na folha") + rótulo `1:40.000` | `voo.enquadramento_ms` |
| `job.progresso` | atualiza a barra; a etapa em curso aparece na legendinha ("baixando camadas externas…") | — |
| `job.log` "aguardando vaga" | legendinha "na fila: 2 mapas sendo gerados"; o palco **não** anima | — |
| `viewport.foco` `folha` | snapshot do canvas → imagem; transição `folha.recuo_ms`: a imagem encolhe até o quadro `mapa` da folha enquanto a folha (branca, sombra suave) aparece em volta | `folha.recuo_ms` |
| `layout.elemento` | o elemento entra na sua `caixa_mm` (convertida para px pela escala da folha na tela); `titulo` desenha o texto; `legenda` lista os itens; `metadados` as linhas; `grade` traça as linhas de borda; `minimapa`/`norte`/`logo`/`tabela` usam o recorte PNG se veio, senão um bloco com o nome | `elemento.entra_ms` |
| `job.artefato_parcial` `tabela_png` | se o elemento `tabela` já entrou, troca o bloco pelo PNG com crossfade | 240 ms |
| `job.artefato_parcial` `pdf` | marca "PDF pronto" na legendinha | — |
| `versao.criada` / `nucleo.res ok` | modo `resultado` | `resultado.crossfade_ms` |
| `nucleo.res` com erro | o palco para onde está, escurece 40%, mostra o código e a mensagem; botão "ver detalhes" abre o log | — |

### Fila e compressão (`palco/coreografia.ts`)

Eventos chegam mais rápido que as animações (camadas locais saem em milissegundos). A
coreografia mantém uma **fila** e aplica:

1. Cada evento vira um **passo** com duração-alvo da tabela.
2. Passos de câmera não se sobrepõem; acendimentos podem começar enquanto o último voo termina
   (último 30% do voo).
3. Se a fila tem mais de 4 passos pendentes, a duração de cada passo cai pela metade (piso
   `voo.min_ms` / `camada.intervalo_min_ms`); com mais de 10, voos intermediários são
   **pulados** (vai direto ao último `viewport.foco` pendente) e acendimentos entram em grupos
   de 3. Nenhum evento é descartado do **estado**; só a animação é encurtada.
4. Replay (`desde=0` ou reconexão): eventos com `ts` mais velho que 5 s antes do "agora" são
   aplicados **sem animação** (estado final direto), e só os recentes animam. Assim recarregar a
   página no meio do job reconstrói o palco instantaneamente e continua animando dali.
5. `prefers-reduced-motion: reduce`: todas as durações viram 0 exceto crossfades (≤ 150 ms);
   voos viram `jumpTo`.
6. Aba em segundo plano (`document.hidden`): a fila é aplicada sem animação ao voltar.

A coreografia é **pura** (entrada: lista de eventos + relógio; saída: lista de passos com
início/fim) para ser testada sem navegador: `coreografia.test.ts` roda roteiros gravados.

### Mapa base do palco

- Sem tiles de terceiros por padrão: fundo escuro liso (token `--palco-fundo`), contorno da UF e
  dos municípios vizinhos em traço fino (`/bases/…`), e o **mosaico real** recortado pelo núcleo
  quando ele chega (`camada.renderizada` raster). Motivo: nada de chave/termos de uso de tile no
  navegador e o palco mostra exatamente a imagem que vai para o PDF.
- Projeção do palco: Web Mercator do MapLibre (é só visualização); áreas e escalas exibidas vêm
  do núcleo, nunca calculadas no navegador.
- Sem WebGL (raro): `WB-001` → o palco cai para o modo "folha + resultado" usando só SVG, e as
  camadas acendem como lista na legendinha. O job funciona igual.

### Montagem da folha — conversão mm → px

`escala_tela = min(largura_palco_px / largura_mm, altura_palco_px / altura_mm) × 0,9` (px por mm); cada
`caixa_mm` vira `x = x0 × escala_tela`, `y = y0 × escala_tela` (origem no topo-esquerda, igual ao
`perfil_pagina.py`). A folha muda de proporção conforme `folha.formato/orientacao`, então a mesma
coreografia funciona em A4 e A0 — numa A0 o palco mostra a folha inteira menor e os elementos
proporcionalmente (D31).

### Desempenho

| Métrica | Alvo |
|---|---|
| FPS durante voo e acendimento (notebook do escritório, Chrome) | ≥ 50 |
| GeoJSON por camada | ≤ 2 MB / 20.000 vértices (garantido pelo núcleo) |
| Memória do palco depois de 10 jobs seguidos no mesmo projeto | estável (sources/layers removidos ao trocar de job) |
| Tempo do primeiro `viewport.foco` até a câmera começar a mover | ≤ 100 ms |

## Tarefas agentáveis

### Núcleo (W7) — em [W-03](03-api-http-e-eventos.md) W7-01…05, mais:

- [ ] **W7-06** `motores/nativo.py`: exportar recortes PNG por elemento em `Mapas/.preview/<job>/layout/` (só quando `RastreadorProgresso.emite_eventos`), 150 dpi, para `minimapa`, `norte`, `logo`, `tabela`.
- [ ] **W7-07** `camadas/materializar.py`: gravar o GeoJSON simplificado de palco por camada (função `palco.gravar_geojson(camada, destino)` em `mapasfacil_nucleo/palco.py`, nova).
- [ ] **W7-08** Raster do basemap recortado para o palco: PNG 1600 px no maior lado + `bbox_4326` (de `motores/basemap.py`).
- [ ] **W7-09** Exportar estilos para a web: `python -m mapasfacil_nucleo estilos --json`.
- [ ] **W7-10** Gravar roteiros reais (`servidor/tests/roteiros/dinamica_ok.ndjson`, `serie_analise.ndjson`, `dinamica_falha_hard.ndjson`) a partir do `imovel_ficticio.zip`, com os arquivos de `.preview` correspondentes em `servidor/tests/roteiros/<nome>/`.

### Web (W8)

- [ ] **W8-01** `palco/Palco.tsx` com os 4 modos e o espaço do W6 substituído.
- [ ] **W8-02** `palco/Camera.ts`: wrapper do MapLibre (criar, `flyTo`/`fitBounds`/`jumpTo`, snapshot, destruir), sem estado global.
- [ ] **W8-03** `palco/Camadas.ts`: adicionar/remover sources e layers por `camada_id`, tradução de `estilo` do evento para paint do MapLibre, animação de traço.
- [ ] **W8-04** `palco/Folha.tsx`: SVG da folha, conversão mm→px, entrada de elementos com `motion`.
- [ ] **W8-05** `palco/coreografia.ts` (pura) + `coreografia.test.ts` com os 3 roteiros, compressão e replay.
- [ ] **W8-06** `estado/palco.ts`: fila, aplicação, limpeza ao trocar de job/versão.
- [ ] **W8-07** Fallback sem WebGL (`WB-001`).
- [ ] **W8-08** Tokens novos em `motion/tokens.ts` + `useReducedMotion` aplicado em todos os passos.
- [ ] **W8-09** Modo `ocioso` com a versão aberta e o perímetro da indexação.
- [ ] **W8-10** Teste visual Playwright: 6 screenshots de referência no roteiro `dinamica_ok` (após estado, município, imóvel, AVN acesa, folha com legenda, resultado), comparação com tolerância de 2% de pixels.

## Critérios de aceite

- [ ] `coreografia.test.ts`: o roteiro `dinamica_ok` produz passos na ordem foco(estado) → foco(municipio) → foco(imovel) → acende(perimetro) → acende(avn) → acende(ac) → acende(auas) → … → foco(folha) → elementos → resultado; com o relógio "rápido" (eventos todos em 50 ms) a duração total cai e nenhum passo some do estado final.
- [ ] Grep no `web/src/palco`: nenhum `setTimeout`/`setInterval` que dispare passo sem evento (o relógio da coreografia é injetado; timers só existem dentro do executor de passos).
- [ ] Desligar o SSE no meio do job (fechar rede no DevTools) → o palco **para**, o banner de conexão aparece; religar → o palco retoma a partir do `seq` certo.
- [ ] Com `prefers-reduced-motion`, nenhum voo nem entrada com mais de 150 ms.
- [ ] FPS ≥ 50 medido pelo Playwright (trace) no roteiro `serie_analise` (20 mapas).
- [ ] Job com erro HARD: o palco termina em `resultado` com o selo "não conforme" e o código, sem animação de "sucesso".

## Fora de escopo

- 3D/terreno, globo, partículas, som.
- Edição interativa no palco (clicar na camada para mudar estilo) — o pedido é pelo chat.
- Gravar a animação como vídeo.

## Anti-padrões

- Animar etapa que não chegou (AW-03/AP-07) — inclusive "enquanto espera, gira o globo".
- Calcular área/escala no navegador para mostrar no rótulo.
- Reordenar camadas no palco diferente da ordem dos eventos.
- Carregar o GeoJSON original (não simplificado) do projeto no navegador.


### W8-11 Clicar na folha para editar (D43)
- Prévia da folha (`Folha.tsx`) com áreas clicáveis a partir de `layout.elemento`:
  - Hover destaca o elemento (`.elementoClicavel:hover`);
  - Clique seleciona e chama `aoSelecionarElemento({ id, tipo, bbox_mm, coord_geo? })`;
  - Acessível via teclado (`tabIndex={0}`, `role="button"`, Enter seleciona) e toque mobile;
  - Clique dentro do quadro do mapa envia também coordenada relativa/geográfica (`coord_geo`);
  - `POST /projetos/{id}/mensagens` envia `contexto: {versao, elemento_id, tipo, bbox_mm, coord_geo?}`;
  - Validação rigorosa no servidor: se o elemento ou a versão não existirem, devolve `SV-242`;
  - Tools de edição no núcleo (`alternar_elemento`, `editar_camada`, `ajustar_elemento`) aceitam `elemento_id`.
