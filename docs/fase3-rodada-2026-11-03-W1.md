# Rodada 2026-11-03 — W1: núcleo em modo servidor + `MapSpec` v3

Marco: **W1** (plano [W-04](../Fase_3_Web/planos/04-ponte-nucleo-servidor.md), [W-02](../Fase_3_Web/planos/02-projeto-folha-e-upload.md))
Branch: `planos/fase3-web-chat` · executor: Hermes-windows (`th/deepseek-v4.1-flash-1017`, reasoning high)
Delegação: **nenhuma** — o W1 é explicitamente do executor (§1 da missão: arquivos que todos usam).

## Feito

| Tarefa | Onde | O que ficou |
|---|---|---|
| W1-01 | `nucleo/mapasfacil_nucleo/motores/folhas.py` (novo) | `FORMATOS` A4–A0 em mm, `folha_mm()`, `folha_padrao()`, `folha_do_template()` (lê `formato_pagina` do `MANIFEST.json`), `fator_k()`; CLI `mapasfacil folhas --json` |
| W1-02 | `config.py` | `MODO_SERVIDOR="servidor"`, `modo()` (valor desconhecido cai em `desktop`), `modo_servidor()`, `versao_saida()`, `pasta_saida_versao(v)` → `Mapas/v003` |
| W1-03 | `cofre.py` | `_ENV_POR_CHAVE` + `_valor_do_servidor()`; em modo servidor `definir()` → `NU-060`; `existe()`/`usar()` leem a env injetada pela ponte, **sem importar keyring** |
| W1-04 | `sessao.py` | `ENV_USUARIO_SERVIDOR`; `estado_atual()`/`conectada()` derivam da env; `definir()` → `AUTH-090` |
| W1-05 | `agente/provisao.py` | `sincronizar_chave_projeto_no_cofre()` → `{"ok": False, "motivo": "modo_servidor"}` |
| W1-06 | `workspace/watcher.py` | em modo servidor devolve `WatcherWorkspace` com `ativo=False`, sem thread |
| W1-07 | `projeto_servidor.py` (novo) + `workspace/servico.py` + `agente/tools.py` | lê `.servidor/projeto.json`; `abrir()` devolve `projeto`; `montar_memoria_trabalho()` ganha `memoria["projeto"] = {nome, folha}` |
| W1-08 | `config.py`, `analise/executar.py`, `galeria/montar.py`, `agente/tools.py` | saída versionada `Mapas/vNNN` e `Mapas/vNNN/serie` no servidor; desktop segue com `Mapas/` + sufixo `_vN` |
| W1-09 | `vagas.py` (novo) + `jobs.py` + `motores/gerar.py` | vaga por `flock` (POSIX) / `msvcrt.locking` (Windows), `MAPASFACIL_VAGAS_DIR`, `MAPASFACIL_MAX_JOBS`; `jobs.cancelado()`; sem diretório de vagas = sem limite (não derruba geração) |
| W1-10 | **bloqueada** | ver "Pendências" |
| W1-11 | `motores/gerar.py` | `_recusar_arcpy_no_servidor()` levanta `NU-127` dentro do `try` do T1, caindo no T2 (motor binário) — ArcPy nem é importado |
| W1-12 | `mapspec/migrar.py` (novo), `shared/schemas/mapspec.schema.json`, `mapspec/validar.py`, `analise/serie.py`, `shared/contract_version.json`, `planos/02-mapspec-contrato.md` | `contract_version = 3` com `folha` obrigatório (`formato`, `orientacao`, `escala_elementos`); migração v1/v2 → v3 determinística **na leitura** |
| W1-13 | `nucleo/tests/test_modo_servidor.py` (novo, 27 testes) | cobre config, cofre sem keyring, sessão, provisão, watcher, `projeto.json`, folhas, v3+migração, vagas, `NU-127` |

## Comandos e resultados (executados aqui, nesta máquina)

