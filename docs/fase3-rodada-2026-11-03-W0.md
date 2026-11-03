# Fase 3 — W0 — 2026-11-03

## Feito

- **W0-01** D22–D39 registradas em `planos/00-visao-e-duas-fases.md`, com coluna "Revisa"; as duas
  linhas revistas da tabela "Fora da v1" (login/mapa/chat no site e sync de conversas) estão
  marcadas com a decisão que as revisa. Nota no topo apontando a Fase 3.
- **W0-02** `AGENT_BRIEF.md`: AP-01 (ArcPy no servidor) e AP-12 (sync de chats) revisados pela Fase 3;
  parágrafo "Fase 3" no snapshot.
- **W0-03** `planos/README.md`: linha da Fase 3 na tabela de fases.
- **W0-04** `Fase_3_Web/servidor/`: `pyproject.toml` (versões fixas), `mapasfacil_servidor/`
  (`__init__`, `__main__` com `--version` e a superfície da CLI, `config.py`, `erros.py`),
  `tests/test_esqueleto.py`.
- **W0-05** `deploy/` (README + `scripts/preflight.sh`), `fixtures/` (README).
- **W0-10** `Fase_3_Web/web/`: Vite 6 + React 19 + TS estrito (`noUncheckedIndexedAccess`,
  `exactOptionalPropertyTypes`), vitest 3 + Testing Library, build em `dist/`.
- **W0-20** `preflight.sh` rodado no server-desktop; saída em `docs/fase3-w0-preflight.md`.
- **W0-30** `.github/workflows/fase3.yml`: jobs `servidor`, `web`, `e2e` (placeholder), `desktop`,
  `nucleo` e `guardas` (bind curinga, import de regra geo no backend, `chamar(`/`setTimeout` na web,
  segredo em texto, `.mxd` com chave).

### Decisão nova registrada

- **Visão usa o mesmo Gemini do chat** (`MAPASFACIL_MODELO_VISAO=ag/gemini-3.8-flash-high`), decisão do
  Álvaro em 2026-11-03: registrada em `W-00` §Decisões tomadas, na lista "Dentro da Fase 3", e a
  **W5-20 passou de opcional a obrigatória** (plano W-05 e checklist).

## Verificado (comandos e resultado)

| Suíte | Comando | Resultado |
|---|---|---|
| núcleo | `cd Fase_1_Desktop/nucleo && .venv/Scripts/python.exe -m pytest -q` | **521 passed**, exit 0 (231 s) |
| desktop | `cd Fase_1_Desktop/app && pnpm test` | **180 passed** (27 arquivos) |
| desktop | `pnpm typecheck` | exit 0 |
| servidor | `cd Fase_3_Web/servidor && .venv/Scripts/python.exe -m pytest -q` | **12 passed** (anel 1) |
| web | `pnpm typecheck` · `pnpm test` · `pnpm build` | exit 0 · **1 passed** · build 186 kB |
| guardas (local) | `grep` de `0.0.0.0`, import de regra geo, segredo em texto | vazio |
| `.mxd` | `python ferramentas/chaves_mxd.py verificar` | "Seguro para commit" |
| preflight | `bash preflight.sh` no server | 2 falhas, 1 aviso (abaixo) |

Testes do servidor cobrem: `--version`; `MF_RAIZ` ausente → `SV-000`; `servidor.env` ausente →
`SV-000` **dizendo o arquivo**; chave faltando → `SV-002` sem vazar valor; defaults do plano;
bind fora do loopback → `SV-001`; `https` obrigatório em `MF_URL_PUBLICA`; inteiro inválido; parser
do arquivo de segredos (comentário/aspas); comandos sem corpo → `SV-098`; guardas de `0.0.0.0` e de
segredo em texto.

## Não feito / pendente (com motivo)

- **Deploy e smoke ao vivo (anel 3)** — dependem de dois pedidos ao Álvaro (abaixo). O W0 não precisa.
- **`fonts-liberation`** no server: falta, exige `sudo`.
- **`segredos/servidor.env`** com a chave dedicada do Mapas Fácil no 9Router: falta, é do Álvaro.
- **Clone do repo no server** (`/home/server/mapasfacil/codigo`): W12. O preflight rodou de
  `/tmp/mf-preflight/`, o que bastou para o diagnóstico.

## Decisões tomadas (e quem decidiu)

- Código de boot: **arquivo de segredos ausente/modo frouxo = `SV-000`** (fecha o critério do W-01);
  **chave faltando dentro do arquivo = `SV-002`**. Antes o plano só dizia `SV-000` para o arquivo.
- O guarda de segredo em texto **não varre `Fase_1_Desktop/nucleo/tests/`**: lá há chaves falsas de
  propósito (casos do redator). Registrado no próprio W-17 e no job `guardas`.
- Piso de versões da web: Vite 6 / vitest 3 / TS 5.7 (a mesma geração do desktop). vitest 2 + Vite 6
  quebra o typecheck do `vite.config.ts` (tipos de Vite 5 no `vitest/config`).
- `*.tsbuildinfo` no `.gitignore`.

## Riscos e o que o próximo agente precisa saber

- O symlink `/home/server/mapasfacil` **já existe** no server, apontando para
  `/media/server/HD Backup/Servidores_NAO_MEXA/mapasfacil` (criado pelo preflight). Não recriar.
- A porta **3130** estava livre em 2026-11-03 10:36; conferir de novo antes do W12 (o mapa do vault
  reserva 3000–3199 para backends Node).
- O job `desktop` do CI é a rede de segurança do app Windows: nunca desligar para "passar".
- Segredos: o `Config` guarda as chaves lidas em `segredos_lidos`, fora do `repr`. Nenhum caminho de
  erro imprime valor — manter assim em todos os marcos seguintes.
