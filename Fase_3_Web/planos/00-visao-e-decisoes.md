# W-00 — Visão, jornada do usuário e decisões D22–D39

## Objetivo

Transformar o Mapas Fácil num **site com chat de IA** que cria e edita mapas oficiais da IMAP
(padrão SEMA-MT / perfil Harmonia), com o processamento no **server-desktop** e sem depender
de ArcMap em nenhum ponto da geração. Cada mapa é um **projeto**; o projeto nasce com folha e
orientação escolhidas e com um `.zip` de dados; daí em diante tudo acontece conversando.

O desktop (Fase 1) **não é apagado**: continua sendo o eixo do Windows com ArcMap e o lugar onde
os templates `.mxd` são preparados. O que muda é que o **núcleo Python** (`mapasfacil_nucleo`)
passa a ter dois "corpos": o Electron no Windows e o servidor web no Linux.

## Estado atual vs alvo

| Item | Hoje (2026-11-03) | Alvo da Fase 3 |
|---|---|---|
| Onde o usuário trabalha | app desktop Windows (Electron) | navegador, em qualquer PC |
| Onde roda o processamento | sidecar Python no PC do usuário | pool de workers no server-desktop |
| Site `mapasfacil.cursar.space` | landing + download (D21), roda no acer | continua igual; o app web ganha hostname próprio (D34) |
| Conta | local, SQLite no PC (F1-14) | no servidor, cadastro aberto; admin bloqueia (D27) |
| IA | DeepSeek V4 com chave do usuário (BYOK) | 9Router da VPS, `ag/gemini-3.8-flash-high`, raciocínio `high` (D33) |
| Conversas | locais (D20) | no servidor, uma por projeto (D26) |
| `.mxd` | T1 (ArcPy no Windows) ou T2 (cópia+patch de template) | só motor binário no servidor (D24); T1 continua só no desktop |
| Folhas | A4 retrato e A4 paisagem | A4, A3, A2, A1, A0 × retrato/paisagem (D31) |
| Animação | M8 no desktop: progresso, tools, preview por etapa | palco com câmera, acendimento de camadas e montagem da folha (D30) |

## A jornada, tela por tela

1. **Entrar.** `mapasfacil-app.cursar.space` → tela com duas abas: **Entrar** (e-mail + senha) e
   **Criar conta** (nome, e-mail, senha). Cadastro aberto, sem confirmação de e-mail (D27): criou,
   já entra. O admin pode bloquear uma conta a qualquer momento.
2. **Projetos.** Grade de cartões: nome, imóvel, município, folha, miniatura da última versão,
   data. Busca, filtro "arquivados". Botão **Novo mapa**.
3. **Novo mapa — passo 1: folha.** Cinco cartões de folha desenhados em proporção real
   (A4 pequeno … A0 grande), cada um com as medidas em mm; alternador **Retrato / Paisagem** que
   gira os cartões com animação. Padrão: A4 retrato. Campo **Nome do projeto**.
4. **Novo mapa — passo 2: dados.** Área de arrastar-e-soltar para **um** `.zip` (até o limite de
   [W-02](02-projeto-folha-e-upload.md)). Barra de envio por partes (real, por byte enviado),
   depois "verificando o pacote" (real, por arquivo extraído).
5. **Novo mapa — passo 3: o que o sistema achou.** Cartão de resumo: nome do imóvel, CAR,
   município/UF, área do recibo, lista de camadas reconhecidas (ATP, AVN, AC, AUAS, APP, ARL…),
   avisos ("AUAS sem `.prj`", "recibo sem quadro de áreas"). O palco já faz o primeiro zoom
   (estado → município → imóvel) porque o núcleo emitiu `viewport.foco` ao indexar.
