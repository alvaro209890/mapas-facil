# Rodada 2026-11-03 — W7 (palco do mapa, lado do núcleo e do servidor)

*(autor: Hermes-windows/default | 2026-11-03)*

O W7 no plano é metade núcleo (W7-01…10, em [W-03](../Fase_3_Web/planos/03-api-http-e-eventos.md)) e
metade web (W8-01…10). **Esta rodada fecha a parte do núcleo/servidor** — é ela que permite o
palco existir sem inventar animação: sem evento real do núcleo, nada se move (AP-07/D30).

## O que ficou pronto

| Tarefa | Entrega | Prova |
|---|---|---|
| W7-01 | `mapasfacil_nucleo/motion.py`: validação pura dos 3 eventos, `NIVEIS_VIEWPORT`, `PRIORIDADE_PAPEL`, `ELEMENTO_PARA_CAIXA`, `ORDEM_LAYOUT` | `tests/test_motion_contrato.py` — 28 verdes |
| W7-02 | `protocolo.EVENTOS` de 10 → **13** e `planos/01-arquitetura.md` §Eventos no mesmo commit | teste de vocabulário |
| W7-03 | `RastreadorProgresso.foco/camada/elemento` (sequência própria, `total` que só cresce, nível que não volta) | idem |
| W7-04 | Emissão real: `gerar.py` (estado, município, imóvel, camada), `nativo.py` (enquadramento, folha, layout), `agente/tools.py` (job_id também na tool do chat) | `tests/test_palco_eventos.py` — 7 verdes |
| W7-05 | Rota `GET /projetos/{id}/palco/{job}/{sub}/{arquivo}` + limpeza de `.preview` > 7 dias | `tests/test_palco_api.py` — 12 verdes |
| W7-06 | Recorte PNG por elemento a partir da página renderizada | arquivos em `palco_dinamica/layout/` |
| W7-07 | `palco.gravar_geojson` (4326, 6 casas, teto 2 MB / 20.000 vértices) | `test_geojson_do_palco_existe_e_e_simplificado` |
| W7-09 | `python -m mapasfacil_nucleo estilos [--json]` | manual, 24 estilos |
| W7-10 | `servidor/tests/roteiros/palco_dinamica.ndjson` (33 eventos reais) + assets | `tests/test_palco_roteiro.py` reprojeta o roteiro pelo contrato |

## O que a fixture real mostra (job sintético, sem dado de cliente)

```
1  job.progresso        validando_spec
2  viewport.foco        estado            (malha IBGE de MT, do repo)
4  viewport.foco        municipio         Vila Rica/MT
7  viewport.foco        imovel            Fazenda Harmonia (bbox 4326 do ATP)
8  camada.renderizada   perimetro
11 camada.renderizada   avn
19 viewport.foco        enquadramento     escala + EPSG + quadro_mm
20 viewport.foco        folha             A4 retrato
21 job.artefato_parcial aplicando_layout  (preview_png)
   layout.elemento × 6  grade, grade_linhas, titulo_caixa, norte, metadados, legenda
```

Ordem de acendimento = ordem de pintura do PDF (`PRIORIDADE_PAPEL`): perímetro → AVN → AC →
hidrografia → AUAS → demais locais → externas → basemap. O palco nunca desenha diferente do que
vai no papel.

## Decisões que a implementação forçou

- **`viewport.foco` de `enquadramento`/`folha` só existe dentro de job.** Fora de job o rastreador
  aceita só `estado`/`municipio`/`imovel` — se o motor roda sem `job_id` (CLI, desktop), nenhum
  evento de palco é emitido e nada de `.preview` é gravado.
- **`agente/tools.py` passou a registrar job**: a tool `gerar_mapa` do chat rodava com
  `RastreadorProgresso` **sem** `job_id`, o que zeraria o palco justamente no caminho da web.
- **Palco é acessório do job**: qualquer falha em GeoJSON/recorte vira `job.log`, nunca derruba o
  PDF. O contrato de entrega é o PDF; a vitrine não pode quebrar a entrega.
- **`.preview` fica fora do `.zip` do pacote** (é mídia do palco, não entrega) e é apagado em 7
  dias pela manutenção.
- **`estilo` do evento usa o dicionário do motor** (`cor_linha`/`hachura`/`largura`) e é traduzido
  para `{preenchimento, contorno, espessura_pt, padrao}` — o emissor não duplica paleta.
- **Malha IBGE do repo** (não API) para `estado`/`municipio`: `ibge.extent_uf()` novo, com
  `lru_cache`; UF/município fora da malha → log e a câmera começa no nível seguinte.

## Pendências honestas

| Item | Por que ficou |
|---|---|
| W7-08 (raster do basemap) | código ligado, **sem exercício real**: o fixture sintético não tem mosaico. Medir no anel 3, no server, com a série de verdade. |
| W7-10 completo | `palco_dinamica` feito dos mapas de dinâmica; `serie_analise` precisa do W9 e o `dinamica_falha_hard` do palco depende do check H17 (W9). |
| W8-01…10 | é a trilha da web (palco em React/MapLibre) — próximo marco. |

## Achados do preflight (medidos no server, 03/11)

| Antes | Depois | Causa |
|---|---|---|
| FALTA `fonte Liberation` | **OK** (`Liberation Sans`) | `fc-list \| grep -q` sob `set -o pipefail`: o `grep -q` sai no primeiro acerto, o `fc-list` morre com SIGPIPE (141) e a pipeline inteira é "falha". Trocado por `fc-match` (uma linha, sem SIGPIPE). |
| FALTA `servidor.env` "modo 777" | **OK 0600** | o caminho dentro do projeto é **symlink** para o ext4; `stat` sem `-L` lia 777 do link. Agora `stat -Lc`. |

Preflight atual: **9 OK, 1 FALTA** — `MAPASFACIL_SEMA_AUTHKEY` e `MAPASFACIL_PLANET_API_KEY`, que
**não estão em nenhum cofre** acessível daqui (nem no do server, nem no do Windows). São do Álvaro.

## Testes ao fim da rodada

| Suíte | Resultado |
|---|---|
| núcleo | **665 verdes** em 68 arquivos (0 falha) |
| servidor | **176 verdes** em 15 arquivos (0 falha) |

⚠️ Achado de operação: o nome `dinamica_ok.ndjson` **já existia** desde o W2 como roteiro do
`fake_nucleo`. O gerador do palco grava `palco_dinamica.ndjson` justamente para não pisar nele — a
primeira versão pisou e quebrou `test_ponte.py` (corrigido e documentado no próprio gerador).
