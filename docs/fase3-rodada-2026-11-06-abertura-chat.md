# Rodada 2026-11-06 — abertura do projeto não pode parecer "nada enviado"

Teste real no app (`mapasfacil-app.cursar.space`): criar projeto, subir o `imovel_ficticio.zip`
(fixtures), importar e acompanhar o SSE com carimbo de tempo.

## O que aparecia

| t | evento |
|---|---|
| 2,7 s | `projeto.estado = pronto` |
| **2,7 s → 27,4 s** | **chat vazio** — a tela mostrava a caixa "O que você precisa neste mapa?" |
| 27,4 s | primeiro `chat.raciocinio` |
| 75,3 s | `chat.pergunta` + `nucleo.res` |

A abertura não tem bolha de usuário (o prompt é `[ORIGEM: sistema]` e a tela o esconde): enquanto o
modelo pensava, `mensagens` e `blocos` ficavam vazios e o `Projeto.tsx` renderizava o estado de
boas-vindas — exatamente "como se eu ainda não tivesse enviado um prompt".

Além disso, o turno terminou **sem texto nenhum** (`assistente: ""`): o modelo chamou `perguntar`
direto, e a ferramenta **encerra o turno** (D40). O usuário via só a pergunta, sem a leitura do
pacote que o D41 promete.

## Correção

- **`chat.turno`** (novo evento de servidor, `{fase: "inicio"|"fim"}`) cerca todo turno:
  - abertura: `abertura.py` emite início antes de tocar no worker e fim num `finally` (worker que
    não sobe também fecha);
  - turno normal: `mensagens.py` emite início junto do `mensagem.criada` e fim no `finally`.
  A tela mostra "pensando" em vez da caixa de boas-vindas (inclusive em outra aba).
- **Apresentação determinística imediata**: `montar_texto_abertura` é emitido como `chat.delta`
  **antes** de `pool.obter` (2,43 s → **0,00 s** depois do `pronto`, medido).
- **Prompt da abertura**: o modelo não é mais convidado a apresentar (o `perguntar` encerraria o
  turno antes); ele só oferece os modelos. A pergunta determinística continua como Plano B quando
  o modelo não pergunta.
- `_abertura_ja_feita` saiu para fora do turno: reload de importação já aberta não pisca o aviso.

## Verificação (segundo teste real, no server)

```
2,43s  projeto.estado  pronto
2,43s  chat.turno      fase=inicio
2,43s  chat.delta      'Leitura do pacote concluída: Imóvel: Imóvel rural ...'
20,2s  chat.raciocinio
...
58,9s  chat.pergunta   'Qual modelo de mapa você deseja gerar ...'
58,9s  nucleo.res
58,9s  chat.turno      fase=fim
```

O bloco de texto nasce no mesmo instante do `pronto` — a caixa de boas-vindas não tem mais janela
para aparecer. O texto é **ao vivo** (não vai para a conversa do núcleo); ao recarregar, o painel de
resumo da importação segue mostrando os mesmos dados, e a pergunta (com as opções) está no histórico
pelos `tool_traces` do `perguntar`.

## Deploy

Server (cópia, não git): `chat/abertura.py`, `api/mensagens.py`, `eventos/{vocabulario,log}.py` +
build novo da SPA em `Fase_3_Web/web/dist` (+ restart do `mapasfacil-app.service`). Testes: servidor
(venv de teste local) e web (216) verdes.
