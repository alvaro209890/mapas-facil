# F1-03 — Núcleo Python

O sidecar onde toda a geo acontece. Empacotado junto do app, falado por NDJSON no stdio
([`01-arquitetura.md`](01-arquitetura.md)).

## Estrutura

```
nucleo/
├─ __main__.py               loop NDJSON, roteamento de métodos
├─ protocolo.py              envelope, ULID, serialização de erro
├─ config.py                 caminhos, TTLs, limites
├─ cofre.py                  keyring (CM/Secret Service); NUNCA devolve valor
├─ fsguard.py                autorização de caminho  ← suíte de testes mais densa
├─ workspace/
│  ├─ indice.py              varredura, metadados, papel de cada arquivo
│  ├─ watcher.py             debounce, reindexação incremental
│  ├─ shapefile.py           .shp/.dbf/.prj, bbox por cabeçalho, encoding
│  ├─ recibo_car.py          parser do PDF (PyMuPDF) — descarta CPF
│  └─ zip_simcar.py          listagem, anti zip slip, extração
├─ camadas/
│  ├─ catalogo.py            lê shared/catalog/*.json
│  ├─ http.py                cliente com retry, timeout, User-Agent, redator de URL
│  ├─ wfs.py                 GetFeature, DescribeFeatureType, hits, fallback 1.0
│  ├─ wms.py                 GetMap + validação de magic bytes
│  ├─ rest_arcgis.py         PAMGIA (IBAMA)
│  ├─ gml_incra.py           parser GML 1.0
│  ├─ ibge.py                malhas municipais (gzip!)
│  ├─ clip.py                bbox → clip fino local
│  ├─ materializar.py        escreve shapefile na pasta de saída
│  └─ cache.py               TTL por tema, modo offline com idade
├─ geo/
│  ├─ crs.py                 zona UTM pelo centroide, conversão de bbox
│  ├─ area.py                cálculo em ha, union, correção de geometria
│  ├─ overlay.py             matriz classe × área
│  ├─ distancia.py           menor distância até TI/UC/embargo + pontos da linha
│  └─ ogr.py                 wrapper de ogr2ogr
├─ mapspec/
│  ├─ modelo.py              dataclasses do MapSpec
│  ├─ schema.py              validação por JSON Schema
│  ├─ regras.py              invariantes (catálogo, escala, CRS, allowlist)
│  ├─ versoes.py             append-only, parent_id, diff
│  └─ determinista.py        MapSpec sem IA, a partir do template + índice
├─ motores/
│  ├─ manifesto.py           lê MANIFEST.json, confere sha256
│  ├─ arcpy_ponte.py         monta o payload, chama o subprocesso, lê o relatório
│  ├─ arcpy_job.py           ★ Python 2.7 — NUNCA importado daqui
│  ├─ patch_mxd.py           T2: offsets, slots de texto, OLE
│  ├─ nativo.py              renderizador matplotlib
│  ├─ tabela_png.py          Pillow, ≥600 dpi
│  └─ minimapa.py            retângulo + linha-guia, coordenada de página
├─ planilha/
│  └─ xlsx.py                openpyxl, estilo institucional
├─ validacao/
│  ├─ checks.py              14 HARD + 11 SOFT
│  ├─ pdf.py                 PyMuPDF: página, texto, cobertura, cor
│  └─ relatorio.py           validacao.json
├─ agente/
│  ├─ deepseek.py            cliente com streaming e tool calling
│  ├─ tools.py               catálogo tipado
│  ├─ contexto.py            montador com tetos
│  ├─ prompt.py              system prompt versionado
│  └─ visao.py               print/zip → MapSpec
└─ doctor.py                 diagnóstico do ambiente
```

## O problema dos dois Pythons

| | Núcleo | ArcPy |
|---|---|---|
| Versão | 3.12 (empacotado) | 2.7 (do ArcMap, no PC do usuário) |
| Onde | `<app>/nucleo/` | `C:\Python27\ArcGIS10.8\python.exe` |
| Bibliotecas | shapely, pyproj, fiona, PyMuPDF, Pillow, openpyxl, matplotlib | só `arcpy` |
| Sintaxe | moderna | sem f-string, sem pathlib, sem type hints |

Eles **nunca se importam**. A ponte é um subprocesso com contrato por arquivo JSON.

### Armadilhas do subprocesso que já custaram caro

1. **Payload por env var apontando para arquivo, nunca por `argv`.** `argv` no Windows passa por
   `mbcs`; `Análise de área` vira lixo. `os.environ["MAPASFACIL_JOB_JSON"] = caminho_ascii`.
2. **Timeout obrigatório.** O `arcpy` trava (ver [motor](04-motor-mxd.md)); sem timeout o app
   congela para sempre. 150 s para adaptar, 200 s para exportar.
3. **Exit 124 não é necessariamente falha.** `mxd.save()` às vezes grava e trava no cleanup. A
   ponte confere se o arquivo de saída existe e é válido antes de declarar erro.
4. **Matar o processo de verdade.** No cancelamento, `taskkill /T /F` na árvore — matar só o pai
   deixa `python.exe` órfão segurando lock.
5. **`cwd` sem acento.** Rodar o subprocesso a partir de uma pasta com acento quebra o `mbcs`. A
   ponte usa `cwd` = pasta temporária ASCII.
6. **Saída em UTF-8 explícito.** O relatório do `arcpy_job.py` é escrito com
   `codecs.open(..., "utf-8")` e `json.dump(..., ensure_ascii=False)`; a ponte lê como UTF-8.
7. **Sem `-u`, o stdout do py2 fica em buffer** e o progresso só aparece no fim.

## Doctor

