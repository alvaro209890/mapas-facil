# 04 — Agente local (Windows)

O agente é o único componente que toca dados do cliente e o único que roda `arcpy`. Ele
implementa o lado "PC do usuário" do protocolo definido em [01-arquitetura.md](01-arquitetura.md);
os tipos de mensagem WebSocket, as 9 etapas de job e o formato do `MapSpec` vêm de lá e não são
redefinidos aqui.

## Por que o agente existe

| Motivo | Consequência de não ter agente |
|---|---|
| `arcpy` é Windows-only e exige ArcMap/ArcGIS Pro licenciado na máquina | rodar na nuvem exigiria licença de servidor ArcGIS — inviável no porte do produto |
| Shapefiles do imóvel são dados de cliente (matrícula, CAR, geometria) | subir para a nuvem cria superfície de risco e conversa de LGPD que não precisamos ter |
| O técnico quer o `.mxd` na pasta do projeto dele, ao lado dos dados | download de ZIP e repontar caminhos é exatamente o atrito que o produto promete remover |

Alternativas descartadas: **túnel reverso** do navegador direto para o agente (WebRTC/ngrok) —
complica auth e auditoria sem ganho, já que o payload é JSON pequeno; **CLI manual** que o usuário
roda a cada mapa — perde a fila, o histórico e o RPC de `fs.list` durante o loop de IA;
**ArcGIS Server / Enterprise** — custo e operação incompatíveis com o produto.

O agente é um cliente WebSocket **outbound-only**. Ele nunca abre porta de escuta, o que faz o
sistema funcionar atrás de NAT, proxy corporativo e VPN sem nenhuma configuração de rede.

## Estrutura de `agent/`

```
agent/
  pyproject.toml
  mapasfacil_agent/
    __init__.py            versão do agente e contract_version suportada
    main.py                entrypoint: tray (pystray) ou serviço, supervisão
    ws_client.py           conexão WSS, envelope, reconexão com backoff, RPC
    jobs.py                máquina de estados do job, as 9 etapas, cancelamento
    doctor.py              diagnóstico do ambiente (ArcMap, Pro, licença, disco)
    fsguard.py             allowlist de pastas, normalização e validação de caminho
    config.py              config em %LOCALAPPDATA%, token via keyring
    logging_setup.py       log rotativo, redaction de token e de caminho
    arcpy_runner.py        ponte subprocess: escolhe interpretador, monta env, mata árvore
    layers/
      local.py             shapefile e .zip: validação, CRS, reprojeção
      wfs.py               camadas do catálogo, recorte por bbox
      cache.py             cache em disco com TTL e chave (id, bbox)
    scripts/
      arcpy_export.py      Python 2.7 puro — arcpy.mapping (ArcMap 10.x)
      arcpy_pro_export.py  Python 3.x — arcpy.mp (ArcGIS Pro 3.x)
    native/
      renderer.py          fallback matplotlib (ver 05-motor-mxd-pdf.md)
  installer/
    mapasfacil.iss         Inno Setup
    build.ps1              PyInstaller + assinatura + compilação do instalador
  tests/
    fixtures/              shapefile mínimo versionado (< 50 KB)
    test_fsguard.py        o arquivo de teste mais importante do agente
    test_jobs.py
    test_layers_local.py
```

`scripts/` é deliberadamente uma pasta de **dados**, não um pacote importável: nada em
`mapasfacil_agent/` faz `import` desses arquivos. Eles só são executados por outro interpretador.

## O problema dos dois Pythons

| Ambiente | Python | API de layout | Produz `.mxd` |
|---|---|---|---|
| ArcMap 10.6 / 10.7 / 10.8 | 2.7 (32 bits) | `arcpy.mapping` | sim |
| ArcGIS Pro 3.x | 3.9–3.11 (conda) | `arcpy.mp` | não (só `.aprx`) |
| Host do agente | 3.11 (embutido no instalador) | nenhuma | não |

O host precisa de `websockets`, `httpx`, `pyproj`, `shapely`, `keyring`, `pydantic` — nada disso
roda em Python 2.7. E `arcpy` do ArcMap **só** roda em Python 2.7. Não há interpretador que
satisfaça os dois.

### A estratégia: isolamento por subprocess, contrato por arquivo JSON

