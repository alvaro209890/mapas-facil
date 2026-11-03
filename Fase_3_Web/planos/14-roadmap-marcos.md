# W-14 — Roadmap por dependência (W0 → W12)

Sem datas e sem estimativa de duração (AP-13). A ordem é a de dependência técnica. Um marco só
começa quando todos os que ele depende estão **fechados** (critério de saída verde e checklist
atualizado).

## Grafo

```
W0 Fundação
 │
 ├──▶ W1 Núcleo modo servidor + MapSpec v3 ──┬──▶ W9 PDF A4–A0 ──┬──▶ W10 .mxd binário
 │                                           │                   └──▶ W11 Inteligência cartográfica
 │                                           │
 │                                           ├──▶ W7 Eventos de motion no núcleo ─────────┐
 │                                           │                                            │
 │                                           └──▶ W2 Ponte e pool ──▶ W3 API base ──▶ W4 Importação ZIP
 │                                                                       │               │
 │                                                                       │               ▼
 │                                                                       └────────▶ W5 SSE + chat relay
 │                                                                                       │
 └──▶ (web) W6 Frontend: shell, login, projetos, assistente, chat ◀──────────────────────┘
                                   │
                                   └──▶ W8 Palco ◀── W7
                                          │
             MVP = W0–W8 + W9(A4,A3) ─────┴──▶ W12 Deploy + piloto
                                                 ▲
                         W10 e W11 entram no ar quando fecham (não bloqueiam o MVP)
```

## Trilhas que podem andar em paralelo (agentes diferentes, arquivos diferentes)

| Trilha | Marcos | Toca | Não toca |
|---|---|---|---|
| A — servidor | W2 → W3 → W4 → W5 | `Fase_3_Web/servidor/` | núcleo (só lê) |
| B — web | W6 → W8 | `Fase_3_Web/web/` | servidor, núcleo |
| C — núcleo/cartografia | W7 → W9 → W11 | `Fase_1_Desktop/nucleo/` (motores, validacao, motion) | servidor, web |
| D — `.mxd` | W10 (depois do W9) | `nucleo/mxd_binario/`, `ferramentas/`, Windows | web |

W1 é pré-requisito de A, C e D e deve ser feito **por um agente só**, antes de abrir as trilhas
(mexe em `config.py`, `cofre.py`, `sessao.py`, schema do `MapSpec` — arquivos que todas usam).
A trilha B pode começar logo depois do W0, contra o `fake_nucleo`/mocks de rota, mas só fecha o
W6 com o W5 pronto.

## Marcos

### W0 — Fundação e alinhamento documental

- **Entra:** nada.
- **Faz:**
  - **W0-01** registra D22–D39 em `planos/00-visao-e-duas-fases.md` (tabela de decisões e a
    tabela "Fora da v1", que hoje proíbe login/chat no site e sync de conversa);
  - **W0-02** revisa AP-01 e AP-12 no `AGENT_BRIEF.md` (com remissão a este diretório) e põe a
    Fase 3 no snapshot;
  - **W0-03** acrescenta "Fase 3" em `planos/README.md` (já há uma linha de ponteiro — completar);
  - **W0-04** esqueleto `servidor/` (pyproject, `__main__` com `--version`, `config.py`, `erros.py`);
  - **W0-05** `deploy/` e `fixtures/` com README;
  - **W0-10** `web/` (Vite vazio, [W-06](06-frontend-web-e-design.md));
  - **W0-20** roda `preflight.sh` no server e registra o que falta ([W-12](12-deploy-servidor-e-operacao.md));
  - **W0-30** `fase3.yml` com `guardas` e `desktop` ([W-13](13-testes-e-qa.md));
  - **W0-40** ~~perguntar P1–P4~~ — **feito em 2026-11-03**: P1–P10 respondidas e registradas em [W-00](00-visao-e-decisoes.md) §Decisões tomadas; no W0 só se registram D37–D39 também no comum.
- **Sai quando:** CI verde com os esqueletos; relatório do preflight anexado em
  `docs/fase3-w0-preflight.md` (sem segredo); D22–D39 registradas no comum.

