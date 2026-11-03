# W-06 — Frontend web e design

## Objetivo

Construir o app web (`Fase_3_Web/web/`) — telas, estado, cliente da API e do SSE — reaproveitando
o design system escuro e os componentes de chat do desktop, com uma experiência que pareça um
produto: o assistente de "Novo mapa" com escolha de folha visual, a tela do projeto com chat e
palco lado a lado, e entrega clara dos arquivos. O palco animado em si está em
[W-07](07-motion-palco-do-mapa.md).

## Estado atual vs alvo

| Item | Hoje | Alvo |
|---|---|---|
| Design system | `Fase_1_Desktop/app/src/estilos/tokens.css`, fontes Space Grotesk / IBM Plex embarcadas, dark padrão (D15) | copiados para `web/src/estilos/` |
| Chat | `PainelChat.tsx` + componentes + `src/chat/timeline.ts` + `src/estado/*.ts` | copiados para `web/src/herdados/` e `web/src/estado/`; fonte de eventos troca para SSE |
| Login | `src/telas/Login.tsx` com cena de mapa animada | adaptado: `web/src/telas/Entrar.tsx` |
| Galeria | `paineis/Galeria*.tsx` | **não** vira tela própria na web: vira sugestões no chat ([W-05](05-chat-agente-web.md)) |
| Roteamento | — (Electron é uma janela) | rotas por URL |

## Dependências

W3 (rotas), W5 (SSE + mensagens). O palco (W8) encaixa no espaço reservado aqui.

## Contratos

### Stack (versões exatas fixadas no `package.json` no W0, sem `^`)

Vite + React 19 + TypeScript estrito + zustand 5 + CSS Modules (mesmo do desktop) +
`maplibre-gl` + `motion`. Sem framework de componentes de terceiros (o desktop não usa; manter
o visual próprio). Roteamento: `react-router` (data router) **ou** roteador mínimo próprio em
`rotas.tsx` — o agente escolhe e registra a decisão no README do `web/`.

### Rotas

| URL | Tela | Exige sessão |
|---|---|---|
| `/entrar` | Entrar | não |
| `/` | redireciona para `/projetos` | sim |
| `/projetos` | Lista de projetos | sim |
| `/projetos/novo` | Assistente Novo mapa (passos 1–3) | sim |
| `/projetos/:id` | Projeto (chat + palco) | sim |
| `/projetos/:id/versoes/:n` | Projeto com a versão `n` aberta no palco | sim |
| `/conta` | trocar senha, sair | sim |
| `/admin` | usuários, auditoria, saúde | papel admin |

Sem sessão → `/entrar?volta=<url>`. Sessão expirada no meio do uso (`401 SV-002`) → modal
"sua sessão expirou" com login inline, sem perder o texto digitado no chat.

### Telas

#### Entrar (`telas/Entrar.tsx`)

- Fundo: a cena de mapa animada do `Login.tsx` do desktop (contorno de MT, linhas de grade
  que se desenham). É decorativa e **não** finge progresso — permitido (não é feedback de job).
- Duas abas: **Entrar** (e-mail, senha) e **Criar conta** (nome, e-mail, senha, repetir senha) —
  cadastro aberto, sem confirmação de e-mail (D27): criou, já entra em `/projetos`.
