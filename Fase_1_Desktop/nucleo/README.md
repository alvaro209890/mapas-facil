# nucleo/

Sidecar Python da Fase 1 — geo, `MapSpec`, motores de `.mxd`/PDF, quantitativos e `fsguard`.
Comunica com o Electron por NDJSON (stdio), quando a UI existir. Empacotamento previsto:
PyInstaller onedir junto do app.

**Status:** M1 **bloco A fechado**; **bloco B parcial** (sem ArcMap). **v0.4.0** — A9 fechado: o
núcleo emite `job.progresso`, `job.artefato_parcial`, `chat.delta` e `chat.tool`.

Acervo de calibração: [`Referencias_IMAP/Mapas/03/`](../../Referencias_IMAP/Mapas/03/README.md).

Documentação do bloco B: [`docs/bloco-b-sem-arcmap.md`](docs/bloco-b-sem-arcmap.md).
Checklist: [`../planos/13-checklist-implementacao.md`](../planos/13-checklist-implementacao.md).

Planos: [`../planos/03-nucleo-python.md`](../planos/03-nucleo-python.md),
[`../planos/04-motor-mxd.md`](../planos/04-motor-mxd.md),
[`../planos/01-arquitetura.md`](../planos/01-arquitetura.md).

## Estrutura

```
nucleo/
  pyproject.toml
  docs/
    bloco-b-sem-arcmap.md
  mapasfacil_nucleo/
    __main__.py             # loop NDJSON + CLI doctor
    protocolo.py            # envelopes, Emissor de eventos, Roteador
    progresso.py            # as 10 etapas de job.progresso
    config.py
    erros.py
    fsguard.py
    doctor.py
    geo/                    # area, crs, bbox_shp, ogr2ogr
    camadas/materializar.py
    workspace/              # indice, shapefile, zip_simcar, recibo_car, servico, papeis
    motores/
      manifesto.py
      gerar.py
      patch_mxd.py
      arcpy_ponte.py
      nativo.py             # PDF matplotlib + overlay tabela PNG
    scripts/arcpy_job.py    # py2.7 — NUNCA importado pelo núcleo 3.12
    validacao/
      relatorio.py
      comparar_pdf.py
    quantitativos/
      calcular.py
      xlsx.py
      png_tabela.py
      conferencia.py
    mapspec/
      validar.py
      diff.py
  tests/                    # anel 1 — CI Linux (133 testes coletados)
```

## Desenvolvimento

Requisitos: **Python 3.12+**.

```bash
cd Fase_1_Desktop/nucleo
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

### CLI

```bash
# Diagnóstico (humano ou JSON)
python -m mapasfacil_nucleo doctor
python -m mapasfacil_nucleo doctor --json

