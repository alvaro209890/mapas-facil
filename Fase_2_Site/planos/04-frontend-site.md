# F2-04 — Frontend (site e chat)

> **LEGADO (2026-07-25).** Corpo ainda assume site na Vercel acoplado a agente WS. Destino D7:
> Next.js em `mapasfacil.cursar.space` consumindo a API neste PC. Ver [`README.md`](README.md).

Implementação do `web/`. Consome exclusivamente os endpoints e eventos de
[01-arquitetura.md](01-arquitetura.md), com os códigos de erro definidos em
[02-backend-api.md](02-backend-api.md). Nada fora desses dois documentos é assumido como pronto — o que
falta está em [Pendências](#pendências-e-decisões-abertas).

## Stack e justificativa

| Componente | Escolha | Por quê | Alternativa descartada |
|---|---|---|---|
| Framework | Next.js 16, App Router | decisão D2 do [00](00-visao-e-escopo.md); layouts aninhados encaixam na estrutura sidebar + chat + painel | Vite + React Router (sem SSR nem auth pronto) |
| Tipos | TypeScript `strict` | o `MapSpec` é um objeto grande e aninhado; sem tipos, cada refactor de painel vira caça a `undefined` | JS puro |
| Estilo | Tailwind + shadcn/ui | componentes acessíveis por padrão (Radix por baixo) que a gente possui no repositório, sem tema de terceiro para lutar | MUI (tema pesado, difícil de fugir do visual padrão) |
| Estado do servidor | TanStack Query | cache, revalidação e paginação por cursor de conversas/mensagens/jobs sem escrever reducer | SWR (menos controle de invalidação); Redux (cerimônia demais) |
| Estado do turno | Zustand | o turno em streaming é estado local efêmero e de alta frequência (`text.delta` a cada poucos ms); manter isso no cache do Query causaria re-render de tudo | Context + useReducer (re-render em cascata) |
| Preview de PDF | `iframe` primeiro, `react-pdf` se precisar | o viewer nativo do navegador é grátis, rápido e já tem zoom e impressão; `react-pdf` custa ~400 kB de bundle e só se justifica para miniatura por página | `react-pdf` desde o início |

## Estrutura de pastas

```
web/
├── app/
│   ├── (marketing)/             # landing, preço, download do agente — estático, sem auth
│   │   ├── page.tsx
│   │   └── download/page.tsx
│   ├── (app)/                   # layout autenticado: sidebar + área de trabalho
│   │   ├── layout.tsx
│   │   ├── chat/[id]/page.tsx   # a tela principal
│   │   ├── agentes/page.tsx     # lista, pareamento, doctor, pastas autorizadas
│   │   └── configuracoes/page.tsx
│   └── api/                     # apenas rotas de sessão/proxy; regra de negócio é do backend
├── components/
│   ├── chat/                    # ListaConversas, Mensagem, CartaoToolCall, Composer,
│   │                            # IndicadorStreaming, BotaoCancelar
│   ├── mapspec/                 # VisualizadorJson, DiffMapSpec, ListaCamadas, PainelValidacao
│   ├── agents/                  # SeletorAgente, ChecklistDoctor, DialogoPareamento,
│   │                            # EstadoVazioSemAgente
│   ├── jobs/                    # BarraEtapas, LogJob, HistoricoVersoes
│   └── ui/                      # shadcn/ui gerado
├── lib/
│   ├── api/                     # um módulo por recurso, tipado: conversations.ts, messages.ts,
│   │                            # jobs.ts, agents.ts, catalog.ts, artifacts.ts
│   ├── sse.ts                   # parser de text/event-stream sobre fetch (ver abaixo)
│   ├── erros.ts                 # codigo -> {titulo, descricao, acao}
│   └── tipos/                   # tipos gerados de shared/schemas (MapSpec, eventos, job)
├── hooks/                       # useTurno, useJobEvents, useAgentes, useAtalhos
├── store/                       # turno.ts (Zustand)
└── package.json
```

`lib/tipos/` é **gerado** de `shared/schemas/*.json`, não escrito à mão: o `MapSpec` tem dezenas de
campos e uma divergência silenciosa entre o tipo do frontend e o schema do backend é o bug mais caro
possível aqui (a UI mostra um mapa que o backend rejeita, ou pior, aceita errado).

## Layout da tela principal

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ Mapas Fácil    Fazenda Trevisol — Dinâmica 2026            [PC-GIS-01 ● online ▾]    │
├───────────────────────┬─────────────────────────────┬────────────────────────────────┤
│ [+ Nova conversa]     │  Você                       │ [Mapa][MapSpec][Camadas][Log]  │
│ [buscar…      Ctrl+K] │  Dinâmica 2026 da Fazenda   │ ┌────────────────────────────┐ │
│                       │  Trevisol, lote 65, com     │ │                            │ │
│ FIXADAS               │  AVN, AC e AUAS             │ │      preview.png           │ │
│ ▸ Trevisol Dinâmica   │                             │ │      (300 dpi, PDF em      │ │
│                       │  Assistente                 │ │       C:\MapasFacil\…)     │ │
│ HOJE                  │  Vou montar a Dinâmica…     │ │                            │ │
│ ▸ Lote 65 embargos ●  │  ┌───────────────────────┐  │ └────────────────────────────┘ │
│ ▸ Sítio Boa Vista     │  │ ▾ Listando shapefiles │  │ v3  atual   ● validado IMAP    │
│                       │  │   4 camadas em D:\…   │  │ v2  "ATP amarela"              │
│ ONTEM                 │  └───────────────────────┘  │ v1  primeira geração           │
│ ▸ Tipologia Querência │  ┌───────────────────────┐  │                                │
│                       │  │ ▾ Adicionando camada  │  │ C:\MapasFacil\trevisol\j91f\   │
│ 7 DIAS                │  │   AVN  ok             │  │ [copiar] [abrir pasta*]        │
│ ▸ Embargos IBAMA      │  └───────────────────────┘  │                                │
│                       │                             │ Etapa 8/9 exportando o PDF     │
│ ⋯ arquivadas          │  ┌───────────────────────┐  │ ████████████████░░░  01:12     │
│                       │  │ escreva sua mensagem  │  │ [cancelar]                     │
│ [conta] [agentes]     │  │            Enter ↵    │  │                                │
└───────────────────────┴─────────────────────────────┴────────────────────────────────┘
  sidebar de conversas      chat (streaming)             painel de contexto (4 abas)
```

`*` "abrir pasta" depende de um comando novo no protocolo do agente — ver
[Como abrir um arquivo local](#como-abrir-um-arquivo-local) e a pendência 4.

Sidebar: busca por título e conteúdo (`GET /v1/conversations?cursor=`, filtro no servidor), agrupamento
por data (Fixadas, Hoje, Ontem, 7 dias, Este mês, Antigas) e menu de contexto com renomear, fixar,
arquivar e excluir — todos `PATCH`/`DELETE /v1/conversations/{id}`. Ponto verde ao lado do título indica
job em andamento, o que permite sair para outra conversa enquanto o mapa gera.

Painel direito, quatro abas:

| Aba | Conteúdo | Fonte |
|---|---|---|
| Mapa | `preview.png`, link para o PDF, lista de versões com miniatura | `GET /v1/jobs/{id}/artifacts` |
| MapSpec | JSON com dobras por seção e diff destacado da última edição | `mapspec.updated` e `GET /v1/conversations/{id}` |
| Camadas | camadas do spec com cor, hachura, filtro, origem (local ou catálogo) e contagem | `MapSpec` + `fs.inspect` via `GET /v1/agents/{id}/fs` |
| Log do job | linhas de `job.log`, filtro por nível, botão copiar tudo | `GET /v1/jobs/{id}/events` |

Abaixo de 1280 px o painel direito vira gaveta sobreposta; abaixo de 768 px sidebar e painel são gavetas
e o chat ocupa a tela toda. O chat é o único elemento que nunca colapsa.

## UX de streaming

O stream do chat é a **resposta de um `POST`**, então `EventSource` está fora da mesa: ele só faz
`GET` e não aceita header `Authorization`. `lib/sse.ts` implementa o parser sobre `fetch`:

```ts
export async function* lerSSE(resp: Response): AsyncGenerator<EventoSSE> {
  const reader = resp.body!.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) return;
    buffer += value;
    let corte: number;
    while ((corte = buffer.indexOf("\n\n")) !== -1) {          // um bloco por evento
      const bloco = buffer.slice(0, corte);
      buffer = buffer.slice(corte + 2);
      if (bloco.startsWith(":")) continue;                     // heartbeat do backend
      yield parseBloco(bloco);                                 // { id?, event, data }
    }
  }
}
```

Consumo por evento, com o estado do turno em Zustand:

| Evento | Efeito na UI |
|---|---|
| `message.start` | cria a mensagem do assistente vazia com cursor piscando |
| `text.delta` | concatena no texto; `requestAnimationFrame` para agrupar deltas e não re-renderizar 60×/s |
| `tool.call` | insere cartão colapsável em estado "executando", com nome amigável |
| `tool.result` | fecha o cartão como sucesso ou falha, mostrando `resultado` |
| `mapspec.updated` | atualiza o painel MapSpec e destaca o `diff` recebido |
| `job.created` | abre a barra de progresso e assina `GET /v1/jobs/{id}/events` |
| `message.end` | remove o cursor, grava `usage`, invalida as queries de conversa e mensagens |
| `error` | encerra o turno e mostra o cartão de erro pelo `codigo` |
| desconhecido | **ignorado em silêncio** — é a regra de evolução do protocolo no 01 |

Cartões de tool call usam nome em português, não o nome técnico da tool:

| Tool | Rótulo enquanto executa | Rótulo depois |
|---|---|---|
| `listar_camadas_locais` | "Listando shapefiles no seu PC…" | "4 camadas encontradas em `D:\Projetos\Trevisol`" |
| `criar_mapa` | "Criando o mapa…" | "Mapa Dinâmica 2026 criado" |
| `adicionar_camada` | "Adicionando camada AVN…" | "Camada AVN adicionada" |
| `editar_tabela` | "Recalculando a tabela…" | "Tabela com 5 colunas atualizada" |
| `validar_mapspec` | "Conferindo o padrão IMAP…" | "Sem pendências" ou lista de problemas |

Colapsados por padrão, exceto quando falham — erro abre expandido. O mapeamento fica em um único
dicionário de tradução; tool desconhecida cai no nome cru, o que é feio mas nunca quebra a tela.

UI otimista: a mensagem do usuário aparece no instante do Enter, com opacidade reduzida até o
`message.start` confirmar. Se o `POST` falhar, a mensagem ganha botão "tentar novamente" em vez de
desaparecer — perder o texto que a pessoa digitou é imperdoável. Cancelamento é
`POST /v1/conversations/{id}/cancel` mais `AbortController` no `fetch`; a UI marca o turno como cancelado
na hora e mantém o texto parcial visível, porque ele costuma explicar por que o usuário cancelou.

## Seletor de agente local

Cabeçalho mostra o agente escolhido com estado: verde online, cinza offline (com "visto há 12 min"
calculado de `ultimo_hello_em`), amarelo online mas com doctor reprovado. Vem de
`GET /v1/agents`, revalidado a cada 20 s enquanto a aba está visível — mesmo período do heartbeat do
01, sem polling quando a aba está oculta.

Doctor como checklist visual (`GET /v1/agents/{id}/doctor`):

```
PC-GIS-01 — Windows 11 — agente 1.2.0
  [ok]    ArcMap 10.8.1        C:\Program Files (x86)\ArcGIS\Desktop10.8
  [ok]    Python 2.7 do ArcMap C:\Python27\ArcGIS10.8\python.exe
  [falha] Licença              ArcInfo indisponível — em uso por outro processo  [rever]
  [ok]    Templates .mxd       5 de 5 do manifesto
  [ok]    Pastas autorizadas   D:\Projetos (ler)   C:\MapasFacil (ler e escrever)