- Erros: `SV-001` ("e-mail ou senha não conferem"), `SV-003` ("esta conta foi bloqueada —
  fale com o administrador"), `SV-012` ("já existe conta com este e-mail — entre ou redefina a
  senha com o administrador"), `SV-010` (regra de senha mostrada antes de enviar), `SV-005` com
  contagem regressiva real devolvida pelo servidor.
- Conta criada pelo admin pela CLI (`trocar_senha: true`) → tela de troca obrigatória no primeiro acesso.

#### Projetos (`telas/Projetos.tsx`)

- Cabeçalho: busca (debounce 250 ms, `GET /projetos?busca=`), filtro (Ativos / Lixeira), botão
  **Novo mapa** (atalho `N`).
- Grade de cartões (3–4 colunas no desktop, 1 no celular). Cartão: miniatura da última versão
  (ou silhueta da folha na proporção certa, se não houver), nome, imóvel · município/UF, selo da
  folha ("A3 · paisagem"), selo de estado (`importando` com barra real, `erro_importacao` em
  vermelho com o código), data relativa. Menu do cartão: renomear, mandar para a lixeira,
  restaurar (na lixeira).
- Estado vazio: ilustração da folha + "Crie seu primeiro mapa".

#### Novo mapa (`telas/NovoMapa/`)

Três passos em uma rota, com indicador de passos no topo. Voltar não perde o que foi feito.

**Passo 1 — `PassoFolha.tsx`**

- Campo **Nome do projeto** (obrigatório, 1–120).
- Cinco cartões de folha **em escala real relativa** (A0 é 4× a largura da A4 na tela, com
  teto de altura: o conjunto cabe na largura útil; A4 continua legível). Cada cartão mostra o
  formato grande, as medidas em mm e o uso típico ([W-02](02-projeto-folha-e-upload.md) §Folhas).
- Alternador **Retrato | Paisagem**: os cinco cartões giram 90° com `motion` (spring, 420 ms;
  `prefers-reduced-motion` → troca instantânea). As medidas trocam.
- Selecionado: borda na cor de destaque + check. Padrão: A4 retrato.
- Botão **Continuar** → `POST /projetos` → passo 2 (o projeto já existe, em `aguardando_zip`).

**Passo 2 — `PassoZip.tsx`**

- Área de soltar arquivo (e botão "Escolher arquivo"); aceita **um** `.zip`. Outro tipo → erro
  local antes de enviar. Maior que `MF_UPLOAD_MAX_MB` (lido de `GET /saude`) → erro local.
- Texto de ajuda: o que colocar no `.zip` (pasta do CAR com ATP/AVN/AC/AUAS…, recibo do CAR em
  PDF, `.zip` do SIMCAR se tiver).
- Enviando: barra por **bytes confirmados** pelo servidor (`204` de cada parte), velocidade e
  tempo restante calculados dos últimos 10 s, botão Cancelar (aborta as partes em voo e
  `DELETE /uploads/{u}`). Queda de rede → "retomando…" e retomada automática pelo
  `GET /uploads/{u}`.
- Depois: "verificando o pacote" → lista de arquivos aparecendo conforme os
  `importacao.progresso` (real), e "lendo os dados do imóvel" durante `indexando`.
- Erro `SV-1xx`: mensagem do servidor com `o_que_fazer`; botão "Enviar outro .zip".

**Passo 3 — `PassoResumo.tsx`**

- À esquerda: cartão do imóvel (nome, CAR, município/UF, área do recibo vs área da geometria com
  a diferença), lista de camadas reconhecidas com ícone de papel e nº de feições, avisos.
- À direita: o **palco** já vivo, mostrando o primeiro voo estado → município → imóvel (vem do
  `viewport.foco` emitido na indexação) e o perímetro aceso.
- Botão **Abrir o projeto** → `/projetos/:id`.

#### Projeto (`telas/Projeto.tsx`)

Layout em duas colunas com divisor arrastável (posição guardada em `localStorage`, com
`try/catch`): **chat** (padrão 38%) | **palco** (62%). Abaixo do palco, faixa de **versões** e
de **downloads**. Em telas < 1024 px: abas "Chat" e "Mapa".

Coluna do chat (herdado do `PainelChat.tsx`):

- Cabeçalho: nome do projeto (editável inline), selo da folha, imóvel.
- Timeline: bolhas markdown (`BolhaMarkdown`), cartões de tool retráteis agrupados
  (`CartaoTool`, `GrupoTools`), raciocínio colapsado (`BlocoRaciocinio`), perguntas com chips
  (`CartaoPergunta`), indicador pensando (`IndicadorPensando`) amarrado a `chat.raciocinio`/
  primeiro `chat.delta` (já é assim no desktop).
- Chat vazio: cartões de sugestão de [W-05](05-chat-agente-web.md) §Sugestões.
- Campo de mensagem (`CampoEntrada`): Enter envia, Shift+Enter quebra linha, Esc cancela o turno
  (`POST /cancelar`) — mesma regra do desktop "Esc ≠ job": Esc cancela o **turno**; o job de
  geração só é cancelado pelo botão do palco.
- Avisos (`aviso`) viram item discreto na timeline e toast.

Coluna do palco: [W-07](07-motion-palco-do-mapa.md). Faixa embaixo:

- **Linha de versões** (`LinhaVersoes` herdado): bolinhas v1…vN com título curto, folha e selo
  conforme/não conforme; clique abre a versão no palco (rota `/versoes/:n`); hover mostra o diff
  resumido (`GET /versoes/{n}/diff/{n-1}`).
- **Downloads** da versão aberta: PDF, XLSX, Pacote ArcMap (`.zip` com `MXD/ SHP/ Mapas/`),
  Relatório de conformidade. **Sempre habilitados** quando a versão tem artefatos (D37). Versão
  não conforme: selo vermelho "não conforme" ao lado dos botões, com a lista curta dos HARD que
  falharam e o botão "pedir para a IA corrigir" (manda a mensagem pelo chat). Gate do `.mxd`
  falho (`MX-0xx`) ou folha sem variante (`MX-020`): o pacote sai com PDF, XLSX e `SHP/` e o aviso
  diz que o `.mxd` daquela versão não foi gerado e por quê.

#### Admin (`telas/Admin.tsx`)

Usuários (lista com busca e data do último acesso; **bloquear/desbloquear** com um clique e
confirmação — é a trava contra abuso do cadastro aberto; criar conta e redefinir senha, que mostra
a senha temporária uma vez com botão copiar), auditoria paginada, saúde (`/admin/saude`: workers,
vagas, disco, versão).

### Estado (zustand) — `web/src/estado/`

| Store | Conteúdo | Alimentado por |
|---|---|---|
| `sessao.ts` | usuário, csrf, estado (`desconhecida`/`ativa`/`expirada`) | `GET /auth/eu`, 401 global |
| `projetos.ts` | lista paginada, busca | `GET /projetos` |
| `projetoAtivo.ts` | projeto, resumo, versões, versão aberta | `GET /projetos/:id`, `projeto.estado`, `versao.criada` |
| `chat.ts` | timeline (herdada de `chat/timeline.ts`), turno em curso | `GET /mensagens` + `chat.*`, `mensagem.criada`, `nucleo.res` |
| `job.ts` | job em curso: etapas, pct, log, artefatos | `job.progresso`, `job.log`, `job.artefato_parcial` (herda `progressoJob.ts`, `logJob.ts`, `artefatos.ts`) |
| `palco.ts` | fila de eventos de motion e estado da coreografia | `viewport.foco`, `camada.renderizada`, `layout.elemento` ([W-07](07-motion-palco-do-mapa.md)) |
| `conexao.ts` | estado do EventSource (`conectado`/`reconectando`/`offline`), último `seq` | `api/eventos.ts` |

`web/src/api/eventos.ts`: um `EventSource` por projeto aberto (`withCredentials: true`),
`addEventListener("mf", …)`, parse, **descarte de `seq` ≤ último aplicado** (idempotência na
reconexão), despacho por `evento` para as stores. Reconexão é a do `EventSource`; se cair em
`offline` por mais de 30 s, banner "sem conexão — tentando de novo" (herda o `rede.ts` do desktop).

`web/src/api/cliente.ts`: `fetch` com `credentials: "include"`, header CSRF nas mutações, parse
do corpo de erro padrão para `ErroApi {codigo, mensagem, o_que_fazer}`, 401 → store de sessão.

Adaptador para reusar os stores do desktop sem reescrever: `web/src/api/ponteWeb.ts` implementa
o subconjunto de `ApiMapasFacil` (`Fase_1_Desktop/app/src/estado/ponte.ts`) que os stores
herdados usam — `aoEvento` (ligado ao SSE) e `aoEstadoNucleo` (ligado a `worker.estado`) — e
**não** implementa `chamar(metodo)` (AW-02): onde o store herdado chamava `chamar`, a cópia
web troca pela rota REST correspondente.

### Design

- Tokens: os do desktop (`tokens.css`), dark padrão; tema claro opcional em `/conta` (D15/AP-08).
- Tipografia: Space Grotesk (títulos), IBM Plex Sans (texto), IBM Plex Mono (números/códigos),
  woff2 servidos pelo próprio app (nada de CDN de fonte, igual ao desktop).
- Números: pt-BR, hectare com 4 casas (`3.823,9033`), escala `1:40.000`.
- Ícones: SVG inline próprio (os do desktop); papel de camada tem ícone e cor do estilo
  cartográfico (amarelo do perímetro, verde AVN, etc. — tirados de `motores/estilos.py` via um
  JSON exportado pelo núcleo: `python -m mapasfacil_nucleo estilos --json`).
- Movimento: `src/motion/tokens.ts` do desktop (durações/curvas) estendido no W8.
- Acessibilidade: foco visível, navegação por teclado no assistente e na timeline, `aria-live`
  "polite" para o texto do chat e para a etapa do job, contraste AA nos dois temas,
  `prefers-reduced-motion` respeitado em tudo.
- Responsivo: ≥ 1280 duas colunas; 1024–1279 duas colunas com chat 42%; < 1024 abas; ≥ 375 sem
  rolagem horizontal. Criar mapa no celular é possível mas não é o alvo.

## Tarefas agentáveis

- [ ] **W0-10** `web/` com Vite + React 19 + TS estrito + ESLint; `pnpm dev` com proxy `/api` → `127.0.0.1:3130`; build em `web/dist`.
- [ ] **W6-01** Copiar tokens, fontes (com OFL), `motion/` e os 10 componentes de chat para `web/src/` com cabeçalho de proveniência.
- [ ] **W6-02** `api/cliente.ts`, `api/eventos.ts`, `api/ponteWeb.ts`, `api/tipos.ts` (tipos gerados à mão a partir de W-03; teste compara o vocabulário).
- [ ] **W6-03** Stores da tabela.
- [ ] **W6-04** `telas/Entrar.tsx` com abas Entrar / Criar conta + troca de senha obrigatória (contas criadas pela CLI).
- [ ] **W6-05** `telas/Projetos.tsx`.
- [ ] **W6-06** `telas/NovoMapa/{PassoFolha,PassoZip,PassoResumo}.tsx` + `componentes/CartaoFolha.tsx` (desenho proporcional + giro).
- [ ] **W6-07** `telas/Projeto.tsx` com divisor, chat herdado, faixa de versões e downloads; espaço do palco com placeholder estático até o W8.
- [ ] **W6-08** `telas/Admin.tsx`, `telas/Conta.tsx`.
- [ ] **W6-09** Modal de sessão expirada que preserva o rascunho do chat.
- [ ] **W6-10** `servidor/estaticos.py`: serve `web/dist` com fallback SPA, `Cache-Control` imutável para assets com hash, `no-cache` para `index.html`.

## Critérios de aceite

- [ ] `pnpm -C Fase_3_Web/web test` (vitest) verde: stores aplicam um roteiro de eventos gravado e chegam ao estado esperado; `seq` repetido é ignorado.
- [ ] Playwright (contra servidor com `fake_nucleo`): criar conta → novo mapa A3 paisagem → enviar `imovel_ficticio.zip` → resumo com 4 camadas → abrir projeto → mandar "faz a dinâmica" → versão 1 aparece na linha → download do PDF responde `200 application/pdf`.
- [ ] Recarregar a página no meio do roteiro `dinamica_ok`: a timeline e a barra de etapas voltam ao mesmo ponto (replay) e continuam.
- [ ] Lighthouse (modo navegação) ≥ 90 em acessibilidade na tela de Projetos e no Projeto.
- [ ] Largura 375 px: nenhuma tela com rolagem horizontal.
- [ ] Nenhuma chamada a `chamar(` no `web/src` (grep no CI).

## Fora de escopo

- Editor de estilo por formulário (o estilo muda pelo chat).
- Arrastar elementos do layout na folha.
- PWA/offline.

## Anti-padrões

- Barra de progresso de upload por `progress` do XHR (mede buffer, não o que o servidor gravou).
- Guardar sessão em `localStorage` (é cookie HttpOnly).
- Componente herdado modificado sem atualizar o cabeçalho de proveniência com "(modificado)".
- Recriar o chat do zero em vez de reusar os componentes do desktop.
