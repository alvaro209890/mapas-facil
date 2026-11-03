# W-08 — Motor `.mxd` binário (geração sem ArcMap)

## Objetivo

Entregar, a partir do servidor Linux, um **pacote ArcMap** (`.mxd` + dados com caminhos
relativos) que abre perfeito em qualquer ArcMap 10.x — **sem ArcMap instalado para gerar**. O
caminho é **remontagem binária de templates preparados**: o `.mxd` é um contêiner CFBF (OLE2);
cada template-variante (modelo × folha × orientação) carrega **slots** marcados com sentinelas;
o motor troca o conteúdo dos slots, reajusta tamanhos de bloco e de stream, e prova com gates
que nada além dos slots mudou.

Não é objetivo da Fase 3 "escrever `.mxd` do zero" (criar camada nova, simbologia nova, elemento
novo sem template). Isso exigiria reimplementar a serialização de centenas de classes ArcObjects;
o retorno não paga o risco (D32, AW-07).

## Estado atual vs alvo

| Peça | Hoje | Alvo |
|---|---|---|
| T2 (`motores/patch_mxd.py`) | copia template `pronto` e grava extent/escala por **offset fixo** validado por sentinela numérica (`*.sentinelas.json`, MANIFEST `patch.offsets`) | vira o caso particular "slot numérico" do motor binário |
| `C:\GIS\MXD_RE\ferramentas\cfbf.py` | `CompoundFilePacker`: lê streams e **reempacota** o CFBF (FAT/MiniFAT/DIFAT) | trazido para `mapasfacil_nucleo/mxd_binario/cfbf.py` com testes de corpus |
| `C:\GIS\MXD_RE\ferramentas\mxd_bin.py` | `MxdBinaryDocument`: `list_layout_texts`, `replace_layout_text`, `replace_data_source_path`, `replace_layer_name`, `replace_wms_url`, `update_dataframe_extent`, `update_dataframe_scale`, `save` | base de `mxd_binario/documento.py` |
| Especificação | `C:\GIS\MXD_RE\docs\formato_mxd.md` (CFBF v3, streams `PageLayout`/`Maps`/`Mx Document`, blocos `FF FF FF FF` + `uint64`, strings UTF-16LE com `uint32`) | copiada para `docs/mxd-formato-binario.md` no repo e mantida lá |
| Templates | 25 `pronto` em `shared/templates/` (todos A4) | + variantes por folha fabricadas no Windows, fora do git, com `sha256` no MANIFEST |
| Verificação no ArcMap | manual / `auditar_templates_mxd.ps1` | G4 automatizado no Windows como **teste de desenvolvimento** do motor (por variante e por versão do motor) — não é portão de entrega (D37) |

## Dependências

W1 (`MapSpec.folha`), W9 (o PDF nativo é a referência visual do `.mxd`), Windows com ArcMap 10.8
para a fábrica e o gate G4 (`pcque001imap`, eixo já documentado em `Fase_1_Desktop/GUIA_WINDOWS.md`).

## Contratos

### Código no núcleo — `mapasfacil_nucleo/mxd_binario/`

| Módulo | Responsabilidade |
|---|---|
| `cfbf.py` | leitura e reempacotamento CFBF (porta do `CompoundFilePacker`); **nunca** edita no lugar: lê da origem, escreve destino novo |
| `blocos.py` | percorre a serialização ArcObjects de uma stream: CLSID (16 B) + ObjectID (4 B) + versão (2 B); blocos `FF FF FF FF` + `uint64`; strings `uint32` + UTF-16LE com `\0\0`; mantém a **árvore de blocos** para recalcular tamanhos quando um conteúdo cresce/encolhe |
| `slots.py` | carrega o `.slots.json` da variante, localiza cada slot, aplica o valor, valida |
| `documento.py` | API de alto nível (`DocumentoMxd.abrir(template) → aplicar(valores) → salvar(destino)`) |
| `gates.py` | G1–G3 (G4 roda no Windows) |
| `pacote.py` | monta o `.zip` de entrega (ver §Pacote) |
| `__main__.py` | CLI: `inspecionar`, `slots`, `aplicar`, `verificar`, `diff` — para depuração e para a fábrica |

