# W-13 — Testes e QA

## Objetivo

Garantir que cada marco é verificável por outro agente sem conversar com quem implementou: anéis
de teste, fixtures sintéticas, roteiros de eventos gravados, testes visuais do palco, testes de
corpus do `.mxd` e o CI que roda tudo isso. Segue a convenção de anéis do repositório
(`AGENT_BRIEF.md` §Convenções: anel 1 puro no CI Linux, anel 2 com fake, anel 3 Windows, anel 4
ArcMap manual).

## Estado atual vs alvo

| Suíte | Hoje | Alvo |
|---|---|---|
| Núcleo | ~521 testes (pytest), CI `.github/workflows/nucleo.yml` | + modo servidor, motion, folhas, enquadramento, metadados, checks novos, `mxd_binario` |
| App desktop | ~180 (vitest) | **continua verde** — nenhuma mudança da Fase 3 pode quebrar |
| Servidor | — | pytest + httpx, anéis 1–2 |
| Web | — | vitest + Playwright |
| `.mxd` | auditoria ArcPy manual (anel 4) | corpus no CI (G1–G3) + G4 automatizado no Windows |

## Dependências

Todas. Cada marco do [W-14](14-roadmap-marcos.md) só fecha com os testes dele verdes.

## Contratos

### Anéis

| Anel | O que roda | Onde | Rede | GDAL | IA | ArcMap |
|---|---|---|---|---|---|---|
| 1 | puros: núcleo (lógica), servidor (rotas com banco em memória), web (stores, coreografia) | CI Linux | não | sim (o CI do núcleo já instala) | fake | não |
| 2 | integração: servidor + `fake_nucleo`; servidor + núcleo real com `imovel_ficticio.zip`; Playwright contra servidor local com `fake_nucleo` | CI Linux | não (camadas externas por cassete/cache) | sim | fake | não |
| 3 | smoke ao vivo no server: deploy de teste, 9Router real (`ag/gemini-3.8-flash-high`), WFS real | server-desktop | sim | sim | real | não |
| 4 | G4 (teste de desenvolvimento do motor): variantes `.mxd` abrindo no ArcMap; comparação PDF ArcMap × nativo; pacote descompactado em caminho com espaço/acento | Windows `pcque001imap` | tailnet | — | — | sim |

### Fixtures (D35 — nada de cliente)

| Fixture | Gerador | Conteúdo |
|---|---|---|
| `imovel_ficticio.zip` | `Fase_3_Web/fixtures/gerar_zip_sintetico.py` | ATP/AVN/AREA_CONSOLIDADA/AUAS em EPSG:4674 em coordenadas plausíveis de MT, mas **geométricas** (polígonos regulares desenhados pelo script, nunca recortados de dado real), recibo PDF falso com nome "Fazenda Fictícia Teste", CAR `MT000000/0000`, quadro de áreas coerente com os polígonos e CPF `000.000.000-00` |
| `imovel_ficticio_21s.zip` | idem com centroide a 56° W | testa zona 21S |
| `imovel_ficticio_20s.zip` | idem a 60,5° W | testa zona 20S |
| `imovel_alongado.zip` | retângulo 3:1 | S14, enquadramento |
| `imovel_sad69.zip` | o `imovel_ficticio` gravado em SAD69 UTM 22S (EPSG:29192), como vem o ArquivoGeometria do SIMCAR | conversão SAD69 → SIRGAS (W4-10) |
| `serie_bloco.zip` | 6 "matrículas" contíguas formando um bloco de ~12 km | escala única da série (D38), rótulo por matrícula, limite das matrículas |
| `zip_slip.zip`, `zip_bomba.zip`, `symlink.zip`, `nomes_cp437.zip`, `truncado.zip`, `sem_atp.zip`, `sem_prj.zip` | idem | segurança e erros de importação |

O gerador é determinístico (semente fixa) e os ZIPs **não** são versionados: o CI gera na hora.

### Roteiros de eventos

`Fase_3_Web/servidor/tests/roteiros/*.ndjson` + pasta irmã com os arquivos de `.preview`. Gravados
do núcleo real (W7-10) por `python -m mapasfacil_servidor gravar-roteiro --zip … --mensagem …`.
Usados por: `fake_nucleo` (servidor), `coreografia.test.ts` (web), Playwright. Regravar quando o
contrato de evento mudar; o teste `test_roteiros_validos.py` valida cada linha contra o
vocabulário e os `montar_dados_*` do núcleo — roteiro velho reprova.

### Testes por plano (resumo — o detalhe está no "Critérios de aceite" de cada plano)