```
cd Fase_1_Desktop/nucleo
.venv/Scripts/python.exe -m pytest -q            → 548 testes, 0 falhas
MAPASFACIL_MODO=servidor .venv/Scripts/python.exe -m pytest -q -m "not desktop"
                                                 → 538 testes, 0 falhas
```

Os 10 testes de comportamento exclusivo de desktop (conta local, provisão, sessão local,
ArcMap, watcher ligado) ficam marcados `pytest.mark.desktop` e são **deselecionados** na
rodada em modo servidor; no modo desktop eles rodam normalmente. Marcador declarado em
`pyproject.toml` (`--strict-markers` ligado).

## Decisões de implementação que divergem do plano (e por quê)

1. **`folha` não deriva de `template`.** O plano 02 dava o formato de página ao template; com
   A4–A0 escolhido pelo usuário o mesmo template tem de servir a todos. `folha` virou campo
   obrigatório e `template` virou estilo — é o que a decisão D25 já implicava.
2. **`fator_k` vem dos milímetros ISO, não de `√2`.** `297/210 = 1,41429` e `841/210 = 4,00476`;
   A3 e A0 **não** são múltiplos exatos. Documentado no plano 02.
3. **Erro tipado deixou de ser `frozen`.** `ErroNucleo` atravessando `@contextmanager` ou
   fixture de gerador estourava `FrozenInstanceError` (o Python grava `__traceback__` na
   exceção). Sem `frozen`, o erro chega ao chamador com código e mensagem.
4. **Vaga sem diretório configurado = sem limite.** `NU-052` derrubava geração em qualquer
   ambiente sem `MAPASFACIL_VAGAS_DIR`; travar trabalho por falta de config de lock é pior que
   rodar uma geração a mais.
5. **Cofre/sessão em modo servidor continuam aceitando backend injetado por teste.** Em
   produção `_backend is None`, então `NU-060`/`AUTH-090` valem integralmente; os dublês de
   teste (memória) preservam as suítes antigas em ambos os modos.

## Pendências

- 🟠 **W1-10 (`doctor.py` modo servidor) — bloqueada por ordem do Álvaro.** `nucleo/mapasfacil_nucleo/doctor.py`
  está na lista de arquivos "de outro trabalho; não mexa neles". Revertido ao HEAD
  (`git checkout HEAD --`), junto com `motores/arcpy_ponte.py` (também modificado por engano).
  Equivalente entregue **fora** do arquivo: `workspace.servico._doctor_resumido()` devolve
  `{nucleo, pronto_para_mxd, motor_preferido, modo}` sem sondar ArcMap no servidor, e o
  `/api/v1/saude` (W3) vai reportar modo/motor a partir de `config`.
  **Preciso de você:** autorizar a edição de `doctor.py` (3 linhas no `_detectar_arcmap` + bloco
  em `rodar()`) ou manter a solução atual.
- 🟡 **`doctor.py` tem bug latente de Windows pt-BR:** `subprocess.run(["tasklist", ...])` sem
  `errors="replace"` estoura `UnicodeDecodeError: 0x80` na thread de leitura (code page 850).
  Hoje só aparece como warning no pytest; no servidor (Linux) o caminho nem é executado.
  Mesmo arquivo bloqueado — mesmo pedido de autorização acima.
- 🟡 **Banco de contas/sessões é do desktop.** O modo servidor tem usuário vindo da env; a
  tabela de contas do site nasce no W3, em SQLite próprio do servidor.

## Riscos

| Risco | Mitigação |
|---|---|
| Spec v3 gravado por motor antigo (v2) reabre migrado em memória e regrava v3 na próxima edição | migração é determinística; `contract_version.json` no repo impede divergência silenciosa |
| Nunca rodar ArcPy no servidor é garantido por `modo_servidor()` em `gerar.py` | teste `test_gerar_no_servidor_recusa_arcpy` + CI `guardas` |
| `flock` não existe no Windows | `vagas.py` usa `msvcrt.locking` na mesma interface; testado nos dois modos aqui |

## Próximo

W2 (ponte servidor ↔ núcleo e pool de workers), plano `04-ponte-nucleo-servidor.md` inteiro
antes de começar.