# Loop NDJSON (como o Electron vai usar)
python -m mapasfacil_nucleo stdio
```

Exemplo de requisição NDJSON:

```json
{"v":1,"id":"01J8X","tipo":"req","metodo":"mapspec.validar","params":{"mapspec":{…}}}
```

### Métodos implementados (v0.4.0 + M6 + M7)

Registrados em `criar_roteador()` — **33 métodos**:

| Método | Descrição |
|---|---|
| `ping` | smoke test |
| `doctor.rodar` | diagnóstico (stub em Linux; ArcMap/chave/rede no Windows) |
| `mapspec.validar` | schema + catálogo + invariantes (CRS, pasta, minimapa, metadados) |
| `mapspec.diff` | lista operações entre duas versões do MapSpec |
| `workspace.abrir` | indexa pasta + lê recibo do CAR (`id_local` = stem do `.shp`) |
| `workspace.reindexar` | atualiza índice |
| `workspace.inspecionar` | metadados de `.shp` ou PDF |
| `car.ler_recibo` | parser do recibo (sem CPF) |
| `mapa.gerar` | SHP/, cópia/patch `.mxd`, PDF nativo com overlay da tabela, quantitativos, `.xlsx`, PNG; `comparar_baseline` opcional |
| `quantitativos.calcular` | áreas a partir das camadas locais |
| `quantitativos.exportar_xlsx` | `*_Quantitativos.xlsx` (inclui aba Conferência) |
| `quantitativos.renderizar_png` | `recursos/tabela_quantitativos.png` (≥ 600 dpi) |
| `validacao.comparar_pdf` | diff raster entre PDFs (tolerância 0,3%) |
| `artefato.ler` | M8 — bytes de PNG/JPG do workspace em base64 (o renderer nunca lê disco) |
| `zip.listar` / `zip.extrair` | ZIP SIMCAR (anti zip-slip) |
| `template.listar` / `template.verificar` | MANIFEST; `sha256_ok` se hash registrado |
| `galeria.listar` / `detalhar` / `montar_mapspec` | M4 — catálogo e MapSpec determinístico |
| `chat.criar_conversa` / `listar_conversas` / `abrir_conversa` / `carregar_anteriores` | M6 — histórico local |
| `chat.renomear` / `arquivar` / `apagar` / `ramificar` / `buscar` | M6 — gestão e FTS |
| `chat.gravar_mensagem` | M6 — gravação determinística (sem LLM) |
| `chat.enviar` / `chat.cancelar` | M7 — orquestrador + stream `chat.delta`/`chat.tool` |

**Não implementado neste sidecar:** tools stub do agente (`IA-022`), visão, cliente WFS/SEMA em runtime.
Conta local / gate AUTH (M5) **implementados**.

### Eventos emitidos (v0.4.0)

| Evento | Dados | Quando |
|---|---|---|
| `job.progresso` | `{etapa, pct, item?}` | durante `mapa.gerar`, ao concluir cada etapa |
| `job.artefato_parcial` | `{tipo, caminho, etapa, camada_id?, ordem?, pct?}` | M8 — artefato intermediário pronto (`camada`, `tabela_png`, `preview_png`, `pdf`) |
| `chat.delta` / `chat.tool` | ver [F1-06](../planos/06-agente-eng-florestal.md) | M7 — durante `chat.enviar` |

Semântica (fixada em `progresso.py`): o evento sai **ao concluir** uma etapa — `etapa` é a que
terminou e `pct` é o acumulado (3, 10, 30, 40, 45, 55, 70, 75, 90, 100). Nas etapas de camada
(`resolvendo_camadas_locais`, `baixando_externas`) vêm eventos intermediários com `item` =
`camadas[].id`. `pct` é monotônico. Nada é simulado por timer.

```json
{"v":1,"id":"01J8X","tipo":"evt","evento":"job.progresso","dados":{"etapa":"exportando_pdf","pct":90}}
```

No `stdio` os eventos saem na hora (com `flush`), antes da linha de `res` da requisição. Quem chama
`processar_linha` sem sink recebe os eventos no prefixo da string devolvida.

`job.artefato_parcial` sai com caminho **sempre relativo** à pasta do projeto (`artefatos.py`
recusa absoluto e `..`); as rasterizações vão para `Mapas/.preview/parcial_NN.png` a 72 dpi e só
são geradas quando há canal de eventos. Para os bytes, o renderer chama `artefato.ler` — nunca lê
o disco direto (F1-01, fronteira 1).

O vocabulário de eventos é fechado em `protocolo.EVENTOS`: emitir nome fora da lista levanta erro.
Emitidos: `job.progresso`, `job.artefato_parcial`, `chat.delta`, `chat.tool`, **`workspace.mudou`**
(A12 — watcher com debounce 500 ms; eventos fora de req saem pelo `configurar_sink_assincrono`).
Ainda sem emissor: `job.log`, `mapspec.atualizado`, `aviso`.

### Limites conhecidos (honestos)

- Doctor não detecta ArcMap/GDAL versão/rede fora do Windows.
- `dinamica_retrato` está `parcial` (sha256 ok; offsets `{}`). Os outros 4 templates estão `a_preparar` (`sha256: null`). `pronto_para_mxd` exige **todos** com sha256 e (patch `pronto` ou ArcMap sondado) — hoje fica `false`.
- PDF nativo é estrutural (não paridade visual Harmonia); já sobrepõe a tabela PNG quando `elementos_layout.tabela` (ou equivalente). Ordem de camadas: menor `ordem` por cima.
- Materialização B4: cópia + **ogr2ogr opcional** (fallback cópia se GDAL ausente).
- Sem agente: o núcleo só executa MapSpec / workspace / motores — não gera MapSpec por linguagem natural.

## CI

Workflow [`.github/workflows/nucleo.yml`](../../.github/workflows/nucleo.yml) — `pytest` anel 1 no Ubuntu,
cobertura 100% em `fsguard`, validação do MapSpec canônico em `shared/fixtures/mapspecs/`.

## Próximos passos (realidade)

Numeração de marcos conforme [`../planos/12-roadmap.md`](../planos/12-roadmap.md) (M0–M11).

- ~~A9 — emitir `job.progresso`~~ **fechado na v0.4.0** (`progresso.py`, `motores/gerar.py`)
- ~~A12 — watcher/`workspace.mudou`~~ **fechado** (`workspace/watcher.py`, debounce 500 ms)
- A10 — `mapa.cancelar`; A11 — `cofre.*`; A13 — `catalogo.listar`
- B1 manual no ArcMap: `TITULO`, `ROTULO_IMOVEL`, minimapa, logo → depois calibrar offsets (B2)
- Smoke Harmonia: PDF nativo vs `Mapas/01` ainda não passa (motor estrutural)
- Evoluir PDF nativo (F1-05): grade DMS, rosa, metadados, minimapa, logo
- Galeria (M4) — métodos `galeria.*`, ver [`../planos/15-galeria-de-modelos.md`](../planos/15-galeria-de-modelos.md)
- Conta local (M5) — `conta.criar`/`entrar`/`sair`/`estado` + `sessao.*` + gate `AUTH-030`
- Conversas (M6) — `chats.sqlite` e os 9 métodos `chat.*` de histórico
- Agente (M7) — pasta `agente/` não existe; ver [`../planos/06-agente-eng-florestal.md`](../planos/06-agente-eng-florestal.md)
- UI Electron (M3) — `Fase_1_Desktop/app/` existe e está **parcial**: scaffold, ponte NDJSON,
  tokens e fontes; falta o shell de painéis e a barra de progresso (ver o README de lá)
