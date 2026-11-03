# Rodada 2026-11-03 — W3: API base (contas, sessões, projetos)

Marco: **W3** (planos [W-03](../Fase_3_Web/planos/03-api-http-e-eventos.md) e [W-11](../Fase_3_Web/planos/11-seguranca-contas-e-lgpd.md))
Branch: `planos/fase3-web-chat` · executor: Hermes-windows · delegação: nenhuma

## Feito

| Tarefa | Arquivo | O que ficou |
|---|---|---|
| W3-01 | `migracoes/0001_inicial.sql` + `db.py` | `usuarios`, `sessoes`, `auditoria`, `projetos`, `versoes`, `importacoes`; migração versionada idempotente, WAL e `foreign_keys=ON` |
| W3-02 | `projetos_repo.py` | CRUD, paginação por cursor estável, `SV-090` para transição inválida, `registrar_versao()` (fecha o W2-05 no banco) |
| W3-03 / W3-10 | `api/projetos.py`, `api/auth.py`, `api/admin.py`, `api/deps.py`, `api/modelos.py`, `app.py` | `/api/v1` com auth, projetos, admin e `/saude`; estado injetado por `create_app` |
| W3-11 | `app.py` | handler que converte `ErroServidor` no corpo `{erro:{codigo,mensagem,porque,o_que_fazer,detalhes}}` |
| W3-20 | `0001_inicial.sql` | índices por usuário/estado e por sessão |
| W3-21 | `auth/{senhas,sessoes,limitador,contas}.py` | scrypt com parâmetros no formato, token de sessão só em sha256, CSRF por sessão, 5 falhas/15 min → `SV-005`, renovação deslizante 30 d com teto de 90 d |
| W3-22 | `api/deps.py` + testes | `pegar_usuario`, `exigir_admin`, `exigir_csrf`; projeto alheio → `404 SV-031`; admin lê tudo |
| W3-23 | `__main__.py` | `conta criar/listar/bloquear/desbloquear` de verdade (senha temporária mostrada uma vez, `--admin`, `--sem-trocar`), `migrar` e `limpar-lixeira` |
| W3-24 | `logs_redigidos.py` | `redigir()` + `FiltroRedacao`; o worker da ponte passou a usar a mesma regra |
| W3-25 | `api/auth.py` + `auth/contas.py` | cadastro aberto (D27), bloqueio derruba sessões na hora, primeiro admin por `MF_ADMIN_EMAIL` |

## Comandos e resultados

```
cd Fase_3_Web/servidor
.venv/Scripts/python.exe -m pytest -q tests/     → 76 testes, 0 falhas
```

Cobrem: senha fraca/lista comum, e-mail inválido, duplicado, login errado com
mensagem idêntica para e-mail inexistente, bloqueio derrubando sessão, limitador,
CSRF ausente/errado, `Origin` estranho, projeto alheio, paginação, lixeira/restaurar,
admin criando e bloqueando conta, auditoria, CLI `conta` ponta a ponta e redação de log.

## Decisões de implementação

1. **scrypt no lugar de Argon2id.** O servidor não importa o núcleo (AW-01) e não
   carrega `argon2-cffi` por um detalhe que a stdlib resolve. O hash guarda os
   parâmetros (`scrypt$n$r$p$salt$hash`), então migrar de algoritmo depois é migração
   de dados, não reescrita.
2. **Cursor de paginação é o último item entregue**, não o primeiro da página
   seguinte — `?antes=` é exclusivo. Ordem `(atualizado_em DESC, id DESC)` para não
   perder projeto quando dois nascem no mesmo segundo.
3. **Bloqueio de conta apaga as sessões** no mesmo commit (`DELETE FROM sessoes`), e
   `pegar_usuario` também derruba sessão de conta inativa — cinto e suspensório.
4. **`/saude` é público e sem dado de usuário**; `/admin/saude` é do admin.

## Pendências

- 🟠 **W1-10 (`doctor.py`)** segue bloqueada pela ordem do Álvaro.
- 🟡 Upload (`/uploads`), importação e chat ficam para W4/W5 — as rotas ainda não existem.

## Próximo

W4 — importação do ZIP e indexação (plano `02-projeto-folha-e-upload.md` §Upload/Importação).