Regra absoluta: **o host nunca faz `import arcpy`**. Nem em `try/except`, nem com import
tardio. O host escreve um arquivo JSON UTF-8 com tudo que o script precisa, invoca o
interpretador correto por `subprocess`, e lê outro JSON de volta.

```
host 3.11                                          Python 2.7 (ArcMap)
  escreve  %TEMP%\mfjob_<job_id>\entrada.json
  env MAPASFACIL_JOB_JSON = <caminho da entrada>
  env MAPASFACIL_OUT_JSON = <caminho da saída>
  subprocess([python27, arcpy_export.py])  ───────▶  lê entrada.json (codecs, utf-8)
                                                     abre template, repõe fontes, exporta
  lê saida.json  ◀───────────────────────────────── escreve saida.json (utf-8)
```

**O caminho do JSON vai por variável de ambiente, jamais por `argv`.** Aprendizado direto do
NexoGeo Ambiental: no Windows, `sys.argv` em Python 2.7 é `bytes` na code page do sistema (cp1252
em pt-BR), então um caminho como `C:\Users\João\Documentos\Fazenda São José\...` chega corrompido
ou quebra o `open()` — e aspas e espaços ainda trazem o inferno de quoting do `cmd.exe`. Com
`os.environ` o valor sobrevive intacto, e a leitura é `json.load(codecs.open(p, "r", "utf-8"))`.

Aprendizado relacionado do mesmo repositório: a ponte ArcMap do NexoGeo
(`templates/mxd/scripts/export_mxd.py`, documentada em `docs/NEXOMAP_AGENT_HANDOFF.md`) nunca saiu
do estágio conservador, e o `.mxd` acabou removido do produto — `"mxd"` virou alias de `"geojson"`
em `core/mapspec.py`. O Mapas Fácil inverte a prioridade justamente por isso.

### Armadilhas do subprocess que já custaram caro

1. **Herança de `PYTHONHOME` / `PYTHONPATH`.** Se o host é congelado com PyInstaller, ele
   exporta essas variáveis. O Python 2.7 do ArcMap herda e falha com `ImportError: No module
   named site`. O `arcpy_runner.py` monta o env do zero, copiando só o necessário
   (`SystemRoot`, `TEMP`, `PATH` do ArcGIS, `APPDATA`) e removendo `PYTHONHOME`,
   `PYTHONPATH`, `PYTHONSTARTUP`, `PYTHONIOENCODING`.
2. **Janela de console piscando.** Usar `CREATE_NO_WINDOW` no `creationflags`.
3. **Encoding do stdout.** O script 2.7 escreve log em `stderr` já codificado em UTF-8, e o
   host lê com `errors="replace"`. Nada de resultado estruturado via stdout — só o JSON de saída.
4. **`arcpy` demora ~8–15 s só para importar.** O tempo do primeiro job inclui isso; a barra de
   progresso precisa refletir a etapa `abrindo_template` começando antes do import terminar.

## Doctor — detecção de ambiente

`doctor.py` roda no start do agente, a cada 6 h, e sob demanda via RPC `doctor.run`. Ele nunca
importa `arcpy` no host: para checar licença e versão, executa um script de sonda de 20 linhas
no interpretador candidato.

### Onde procurar

| Alvo | Ordem de busca |
|---|---|
| ArcMap | registro `HKLM\SOFTWARE\ESRI\Desktop10.8\InstallDir` (e `10.7`, `10.6`), depois `HKLM\SOFTWARE\WOW6432Node\ESRI\...` |
| Python do ArcMap | registro `HKLM\SOFTWARE\ESRI\Python10.8\PythonDir`, depois `C:\Python27\ArcGIS10.8\python.exe`, `C:\Python27\ArcGIS10.7\...`, `C:\Python27\ArcGIS10.6\...` |
| ArcGIS Pro | `%ProgramFiles%\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe`, registro `HKLM\SOFTWARE\ESRI\ArcGISPro\InstallDir` |
| Licença | sonda executando `arcpy.CheckProduct("ArcInfo")` / `arcpy.ProductInfo()` |
| Versão | sonda executando `arcpy.GetInstallInfo()["Version"]` |
| Templates | `sha256` de cada `.mxd` conferido contra `shared/templates/MANIFEST.json` ([05](05-motor-mxd-pdf.md)) |
| Disco | espaço livre em `C:\MapasFacil` e em `%TEMP%` |
| Escrita | criar e apagar um arquivo `.probe` em cada pasta autorizada |

