# Rodada 2026-11-03 — W2: ponte servidor ↔ núcleo

Marco: **W2** (plano [W-04](../Fase_3_Web/planos/04-ponte-nucleo-servidor.md) §Ponte)
Branch: `planos/fase3-web-chat` · executor: Hermes-windows · delegação: nenhuma

## Feito

| Tarefa | Arquivo | O que ficou |
|---|---|---|
| W2-01 | `servidor/mapasfacil_servidor/ponte/worker.py` | `Worker` com spawn `create_subprocess_exec(start_new_session=True)`, stdin/stdout NDJSON, `res` casado por `id`, `evt` para o dono da req (ou callback de projeto), timeout, morte → `SV-221`, linha inválida → `SV-230`, stderr redigido em `logs/workers/<projeto>.log` |
| W2-02 | `ponte/pool.py` | `Pool.obter/chamar/estado/encerrar_todos`, teto `max_workers` encerrando o **ocioso mais antigo**, espera de 60 s → `SV-211`, varredura de ociosidade a cada 60 s, um turno de `chat.enviar` por projeto → `SV-210` |
| W2-03 | `ponte/allowlist.py` + `tests/test_ponte.py` | 23 métodos permitidos, 16 bloqueados **com motivo escrito**, `SV-201` antes de tocar o worker; teste lê os `registrar()` do `__main__` do núcleo e falha se aparecer método sem classificação (e se a allowlist citar método inexistente) |
| W2-04 | `ponte/fake_nucleo.py` + `tests/roteiros/*.ndjson` | 4 roteiros: `indexar_ok`, `dinamica_ok` (progresso + log), `dinamica_falha_hard` (erro tipado), `morrer_no_meio` (kill -9 simulado) |
| W2-05 | `ponte/versao.py` + `tests/test_versao.py` | lê `Mapas/vNNN/`, copia artefatos, `conforme` = todos os HARD ok (SOFT reprovado não tira conformidade), miniatura = PNG; **o insert no SQLite fica no W3**, quando o schema existir |
| W2-06 | `tests/test_ponte_nucleo_real.py` | 3 testes `@pytest.mark.nucleo_real` contra o **núcleo real** (venv do núcleo): métodos reais × allowlist, `doctor.rodar` + `galeria.listar` pela ponte em modo servidor, env do worker |

## Comandos e resultados

```
cd Fase_3_Web/servidor
.venv/Scripts/python.exe -m pytest -q tests/     → 41 testes, 0 falhas
```

Inclui 3 testes que **sobem o núcleo de verdade** (`-m mapasfacil_nucleo`) em modo servidor e
conversam por stdio. Não há skip escondido: sem núcleo instalado eles pulam citando
`MF_PYTHON_NUCLEO`, e aqui eles rodaram.

## Critérios de aceite do W-04

| Critério | Como foi verificado |
|---|---|
| Matar o worker no meio do job → `SV-221`, próxima mensagem sobe worker novo | `test_morte_do_worker_derruba_a_requisicao` + `test_pool_sobe_worker_novo_depois_da_morte` |
| Teto de workers encerra o mais ocioso, sem matar job em curso | `test_pool_respeita_o_teto_encerrando_o_ocioso` (só encerra `estado == "pronto"`) |
| 3 gerações com `MF_MAX_JOBS=2` → a terceira espera | W1: `vagas.py` (`flock`) + `job.log` de espera; exercitado em `tests/test_modo_servidor.py` |
| `keyring` não é tocado em modo servidor | `test_cofre_le_env_e_nao_toca_keyring` (W1) — módulo explode se for importado |
| CPF em stderr aparece redigido | `test_stderr_vai_redigido_para_o_log` |
| Desktop continua igual | suíte do núcleo: 548 testes verdes sem `MAPASFACIL_MODO` |

## Decisões de implementação

1. **Handshake é `ping`, não `doctor.rodar`.** O núcleo já registra `ping` (resposta `{pong:true}`):
   prova o canal sem carregar manifesto nem sondar ArcMap a cada subida.
2. **`montar_env` repassa uma lista curta de variáveis do SO** (`SYSTEMROOT`, `WINDIR`, `COMSPEC`,
   `PATHEXT`, `TEMP`, `TMP`, `USERPROFILE`, `LOCALAPPDATA`, `NUMBER_OF_PROCESSORS`). Sem isso o
   Python no Windows nem inicializa o Winsock no filho (`OSError 10106` em `_overlapped`) — foi o
   que quebrou os primeiros testes. Não é herança do ambiente: é plomería do SO.
3. **`ErroServidor` deixou de ser `frozen`.** Mesma armadilha do `ErroNucleo`: exceção atravessando
   `@contextmanager`/fixture de gerador estourava `FrozenInstanceError`.
4. **`versao.conforme` nunca inventa conformidade**: sem `validacao.json` legível, é `False`.

## Pendências

- 🟠 **W1-10 (`doctor.py`)** continua bloqueada pela ordem do Álvaro (ver rodada do W1).
- 🟡 **Insert de versão no banco** depende do schema do W3 (W2-05 entregou só o registro).

## Próximo

W3 — API base (contas, sessões, projetos) no plano `03-api-e-projetos.md`.