| Plano | Arquivo(s) de teste principais |
|---|---|
| W-02 | `servidor/tests/test_importacao.py`, `test_uploads.py`, `test_folhas_espelho.py` |
| W-03 | `servidor/tests/test_sse.py`, `nucleo/tests/test_motion_contrato.py`, `test_eventos_job_real.py` |
| W-04 | `nucleo/tests/test_modo_servidor.py`, `servidor/tests/test_worker.py`, `test_pool.py`, `test_allowlist.py` |
| W-05 | `nucleo/tests/agente/test_roteiros_web.py` (7 cassetes) |
| W-06 | `web/src/**/*.test.ts(x)`, `web/e2e/fluxo_basico.spec.ts` |
| W-07 | `web/src/palco/coreografia.test.ts`, `web/e2e/palco_visual.spec.ts` |
| W-08 | `nucleo/tests/test_cfbf_corpus.py`, `test_gates_mxd.py`, `test_slots.py` |
| W-09 | `nucleo/tests/test_golden_anatomia.py` (parametrizado por folha) |
| W-10 | `nucleo/tests/test_enquadramento.py`, `test_metadados.py`, `test_checks_novos.py` |
| W-11 | `servidor/tests/test_permissoes.py`, `test_auth.py`, `test_pii.py` |
| W-12 | `deploy/scripts/preflight.sh` (anel 3), smoke do `atualizar.sh` |

### Testes visuais do palco

Playwright com o roteiro `dinamica_ok` e relógio controlado (`page.clock`): 6 capturas de
referência ([W-07](07-motion-palco-do-mapa.md) W8-10) em `web/e2e/__screenshots__/`, comparação
com `maxDiffPixelRatio: 0.02`. Rodam em Chromium no CI; o MapLibre usa WebGL por software
(SwiftShader) — se ficar instável, o teste visual do modo `mapa` vira só de estado (sources e
layers presentes), mantendo o visual dos modos `folha` e `resultado` (SVG/PNG, estáveis).

### CI — `.github/workflows/fase3.yml` (novo; o do núcleo continua)

| Job | Passos |
|---|---|
| `nucleo` | o existente + os testes novos do núcleo (rodam no mesmo workflow do núcleo) |
| `servidor` | Python 3.12, instala núcleo + servidor, gera fixtures, `pytest Fase_3_Web/servidor` (anéis 1–2) |
| `web` | Node 22, `npm ci`, `typecheck`, `lint`, `vitest`, `build` |
| `e2e` | depende de `servidor` + `web`; sobe servidor com `fake_nucleo`, roda Playwright |
| `desktop` | `pnpm test` + `typecheck` do `Fase_1_Desktop/app` — garante que a Fase 3 não quebrou o desktop |
| `guardas` | `grep` de anti-padrões: `0.0.0.0` no servidor/deploy; `chamar(` no `web/src`; `setTimeout` no `web/src/palco` fora do executor; `import mapasfacil_nucleo.(motores|camadas|agente|quantitativos)` no servidor; `ferramentas/chaves_mxd.py verificar` |

Nenhum job usa segredo real. 9Router, Planet e SEMA ficam em fake/cassete no CI. O job `guardas`
também roda o `grep` de segredo de [W-17](17-conhecimento-das-skills.md) §Critérios.

## Tarefas agentáveis

- [ ] **W0-30** `.github/workflows/fase3.yml` com os jobs (vazios onde o código ainda não existe, mas o `guardas` e o `desktop` já rodando).
- [ ] **W4-08** Gerador de fixtures ([W-02](02-projeto-folha-e-upload.md)).
- [ ] **W7-10** `gravar-roteiro` + roteiros + `test_roteiros_validos.py`.
- [ ] **W8-10** Testes visuais.
- [ ] **W10-02/07** Corpus e sabotagem do `.mxd`.

## Critérios de aceite

- [ ] `fase3.yml` verde no `main` depois de cada marco.
- [ ] O job `desktop` nunca foi desligado para "passar".
- [ ] Cobertura (relatório, não meta rígida): `servidor/` ≥ 85% de linhas; `mxd_binario/` ≥ 90%; `fsguard`/`importacao/extrair.py` 100%.

## Fora de escopo

- Teste de carga pesado (o porte é de escritório); só o teste de 3 gerações simultâneas do W-04.
- Testes em Safari/Firefox além de um smoke manual no piloto.

## Anti-padrões

- Fixture com dado real "anonimizado à mão".
- Marcar teste como `skip` para fechar marco.
- Regravar golden/screenshot sem olhar o diff (todo golden novo vai no commit com a justificativa).
