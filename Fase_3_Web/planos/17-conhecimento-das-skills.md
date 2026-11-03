# W-17 — O que as skills de MXD e GIS ensinam (e onde cada lição entra)

## Objetivo

O escritório já resolveu, em sessões reais de mapa, dezenas de problemas que o Mapas Fácil vai
encontrar de novo: enquadramento, imagem de cada ano, armadilhas do formato `.mxd`, layout,
dados do SIMCAR. Essas lições estão espalhadas nas skills do **Hermes deste Windows** e nas
skills do **Claude**. Este plano consolida o que vale para o sistema e diz **em qual plano e
arquivo** cada lição vira código, regra ou check — para o agente implementador não redescobrir.

As skills **não** são copiadas para o repositório (ele é público e uma delas tem segredo em
claro — §8). As regras estão reescritas aqui, com a fonte citada.

## Fontes lidas (2026-11-03)

| Skill | Onde | O que trouxe |
|---|---|---|
| `mapas-facil-automacao` | Hermes Windows `%LOCALAPPDATA%\hermes\skills\software-development\` | uso do núcleo pelo Windows, nomes dos entregáveis, pitfalls de encoding |
| `mxd-edit-binary` | idem | edição binária com `mxd_bin.py`, os 3 tamanhos do texto, `Mx Document` |
| `arcgis-desktop-automation` (+ `references/`) | idem | resíduo nos setores livres, WMS grande, cache de tiles, segfault em lote, enquadramento em Web Mercator, quadro cadastral PNG |
| `mxd-service-layers` | idem | camadas de serviço, grupo vazio, credencial na URL, dois grupos com o mesmo nome |
| `mxd-imagem-satelite` | idem | catálogo de mosaicos SEMA, regra de imagem por ano, o que não dá para automatizar |
| `mxd-layout-elements` | idem (portada da do Claude) | duas sessões, figura colada, mundo → página, faixa livre, casar elemento por posição |
| `mxd-fix-links` | idem | religar por pasta, hachura que some, rótulo dinâmico que liga sozinho |
| `mxd-conform-layout` (+ `references/regras-dinamica-temporal.md`) | idem | série Dinâmica (3 marcos com quantitativo), hachura AC/AVN, legenda, minimapa, ordem do compilado |
| `mxd-propagate-extents` | idem | extents por índice de data frame, CRS do frame |
| `mxd-clone-parcel` | idem | clonar de dentro da série, um processo = um mapa, SIMCAR em SAD69 |
| `mxd-caracterizacao-embargo` | idem | pastas de sempre, interseção em UTM, quadro PROPRIEDADE/PROPRIETÁRIO/CAR/ÁREA |
| `mapa-distancias-ambientais` | idem | distâncias em AEQD, TI × zona de amortecimento, GEOBASES |
| `wms-imap-diagnostico` | idem | crash do `Map.dll`, serviço virtual por camada do GeoServer |
| `mxd-edit-text`, `mxd-export-pdf`, `mxd-inspect` | idem | formato da caixa METADADOS, verificação visual (100 dpi engana) |
| `analise-auas-planet` | idem | mosaicos mensais Planet, critérios periciais de desmate (⚠️ §8) |
| `imap-dla`, `sema-mt-car`, `simcar-*` (varredura) | Hermes Windows `productivity\` | DLA: superzoom + encarte com a mesma imagem; SIMCAR em SIRGAS 4674 |
| `mxd-*` (origem das do Hermes) | Claude `~\.claude\skills\` | as mesmas lições na versão original |
| Análise PH (`Downloads\Analise_de_area\Analise_PH`) | pasta de trabalho, scripts 10–14 e `DOCUMENTACAO_MAPAS.md` | o "zoom na camada" medido (D38) |

## 1. Enquadramento e escala → [W-10](10-inteligencia-cartografica.md)

| Lição | Fonte | Vira |
|---|---|---|
| Conteúdo centrado na **faixa útil abaixo do título**, não no quadro inteiro | PH `11_montar_mxd_arcpy.py::enquadrar` | passo 3/7 do `enquadrar` |
| Escala **redonda**, arredondada **para cima** ("sempre com menos zoom") | PH, `arcgis-desktop-automation` (`df.scale = 4000.0`) | degrau de escala (passo 5), check S20 |
| Mesma escala em todos os mapas do bloco/série | PH (todos a 1:50.000) | passo 6 |
| TI/UC/TE de terceiro enquadram imóvel + alvo + linha de distância | PH | caixa `imovel_mais_alvo` |
| DLA: superzoom na área (~1:2.000–1:2.500, grade de 5") + encarte da propriedade (~1:180.000) com **a mesma imagem** | `imap-dla` | modelo da galeria de DLA + regra de imagem do encarte |
| Nenhum texto/caixa/tabela cobre linha de shapefile — desloca-se o **centro** do extent, não o tamanho do frame | `mxd-layout-elements` | zonas proibidas + H21 |
| Extent no CRS do frame; frame com Planet/SIMCAR costuma ser **Web Mercator**; GCS num frame métrico = mapa branco | `arcgis-desktop-automation`, `mxd-layout-elements`, `mxd-propagate-extents` | passo 1 do `enquadrar`; teste com frame 3857 |
| Minimapa: município inteiro centrado, folga 0,2 cm, 0,1 cm do encarte do MT (40% da largura), quadradinho + linha-guia em L movidos juntos | PH, `mxd-conform-layout`, `mxd-layout-elements` | passo 8 + `motores/minimapa.py` |
| Fórmula mundo → página: `x = df.x + (wx − xmin) · df.w / (xmax − xmin)` (idem y), âncora no canto inferior-esquerdo | `mxd-layout-elements` (conferida contra o modelo, erro de 0,003 cm) | `motores/minimapa.py`, slots de envelope do W-08 |

## 2. Imagem de fundo e metadados → [W-10](10-inteligencia-cartografica.md), [W-09](09-motor-pdf-nativo-e-folhas.md)

| Lição | Fonte | Vira |
|---|---|---|
| Até 2015 → mosaico SEMA; 2016 em diante → Planet de **outubro**; ano corrente → mês mais recente sem nuvem no imóvel | `mxd-imagem-satelite` §5, PH (abril/2026) | tabela de imagem por ano + S18 |
| Catálogo SEMA: `LANDSAT_5_<ano>` 1984–2011 (sem 2001/2002), `LANDSAT_8_<ano>` 2013–2018, `SENTINEL_2_<ano>` 2016–2025; **não há SPOT** | `mxd-imagem-satelite` §2 | `shared/catalog/mosaicos_sema.json` (conferir se já tem tudo) |
| Nunca carregar o GetCapabilities inteiro (SEMA ~300 camadas, IMAP ~2.400 → crash do `Map.dll`); usar o **serviço virtual por camada** do GeoServer | `wms-imap-diagnostico`, `mxd-service-layers` | `camadas/wms.py` (conferir), pacote sem WMS (W-08) |
| Grafias da caixa METADADOS (`LANDSAT 5/TM`, `LANDSAT 8/OLI`, `SPOT`, `CBERS-4A/WPM`, `PLANET`); `Fonte:` por origem; formato com `<bol>` | `regras-dinamica-temporal.md` §4, `mxd-edit-text` | `motores/metadados.py` |
| Satélite, data, órbita e datum vêm **da fonte** — não inventar | `mxd-imagem-satelite` §5 | regra do `metadados.py` + S15 |
| "Sumiu a imagem" quase nunca é link quebrado: grupo de serviço vazio, credencial vencida, serviço fora do ar — e é **silencioso** | `mxd-imagem-satelite` §1, `mxd-service-layers` arm. 8 | S08 no PDF nativo (raster desenhou de fato); GeoTIFF local no pacote |
| Cache de tiles do ArcMap (`MapCacheV1`, `BmLCacheV2`) pode servir mosaico velho do mês corrente | `arcgis-desktop-automation` | só na fábrica/G4 do Windows (o servidor não usa ArcMap) |

## 3. Série Dinâmica, quantitativos e simbologia → [W-10](10-inteligencia-cartografica.md), [W-09](09-motor-pdf-nativo-e-folhas.md), [W-07](07-motion-palco-do-mapa.md)

| Lição | Fonte | Vira |
|---|---|---|
| Só **2000, 2008 e o ano atual** levam AC, AVN, tabela e legenda temática; as intermediárias são limpas | `mxd-conform-layout`, `regras-dinamica-temporal.md` §1 | `analise/serie.py` + galeria (W11-11) |
| AC/AVN sobre satélite em **hachura** (AC amarelo 255,255,0; AVN verde 56,168,0; contorno 0,4 pt), nunca sólido | `mxd-conform-layout`, `arcgis-desktop-automation` | `motores/estilos.py`; palco desenha `padrao: hachura` ([W-07](07-motion-palco-do-mapa.md)) |
| `AVN = AIR − AC − massa d'água` (RIO_ATE_10 + RESERVATORIO_ARTIFICIAL); área úmida é vegetação; lascas < 100 m² descartadas | `regras-dinamica-temporal.md` §2 | `quantitativos/calcular.py` (conferir) |
| Desmate pós-2008 = AC + AUAS, separado em autorizado (AEF da própria matrícula) e não autorizado | idem | quantitativos do marco atual |
| Limite das matrículas: amarelo 1 pt contínuo (tracejado defasado deixa falhas nas divisas internas); nas pranchas 2000/2008 com AVN, vermelho 1 pt | PH, `mxd-conform-layout` | `motores/estilos.py` |
| Rótulo "Mat. N" no centroide (polo de inacessibilidade só se o centroide cair fora ou a < 150 m da divisa) | PH | rótulos do motor nativo |
| Ordem do compilado `Mapas_unidos.pdf` (UC → Tipologia → TI → TACs → Embargos… → Dinâmicas do mais recente a 2000) | `mxd-conform-layout` | `analise/serie.py` (conferir contra a ordem atual) |