Roda no boot, no `F1` e antes de cada geração (versão rápida).

### Onde procurar o ArcMap

```
1. Registro: HKLM\SOFTWARE\WOW6432Node\ESRI\Desktop10.8  → InstallDir, PythonDir
   (e 10.7, 10.6 — nessa ordem, maior primeiro)
2. Caminhos convencionais: C:\Python27\ArcGIS10.8\python.exe …
3. ArcGIS Pro:  %ProgramFiles%\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe
4. Variável de ambiente MAPASFACIL_ARCPY_PYTHON (escape manual)
```

Achado o interpretador, roda um script mínimo com timeout de 30 s:

```python
import arcpy, json
print(json.dumps({"versao": arcpy.GetInstallInfo()["Version"],
                  "licenca": arcpy.ProductInfo()}))
```

Se esse teste travar, o doctor marca `arcpy_instavel: true` e o app **prefere o T2** — é
exatamente o cenário da máquina onde a Harmonia foi feita.

### JSON do doctor

```json
{
  "so": "Windows 11 22H2",
  "app": "0.4.0", "nucleo": "0.4.0",
  "arcmap": { "encontrado": true, "versao": "10.8.1",
              "python": "C:\\Python27\\ArcGIS10.8\\python.exe",
              "licenca": "ArcInfo", "estado": "Available",
              "instavel": false, "ms_teste": 4120 },
  "arcgis_pro": { "encontrado": false },
  "gdal": { "ogr2ogr": "…\\ogr2ogr.exe", "versao": "3.8.4" },
  "fonte_esri_north": true,
  "templates": [ { "id": "dinamica_retrato", "sha256_ok": true, "patch_ok": true } ],
  "chaves": { "deepseek": true, "sema": true, "planet": false },
  "rede": { "sema": "ok 240ms", "planet": "sem chave", "ibge": "ok 180ms" },
  "espaco_livre_gb": 84,
  "pronto_para_mxd": true,
  "motor_preferido": "arcpy"
}
```

`chaves` traz **booleano**, nunca valor. `pronto_para_mxd` é o resumo que a UI mostra.

## Cofre

```python
def definir(nome: str, valor: str) -> None: ...   # grava no Credential Manager
def existe(nome: str) -> bool: ...                # a UI só recebe isto
def usar(nome: str) -> str: ...                   # uso interno; nunca cruza o stdio
def testar(nome: str) -> ResultadoTeste: ...      # faz uma chamada real e devolve ok/erro
```

`usar()` é chamada só dentro do núcleo, no momento de montar a URL ou o header. O valor **nunca**
aparece em resposta NDJSON, log, telemetria ou mensagem de erro — o redator de URL garante isso
mesmo em traceback.

## Cliente HTTP

| Regra | Motivo |
|---|---|
| User-Agent de navegador | alguns WAF governamentais bloqueiam clientes "bot" |
| TLS verify relaxado **só** para domínios do catálogo | cadeias incompletas em geosserviços brasileiros |
| Timeout 60 s (120 s para INCRA) | serviços públicos lentos |
| Retry 2× com backoff e jitter | queda intermitente |
| Concorrência limitada entre camadas (4) | não derrubar a SEMA; falha isolada |
| Redator de URL antes de qualquer log | `api_key`/`authkey` → `***` |

## Modo offline

1. Toda camada externa tenta o cache primeiro.
2. Sem rede, usa cache expirado **com aviso de idade** na conversa e no `validacao.json`.
3. Camada sem cache entra vazia → check `S09` → o job **continua**.
4. Basemap sem cache → fundo branco → check `S08`.
5. Sem chave DeepSeek ou sem rede → modo determinístico.

Falha de camada externa **nunca** aborta o mapa. O técnico prefere um mapa com aviso a nenhum
mapa.

## Empacotamento do núcleo

- **PyInstaller** em modo *onedir* (inicia rápido; *onefile* extrai a cada boot e custa 3–5 s).
- GDAL/`ogr2ogr` embarcado — não depende de QGIS instalado, como o trabalho manual dependia.
- `PROJ_LIB` e `GDAL_DATA` apontados para dentro do pacote.
- Teste de fumaça no CI: subir o núcleo empacotado e responder um `doctor.rodar`.

## Checklist de implementação

- [ ] Loop NDJSON com roteamento e tratamento de erro por método
- [ ] `fsguard` completo (ver [testes](10-testes-e-qa.md))
- [x] Indexador + watcher com debounce (`workspace/watcher.py`, A12)
- [ ] Leitor de shapefile: `.prj`, encoding em cascata, bbox por cabeçalho
- [ ] Parser de recibo do CAR com descarte de CPF
- [ ] Leitor de `.zip` com anti zip slip
- [ ] Clientes WFS/WMS/REST/GML/IBGE com todos os gotchas cobertos
- [ ] Cache com TTL por tema
- [ ] `geo/`: zona UTM, área, overlay, distância
- [ ] Ponte ArcPy com as 7 armadilhas tratadas
- [ ] Doctor completo, com detecção de `arcpy_instavel`
- [x] Cofre que nunca devolve valor (`cofre.py`, A11)
- [ ] Redator de URL
- [ ] Empacotamento PyInstaller com GDAL embarcado

## Pendências

| # | Questão |
|---|---|
| P1 | GDAL embarcado infla o pacote (~80 MB). Vale, ou dependemos de QGIS/OSGeo instalado? |
| P2 | Uma instância do núcleo por projeto, ou uma só com contexto por projeto? |
| P3 | Se o núcleo morre no meio de um job, retomar ou marcar falho? |
| P4 | Detectar `arcpy_instavel` custa até 30 s no boot — rodar em background e só avisar? |
