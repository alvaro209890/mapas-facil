# Rodada 2026-11-03 — W5 (parcial): stream de eventos

Marco: **W5** (plano [W-03](../Fase_3_Web/planos/03-api-http-e-eventos.md) §Stream de eventos)
Branch: `planos/fase3-web-chat` · executor: Hermes-windows · delegação: nenhuma

Esta rodada fechou **W5-01, W5-02 e W5-03**. O chat (W5-10 a W5-20) é a próxima etapa.

## Feito

| Tarefa | Arquivo | O que ficou |
|---|---|---|
| W5-01 | `eventos/log.py` | NDJSON append-only por projeto em `.servidor/eventos.ndjson`; `seq` inteiro crescente **gravado antes de enviar**; `fsync` a cada 50 eventos ou 1 s; índice de offsets a cada 1.000 linhas; leitura tolerante a linha truncada por queda |
| W5-02 | `eventos/sse.py` + `api/eventos.py` | inscrição no fan-out **antes** da leitura do log (sem vão entre replay e ao vivo), descarte por `seq` já entregue, heartbeat `: ♥` a cada 15 s, cabeçalhos `no-cache`/`X-Accel-Buffering: no`, desconexão limpa, compactação na reabertura |
| W5-03 | `eventos/vocabulario.py` | eventos do núcleo (13, inclusive os 3 do palco) + 7 do servidor, origens fechadas, `EVENTOS_DE_JOB` |
| — | `api/importacao.py` | a importação agora publica `projeto.estado` e `importacao.progresso` no log e no hub — o stream mostra a extração ao vivo |

## Comandos e resultados

```
cd Fase_3_Web/servidor
.venv/Scripts/python.exe -m pytest -q tests/     → 121 testes, 0 falhas
```

Critérios de aceite do W-03 §SSE, medidos:

| Critério | Teste |
|---|---|
| 500 eventos gravados, `desde=250` recebe 251–500 | `test_replay_de_500_com_desde_250` |
| reconexão com `Last-Event-ID` não duplica | `test_replay_e_ao_vivo_sem_duplicata` (+ `test_replay_usa_indice_e_nao_duplica` no log) |
| `desde=0` com jobs terminados recebe versão compactada | `test_compactacao_quando_desde_zero_e_arquivo_grande` |
| heartbeat chega no prazo | `test_heartbeat_chega_quando_nao_ha_evento` |
| duas abas recebem o mesmo fluxo | `test_duas_abas_recebem_o_mesmo_evento` |
| rota HTTP real entrega `text/event-stream` com os eventos da importação | `test_sse_entrega_eventos_da_importacao` |

## Decisões de implementação

1. **Compactação sempre que `desde == 0`**, não só acima de 500 eventos. Job **terminado**
   (`nucleo.res`) vira 1 progresso final + camadas/layout/viewport + o próprio `nucleo.res`;
   job **em andamento** é reenviado inteiro, como o plano manda.
2. **Caminho com espaço é mascarado só até o espaço.** `/media/server/HD Backup/x` sai como
   `<caminho removido> Backup/x`. O prefixo que identifica a máquina não vaza; mascarar o
   resto exigiria adivinhar onde o caminho termina dentro de texto livre. Registrado no teste.
3. **`check_same_thread=False` no SQLite.** Rota `async def` executa a dependência síncrona
   em outro thread; a conexão é por requisição, então não há concorrência real sobre ela.
   Foi o que quebrou o primeiro teste HTTP do SSE.

## Pendências

- 🟠 **W1-10 (`doctor.py`)** continua bloqueada pela ordem do Álvaro.
- 🟡 **W5-10..W5-20 (chat)**: mensagens, conversa principal, tools, prompt web, provedor
  `openai_compat` no 9Router e a **visão obrigatória** (`MAPASFACIL_MODELO_VISAO`).
- 🟡 **`nucleo.res`** ainda não é emitido pela ponte ao fim de cada requisição — entra junto
  com o chat, que é quem sabe quando o turno acabou.

## Próximo

W5 (chat): `api/mensagens.py`, conversa principal, relay `chat.enviar` pela ponte e o
provedor `openai_compat` apontando para o 9Router da VPS.