## 4. Formato `.mxd` e operação do ArcMap → [W-08](08-motor-mxd-binario.md)

| Lição | Fonte | Vira |
|---|---|---|
| Setores livres do CFBF guardam **resíduo** (camadas fantasmas, URLs velhas): procurar só nas streams vivas; reempacotar limpa | `arcgis-desktop-automation` §MXD | busca de slot + G1 |
| O ArcObjects prioriza a stream `Mx Document`; o `mxd_bin.py` propaga para todas as streams — não remover essa sincronização | `mxd-edit-binary` | `streams` do `.slots.json`, spike S0 |
| `ParagraphTextElement`: 3 tamanhos coerentes (texto cru, BSTR formatado, bloco) | `mxd-edit-binary` | slot `texto` |
| Texto vazio é recusado: "apagar" = um espaço; elemento não se deleta no 10.x (manda-se para fora da página) | `arcgis-desktop-automation`, `mxd-layout-elements` | slot `texto` + fábrica |
| Figura colada pode ser **PNG ou EMF embutido**; trocar pelo mesmo caminho é no-op; trocar a figura reseta tamanho/posição | `mxd-layout-elements` | spike S6 |
| Legenda vem do TOC: remover camada limpa a legenda; `AddLayer` de raster cria "RGB / Band_1"; `autoAdd = False` | `mxd-service-layers`, `regras-dinamica-temporal.md` §5 | fábrica + H22 |
| Religar shapefile com outros campos liga **rótulos dinâmicos** herdados | `mxd-fix-links` | fábrica desliga `showLabels` herdado |
| Religar link quebrado há muito tempo pode **perder a hachura** (símbolo com referência inválida) | `mxd-fix-links` | fábrica parte de template saudável; G4 confere hachura no PDF |
| Dois grupos de serviço com o **mesmo nome** podem ser um bom e um ruim — decidir pelo conteúdo | `mxd-service-layers` | fábrica (limpeza de templates) |
| Credencial embutida na URL do serviço (Planet `api_key`, SEMA `authkey`) | `mxd-service-layers` arm. 9 | H18 + redação de log |
| Mudar o extent desloca a posição **reportada** dos gráficos na mesma sessão (regra das duas sessões) | `mxd-layout-elements` | fábrica: extent numa sessão, gráficos noutra; no binário, posição calculada do extent final |
| Pan por delta de centróide preserva a escala do modelo | `arcgis-desktop-automation`, `mxd-clone-parcel` | alternativa do enquadramento quando o modelo pede escala fixa |
| `replaceDataSource`, `SaveToLayerFile`, `Describe`, cursores **travam** nesta máquina; um MXD por subprocesso; `PYTHONPATH=` vazio; `timeout`; não confiar no código de saída do `save()`; `argv` em `mbcs`; ArcMap aberto trava o arquivo (pedir para fechar, nunca matar) | `mxd-fix-links`, `arcgis-desktop-automation`, `mxd-layout-elements` | fábrica e G4 no Windows |
| Gratícula e fonte de texto **sem API** no arcpy 10.x | `mxd-layout-elements` | entram prontas no template; spike S11 no binário |
| "Clonar de dentro da série, nunca de modelo externo" (o Álvaro edita o layout entre um imóvel e outro) | `mxd-clone-parcel`, `arcgis-desktop-automation` | fábrica usa o template mais recente da série; nunca ressuscitar elemento que ele removeu |