Nota de licença: `arcpy.CheckProduct` devolve `"Available"`, `"AlreadyInitialized"`,
`"NotLicensed"` ou `"Failed"`. Um ArcMap instalado com licença **flutuante indisponível no
momento** aparece como `NotLicensed` — o doctor precisa distinguir "não tem ArcMap" de "tem
ArcMap sem licença agora", porque a mensagem para o usuário é completamente diferente.

### JSON do doctor

Este objeto é o payload de `rpc.result` para `doctor.run` e também vai dentro de `hello`.

```json
{
  "gerado_em": "2026-07-24T23:41:02Z",
  "agent_version": "1.0.3",
  "contract_version": 1,
  "os": { "nome": "Windows 11 Pro", "build": "22631.4460", "arch": "x64", "locale": "pt-BR" },
  "python_host": { "versao": "3.11.9", "frozen": true },
  "arcmap": {
    "encontrado": true,
    "versao": "10.8.1",
    "install_dir": "C:\\Program Files (x86)\\ArcGIS\\Desktop10.8",
    "python_exe": "C:\\Python27\\ArcGIS10.8\\python.exe",
    "arcpy_import_ok": true,
    "arcpy_import_ms": 9420,
    "licenca": { "produto": "ArcInfo", "estado": "Available", "tipo": "single-use" },
    "extensoes": { "Spatial": "Available", "3D": "NotLicensed" }
  },
  "arcgis_pro": {
    "encontrado": true,
    "versao": "3.3.2",
    "python_exe": "C:\\Program Files\\ArcGIS\\Pro\\bin\\Python\\envs\\arcgispro-py3\\python.exe",
    "licenca": { "estado": "Available", "tipo": "named-user" },
    "pode_salvar_mxd": false
  },
  "templates": {
    "manifest_version": 3,
    "diretorio": "C:\\ProgramData\\MapasFacil\\templates",
    "itens": [
      { "id": "dinamica_2026", "arquivo": "Dinamica_2026.mxd", "sha256_ok": true },
      { "id": "alertas_mapbiomas", "arquivo": "Alertas_MAPBIOMAS_2.mxd", "sha256_ok": false }
    ]
  },
  "pastas_autorizadas": [
    { "path": "D:\\Projetos\\CAR", "leitura": true, "escrita": false, "existe": true },
    { "path": "C:\\MapasFacil", "leitura": true, "escrita": true, "existe": true }
  ],
  "disco": { "saida_livre_gb": 184.2, "temp_livre_gb": 184.2, "minimo_exigido_gb": 2 },
  "rede": { "backend_alcancavel": true, "latencia_ms": 78, "wfs_sema_ok": true },
  "capacidades": ["mxd", "pdf", "preview_png", "geojson"],
  "avisos": [
    { "codigo": "TPL-HASH", "mensagem": "Template Alertas_MAPBIOMAS_2.mxd difere do manifesto." }
  ],
  "pronto_para_mxd": true
}
```

`capacidades` é o campo que o backend consulta antes de aceitar `strict_mxd: true`. Se `mxd`
não está na lista, o job é recusado na criação, com mensagem explicando o porquê — nunca falha
depois de 2 minutos de execução.

## Ciclo de vida

### Instalação

Instalador `.exe` (Inno Setup). Por padrão instala **por usuário** em
`%LOCALAPPDATA%\Programs\MapasFacil` — sem UAC, sem admin. Instalação por máquina
(`C:\Program Files\MapasFacil`) é opção para quem quer rodar como serviço.

### Pareamento

1. No site, o usuário clica "Parear novo PC" → backend gera um código de 8 caracteres
   (`POST /v1/agents/pair-code`, TTL 10 min). Alfabeto Crockford base32 sem `I`, `L`, `O`, `U`,
   exibido como `XXXX-XXXX`.
2. No agente, o usuário digita o código e **escolhe as pastas autorizadas** numa tela explícita
   (não há default silencioso; a lista vazia bloqueia jobs).
3. O agente chama `POST /v1/agents/pair` com o código, hostname, SO e o doctor inicial. Recebe
   um `agent_token` permanente.
4. O token é gravado no **Windows Credential Manager** via `keyring`
   (`keyring.set_password("MapasFacil", "agent_token", token)`), nunca em texto plano.
   Limitação conhecida: o blob do Credential Manager tem ~2560 bytes; o token precisa caber
   folgadamente nisso (usar um opaco de 43 caracteres, não um JWT gordo).