```

Cada item falho tem ação concreta em vez de mensagem genérica: licença abre a instrução de liberar o
ArcMap; template faltando oferece baixar o pacote; pasta ausente abre a tela de pastas autorizadas
(`PATCH /v1/agents/{id}`). Doctor reprovado não bloqueia a conversa — bloqueia só a criação de job com
`strict_mxd`, e nesse caso a UI explica que sai PDF mas não `.mxd`.

Pareamento, três passos numa única tela: (1) "Conectar meu PC" chama `POST /v1/agents/pair-code` e
devolve o código de 8 caracteres; (2) a UI mostra o código em monoespaçada grande com contagem
regressiva de 10 min (o TTL do 01) e botão para gerar outro; (3) o usuário digita o código no agente
instalado, e a tela, fazendo polling de `GET /v1/agents`, mostra o doctor do novo agente e o seleciona.

Estado vazio "nenhum PC conectado": ilustração, uma frase explicando por que o agente existe ("o ArcMap
está no seu computador, então o mapa é gerado aí"), botão primário para baixar o instalador e secundário
"já instalei, quero o código". Sem agente o chat continua utilizável para montar o `MapSpec` — só o
botão de gerar fica indisponível, com tooltip dizendo por quê.

## Progresso do job

Barra com as nove etapas do 01, com peso proporcional (5, 10, 20, 5, 15, 15, 5, 15, 10 por cento), o
que evita a barra que fica em 90 por cento por um minuto:

| Etapa (01) | Rótulo na UI |
|---|---|
| `validando_spec` | Validando o pedido |
| `resolvendo_camadas_locais` | Localizando seus shapefiles |
| `baixando_wfs` | Baixando camadas externas |
| `abrindo_template` | Abrindo o modelo `.mxd` |
| `repontando_fontes` | Apontando as camadas |
| `aplicando_layout` | Montando o layout |
| `salvando_mxd` | Salvando o `.mxd` |
| `exportando_pdf` | Exportando o PDF |
| `validando_saida` | Conferindo o padrão IMAP |

Mostra tempo decorrido (não estimativa — a variação entre imóveis é grande demais para prometer prazo),
a etapa atual em destaque, as concluídas marcadas e botão cancelar (`POST /v1/jobs/{id}/cancel`).

Quando o agente cai no meio, a UI **não** declara falha: o job segue `running` pelo contrato do 01. O
banner muda para "Seu PC desconectou. O mapa continua sendo gerado e o progresso volta quando ele
reconectar", o cronômetro continua e o botão cancelar permanece; só depois de `job_timeout` vindo do
backend a barra vira erro. O oposto — mostrar falha e o arquivo aparecer no disco depois — destruiria a
confiança no sistema.

Ao recarregar a página, `useJobEvents` reabre `GET /v1/jobs/{id}/events` enviando `Last-Event-ID` com o
último id recebido, e o backend faz replay de `job_events` (ver [02](02-backend-api.md)). Como o parser é
`fetch` e não `EventSource`, esse header vai manualmente.

## Histórico de versões do mapa

Cada geração é um job com `parent_job_id` e `versao` (01), e cada edição é uma linha nova em
`map_specs` com `parent_id`. A aba Mapa lista as versões em ordem decrescente:

```
v3  atual    14:32   "deixa a ATP amarela e tira a barra de escala"   [miniatura]  IMAP ok
v2           14:19   "adiciona os embargos do IBAMA"                  [miniatura]  IMAP ok
v1           14:03   "Dinâmica 2026 da Fazenda Trevisol, lote 65…"    [miniatura]  1 aviso
```

A frase de cada versão é a mensagem do usuário que originou o `MapSpec` daquela versão
(`messages.mapspec_id`). "Voltar para esta versão" **cria uma nova versão** a partir da antiga — nunca
sobrescreve, nunca apaga a linhagem: novo job com o `mapspec_id` da versão escolhida, e a lista passa a
mostrar `v4 (a partir da v1)`. Isso mantém a regra de append-only do 01 e torna impossível perder um mapa
já entregue ao cliente. Comparar duas versões abre o diff do `MapSpec` lado a lado, mais útil que
comparar imagens: a diferença aparece como "cor da camada ATP: `#00b050` → `#ffc000`", não como dois PNG
parecidos.