### W1 — Núcleo em modo servidor + `MapSpec` v3

- **Entra:** W0.
- **Faz:** W1-01…W1-13 ([W-04](04-ponte-nucleo-servidor.md), [W-02](02-projeto-folha-e-upload.md)).
- **Sai quando:** `pytest` do núcleo inteiro verde **com e sem** `MAPASFACIL_MODO=servidor`;
  `test_modo_servidor.py` verde; `MapSpec` v2 antigo migra para v3 sem perder campo; desktop verde.

### W2 — Ponte e pool de workers

- **Entra:** W1.
- **Faz:** W2-01…W2-06.
- **Sai quando:** critérios de aceite de [W-04](04-ponte-nucleo-servidor.md) (kill -9, teto de
  workers, vagas, redação de stderr) verdes.

### W3 — API base: contas, sessões, projetos

- **Entra:** W2.
- **Faz:** W3-01…03, W3-10…11, W3-20…24.
- **Sai quando:** `test_auth.py`, `test_permissoes.py`, CRUD de projetos e máquina de estados verdes.

### W4 — Importação do ZIP

- **Entra:** W3.
- **Faz:** W4-01…09.
- **Sai quando:** critérios de [W-02](02-projeto-folha-e-upload.md) verdes, incluindo os ZIPs
  maliciosos e o teste de CPF.

### W5 — SSE + chat relay

- **Entra:** W4.
- **Faz:** W5-01…03 ([W-03](03-api-http-e-eventos.md)), W5-10…18 ([W-05](05-chat-agente-web.md)).
- **Sai quando:** `test_sse.py` e os 7 roteiros de conversa verdes.

### W6 — Frontend

- **Entra:** W0 (para começar), W5 (para fechar).
- **Faz:** W0-10, W6-01…10.
- **Sai quando:** Playwright `fluxo_basico` verde contra o servidor com `fake_nucleo`.

### W7 — Eventos de motion no núcleo

- **Entra:** W1.
- **Faz:** W7-01…10.
- **Sai quando:** job real no `imovel_ficticio.zip` emite os 3 eventos na ordem do contrato;
  roteiros gravados e válidos.

### W8 — Palco

- **Entra:** W6 + W7.
- **Faz:** W8-01…10.
- **Sai quando:** critérios de [W-07](07-motion-palco-do-mapa.md) verdes (coreografia, replay,
  reduced motion, FPS, visual).

### W9 — PDF A4–A0

- **Entra:** W1.
- **Faz:** W9-01…11.
- **Sai quando:** golden 5 folhas × 2 orientações × 3 modelos verde; A4 sem regressão. **Para o
  MVP basta A4 e A3** (as demais podem fechar depois do deploy, sem bloquear).

### W10 — `.mxd` binário

- **Entra:** W9 (o PDF nativo é a referência visual do G4).
- **Faz:** W10-01…12, com os spikes S0–S11 em ordem.
- **Sai quando:** critérios de [W-08](08-motor-mxd-binario.md) verdes. O pacote é oferecido
  sempre (D37); o G4 de desenvolvimento verde nas variantes A4 é o que dá ao agente a confiança de
  que o motor está certo.

### W11 — Inteligência cartográfica

- **Entra:** W9.
- **Faz:** W11-01…10.
- **Sai quando:** critérios de [W-10](10-inteligencia-cartografica.md) verdes, incluindo a
  reprodução das escalas da Análise PH.

### W12 — Deploy + piloto

- **Entra:** W0–W8 + W9 (A4/A3).
- **Faz:** W12-01…08, W12-20…22.
- **Sai quando:** critérios de [W-12](12-deploy-servidor-e-operacao.md) verdes e o piloto
  registrou pelo menos 15 mapas reais gerados por 3 pessoas, com os problemas anotados.

## Definição de "pronto" da Fase 3

1. Todos os marcos fechados, incluindo W10 e W11.
2. Os 6 critérios de sucesso de [W-00](00-visao-e-decisoes.md) medidos e registrados em
   `docs/fase3-resultado.md`.
3. `AGENT_BRIEF.md`, `planos/00…`, este diretório e o vault refletem o estado real.