5. Revogação: `DELETE /v1/agents/{id}` invalida o token; o agente recebe fechamento do WS com
   código de aplicação e apaga a credencial local.

Config não-secreta (id do agente, pastas autorizadas, preferências) fica em
`%LOCALAPPDATA%\MapasFacil\config.json`. As pastas autorizadas são **também** guardadas no
backend, mas a versão local é a que vale para o `fsguard` — o backend não pode ampliar o escopo
remotamente.

### Execução contínua

| Aspecto | Decisão |
|---|---|
| Autostart | atalho em `shell:startup` (modo por usuário) ou serviço via `nssm` (modo máquina) |
| Bandeja | ícone com quatro estados: online, ocupado (job rodando), offline, erro de ambiente |
| Menu da bandeja | abrir pasta de saída, abrir logs, rodar doctor, pausar (recusa novos jobs), sair |
| Logs | `%LOCALAPPDATA%\MapasFacil\logs\agent.log` + `job-<job_id>.log`, rotação 10 MB × 5 |
| Redaction | o formatter remove `agent_token` e mascara caminhos fora da saída antes de gravar |
| Atualização | **opt-in**: `agent.update` mostra notificação; usuário confirma; download verificado por `sha256` e assinatura antes de trocar o binário |

O agente **nunca** se atualiza sozinho por padrão. Um agente que se auto-atualiza silenciosamente
é um canal de execução remota de código na máquina do cliente, e isso contradiz a regra 4 de
[01-arquitetura.md](01-arquitetura.md).

## `fsguard.py` — segurança de sistema de arquivos

O backend manda caminhos (`fs.list`, `fs.inspect`, `pasta_destino`, `fonte` de camada). Todo
caminho passa pelo `fsguard` antes de qualquer I/O. Falha fechada: na dúvida, rejeita.

Normalização, nesta ordem:

1. Rejeitar caminho vazio, relativo, com byte nulo ou com `:` em posição inválida (bloqueia
   *alternate data streams* como `dados.shp:oculto`).
2. `os.path.abspath` + `os.path.normpath` para resolver `..` e `.`.
3. Expandir nomes curtos 8.3 (`PROGRA~1`) via `GetLongPathName` do Win32 — sem isso, um caminho
   curto burla a comparação de prefixo.
4. Resolver *symlinks*, *junctions* e *reparse points* com `Path.resolve(strict=False)`; se o
   alvo resolvido sair da allowlist, rejeitar mesmo que o caminho literal estivesse dentro.