## Como abrir um arquivo local

O `.mxd` e o `.pdf` ficam em `C:\MapasFacil\<projeto>\<job_id>\`, e o navegador não pode abrir
`C:\...` por link: `file://` a partir de página HTTPS é bloqueado por todos os navegadores modernos,
por razão de segurança que não vai mudar. Não existe truque aceitável aqui.

A UI faz três coisas, em ordem de preferência:

1. **Caminho copiável.** O caminho completo aparece em fonte monoespaçada com botão de copiar. É o
   único mecanismo que funciona hoje sem contrato novo, e resolve o caso real: colar no Explorer.
2. **Abrir pasta / abrir no ArcMap pelo agente.** O agente é um processo local e pode executar a
   abertura. Isso exige um tipo de mensagem novo no protocolo (proposta na pendência 4), e a UI já
   deve prever o botão desabilitado com tooltip "requer agente 1.3+".
3. **Baixar cópia.** Só quando o artefato tiver sido enviado à nuvem (`artifacts.storage_key` não
   nulo), via `GET /v1/artifacts/{id}`. Por padrão isso não acontece: o 01 mantém os artefatos locais.

Consequência importante para o preview: o `.pdf` **não está no navegador** a menos que o usuário opte
por enviá-lo. A aba Mapa mostra o `preview.png` (opt-in, com aviso, conforme o 01) e, quando nem ele
existe, mostra o caminho local com a mensagem "o arquivo está no seu PC" em vez de um viewer vazio. O
`iframe`/`react-pdf` só entra em cena para artefato com URL assinada.