O motor é escolhido em `motores/gerar.py` como `motor="binario"` (em modo servidor, sempre; no
desktop sem ArcMap, também — substitui o T2 atual quando a variante tiver `.slots.json`).

### Slots

Um slot é um ponto variável do template, marcado na fábrica com uma **sentinela**:

| Tipo | Sentinela | Como localizar | Como aplicar |
|---|---|---|---|
| `texto` | string única `«MF:<slot_id>»` gravada no elemento de texto | busca UTF-16LE da sentinela em cada stream relevante | troca texto puro **e** texto formatado (`<FNT …>…</FNT>`) do mesmo elemento, ajusta os `uint32` e o `uint64` do bloco envolvente (regra de expansão de `formato_mxd.md` §5.A) |
| `numero` | valor `double` improvável (`111111.0`, `987654.0`…) — como o T2 atual | busca do padrão IEEE-754 LE; exige ocorrência **única** por slot | sobrescreve no lugar (tamanho fixo) |
| `envelope` | 4 doubles sentinela | idem | idem (32 B) |
| `caminho` | workspace `«MF:ws_<camada>»` + dataset `«MF:ds_<camada>»` | busca UTF-16LE no `IWorkspaceName` | caminho **relativo ao `.mxd` em `MXD/`** (`..\SHP\ATP.shp` → workspace `..\SHP`, dataset `ATP.shp`); ajusta tamanhos |
| `consulta` | `"nome" = '«MF:municipio»'` na definition query | busca da sentinela | troca só o valor entre aspas, com escape de `'` → `''` |
| `nome_camada` | `«MF:nome_<camada>»` | busca no `FeatureLayer` | troca nome do TOC (que é o que a legenda mostra) |
| `figura` | ver spike S6 | — | — |

`.slots.json` (gerado pela fábrica, versionado no MANIFEST com `sha256`):

```json
{
  "template_id": "dinamica_retrato",
  "variante": { "formato": "A3", "orientacao": "retrato" },
  "arquivo_sha256": "…",
  "streams": ["Mx Document", "PageLayout", "Maps"],
  "slots": [
    { "id": "titulo",          "tipo": "texto",    "obrigatorio": true,  "origem": "mapspec.titulo" },
    { "id": "meta_data",       "tipo": "texto",    "obrigatorio": true,  "origem": "mapspec.metadados[Data da imagem]" },
    { "id": "rotulo_imovel",   "tipo": "texto",    "obrigatorio": true,  "origem": "mapspec.imovel.nome" },
    { "id": "df_principal",    "tipo": "envelope", "obrigatorio": true,  "origem": "enquadramento.extent", "sentinela": [111111.0, 222222.0, 333333.0, 444444.0] },
    { "id": "escala",          "tipo": "numero",   "obrigatorio": true,  "origem": "enquadramento.escala", "sentinela": 987654.0 },
    { "id": "ws_perimetro",    "tipo": "caminho",  "obrigatorio": true,  "origem": "pacote.dados.perimetro" },
    { "id": "municipio_query", "tipo": "consulta", "obrigatorio": true,  "origem": "mapspec.imovel.municipio.nome" },
    { "id": "df_minimapa",     "tipo": "envelope", "obrigatorio": true,  "origem": "minimapa.extent" },
    { "id": "ret_localizador", "tipo": "envelope", "obrigatorio": true,  "origem": "minimapa.retangulo_pagina_mm" }
  ]
}
```

Regras: sentinela **não encontrada** → `MX-010`; encontrada **mais de uma vez** (quando o slot
exige única) → `MX-011`; sobrar qualquer `«MF:` no arquivo final → `MX-012`.