5. Normalizar o prefixo `\\?\` e recusar UNC (`\\servidor\share`) a menos que aquele exato share
   esteja na allowlist.
6. Rejeitar nomes de dispositivo reservados do Windows (`CON`, `PRN`, `AUX`, `NUL`, `COM1`–`COM9`,
   `LPT1`–`LPT9`), em qualquer componente e com qualquer extensão.
7. Comparar com `os.path.normcase` (Windows é *case-insensitive*) usando **comparação por
   componente de caminho**, não por prefixo de string: `D:\Projetos` não pode autorizar
   `D:\ProjetosAntigos`.
8. Escrita só é permitida na raiz de saída (`C:\MapasFacil` por padrão) e em `%TEMP%`; as pastas
   de dados do cliente são **somente leitura**.

Reforços de contexto:

- `fs.list` devolve apenas nomes de arquivo e metadados (tamanho, CRS, contagem de feições).
  Nunca conteúdo geométrico.
- O backend não manda código. `MapSpec` é declarativo e validado por schema também no agente,
  não só no backend — o agente não confia no chamador.
- O script ArcPy recebe apenas caminhos já validados; ele não faz descoberta de arquivos.
- Todo caminho rejeitado gera log em nível `warning` e um `job.error` com código `AG-020`.

`tests/test_fsguard.py` é obrigatório na CI com casos para cada item acima. É o teste que impede
o pior bug possível deste produto.

## Execução de um job

Estados do job e as 9 etapas vêm de [01-arquitetura.md](01-arquitetura.md). O agente mapeia assim:

| Etapa | O que faz | Timeout | Falha é fatal? |
|---|---|---|---|
| `validando_spec` | schema + `contract_version` + `fsguard` em todo caminho | 5 s | sim |
| `resolvendo_camadas_locais` | abre `.shp`/`.zip`, lê `.prj`, calcula bbox | 60 s | sim |
| `baixando_wfs` | recorte por bbox, com cache | 120 s por camada | não (vira aviso) |
| `abrindo_template` | copia template para `%TEMP%`, `sha256`, spawn do ArcPy | 120 s | sim |
| `repontando_fontes` | `replaceDataSource` por camada | 180 s | sim |
| `aplicando_layout` | extent, escala, legenda, textos, tabela | 180 s | sim |
| `salvando_mxd` | `saveACopy` para `.tmp` | 120 s | sim |
| `exportando_pdf` | `ExportToPDF` 300 dpi | 300 s | sim se `pdf` em `saidas` |
| `validando_saida` | PyMuPDF + `ListBrokenDataSources` | 60 s | sim se `strict_mxd` |

Regras de execução:

- **Um job por vez.** Duas instâncias de `arcpy` na mesma máquina competem por licença
  *single-use* e o segundo falha com erro obscuro. Jobs adicionais ficam na fila local.
- **Escrita atômica.** Tudo é gerado como `mapa.mxd.tmp` / `mapa.pdf.tmp` no diretório final e
  renomeado com `os.replace` ao fim. Um job que morre no meio nunca deixa `.mxd` truncado na pasta
  do usuário.
- **Saída:** `C:\MapasFacil\<projeto>\<job_id>\{mapa.mxd, mapa.pdf, preview.png, mapspec.json,
  validacao.json, job.log}`. `<projeto>` é sanitizado para ASCII e sem caracteres proibidos do
  Windows — `arcpy` 10.x tem problemas conhecidos com acentuação em caminhos de saída.
- **Temporários** em `%TEMP%\mapasfacil\<job_id>\`, apagados no `finally`, inclusive em
  cancelamento. Um limpador no start remove restos com mais de 48 h.
- **Cancelamento** (`job.cancel`): sinaliza o flag e, se houver subprocess ArcPy vivo, mata a
  **árvore** de processos. `Popen.terminate()` não basta: `arcpy` gera filhos (`ArcGISVersion`,
  geoprocessamento em background). Usar `psutil.Process(pid).children(recursive=True)` ou, na
  falta dele, `taskkill /PID <pid> /T /F`; depois o job vira `cancelled` e limpa os temporários.
- **Reconexão:** o job continua rodando se o WebSocket cair. Eventos de progresso vão para buffer
  em disco e são reenviados no `hello` seguinte. `job.progress` sai no máximo a cada 500 ms.

## Resolução de camadas

### Shapefile local e `.zip`

Antes de qualquer coisa, validar que os quatro arquivos existem com o mesmo nome-base:
`.shp`, `.shx`, `.dbf`, `.prj`. Falta de `.prj` é erro (`AG-011`), não suposição — assumir
SIRGAS 2000 em silêncio produz mapa deslocado em algumas centenas de metros e ninguém percebe.

Sequência: ler o `.prj` com `pyproj.CRS.from_wkt`, comparar com o `crs` do `MapSpec`, e se
diferir, reprojetar para uma cópia em `%TEMP%\mapasfacil\<job_id>\reproj\`. O original do cliente
**nunca** é modificado. Também são registrados: contagem de feições, bbox e lista de campos
(usados pelo `fs.inspect` e pela escolha de `campo_rotulo`).

Cuidados: `.dbf` em cp1252 versus UTF-8 (tentar `utf-8`, cair para `cp1252`, registrar qual foi
usado); shapefile com mais de 2 GB; nomes de campo truncados em 10 caracteres.

`.zip` é extraído para `%TEMP%\mapasfacil\<job_id>\zip\<hash>\`, com proteção contra *zip slip*
(nenhuma entrada pode escapar do diretório de extração) e limite de tamanho descompactado. Se o
ZIP tiver mais de um shapefile, o agente devolve a lista e a IA precisa escolher — não adivinhar.

### WFS externo

Receitas completas em [`13-wfs-e-servicos-geo.md`](13-wfs-e-servicos-geo.md). Implementação
inspirada no GeoForest (`wfs-intersection.ts` / `simcar-clip.ts`) e no NexoGeo
(`nexomap_layers.py`), com as correções de 2026-07-10:

- **BBOX como método primário** + clip fino local (shapely). `INTERSECTS` da SEMA perde
  feições em imóveis grandes sem erro — só usar se BBOX vier vazio.
- `GetFeature` com bbox **expandido ~25%** (mín. 0,002°) para feições na moldura.
- WFS 2.0.0 (`typeNames`, `count`, `srsName=EPSG:4674`) com *fallback* 1.0.0
  (`typeName`, `maxFeatures`) — FUNAI e servidores antigos.
- **Sem `startIndex` cego:** se paginação der 400 (`Cannot do natural order…`) ou timeout
  (`PagingIsTransactionSafe=FALSE`), uma chamada sem paginação e `resultado_parcial=true`.
- Limite de feições por camada no mapa: 500–2000 (não os 50.000 da análise GeoForest).
- PAMGIA (ArcGIS REST→GeoJSON) para embargos IBAMA; SISCOM WMS só como fallback.
- INCRA: parser GML próprio, timeout 120 s, geometria 4326.
- `DescribeFeatureType` para descobrir campo de geometria (cache 30 min); não assumir `the_geom`.
- Cache em `%LOCALAPPDATA%\MapasFacil\cache\wfs\<id>_<hash-bbox>.geojson`, TTL por tema
  (ver [13](13-wfs-e-servicos-geo.md)).
- **Fallback quando o serviço cai:** cache mesmo vencido + aviso; sem cache, camada sai e
  vira warning — rede não derruba o job.
- Auth: `sema_authkey` / `planet_api_key` no Credential Manager — **default vazio**, nunca
  hardcoded (dívida do GeoForest que não se replica).
- Materializar GeoJSON → shapefile em `<job_id>\camadas\<id>.shp` (allowlist), para o `.mxd`
  continuar abrindo depois do job.

Estrutura sugerida: `layers/{catalog,wfs_client,wms_client,rest_arcgis,gml_incra,clip,cache,secrets}.py`.

## Modo offline

| Funciona sem internet | Não funciona |
|---|---|
| Job já despachado que estava em execução | conversar com a IA (o loop é no backend) |
| Camadas locais (`.shp`, `.zip`) | criar job novo |
| Camadas do catálogo que estejam em cache válido | camadas externas fora do cache |
| Geração de `.mxd`, `.pdf`, `preview.png` | upload de `preview.png` / `validacao.json` |
| Doctor local | basemap online no template (Esri World Imagery) |
| Fila local de jobs pendentes | pareamento e atualização |

Ao voltar a rede, o agente reconecta com backoff, reenvia o buffer de eventos e sobe os artefatos
pendentes. O basemap merece atenção: um template cujo fundo é Esri World Imagery gera, offline,
um mapa com fundo cinza. O `validando_saida` detecta isso e marca aviso `basemap_ausente`.

## Códigos de erro

`job.error` carrega `{job_id, codigo, mensagem, etapa, log_tail}`. A coluna "mensagem ao usuário"
é o texto exato mostrado no chat — escrito para um técnico de GIS, não para um desenvolvedor.

| Código | Etapa | Mensagem ao usuário | Ação sugerida na UI |
|---|---|---|---|
| `AG-001` | qualquer | "O agente deste PC está com versão antiga e não entende este pedido." | botão Atualizar agente |
| `AG-002` | `validando_spec` | "O pedido tem um campo inválido e foi recusado antes de gerar o mapa." | mostrar erro de schema |
| `AG-010` | `resolvendo_camadas_locais` | "Não encontrei o shapefile *nome*. Ele foi movido ou renomeado?" | reabrir seletor de camadas |
| `AG-011` | `resolvendo_camadas_locais` | "O shapefile *nome* está sem o arquivo `.prj`, então não sei em que projeção ele está." | link de ajuda |
| `AG-012` | `resolvendo_camadas_locais` | "O shapefile *nome* não tem nenhuma feição." | — |
| `AG-013` | `resolvendo_camadas_locais` | "O `.zip` tem mais de um shapefile; escolha qual usar." | lista de escolha |
| `AG-020` | qualquer | "O caminho *X* está fora das pastas que você autorizou." | abrir configuração de pastas |
| `AG-021` | `salvando_mxd` | "Sem permissão de escrita em *pasta*." | escolher outra pasta |
| `AG-022` | `salvando_mxd` | "Espaço em disco insuficiente." | — |
| `AG-030` | `abrindo_template` | "Não encontrei o ArcMap neste PC, então não dá para gerar o `.mxd`." | oferecer PDF nativo |
| `AG-031` | `abrindo_template` | "O ArcMap está instalado, mas a licença não está disponível agora." | ajuda sobre licença |
| `AG-032` | `abrindo_template` | "O template *nome* não está instalado ou foi alterado." | botão Reinstalar templates |
| `AG-033` | `abrindo_template` | "O ArcMap não conseguiu iniciar (falha ao carregar o `arcpy`)." | anexar log |
| `AG-040` | `repontando_fontes` | "A camada *nome* ficou com a fonte quebrada dentro do `.mxd`." | mostrar quais |
| `AG-041` | `aplicando_layout` | "O template não tem o elemento *NOME* esperado pelo layout." | reportar template |
| `AG-050` | `exportando_pdf` | "A exportação do PDF falhou." | anexar log |
| `AG-051` | qualquer | "A etapa *X* passou do tempo limite e foi interrompida." | tentar de novo |
| `AG-052` | qualquer | "Job cancelado." | — |
| `AG-060` | `baixando_wfs` | "A camada externa *nome* está indisponível; o mapa saiu sem ela." | aviso, não erro |
| `AG-070` | `validando_saida` | "O PDF foi gerado, mas não passou na validação do padrão IMAP." | abrir relatório |

Erros `AG-0xx` do agente são distintos dos erros do backend, para que o suporte saiba de imediato
de que lado da fronteira o problema está.

## Empacotamento e distribuição

| Etapa | Ferramenta | Detalhe |
|---|---|---|
| Congelar o host | PyInstaller (`--onedir`) | `--onefile` foi descartado: extrai para `%TEMP%` a cada start, o que é lento e dispara antivírus |
| Instalador | Inno Setup 6 | por usuário sem UAC; por máquina com UAC e opção de serviço |
| Assinatura | `signtool` com certificado OV | assinar o `.exe` do agente e o do instalador |
| Templates | pacote separado, versionado pelo `MANIFEST.json` | instalado em `C:\ProgramData\MapasFacil\templates` |

Tamanho esperado: 55–75 MB descompactado (Python 3.11 embutido + `shapely`, `pyproj`,
`matplotlib`, `PyMuPDF`), instalador de 25–35 MB. `arcpy` **não** é empacotado — é sempre o do
usuário.

**SmartScreen.** Com certificado OV, os primeiros downloads ainda mostram "aplicativo não
reconhecido" até a reputação acumular; só o **EV** (token de hardware, ~US$ 300–600/ano) dá
reputação imediata. Como o público-alvo da v1 é pequeno e conhecido, a decisão é começar com OV,
documentar o aviso na página de download com captura do "Mais informações → Executar assim mesmo",
e reavaliar EV quando houver distribuição aberta. Instalador **sem assinatura nenhuma** é
inaceitável — este é um programa que escreve na pasta de projetos do cliente.

Antivírus: agentes Python congelados viram falso positivo com frequência. Mitigação: submeter cada
release ao VirusTotal antes de publicar e enviar amostra para whitelist da Microsoft.

## Pendências e decisões abertas

| # | Questão | Situação |
|---|---|---|
| P1 | Serviço do Windows ou tray como padrão? | tray é o padrão da v1 (mais simples, mostra estado); serviço fica como opção documentada |
| P2 | `pystray` versus tray nativo em `pywin32` | avaliar consumo e estabilidade em Windows 11 antes de fechar |
| P3 | Suporte a ArcMap 10.5 | fora do escopo até aparecer usuário real; a matriz de [05](05-motor-mxd-pdf.md) só cobre 10.6+ |
| P4 | Multiusuário na mesma máquina (terminal server) | fora da v1; exigiria fila por sessão e licença concorrente |
| P5 | Instalar templates junto do agente ou baixar sob demanda | inclinação: baixar sob demanda com verificação de `sha256`, para desacoplar release de agente e de template |
| P6 | Certificado EV | reavaliar antes do primeiro release público |
| P7 | Limite de tamanho para camadas WFS (500 feições) | número herdado do NexoGeo; medir com dados reais de MT antes de fixar |
| P8 | Telemetria de erro (opt-in) | desejável para suporte; precisa de decisão explícita sobre o que é enviado, dado o compromisso de não subir dado de cliente |