## Acessibilidade e atalhos

| Atalho | Ação |
|---|---|
| `Ctrl/Cmd + K` | busca de conversas |
| `Ctrl/Cmd + Shift + O` | nova conversa |
| `Enter` / `Shift + Enter` | enviar / quebrar linha |
| `Esc` | cancelar o turno em andamento; se não houver, fechar gaveta ou diálogo |
| `Ctrl/Cmd + \` | mostrar ou esconder o painel direito |
| `Ctrl/Cmd + 1..4` | ir para a aba Mapa, MapSpec, Camadas ou Log |
| `Ctrl/Cmd + Enter` | gerar o mapa com o `MapSpec` atual |

Acessibilidade: shadcn/ui já entrega foco e semântica de Radix, e o que precisa de cuidado explícito é o
streaming. O bloco de resposta é `aria-live="polite"` com `aria-busy` durante o turno, para o leitor de
tela anunciar o resultado sem ler cada delta; cartões de tool call são `<button aria-expanded>` de
verdade, não `div` com `onClick`; o foco volta para o composer ao fim do turno. O status do agente nunca
é comunicado só por cor — verde vem com "online" escrito ao lado, o que também ajuda quem tem deficiência
de percepção de cor olhando um mapa cheio de verdes. Contraste mínimo AA, inclusive nas amostras de cor
das camadas, que ganham borda para não sumir sobre fundo claro.

## Estados vazios, carregamento e erros

| Situação | O que a tela mostra |
|---|---|
| Nenhuma conversa | tela central com três exemplos de prompt clicáveis, tirados da série IMAP |
| Nenhum agente | ver [seletor de agente](#seletor-de-agente-local): CTA para baixar o instalador |
| Carregando conversas | skeleton de 6 linhas na sidebar, com a mesma altura das reais |
| Carregando mensagens | skeleton de bolhas alternadas; nunca spinner centralizado, que faz a tela pular |
| MapSpec ainda inexistente | "o JSON aparece aqui quando o mapa começar a ser montado" |
| Job em `queued` sem agente | banner "aguardando seu PC" com o estado do agente, não erro |

Erros do backend viram cartão com título, explicação e ação, mapeados em `lib/erros.ts` a partir do
`codigo` (nunca do texto de `mensagem`, que muda):

| Código | Título | Ação primária |
|---|---|---|
| `agent_offline` | Seu PC não está conectado | abrir o agente / baixar instalador |
| `agent_outdated` | Atualize o agente | atualizar agora |
| `mapspec_invalid` | O pedido precisa de ajuste | ir para o campo com problema no painel MapSpec |
| `template_not_found` | Modelo indisponível | escolher um dos modelos válidos |
| `layer_not_allowed` | Camada não encontrada | abrir a aba Camadas com o que existe na pasta |
| `arcpy_failed` | O ArcMap falhou ao gerar | ver log do job, tentar novamente |
| `license_unavailable` | ArcMap sem licença | como liberar a licença, tentar novamente |
| `path_not_allowed` | Pasta não autorizada | configurar pastas autorizadas |
| `job_timeout` | Demorou demais | tentar novamente |
| `rate_limited` | Limite atingido | mostra o limite e quando libera (`Retry-After`) |

Erro dentro do stream aparece como mensagem na conversa, não como toast: toast desaparece e o usuário
fica sem saber o que aconteceu com o mapa dele. Toast fica reservado para ações fora do chat, como
"conversa arquivada" com desfazer.

## Pendências e decisões abertas

1. **Autenticação do SSE de job.** `GET /v1/jobs/{id}/events` precisa de `Authorization`, o que
   inviabiliza `EventSource`. Usar `fetch` resolve, mas perde a reconexão automática — o
   `useJobEvents` tem de reimplementar backoff. Decidir se vale um cookie `httpOnly` de sessão para o
   caso específico de streams.
2. **`parent_job_id` na criação de job.** O corpo de `POST /v1/jobs` no 01 é
   `{conversation_id, mapspec_id, agent_id, strict_mxd}` e não tem `parent_job_id`, mas a tabela
   `jobs` tem a coluna e o botão "voltar para esta versão" depende dela. Proposta: aceitar
   `parent_job_id` opcional no corpo.
3. **Miniatura de versão sem `preview.png`.** Se o usuário não optar pelo upload do preview, a lista de
   versões fica sem imagem. Proposta: miniatura de 256 px gerada pelo agente como artefato separado e
   de upload opt-in independente, por ser muito menor que o preview de 300 dpi.
4. **Comando de abrir pasta ou arquivo.** Não existe no protocolo do 01 (os tipos backend → agente são
   `job.dispatch`, `job.cancel`, `fs.list`, `fs.inspect`, `doctor.run`, `agent.update`, `ping`).
   Proposta: `shell.open {caminho, com: "explorer" | "arcmap"}`, restrito à allowlist e sempre
   iniciado por clique explícito do usuário.
5. **Busca por conteúdo de mensagem.** `GET /v1/conversations` do 01 tem só `cursor` e `limit`. A busca
   da sidebar precisa de `?q=`, ou fica limitada a filtrar títulos no cliente.
6. **Diff do `MapSpec`.** O evento `mapspec.updated` traz `diff: [...]` sem formato definido.
   Precisamos do formato (proposta: JSON Patch RFC 6902, que tem biblioteca pronta nos dois lados)
   para desenhar o componente de diff.
7. **Indicador de job por conversa.** O ponto verde na sidebar exige saber se há job ativo sem abrir
   cada conversa. `GET /v1/conversations` hoje não devolve isso. Proposta: campo derivado
   `job_ativo: {id, etapa, pct} | null`.
8. **Multi-agente na mesma conversa.** `conversations.agent_id` é único, mas o usuário pode ter dois
   PCs. Definir se trocar de agente no meio da conversa é permitido e o que acontece com os jobs já
   gerados no outro PC.
9. **Título automático da conversa.** O 01 diz que o título é "gerado depois pela IA", sem definir quando
   nem por qual evento a UI descobre. Proposta: evento `conversation.renamed` no stream, ou simples
   invalidação da query no `message.end`.
10. **Editar o `MapSpec` à mão.** Técnicos vão querer mudar um hex de cor sem pedir à IA. Fora do escopo
    desta versão, mas decide se o painel MapSpec é somente leitura para sempre.