Lições das skills que valem para o motor (detalhe e fonte em [W-17](17-conhecimento-das-skills.md) §4):

- **Procure slot só dentro das streams vivas** (lidas pela árvore de diretório do CFBF), nunca
  no arquivo cru: setores livres guardam **resíduo de salvamentos antigos** — camadas fantasmas,
  URLs velhas, ids de mosaico antigos. Como o `cfbf.py` reempacota só o que está vivo, o `.mxd`
  gerado sai **sem** esse resíduo (o mesmo efeito de abrir e salvar no ArcMap).
- Em `ParagraphTextElement` há **três** tamanhos a manter coerentes: `uint32` do texto cru,
  `uint32` do BSTR formatado e `uint64` do bloco do elemento (o `mxd_bin.py` já faz).
- Texto "apagado" é **um espaço** (`" "`), não string vazia (o ArcMap recusa texto vazio em
  `TextElement`; manter o mesmo no binário evita elemento inválido).
- Figura colada pode estar **embutida como PNG ou EMF** (`sourceImage` vazio) — o S6 tem de cobrir
  os dois; a âncora é o canto inferior-esquerdo.
- Data frames com mosaico Planet/SIMCAR costumam estar em **Web Mercator** (3857): o envelope do
  slot tem de estar no CRS do frame, senão o mapa sai em branco.
- Gratícula (grade) e fonte de elemento de texto **não têm API no arcpy 10.x** — no binário são
  candidatas a slot (S11), na fábrica entram prontas no template.

> **Ponto de atenção registrado no vault (`02-projetos/mxd-formato-binario.md`):** o ArcObjects
> prioriza a stream agregada `Mx Document` quando ela existe. O spike S0 decide, para os nossos
> templates, em quais streams cada slot aparece; o motor aplica em **todas** as ocorrências
> listadas em `streams`, nunca só na `PageLayout`.

### Matriz de capacidade e spikes

O agente **não implementa** um tipo de slot sem fechar o spike dele (com relatório em
`docs/mxd-binario-spikes.md`: hipótese, arquivos do corpus usados, bytes antes/depois, resultado
do G4 no Windows).

| Spike | Pergunta | Base já existente | Se falhar (plano B) |
|---|---|---|---|
| S0 | Em quais streams cada tipo de slot aparece nos 25 templates? `Mx Document` duplica `PageLayout`/`Maps`? | `mxd_bin.py`, `inspecionar_mxd_offsets.py` | — (é diagnóstico) |
| S1 | Troca de texto que cresce/encolhe (título 12 → 40 caracteres) abre no ArcMap? | `replace_layout_text` | limitar ao tamanho da sentinela com preenchimento de espaços (sentinela longa) |
| S2 | Envelope/escala de 2 data frames (principal + minimapa) | T2 + `update_dataframe_*` | — (já funciona no T2) |
| S3 | Caminho relativo de shapefile **e** de raster (GeoTIFF do mosaico) resolve em outra máquina | `replace_data_source_path`, I3 do desktop (`broken: []`) | — |
| S4 | Nome de camada no TOC/legenda | `replace_layer_name` | template com nomes fixos já corretos |
| S5 | Valor da definition query de municípios | — | camada de município materializada **só** com o município do imóvel (sem query) |
| S6 | Figura (tabela de quantitativos): o ArcMap 10 **embute** a imagem no documento por padrão. Dá para trocar os bytes embutidos (PNG/EMF + tamanhos)? | — | B1: na fábrica, gravar a figura como **vinculada** (`dados/tabela.png`, caminho relativo) e trocar só o caminho; B2: tabela como texto multilinha (slot `texto`) |
| S7 | Visibilidade de camada (camadas opcionais ausentes no imóvel) | — | variante de template sem a camada; ou camada apontando para shapefile vazio com o esquema certo + remoção do item de legenda (só se S8 fechar) |
| S8 | Itens de legenda (remover item de camada ausente) | — | variante de template |
| S9 | Retângulo localizador do minimapa (elemento gráfico) — envelope em mm de página | memória `mxd-layout-elements` (move o quadrinho por ArcObjects) | posição fixa no centro do minimapa (S01 vira aviso) |
| S10 | Cor de simbologia (`IRgbColor` no renderer) — para "clareia a vegetação" | — | o `.mxd` mantém a simbologia do template e o resultado traz `MX-030` ("o .mxd mantém o estilo padrão; o PDF tem o estilo pedido") |
| S11 | Grade (graticule): intervalo e rótulos coerentes com o extent novo | — | intervalo calculado pelo núcleo gravado como slot `numero` (se o ArcMap persistir o intervalo); senão aviso S07 |
| S12 | Tamanho de página puramente binário (A4 → A3 sem fábrica) | — | é o caminho da fábrica (D32); S12 é pesquisa, **fora** do caminho de produção da Fase 3 |

