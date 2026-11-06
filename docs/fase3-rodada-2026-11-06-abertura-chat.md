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
para aparecer. Nesta primeira rodada o texto era **ao vivo** (não ia para a conversa do núcleo); na
segunda rodada ele passou a ser gravado junto com a pergunta (ver abaixo).

## Segundo achado (mesmo dia): a pergunta chegava, mas 75 s depois

Teste do usuário com um pacote real (37 shapefiles, 450,6795 ha): a leitura apareceu, mas **nenhuma
opção**. O log do projeto mostrou o porquê:

```
17:48:03  pronto + chat.delta (leitura)
17:48:55  primeiro chat.raciocinio      (52 s depois)
17:48:57  listar_modelos_galeria
17:49:32  chat.pergunta                 (89 s depois do pronto)
```

A pergunta era do LLM (`perguntar`), e o modelo levava 52–89 s para chegar nela. O cartão só existe
quando o evento chega; até lá a tela mostra "Escolha abaixo..." e nada abaixo.

**Correção**: a abertura deixou de chamar o LLM. A leitura e a pergunta saem da indexação +
`galeria.listar`, em ~1,5 s; o turno fecha em seguida. A mensagem (texto + trace do `perguntar`) é
gravada na conversa com `chat.gravar_mensagem` (agora permitido na allowlist; **não** chama modelo),
então um F5 antes da primeira resposta devolve o cartão com as opções. O trace guarda o JSON
completo — o limite do `args_resumo` subiu de 500 para 4000 caracteres, porque 500 cortava a lista
no meio (3 de 6 opções voltavam ao recarregar).

```
2,4 s  pronto → chat.turno inicio → chat.delta (leitura)
3,9 s  chat.pergunta (6 opções da galeria)
3,9 s  nucleo.res
4,8 s  chat.turno fim
```

Conferido em navegador real: o cartão renderiza os 6 chips, clicar marca `data-respondida` e abre o
turno normal. O replay do SSE depois do turno não repete texto nem pergunta (o `nucleo.res` compacta
os eventos do turno); o histórico do núcleo é a fonte no reload.

## Deploy

Server (cópia, não git): `chat/abertura.py`, `api/mensagens.py`, `eventos/{vocabulario,log}.py`,
`ponte/allowlist.py` + núcleo `conversas/{servico,repositorio}.py` + build novo da SPA em
`Fase_3_Web/web/dist` (+ restart do `mapasfacil-app.service`). Testes: servidor (venv de teste local),
núcleo (`test_conversas.py`) e web (216) verdes.