6. **Projeto.** Tela dividida: **chat** à esquerda, **palco** à direita, **linha de versões** e
   **downloads** embaixo do palco. Campo de mensagem com sugestões ("Dinâmica 2026", "Série
   Análise de área completa", "Mapa de APP").
7. **Conversa.** O usuário escreve; a IA responde em streaming, mostra as ferramentas que usou
   (cartões retráteis), pergunta quando precisa (chips de opção) e, quando gera, o palco anima
   o job real. Cada edição vira uma **versão** nova; as anteriores ficam intactas.
8. **Entrega.** Botões: **PDF**, **XLSX**, **Pacote ArcMap** e "Relatório de conformidade"
   (HARD/SOFT). O pacote é **um `.zip` organizado como as pastas de análise do escritório**
   (`MXD/`, `SHP/`, `Mapas/` — D37): a pessoa baixa, abre o `.mxd` e, se o ArcMap pedir, só
   revincula os shapes à pasta `SHP/`. Tudo é liberado sempre, **sem validação manual de ninguém**.
   Se um check HARD falhou, a versão aparece como **"não conforme"** (selo na linha de versões, aviso
   nos downloads e no relatório) e a IA explica o que falhou e oferece corrigir — mas o download
   continua disponível.

### Exemplo de conversa (é o roteiro dos testes de ponta a ponta)

```
Usuário: faz a dinâmica 2026
IA:      li o recibo do CAR: Fazenda Boa Vista, MT123456/2019, Querência/MT, 1.240,5512 ha
         (palco: câmera desce MT → Querência → imóvel; ATP acende em amarelo)
         camadas locais: ATP, AVN, AREA_CONSOLIDADA, AUAS
         (palco: AVN acende verde, AC acende, AUAS acende vermelho)
         mosaico Planet de 03/2026 recortado · escala 1:40.000 na A4 retrato
         (palco: a câmera recua para a folha; moldura, grade, norte, minimapa, legenda,
          metadados e tabela entram na ordem real em que o motor os desenha)
         → versão 1: Dinamica_2026.pdf · Quantitativos.xlsx · pacote ArcMap
         14 checks HARD ok · 1 aviso: AUAS 2,1 ha fora da ATP

Usuário: a vegetação tá escura demais e tira a tabela
IA:      → versão 2 (estilo avn_claro, tabela desligada) — a versão 1 continua disponível

Usuário: passa pra A3 paisagem
IA:      a A3 paisagem comporta 1:25.000 com o imóvel inteiro (antes 1:40.000)
         → versão 3
```

## Escopo

### Dentro da Fase 3

- Cadastro aberto e login por e-mail e senha, troca de senha, sair; admin bloqueia conta.
- Projetos: criar, listar, buscar, renomear, arquivar, mandar para a lixeira.
- Folha A4–A0 e orientação na criação; troca de folha pelo chat gera versão nova.
- Envio de **um** `.zip` por projeto, por partes, com verificação de integridade; reenvio
  substitui a entrada e gera aviso de que as versões antigas usaram a entrada anterior.
- Chat em streaming com as 27 tools do agente do desktop + as tools novas de [W-05](05-chat-agente-web.md).
- Palco animado amarrado a eventos reais ([W-07](07-motion-palco-do-mapa.md)).
- PDF vetorial nativo em todas as folhas ([W-09](09-motor-pdf-nativo-e-folhas.md)).
- `.mxd` por motor binário, entregue sempre em pacote `MXD/ SHP/ Mapas/` com caminhos relativos ([W-08](08-motor-mxd-binario.md)).
- Quantitativos `.xlsx`, relatório de conformidade.
- Série "Análise de área" (20 mapas) disparada pelo chat, com o mesmo palco.
- **Visão**: interpretação de print/PDF de referência (`analisar_referencia`) pelo mesmo Gemini do
  chat (`MAPASFACIL_MODELO_VISAO=ag/gemini-3.8-flash-high`) — decisão de 2026-11-03, teste na W5-20.

### Fora da Fase 3 (e por quê)

| Fora | Motivo |
|---|---|
| Cobrança, planos, quota de produto | D18 continua: autenticado = ilimitado. Limite **técnico** (tamanho de upload, vagas de job) não é quota |
| Compartilhar projeto entre usuários, times | uma pessoa por projeto na v1; o admin vê tudo para suporte |
| Edição de geometria no navegador (desenhar, cortar polígono) | é trabalho de GIS — ArcMap/QGIS. O chat edita o **mapa**, não o dado |
| ArcMap/ArcPy no servidor | D24 |
| Gerar `.mxd` "do zero" (sem template) | D32 — o binário é remontagem de template, não autoria |
| ~~Visão (IA olhando print)~~ | **entrou na Fase 3 em 2026-11-03** (decisão do Álvaro): o Gemini 3.8 aceita imagem e a visão usa o mesmo modelo do chat — ver §Dentro da Fase 3 e W5-20 |
| App mobile | o site é responsivo para **consultar**; criar/editar mapa é desktop-first |
| Sync com o app desktop | os dois coexistem; projeto web não aparece no desktop e vice-versa |

## Decisões

Numeração continua a de [`../../planos/00-visao-e-duas-fases.md`](../../planos/00-visao-e-duas-fases.md)
(D1–D21). **No W0, o agente registra D22–D39 lá também** e marca o que cada uma revisa.

| # | Decisão | Revisa |
|---|---|---|
| **D22** | Existe uma **Fase 3**: app web com login + chat de IA que cria/edita mapas, backend no server-desktop. A landing de distribuição (Fase 2) continua; o desktop (Fase 1) continua | D21 (só para o app web; a landing segue D21) |
| **D23** | O backend **não reimplementa regra geo**. Ele hospeda o núcleo `mapasfacil_nucleo` como **processo filho por projeto**, falando o mesmo NDJSON por stdio que o Electron fala. Toda regra cartográfica continua num lugar só | — |
| **D24** | No servidor, `.mxd` só sai do **motor binário** (T2 patch de template + `mxd_binario`). ArcMap/ArcPy **nunca** roda no servidor | AP-01 ("nunca gerar `.mxd` em servidor Linux") vira "nunca **ArcPy** no servidor; `.mxd` no servidor só por motor binário que passou nos gates do W-08" |
| **D25** | **Um projeto = um mapa** (ou uma série, como a Análise de área). O projeto nasce com `folha` (A4–A0) e `orientacao`; a entrada é **um** `.zip`; há **uma conversa principal** por projeto | — |
| **D26** | Projetos, conversas e versões da Fase 3 ficam **no servidor**. O desktop continua local-only | D20 e AP-12, só para a Fase 3 |
| **D27** | **Cadastro aberto**: qualquer pessoa cria conta com nome, e-mail e senha (Argon2id, o mesmo `contas/senha.py` do núcleo), **sem confirmação de e-mail**, e já entra. A única trava contra abuso é o **admin bloquear a conta**. Sem OAuth. O admin também pode criar conta pela CLI | F2-05 (adiado) fica substituído por W-11 |
| **D28** | Metadados do backend em **SQLite WAL**, um processo uvicorn. Postgres só se um dia houver mais de uma instância | — |
| **D29** | Eventos para o navegador por **SSE** com replay por `Last-Event-ID`; comandos por `POST`. Nada de WebSocket na v1 (passa melhor por Cloudflare, reconecta sozinho, replay é trivial) | — |
| **D30** | Toda animação do palco é **consequência de evento real**. Vocabulário ganha três eventos: `viewport.foco`, `camada.renderizada`, `layout.elemento` ([W-03](03-api-http-e-eventos.md)) | AP-07 continua integral |
| **D31** | Folhas maiores que A4 = **perfil A4 medido escalado por igual** (todas as folhas A têm razão √2; é o mesmo que a opção do ArcMap "escalar elementos proporcionalmente ao tamanho da página"). Nenhum layout novo é inventado | H02 vira H02 (A4) + H15 (folha do `MapSpec`) |
| **D32** | Templates `.mxd` por folha são **fabricados uma vez no Windows** (ArcMap, offline, fora do caminho do usuário), entram no servidor com `sha256` no MANIFEST. O servidor só remonta | — |
| **D33** | A IA do servidor é o **9Router central da VPS** (`http://100.104.255.35:20128/v1`, pela tailnet) com o modelo **`ag/gemini-3.8-flash-high`** e `reasoning_effort: "high"` (o máximo que o 9Router honra), **para o chat e para a operação de mapas**. Chave **própria do Mapas Fácil** no 9Router (revogável, uso separado no painel), em `segredos/servidor.env` (600). DeepSeek direto continua possível por env, como alternativa | BYOK do desktop continua só no desktop |
| **D34** | Hostname do app: **`mapasfacil-app.cursar.space`** (um nível — o certificado universal da Cloudflare cobre `*.cursar.space`, **não** cobre `app.mapasfacil.cursar.space`). API no mesmo host, em `/api/v1` | confirmado (P1) |
| **D35** | Dado de cliente **nunca** entra no git. Testes usam ZIPs **sintéticos** gerados por script em `Fase_3_Web/fixtures/` | reforça AP-03/AP-09 |
| **D36** | O `MapSpec` sobe para `contract_version: 3` com o bloco obrigatório `folha`. v2 é migrado na leitura (folha sai do `formato_pagina` do template) | [`../../planos/02-mapspec-contrato.md`](../../planos/02-mapspec-contrato.md) é atualizado no W1 |
| **D37** | **Pacote sempre liberado**: toda versão gerada oferece PDF, XLSX e o pacote ArcMap (`.zip` com `MXD/`, `SHP/`, `Mapas/`, como as pastas de análise do escritório). Não há validação manual (de admin ou de ninguém). Os gates **automáticos** G1–G3 do `.mxd` e os checks HARD continuam rodando: falha vira selo "não conforme" + explicação da IA, **não** bloqueio de download. O G4 (abrir no ArcMap) é teste de **desenvolvimento** do motor, não portão de entrega | AP "HARD bloqueia a entrega" do comum vira "HARD marca a versão como não conforme" na Fase 3 |
| **D38** | Enquadramento = **"zoom na camada"**, como o escritório faz no ArcMap (medido na Análise PH): o conteúdo centrado na faixa útil do quadro (abaixo do título, fora do que o layout cobre), margem, e escala **redonda arredondada para cima** — sem lista fixa de escalas. Todos os mapas de uma série usam a **mesma** escala; mapas de contexto (TI, UC, TE de terceiro) enquadram imóvel + alvo + linha de distância ([W-10](10-inteligencia-cartografica.md)) | substitui a lista fixa de escalas e o H05 do comum |
| **D39** | Regras do escritório que entram no núcleo (vindas das skills, [W-17](17-conhecimento-das-skills.md)): série Dinâmica só leva AC/AVN/tabela nos marcos **2000, 2008 e atual**; imagem por ano (até 2015 mosaico SEMA; 2016 em diante Planet de **outubro**; ano corrente, o mês mais recente sem nuvem no imóvel); AC/AVN em **hachura** sobre satélite; nenhum texto, caixa ou tabela cobre linha de shapefile | — |

### Decisões tomadas pelo Álvaro em 2026-11-03

Todas as pendências foram respondidas. O agente **não** precisa perguntar de novo — só se o que
encontrar no código contrariar a decisão.

| # | Pergunta | Resposta | Onde aplica |
|---|---|---|---|
| P1 | Hostname do app web | `mapasfacil-app.cursar.space` | D34, W-12 |
| P2 | Quem pode criar conta | **cadastro aberto**, sem confirmação de e-mail; só o admin bloqueia conta (sem captcha, sem fila por conta) | D27, W-11, W-03, W-06 |
| P3 | Lixeira | 30 dias; o `.zip` original fica enquanto o projeto existir | W-02 |
| P4 | Admin vê projetos alheios | sim, **só leitura**, registrado na auditoria | W-11 |
| P5 | `.mxd` só depois do ArcMap conferir? | **não**: `.mxd`, PDF e dados saem sempre juntos no `.zip` organizado; a pessoa abre e, se preciso, revincula os shapes; nada de validação manual | D37, W-08 |
| P6 | `analises.cursar.space` | não é usado; **pode ser desligado** | W-12 (tarefa W12-08) |
| P7 | Backup externo | **nenhum** — fica só no HD do server | W-12 |
| P8 | Lista de escalas | sem lista: **zoom na camada** como no ArcMap, ver a Análise PH | D38, W-10 |
| P9 | S12 (áreas por classe × recibo) | **só avisa, sempre** (SOFT, nunca HARD) | W-10 |
| P10 | Descompilar DLL da Esri | **liberado em sala limpa** sempre que o diff e o Frida não explicarem um campo | W-08 §Laboratório |
| — | IA do servidor | **9Router da VPS, `ag/gemini-3.8-flash-high`, raciocínio `high`**, para chat e operação de mapas | D33, W-05 |
| — | Estrutura do pacote | **`MXD/ SHP/ Mapas/`** (igual às pastas de análise) | D37, W-08 |
| — | Visão (IA olhando print/PDF de referência) | **usa o mesmo Gemini do chat**: `MAPASFACIL_MODELO_VISAO=ag/gemini-3.8-flash-high`. A W5-20 deixa de ser opcional: testar o repasse de imagem pelo 9Router, ligar a visão e reabrir `analisar_referencia` na web | D33, W-05 (W5-20) |

## Critérios de sucesso da Fase 3

1. Do zero (login) ao primeiro PDF conforme de uma Dinâmica em **menos de 10 minutos** de
   relógio, com um `.zip` típico de CAR, no server-desktop.
2. 100% dos checks HARD verdes nos mapas entregues como "conforme".
3. Pacote baixado abre num ArcMap 10.x de outra máquina **sem `!` vermelho** — ou, no pior caso,
   com um único passo: revincular os shapes à pasta `SHP/` do próprio pacote.
4. Uma pessoa que nunca viu o sistema cria um projeto e gera o primeiro mapa sem ajuda.
5. Recarregar a página no meio de um job **não perde nada**: o palco reconstrói o estado pelo
   replay de eventos e continua.
6. Nenhum CPF em log, banco, prompt ou evento (varredura automática no CI e no servidor).

## Glossário

| Termo | Significado aqui |
|---|---|
| Projeto | uma pasta no servidor + uma linha no banco + uma conversa. Gera uma ou mais versões |
| Versão | um `MapSpec` versionado + os artefatos que ele gerou (`Mapas/vNNN/`) |
| Folha | formato de papel ISO A (A4–A0) + orientação |
| Palco | o painel animado da direita (câmera de mapa + montagem da folha) |
| Worker | processo `python -m mapasfacil_nucleo` dedicado a um projeto |
| Ponte | o código do backend que fala NDJSON com os workers ([W-04](04-ponte-nucleo-servidor.md)) |
| Motor binário | geração de `.mxd` por remontagem do CFBF de um template ([W-08](08-motor-mxd-binario.md)) |
| Perfil | geometria medida da página (mm) — `motores/perfil_pagina.py` |
| HARD / SOFT | check que bloqueia a entrega / check que só avisa ([`../../planos/01-padrao-imap-harmonia.md`](../../planos/01-padrao-imap-harmonia.md) §Checklist) |

## Anti-padrões específicos da Fase 3

| # | Não faça | Por quê |
|---|---|---|
| AW-01 | Copiar lógica do núcleo para o backend "porque é mais fácil" | duas fontes de verdade divergem; D23 |
| AW-02 | Expor `chamar(metodo)` genérico do núcleo para o navegador | o navegador viraria cliente de `cofre.*`, `conta.*`, `workspace.abrir` com caminho arbitrário; a API tem rotas próprias e a ponte tem allowlist ([W-04](04-ponte-nucleo-servidor.md)) |
| AW-03 | Animar etapa por `setTimeout` | AP-07; o palco só se move quando chega evento |
| AW-04 | Mandar geometria completa pelo evento SSE | evento carrega caminho de arquivo simplificado; o navegador baixa por rota autenticada |
| AW-05 | Guardar o `.zip` ou a pasta do projeto no SSD do server | o SSD tem ~19 GB livres; dado vive no HD (`/media/server/HD Backup/...`) — [W-12](12-deploy-servidor-e-operacao.md) |
| AW-06 | Abrir porta no `0.0.0.0` | o backend escuta `127.0.0.1:3130`; só o túnel fala com ele |
| AW-07 | Entregar `.mxd` sem rodar os gates automáticos G1–G3, ou esconder do usuário que um gate/HARD falhou | o pacote sai sempre (D37), mas o selo "não conforme" e a explicação são obrigatórios |
| AW-08 | Reaproveitar token/credencial anterior ao incidente de 15–16/10/2026 | chaves foram trocadas; use só segredo novo criado para este serviço |