### Laboratório de engenharia reversa (REA no Windows)

Os spikes rodam no Windows `pcque001imap`, que tem o ArcMap 10.8 e o **REA** (`rea-agents`
6.5.0, CLI `rea` — conferido em 2026-11-03; Ghidra/Rizin/Frida/GDB disponíveis; ficha no vault:
`01-infra/rea-frota.md`). O REA serve para **observar o ArcMap trabalhando** e entender o formato;
o código do `mxd_binario/` é sempre **nosso**, escrito a partir da especificação.

Artefatos do laboratório (capturas, logs de Frida, pares de `.mxd`, anotações) ficam em
`C:\GIS\MXD_RE\` — **nunca** no repositório `mapas-facil`, que é **público** no GitHub.

| Técnica | Para quê | Pode? |
|---|---|---|
| **Diff controlado**: o ArcMap salva duas cópias do template com **uma** mudança só (pela mesma automação ArcObjects/`comtypes` da fábrica) e `python -m mapasfacil_nucleo.mxd_binario diff a.mxd b.mxd` mostra stream, offset e bytes alterados | todos os spikes — é o método principal | sim |
| Parser próprio (`cfbf.py`, `blocos.py`) e `olefile` sobre os `.mxd` do acervo | S0, corpus | sim |
| Documentação **pública** do ArcObjects SDK (interfaces, CLSIDs, `IPersistStream`, `IPage.FormID`) | dar nome a classe e campo | sim |
| `rea instrument-with-frida` no processo do ArcMap, enganchando **APIs do Windows** usadas para ler o arquivo (ole32: `StgOpenStorage`/`StgOpenStorageEx`, `IStorage::OpenStream`, `IStream::Read`/`Seek`) e registrando stream, offset e tamanho lidos | S0 (qual stream o ArcMap usa de fato: `Mx Document` × `PageLayout`/`Maps`); diagnóstico de `.mxd` gerado que não abre (onde a leitura para) | sim — observa comportamento, não copia código |
| `rea capture-process` + `rea compare-process-captures` abrindo o template × o gerado | G4 e diagnóstico | sim |
| Descompilar/desmontar DLLs da Esri (`esriCarto.dll`, `Map.dll`, …) com Ghidra ou `rea decompile` | entender um campo que o diff e o Frida não explicaram | **sim, em sala limpa** (P10 respondida em 03/11: liberado sempre que travar) — regras abaixo |
| Copiar código, pseudocódigo, tabela interna ou trecho de DLL da Esri para o núcleo, o repo ou o vault | — | **nunca** |

Por que a fronteira é essa: a licença do ArcMap restringe descompilar o produto (salvo o que a
lei permitir — a decisão de usar foi do Álvaro), o repositório é público — código derivado da
Esri lá dentro é publicação de código alheio — e o que o motor precisa é só o **layout dos bytes
do arquivo**. Por isso: diff e Frida primeiro; descompilação quando eles não bastarem; e o que
sai da descompilação entra no projeto só como **fato sobre o formato**.

**Sala limpa** (obrigatória sempre que houver descompilação):

1. Quem olhou a descompilação escreve só **fatos**, com palavras próprias, em
   `docs/mxd-binario-spikes.md` ("no bloco do `PictureElement`, depois do CLSID vem um `uint32`
   com o tamanho da imagem embutida") — sem código, sem pseudocódigo, sem nome de função interna.
2. O código do `mxd_binario/` é escrito a partir desse texto e provado por diff + G1–G4.
3. Projetos do Ghidra e dumps ficam em `C:\GIS\MXD_RE\lab\`, fora de qualquer git.

Fluxo de um spike:

1. A fábrica salva o par A / A′ com uma mudança (ex.: cor da AVN de verde para azul — S10).
2. `diff` aponta a stream e os bytes que mudaram; repetir com outro valor confirma a codificação
   (ex.: RGB em 3 bytes, ou HSV em doubles).
3. Se o significado não fica claro, o Frida mostra se o ArcMap lê aquela região ao abrir/desenhar.
4. Hipótese no relatório do spike → implementação do slot → G1–G3 no Linux → G4 no Windows.

Cuidados da máquina: o ArcMap 10.8 é processo **32 bits** (usar o agente Frida x86); o `arcpy`
de acesso a dados trava aqui — automatizar o ArcMap pela fábrica (ArcObjects/`comtypes`) e usar
`arcpy.mapping` só com timeout (memória `arcpy-dataaccess-hangs-mxd-workflow`); `.mxd` com
camada WMS da IMAP derruba o `Map.dll` em modo headless (memória `wms-imap-derruba-arcpy`) —
nos pares de laboratório, tirar o WMS antes.

### Fábrica de variantes (Windows, uma vez por template × folha × orientação)

`ferramentas/fabricar_variantes_mxd.py` (Python 3 + `comtypes` + ArcObjects — **não** `arcpy`
de dados, que trava nesta máquina; ver memória `arcpy-dataaccess-hangs-mxd-workflow`). Regras de
operação herdadas das skills do Hermes (`arcgis-desktop-automation`, `mxd-fix-links`,
`mxd-layout-elements`): **um MXD por subprocesso** (o ArcObjects estoura após 5–10 documentos no
mesmo processo — exit 139); `PYTHONPATH=` vazio ao chamar o Python 2.7 do ArcGIS; sempre com
`timeout`; validar pelo arquivo gerado, não pelo código de saída (o `save()` às vezes grava e
trava na limpeza); nunca `replaceDataSource`/`SaveToLayerFile` (travam); caminho com acento em
py2 via `sys.argv[1].decode("mbcs")`; checar se o ArcMap do Álvaro está com o arquivo aberto e
**pedir para fechar**, nunca matar o processo.

1. Abrir o template `pronto` (cópia, nunca o original).
2. `IPage.StretchGraphicsWithPage = True`; `IPage.FormID = esriPageFormA3` (ou A2/A1/A0);
   `IPage.Orientation` conforme a variante. É a opção "escalar elementos proporcionalmente" do
   ArcMap (D31).
3. Gravar as sentinelas: textos `«MF:<slot>»`, envelopes/escala com os doubles sentinela, data
   sources para `..\SHP\«MF:ds_<camada>»` (com "Store relative pathnames" ligado no documento),
   figura da tabela como vinculada (plano B1 do S6, se o spike não fechar), query com
   `«MF:municipio»`; legenda com `autoAdd = False`; remover WMS/WMTS, grupos de serviço vazios e
   rasters fantasmas de anos anteriores herdados do modelo ([W-17](17-conhecimento-das-skills.md) §4).
4. Remover qualquer `authkey`/token (rodar `ferramentas/chaves_mxd.py limpar` na saída).
5. Salvar como `<template>__<A3>_<retrato>.mxd`, calcular `sha256`, gerar `.slots.json` com
   `python -m mapasfacil_nucleo.mxd_binario slots <arquivo>` (localiza todas as sentinelas e
   falha se faltar ou duplicar).
6. Exportar um PDF do ArcMap da variante com sentinelas trocadas por valores de teste
   (`imovel_ficticio`) → referência para o G4.
7. Copiar para o server (`$MF_RAIZ/dados/templates/`) com `scp` e conferência de `sha256`.

MANIFEST (`shared/templates/MANIFEST.json`) ganha, por template, a lista de variantes:

```json
"variantes": [
  { "formato": "A4", "orientacao": "retrato", "arquivo": "Dinamica_retrato__A4_retrato.mxd",
    "sha256": "…", "slots": "Dinamica_retrato__A4_retrato.slots.json", "slots_sha256": "…",
    "verificado_arcmap": { "em": "2026-11-20T15:00:00Z", "arcmap": "10.8", "motor_binario": "0.1.0", "ok": true } }
]
```

Os arquivos das variantes **não** entram no git (tamanho e porque saem de `.mxd` do acervo):
ficam em `$MF_RAIZ/dados/templates/` no server e em `C:\GIS\mapas-facil-templates\` no Windows;
o git guarda só MANIFEST + `.slots.json`.

### Gates

| Gate | Onde roda | O que prova | Falha |
|---|---|---|---|
| **G1 estrutural** | servidor, em todo `.mxd` gerado | CFBF reabre por um leitor **independente** (`olefile`), todas as streams do template existem, árvore de blocos re-percorrida sem erro, tamanhos de stream batem com os blocos, nenhuma sentinela sobrou | `MX-012`/`MX-013` |
| **G2 semântico** | servidor | cada slot relido devolve o valor aplicado; todo caminho de dado é relativo e resolve **dentro do pacote** (H20); nenhum segredo (H18, `chaves_mxd.py verificar`) | `MX-040`/`MX-050` |
| **G3 diferencial** | servidor | comparando template × gerado, **só** os intervalos de bytes dos slots (e os campos de tamanho que dependem deles) mudaram | `MX-013` |
| **G4 ArcMap real** (teste de desenvolvimento) | Windows de referência, por variante e a cada versão nova do motor | abre headless (`arcpy.mapping` com timeout — só mapping, sem cursor), `ListBrokenDataSources` vazio, `ExportToPDF`, anatomia do PDF exportado igual à do PDF nativo do servidor (tolerância 0,5 mm) | o agente corrige o motor ou a variante; **não** bloqueia entrega ao usuário (D37) |

G4 é automatizado por `ferramentas/verificar_variantes_windows.ps1`: o server gera um pacote de
teste por variante com `python -m mapasfacil_servidor amostras-mxd` (usa o `imovel_ficticio.zip`,
nunca dado de cliente); o script do Windows puxa esses pacotes por `scp` pela tailnet, roda a
verificação e grava o resultado no MANIFEST (commit no repo). É o jeito de o agente saber que o
motor está certo; o usuário nunca espera por ele.

**Política de entrega (D37, P5):** o pacote sai **sempre**. G1–G3 são automáticos e rodam em todo
`.mxd`; se um deles falhar, o `.mxd` daquela versão não entra no pacote (arquivo estruturalmente
quebrado não serve nem para revincular), o pacote leva `Mapas/` e `SHP/` normalmente, e o
`LEIA-ME.txt` + o chat dizem o código `MX-0xx` e o que aconteceu. Nenhuma pessoa valida nada à mão.

### Pacote de entrega — `MXD/ SHP/ Mapas/` (D37)

Organizado **como as pastas de análise do escritório** (ex.: `Analise_PH\MXD`, `SHP`, `Mapas`, e o
padrão "pastas de sempre" da skill `mxd-caracterizacao-embargo`), que é também o conjunto de
`PASTAS_ESCRITA` do núcleo:

```
Fazenda_Boa_Vista__Dinamica_2026__v003.zip
├── MXD/
│   └── Dinamica_2026.mxd             ← caminhos RELATIVOS: ..\SHP\…
├── SHP/
│   ├── ATP.shp .shx .dbf .prj .cpg   ← nomes que o template espera, no CRS do data frame
│   ├── AVN.* AREA_CONSOLIDADA.* AUAS.* …
│   ├── externas/terras_indigenas.* … ← camadas WFS materializadas (recorte do imóvel + margem), com a data da base no nome
│   ├── minimapa/municipios_mt.* uf.* ← da base IBGE do repo (shared/bases/ibge)
│   ├── imagens/mosaico_2026_10.tif + .tfw + .aux.xml   ← o mesmo recorte do PDF, GeoTIFF
│   └── layout/tabela_quantitativos.png  ← se S6 cair no plano B1
├── Mapas/
│   ├── Dinamica_2026.pdf
│   ├── Quantitativos.xlsx
│   └── validacao.json                ← HARD/SOFT da versão
└── LEIA-ME.txt
```

`LEIA-ME.txt` (texto fixo + dados da versão): "Descompacte a pasta inteira e abra
`MXD\Dinamica_2026.mxd` no ArcMap 10.x sem mover as subpastas. Se alguma camada aparecer com `!`
vermelho, clique com o botão direito nela → *Data* → *Repair Data Source* e aponte para a pasta
`SHP` deste pacote — o ArcMap repara as demais da mesma pasta sozinho." + datum, data do mosaico,
versão, e a lista dos checks que falharam (se houver).

O pacote **não** leva WMS/WMTS com chave: o mosaico vai como GeoTIFF local em `SHP/imagens/`
(resolve de quebra o crash do catálogo WMS grande da IMAP no `Map.dll` e o "grupo de serviço
vazio" que exporta mapa sem imagem — skills `wms-imap-diagnostico`, `mxd-service-layers`,
`mxd-imagem-satelite`; ver [W-17](17-conhecimento-das-skills.md)).

### Erros

| Código | Quando |
|---|---|
| `MX-001` | não existe variante para (template, folha, orientação) |
| `MX-010` / `MX-011` / `MX-012` | sentinela ausente / duplicada / sobrou no arquivo |
| `MX-013` | G3: mudança fora dos slots, ou bloco inconsistente no G1 |
| `MX-020` | a folha do `MapSpec` não tem variante — PDF segue, `.mxd` não |
| `MX-021` | variante ainda sem G4 ok para a versão atual do motor — **só informativo** no relatório; não bloqueia (D37) |
| `MX-030` | estilo pedido não suportado no binário (aviso, não erro) |
| `MX-040` | segredo encontrado no `.mxd` |
| `MX-050` | caminho de dado não resolve dentro do pacote |

## Tarefas agentáveis

- [ ] **W10-01** Copiar `formato_mxd.md` e `wms_crash.md` de `C:\GIS\MXD_RE\docs\` para `docs/` (autoria preservada).
- [ ] **W10-02** `mxd_binario/cfbf.py` + `tests/test_cfbf_corpus.py`: para cada `.mxd` de `Referencias_IMAP/MXD/` (61) e `shared/templates/` (25), ler → reempacotar sem mudança → `olefile` lê igual, streams byte a byte iguais.
- [ ] **W10-03** `mxd_binario/blocos.py` + teste: percorrer `PageLayout`/`Maps`/`Mx Document` dos 25 templates sem erro; contar elementos de texto e camadas e bater com o `inspecionar_mxd_arcpy.py` já gravado em `output/mxd_auditoria_templates/`.
- [ ] **W10-04** Spike S0 + relatório.
- [ ] **W10-05** Spikes S1–S11 na ordem da tabela, cada um com relatório e G4 manual.
- [ ] **W10-06** `mxd_binario/slots.py` + `documento.py` para os tipos cujos spikes fecharam.
- [ ] **W10-07** `mxd_binario/gates.py` (G1–G3) + `tests/test_gates_mxd.py` com casos de sabotagem (bloco com tamanho errado, sentinela sobrando, byte mudado fora de slot).
- [ ] **W10-08** `ferramentas/fabricar_variantes_mxd.py` (Windows) + MANIFEST `variantes`.
- [ ] **W10-09** `ferramentas/verificar_variantes_windows.ps1` (G4) + `python -m mapasfacil_servidor amostras-mxd`.
- [ ] **W10-10** `mxd_binario/pacote.py` + rota `GET /versoes/{n}/pacote.zip`.
- [ ] **W10-11** `motores/gerar.py`: `motor="binario"`, avisos `MX-020/021/030` no relatório; T2 antigo passa a delegar ao binário quando houver `.slots.json`.
- [ ] **W10-12** Checks H18, H19, H20 em `validacao/saida.py` ([W-10](10-inteligencia-cartografica.md)).
- [ ] **W10-14** Checklist da fábrica com as lições de [W-17](17-conhecimento-das-skills.md) §4 (legenda `autoAdd=False`, rótulos dinâmicos herdados desligados, WMS/grupos vazios/rasters fantasmas fora, um MXD por subprocesso, duas sessões, template mais recente da série) + teste de aceite do pacote num ArcMap com caminho com espaço e acento.
- [ ] **W10-13** Laboratório REA no Windows: script Frida (em `C:\GIS\MXD_RE\lab\frida\`, fora do repo) que registra as leituras de stream do ArcMap via ole32; rodar abrindo 3 templates e usar no relatório do S0. Automação dos pares A/A′ na fábrica (`ferramentas/fabricar_variantes_mxd.py --par-laboratorio <mudança>`).

## Critérios de aceite

- [ ] Corpus: 86/86 `.mxd` passam no round-trip (W10-02).
- [ ] Para **cada** variante A4 dos templates da Dinâmica e dos temáticos da série: pacote gerado no Linux com o `imovel_ficticio.zip` passa G1–G3 no servidor e G4 no Windows (abre, `broken: []`, PDF do ArcMap com anatomia igual ao nativo ± 0,5 mm).
- [ ] Pelo menos A3 e A1 de `dinamica_retrato` e de um paisagem passam G4.
- [ ] Teste de sabotagem: alterar 1 byte fora de slot → G3 reprova com `MX-013`.
- [ ] Nenhum `.mxd` entregue contém `authkey` (H18 em todos os pacotes do CI).
- [ ] Servidor sem a variante pedida: pacote entregue com `Mapas/` e `SHP/`, sem o `.mxd`, e aviso `MX-020` na UI e no `LEIA-ME.txt`.
- [ ] Pacote descompactado num PC Windows com ArcMap, numa pasta qualquer (inclusive com espaço e acento no caminho): o `.mxd` abre sem `!` vermelho; movendo a pasta `SHP/` de lugar, o *Repair Data Source* numa camada conserta todas.

## Fora de escopo

- Autoria de `.mxd` sem template (camada nova, símbolo novo, elemento novo).
- `.aprx` (ArcGIS Pro) — o Pro não salva `.mxd`; pode virar pedido futuro com outro formato (zip JSON), não aqui.
- `.qgz` (QGIS) — formato aberto, seria fácil, mas não foi pedido.

## Anti-padrões

- Editar o template ou um `.mxd` de cliente no lugar (regra de ouro do vault: sempre cópia).
- Localizar slot por **offset fixo** sem sentinela (quebra na primeira mudança de template).
- Considerar "abre no `olefile`" como prova de que abre no ArcMap (o G4 de desenvolvimento existe para isso).
- Pular o G3 "porque o G1 passou".
- Deixar WMS com chave no `.mxd` entregue.