## 5. Layout → [W-09](09-motor-pdf-nativo-e-folhas.md) (motor nativo) e fábrica do [W-08](08-motor-mxd-binario.md)

| Lição | Fonte | Vira |
|---|---|---|
| Legenda com o topo **0,5 cm abaixo** do quadro (0,1 cm deixava "LEGENDA" em cima do rótulo da grade); borda direita 0,2 cm antes do logo; encolhe se não couber | PH | `motores/blocos.py` (legenda) + H16 |
| Grade com intervalo fino (5") empurra rótulos para o rodapé: rebaixar/recuar a legenda | `imap-dla`, `arcgis-desktop-automation` | `grade_dms.py` × `blocos.py` |
| METADADOS do modelo em 16 pt descendo do topo; com 6 linhas vai a 12 pt, com 5 linhas a 14 pt | PH | `blocos.py` (metadados) |
| Quadro cadastral (A4 paisagem): PNG 2549 × 217 px, 2 linhas × 4 colunas `PROPRIEDADE · PROPRIETÁRIO · CAR · ÁREA (HA)`; uma divisória vertical; "PROPRIETÁRIA" quando a titular é mulher; Tahoma/Arial; área com vírgula e 4 casas; nome longo reduz o corpo na célula | `arcgis-desktop-automation`, `mxd-caracterizacao-embargo`, `mxd-layout-elements` | `quantitativos/png_tabela.py` (quadro cadastral) — ver §8 sobre dado pessoal |
| Caixa de distâncias tem de caber na folha (`x + largura ≤ página`) | `mapa-distancias-ambientais` | H16 (span fora da página) |
| Casar elemento pela **posição** + texto, nunca só pelo texto (o mesmo nome aparece em vários elementos) | `mxd-layout-elements` | fábrica (sentinelas) |
| Números no layout em pt-BR (vírgula decimal, milhar com ponto) | `mxd-layout-elements`, `mapa-distancias-ambientais` | S19 |

## 6. Dados de entrada → [W-02](02-projeto-folha-e-upload.md)

| Lição | Fonte | Vira |
|---|---|---|
| O pacote **ArquivoGeometria do SIMCAR vem em SAD69 UTM 22S (EPSG:29192)**; sem converter, o imóvel cai ~60 m fora do lugar. Conversão oficial `SAD_1969_To_SIRGAS_2000` (Helmert −67,35 / +3,88 / −38,22) | `mxd-clone-parcel`, memória `pcf-mxd-sad69-para-sirgas` | detecção do `.prj` SAD69 na indexação + reprojeção com a transformação certa + aviso no resumo (W4-10) |
| Shapefiles do SIMCAR Digital ficam em SIRGAS 2000 geográfico (4674) | `simcar-validacao-geometrias` | padrão de leitura |
| "Um processo = um mapa": o mapa do imóvel não mostra o vizinho, mesmo do mesmo dono e da mesma matrícula-mãe | `mxd-clone-parcel` (regra do Álvaro, 10/08/2026) | prompt do agente + modelo da galeria |
| GEOBASES da IMAP (OneDrive) são as versões datadas de TI, UC, zona de amortecimento, sítios, hidrografia, IBGE | `mapa-distancias-ambientais`, memória `geobases-onedrive-imap` | no servidor, as camadas vêm do catálogo/WFS (`shared/catalog/camadas.json`); a data da base vai para os metadados |

## 7. Verificação → [W-13](13-testes-e-qa.md), [W-10](10-inteligencia-cartografica.md)

| Lição | Fonte | Vira |
|---|---|---|
| "Exportou sem erro" não prova nada: rasterizar o PDF e olhar | todas as `mxd-*` | checks automáticos sobre o PDF (H09, S08, H16, H21, H22) + G4 compara com o nativo |
| 100 dpi engana (some acento e traço fino); julgar a 150–300 dpi | `mxd-export-pdf` | rasterização dos checks a ≥ 200 dpi |
| Comparar lado a lado com o modelo pegou a hachura perdida | `mxd-export-pdf`, `mxd-fix-links` | golden por anatomia (W-09) + G4 |
| PDF aberto no visualizador faz o export falhar calado | `mxd-export-pdf` | só Windows (G4); no servidor o arquivo é sempre novo por versão |

## 8. Segredos e dado pessoal → [W-11](11-seguranca-contas-e-lgpd.md)

- 🔴 A skill **`analise-auas-planet`** do Hermes deste Windows tem a **chave da API da Planet
  escrita em claro** no `SKILL.md`. Ela **não** foi copiada para cá. Recomendação ao Álvaro:
  trocar a linha por um ponteiro ("a chave está na conexão `PLANET.wmts` do ArcCatalog") e, se
  essa chave for anterior ao incidente de 15–16/10/2026, rodá-la. O Mapas Fácil usa a chave da
  Planet só pelo `servidor.env` (W-11).
- Skills e saídas de inspeção imprimem URL de serviço com chave — por isso a redação de log e o
  H18 (`mxd-service-layers` arm. 9).
- O quadro cadastral leva o **nome do proprietário** (dado pessoal, sem CPF): ele entra no
  `MapSpec` e no PDF porque é parte do mapa oficial, mas **não** vai para log técnico nem para o
  provedor de IA (o agente se refere a "o proprietário do recibo"; o nome é preenchido pelo motor).

## Tarefas agentáveis

As lições acima viram tarefas nos planos donos; aqui ficam só as novas que não existiam:

- [ ] **W4-10** ([W-02](02-projeto-folha-e-upload.md)) Detectar SAD69 (EPSG:29192 ou `.prj` com `SAD_1969`) na indexação e reprojetar para SIRGAS 2000 com `SAD_1969_To_SIRGAS_2000`; aviso no resumo; teste com o `imovel_sad69.zip`.
- [ ] **W5-19** ([W-05](05-chat-agente-web.md)) Bloco do prompt com as regras do escritório que o agente precisa **explicar** (não aplicar — quem aplica é o núcleo): série Dinâmica com 3 marcos, imagem por ano, um processo = um mapa, nome do proprietário nunca no texto da IA.
- [ ] **W9-12** ([W-09](09-motor-pdf-nativo-e-folhas.md)) Regras de layout do §5 no motor nativo (legenda 0,5 cm / 0,2 cm, corpo dos METADADOS por nº de linhas, quadro cadastral) — conferir o que já existe em `blocos.py` antes.
- [ ] **W10-14** ([W-08](08-motor-mxd-binario.md)) Checklist da fábrica com os itens do §4 (autoAdd, rótulos dinâmicos, WMS/grupos vazios/rasters fantasmas fora, um MXD por subprocesso, duas sessões).
- [ ] **W11-11 / W11-12** ([W-10](10-inteligencia-cartografica.md)) Série Dinâmica, imagem por ano, distâncias AEQD.
- [ ] **W17-01** Avisar o Álvaro da chave em claro na skill `analise-auas-planet` (feito na conversa de 2026-11-03; a correção da skill é decisão dele).

## Critérios de aceite

- [ ] Cada linha das tabelas §1–§7 tem dono: a tarefa correspondente está no [checklist](15-checklist-implementacao.md).
- [ ] Nenhum arquivo do repositório contém trecho copiado de skill com segredo:
  `grep -rEn "(^|[^[:alnum:]_])(api_key|authkey)=[A-Za-z0-9_-]{12,}|PLAK[0-9a-f]{16,}" Fase_3_Web Fase_1_Desktop/nucleo/mapasfacil_nucleo` → vazio.
  🔴 **`Fase_1_Desktop/nucleo/tests/` fica fora do padrão de propósito**: `test_conversas_redator.py`
  e `test_contexto_vazamento.py` contêm chaves **falsas** para provar que o redator as apaga.
  O job `guardas` do CI usa exatamente esse recorte — sem ele o guarda acusaria para sempre um
  fixture legítimo.

## Anti-padrões

- Copiar a pasta de skills para o repositório "para o agente ter à mão".
- Aplicar uma regra das skills que contradiz uma decisão já tomada nestes planos sem perguntar (as decisões D22–D39 e P1–P10 ganham).
