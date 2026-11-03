# W-10 — Inteligência cartográfica: enquadramento, metadados e validação

## Objetivo

Fazer o mapa sair **certo sem ninguém ajeitar**: escala e enquadramento escolhidos a partir da
geometria real, da folha e dos elementos do layout que caem sobre o quadro; metadados técnicos
preenchidos a partir do que foi **de fato** usado (CRS, mosaico, fontes); e uma validação que
bloqueia o que não pode sair (texto sobre texto, link quebrado, área que não bate com o recibo do
CAR) e explica o que fazer.

## Estado atual vs alvo

| Item | Hoje | Alvo |
|---|---|---|
| Escala `auto` | algoritmo de 7 passos em `planos/01-padrao-imap-harmonia.md` §Escalas (bbox + 15% + quadro em mm + arredondar para cima na lista) | `motores/enquadramento.py`: **zoom na camada** como o escritório faz no ArcMap (D38) — faixa útil, margem, escala redonda para cima, escala única por série |
| Lista de escalas | 5.000 … 250.000 (20 valores), check H05 | **sem lista** (P8): escala redonda por degrau; H05 vira "escala redonda" |
| CRS | zona UTM pelo centroide (21S `31981` / 22S `31982`) | + 20S `31980` (MT a oeste de 60° W) |
| Metadados | rótulos do `MapSpec.metadados`, `Escala: auto` derivada | preenchimento automático por proveniência real |
| Checks | H01–H14 HARD, S01–S11 SOFT (`validacao/saida.py`, `anatomia.py`) | + H15–H22, S12–S20; H05 sai (vira S20); HARD marca "não conforme" sem bloquear download (D37) |

## Dependências

W9 (perfil por folha). Os checks H18–H20 dependem do W10-motor binário.

## Contratos

### Enquadramento — `mapasfacil_nucleo/motores/enquadramento.py` (novo)

```python
@dataclass(frozen=True)
class Enquadramento:
    crs: str                       # "EPSG:31982"
    escala: int                    # denominador da lista
    extent: tuple[float, float, float, float]   # no CRS do data frame
    quadro_mm: tuple[float, float]
    aproveitamento: float          # área do bbox do imóvel / área útil do quadro, 0–1
    deslocamento_mm: tuple[float, float]        # quanto o centro foi empurrado para fugir de zonas proibidas
    alternativas: list[dict]       # [{formato, orientacao, escala, aproveitamento}] — 10 combinações

def enquadrar(geometrias_visiveis, perfil: PerfilPagina, *, margem=0.15,
              zonas_proibidas: list[Caixa], escala_fixa: int | None = None) -> Enquadramento: ...
```

É o **"zoom na camada"** do ArcMap, do jeito que o escritório faz (D38, resposta P8). Medido nos
mapas da **Análise PH** (`Downloads\Analise_de_area\Analise_PH`, `Scripts\11_montar_mxd_arcpy.py`
e `DOCUMENTACAO_MAPAS.md` §Decisões de layout):

- o bloco de 12 matrículas (12,1 km de largura) saiu a **1:50.000**, ocupando 25 dos 28,5 cm do
  quadro — e **todos** os mapas do bloco (dinâmicas, DLA, alertas, embargos, tipologia) usam a
  mesma escala;
- o conteúdo fica **centrado na faixa útil abaixo do título** (o título fica por cima do topo do
  quadro), não no centro do quadro;
- mapas de contexto mudam a caixa: TI a 1:100.000, UC a 1:1.100.000, TE de terceiro a 1:800.000,
  para caber o alvo e a linha de distância;
- o minimapa enquadra o **município inteiro**, centrado, com 0,2 cm de folga da borda e 0,1 cm do
  encarte do MT (que ocupa 40% da largura do minimapa), escala arredondada para cima ("sempre com
  menos zoom").

Outras referências das skills: DLA usa superzoom na área da DLA (~1:2.000–1:2.500, grade de 5")
com encarte da propriedade inteira (~1:180.000) **com a mesma imagem** do mapa principal (skill
`imap-dla`); caracterização de embargo de lote ~1:10.000 (skill `mxd-caracterizacao-embargo`).

Algoritmo (substitui os passos 1–5 do comum; 6–7 continuam):

1. **CRS de cálculo**: zona UTM do **centroide** do imóvel em SIRGAS 2000 — `31980` (20S) se
   lon < −60°, `31981` (21S) se −60° ≤ lon < −54°, `31982` (22S) se lon ≥ −54°. Nunca hardcodar.
   (Conferir no W11 se `geo/crs.py` já cobre a 20S; se não, acrescentar.) O **CRS do data frame**
   é o do template — muitos frames com Planet/SIMCAR estão em **Web Mercator (3857)**: o extent
   final é convertido para ele antes de aplicar (senão o mapa sai em branco — `planos/01` §CRS).
2. **Caixa de conteúdo** (a "camada" do zoom): por tipo de mapa, vinda do modelo da galeria —
   `imovel` (perímetro + internas; padrão), `imovel_mais_alvo` (TI/UC/TE: une o imóvel, a feição
   alvo e a linha de distância), `area_tematica` (DLA, AUAS: só a feição do tema). Camadas externas
   não entram na caixa, salvo `imovel_mais_alvo`.
3. **Faixa útil**: o quadro do mapa (`perfil.mapa`) menos as **zonas proibidas** — retângulos dos
   elementos opacos que ficam **sobre** o quadro (título, rosa, minimapa/encarte, legenda
   flutuante, tabela, logo — o que interceptar `perfil.mapa` com mais de 1 mm²). A faixa útil é o
   maior retângulo alinhado aos eixos dentro do quadro sem tocar zona proibida (no perfil do
   escritório, a faixa **abaixo do título**). Regra do Álvaro: **nenhum texto, caixa ou tabela
   pode cobrir linha de shapefile** — por isso a caixa de conteúdo tem de caber inteira na faixa
   útil (check H21).
4. **Margem** de 15% sobre a caixa (é o que reproduz a PH: 12,1 km × 1,15 = 13,9 km em 28,5 cm →
   1:48.800 → 1:50.000). Parâmetro calibrado no W11-08 com o acervo, não chute.
5. **Escala**: `k = max(largura_m / largura_util_mm, altura_m / altura_util_mm) × 1000` e
   **arredondar para cima** para a escala redonda pelo degrau:

   | Escala calculada | Arredonda para múltiplo de | Exemplo |
   |---|---|---|
   | até 1:10.000 | 500 | 1:2.180 → 1:2.500 |
   | 1:10.000 a 1:200.000 | 5.000 | 1:48.800 → 1:50.000 · 1:103.200 → 1:105.000 |
   | 1:200.000 a 1:1.000.000 | 50.000 | 1:812.000 → 1:850.000 |
   | acima de 1:1.000.000 | 100.000 | 1:8.335.900 → 1:8.400.000 |

   (Os degraus reproduzem as escalas dos modelos da Harmonia e da PH — 1:2.500, 1:10.000,
   1:50.000, 1:60.000, 1:90.000, 1:100.000, 1:105.000, 1:800.000, 1:1.100.000 e os minimapas de
   1:7.500.000 a 1:11.300.000. A lista antiga tinha também 1:12.500 e 1:22.000, que não caem no
   degrau de 5.000: o W11-08 confere contra o acervo e, se elas aparecerem nos modelos, o degrau
   abaixo de 1:25.000 vira 500.)
6. **Série com escala única**: quando o pedido gera vários mapas do mesmo imóvel com a mesma
   caixa (a série da Análise de área, as dinâmicas), calcula-se a escala de cada um e **todos
   usam a maior** (menos zoom) — como na PH. Mapas `imovel_mais_alvo` ficam fora da regra.
7. **Centro**: o centro da caixa cai no centro da faixa útil (não do quadro) — isto é o
   `deslocamento_mm`. Extent final = quadro inteiro na escala escolhida, com esse centro.
8. **Minimapa**: município inteiro centrado, folga 0,2 cm da borda e 0,1 cm do encarte do MT;
   se não couber centrado nem a 60% do tamanho, desliza para o lado do encarte até sair dele;
   escala arredondada para cima pelo degrau. O quadradinho do imóvel e a linha-guia em L são
   reposicionados pela fórmula mundo → página (`mxd-layout-elements`) e movidos **juntos**.
9. **Alternativas**: repetir 3–5 para as 10 combinações folha × orientação; devolve tabela.
   `aproveitamento` = área da caixa (com margem) ÷ área da faixa útil, em mm na escala escolhida.
10. Gravar `escala`, `extent` e `crs` resolvidos no `MapSpec` da versão (regra 6 do comum —
    reexecução dá o mesmo mapa).

Escala pedida pelo usuário ("põe em 1:50.000") vira `escala_fixa`; se a caixa não couber na
faixa útil, o núcleo **não** corta: responde `NU-301` ("na A4 retrato, 1:50.000 corta 18% do
imóvel; a menor escala que cabe é 1:60.000 ou passe para A3") e o agente repassa. Escala pedida
que não é redonda é aceita como o usuário pediu (é decisão dele) e só gera aviso S20.

A troca da lista fixa pelo degrau **muda o padrão comum**: o W11 atualiza
`planos/01-padrao-imap-harmonia.md` §Escalas e o H05 no mesmo commit.

### Metadados automáticos — `mapasfacil_nucleo/motores/metadados.py` (novo)

Cada linha do bloco de metadados tem **proveniência**; nenhum valor é digitado pela IA quando
pode ser derivado.

| Rótulo (os que o perfil já tem) | Valor derivado de | Exemplo |
|---|---|---|
| `Datum` | EPSG do data frame → tabela fixa | `SIRGAS 2000 UTM 22 S` (`31982`), `SIRGAS 2000 UTM 21 S` (`31981`), `SIRGAS 2000 UTM 20 S` (`31980`), `SIRGAS 2000` (`4674`), `WGS 84 / Pseudo-Mercator` (`3857`) |
| `Escala` | `Enquadramento.escala` | `1:40.000` |
| `Satélite/Sensor` | basemap **efetivamente usado** (não o pedido) — grafias do escritório (skill `mxd-conform-layout`, `references/regras-dinamica-temporal.md`): `LANDSAT 5/TM`, `LANDSAT 8/OLI`, `SPOT`, `CBERS-4A/WPM`, `PLANET`, `SENTINEL-2` | `PLANET` |
| `Data da imagem` | id do mosaico Planet mensal (`global_monthly_2026_10_mosaic` → `Outubro/2026`); data da cena do acervo (`30/07/2000`); data do mosaico SEMA | `Outubro/2026` |
| `Órbita/Ponto` | só para cena Landsat/CBERS/SPOT do acervo (path/row); senão `Não se aplica`. O rótulo segue a grafia do template (há modelos com "Óbita/Ponto" — não corrigir sem o Álvaro pedir, para casar com os mapas já entregues) | `224/069` |
| `Fonte` (da imagem) | por ano, regra do Álvaro (skill `mxd-imagem-satelite` §5): até 2015 `Servidor WMS SEMA`; 2016 em diante `Servidor WMS Planet`; acervo local `Acervo Landsat / IMAP` / `Acervo SPOT / IMAP`; CBERS do GeoServer `WMS IMAP` | `Servidor WMS Planet` |
| Fontes das camadas (bloco de créditos, quando o perfil tem) | órgãos das camadas **presentes no mapa**, do `orgao`/`fonte` de `shared/catalog/camadas.json`, com a data da base | `SEMA-MT; FUNAI (15/05/2025); IBGE (BC250 2023)` |

Regras da imagem de fundo (D39; skills `mxd-imagem-satelite`, `regras-dinamica-temporal`):

| Ano do mapa | Imagem | Mês |
|---|---|---|
| 1984–2011 | mosaico SEMA `Mosaicos:LANDSAT_5_<ano>` (faltam 2001 e 2002) ou cena do acervo local | o do mosaico/cena |
| 2008 (marco legal) | SPOT 2008 do acervo (o endpoint da SEMA **não tem** SPOT) ou `LANDSAT_5_2008` | o da cena |
| 2013–2015 | `Mosaicos:LANDSAT_8_<ano>` | o do mosaico |
| 2016 em diante | Planet mensal | **outubro** do ano |
| ano corrente (outubro ainda não existe) | Planet mensal | o mês mais recente **sem nuvem sobre o imóvel** (na PH, abril/2026 porque março tinha nuvem) — medir a cobertura de nuvem no recorte, não no mosaico inteiro |
| sem Planet | Esri World Imagery, registrado como tal nos metadados, e aviso ao usuário | — |

- Se a imagem pedida não existe e caiu no fallback, os metadados descrevem o **fallback** e S15 avisa.
- O mosaico escolhido vai para `MapSpec.basemap.mosaico` (determinismo).
- Nunca carregar o GetCapabilities inteiro da SEMA (~300 camadas) ou da IMAP (~2.400) — usar o
  catálogo `shared/catalog/mosaicos_sema.json` e, no GeoServer da IMAP, o **serviço virtual por
  camada** (`/geoserver/cbers/<camada>/wms?`).

Regras da série Dinâmica (D39; skill `mxd-conform-layout` §Regra de Ouro):

- **Só três marcos levam quantitativo** (AC, AVN, tabela de áreas, legenda temática): **2000**,
  **2008** e o **ano atual**. As intermediárias (2005, 2009, 2012, 2013, 2015, 2017, 2019, 2023…)
  são **limpas**: imagem do ano + limite do imóvel/matrículas + título + METADADOS IMAGEM.
- AC e AVN sobre satélite em **hachura** (nunca sólido): AC hachura amarela `255,255,0`, AVN
  verde `56,168,0`, contorno 0,4 pt — o sólido esconde a imagem e impede a leitura pericial.
- `AVN = AIR − AC − massa d'água` (massa d'água = `RIO_ATE_10` + `RESERVATORIO_ARTIFICIAL` do CAR
  Digital; área úmida continua vegetação); lascas < 100 m² na divisa são descartadas.
- No marco atual, `desmate pós-2008 = AC + AUAS`, separado em **autorizado** (intersecta AEF
  vigente da SEMA da própria matrícula) e **não autorizado**.
- Ordem do PDF compilado (`Mapas_unidos.pdf`): UC → Tipologia → TI → TACs → Embargos SEMA/SIGA →
  Embargos SEMA → TE → Embargos IBAMA → Alertas MapBiomas → Alertas PRODES → Dinâmicas do ano mais
  recente até 2000. Conferir com `analise/serie.py` (a série atual tem ordem própria — se divergir,
  perguntar ao Álvaro qual vale).

Distâncias (caixa de distâncias e mapas de TI/UC — skill `mapa-distancias-ambientais`):

- projeção **azimutal equidistante centrada no centroide do imóvel** (`+proj=aeqd`), distância
  **entre bordas**; 0 = escrever "sobrepõe", nunca "0 m";
- reportar sempre **TI e zona de amortecimento da TI** (e da UC) separadas — na Harmonia a TI
  estava a 0,51 km, dentro da zona, o que muda o texto do laudo;
- área de sobreposição (embargo × lote) calculada em UTM local, 4 casas, e o shapefile salvo em SIRGAS 2000 (4674);
- citar fonte e data da base; vírgula decimal.
- Rótulo que o perfil não tem não é inventado (corolário do `MapSpec`: campo só existe se o
  motor tem). Rótulo novo = mudança no perfil, nos templates e no comum.
- `mapspec.metadados[].valor = "auto"` significa "derive"; valor explícito do usuário prevalece,
  mas H04 continua checando coerência do Datum.

### Checks novos (entram na tabela do comum `planos/01-padrao-imap-harmonia.md` §Checklist)

| ID | Check | Como verificar | Sev. |
|---|---|---|---|
| `H15` | Página no formato do `MapSpec.folha` | `fitz` page.rect em mm vs `folha_mm` ± 1 mm (generaliza H02, que fica para A4) | HARD |
| `H16` | Nenhum texto do layout sobrepõe outro texto | spans de texto do PDF (`page.get_text("dict")`) agrupados por elemento (pela `caixa_mm` do perfil); interseção de bbox entre spans de **elementos diferentes** > 0,5 mm² ⇒ falha; span que sai da página ou da caixa do próprio elemento > 0,5 mm ⇒ falha | HARD |
| `H17` | Área total = área do recibo do CAR | área do perímetro calculada **como o SIMCAR calcula** (projeção usada pelo SIMCAR — ver vault/memória `simcar-car-shapefile-model`: SIRGAS 2000 UTM 22S; confirmar no W11-06 com 3 recibos reais do acervo) vs `area_recibo_ha`; tolerância inicial `max(0,01 ha; 0,01%)`, calibrada no W11-06. Sem recibo ⇒ check não se aplica (registrado como `n/a`, não como ok) | HARD |
| `H18` | `.mxd` sem segredo | `chaves_mxd.py verificar` no `.mxd` do pacote | HARD |
| `H19` | `.mxd` estruturalmente válido | gates G1–G3 de [W-08](08-motor-mxd-binario.md) | HARD |
| `H20` | Todo dado do `.mxd` resolve dentro do pacote | todo `IWorkspaceName` relativo e o arquivo existe no `.zip` | HARD |
| `H21` | Nenhum texto, caixa ou tabela cobre linha de shapefile | elementos opacos do layout (título, minimapa/encarte, legenda, tabela, logo, balões) × geometria das camadas do imóvel na página: interseção > 0,5 mm² ⇒ falha (regra do Álvaro, skills `mxd-layout-elements`/`mapa-distancias-ambientais`) | HARD |
| `H22` | Legenda só com o que está no mapa | todo item da legenda corresponde a camada desenhada no quadro; nenhum item órfão de camada removida, nenhum "RGB / Band_1" de raster, nenhuma amostra de outro cliente (complementa o H08, que é o inverso) | HARD |
| `S12` | Classes de área batem com o quadro do recibo | AVN, AC, AUAS, ARL, APP calculadas como no H17 vs quadro de áreas do recibo; mesma tolerância. **Sempre SOFT** — decisão do Álvaro (P9): só avisa, nunca bloqueia | SOFT |
| `S13` | Quadro bem aproveitado | `Enquadramento.aproveitamento` ≥ 0,60 | SOFT |
| `S14` | Existe folha/orientação claramente melhor | alguma alternativa dá escala ≥ 2 degraus da lista melhor com a mesma folha (troca de orientação) ⇒ aviso com a sugestão; o agente oferece trocar | SOFT |
| `S15` | Metadados de imagem = imagem usada | basemap usado ≠ pedido, ou `Data da imagem` vazio/placeholder | SOFT |
| `S16` | Rótulos de feição livres | rótulo do imóvel e rótulos de camadas não colidem com zonas de elemento do layout nem entre si (bbox > 0,5 mm²) | SOFT |
| `S17` | Resolução do mosaico para a folha | dpi efetivo do raster no quadro < alvo da folha ([W-09](09-motor-pdf-nativo-e-folhas.md) §Raster) | SOFT |
| `S18` | Imagem de fundo do ano certo | sensor/mês usados × tabela de imagem por ano acima (ex.: Dinâmica 2019 sem Planet de outubro) | SOFT |
| `S19` | Números do layout em pt-BR | textos de metadados, tabela, balões e caixa de distâncias sem número com ponto decimal (`\d\.\d` fora de coordenada DMS) | SOFT |
| `S20` | Escala redonda | o denominador cai no degrau da tabela do enquadramento (substitui o H05 de lista fixa) | SOFT |

`H05` (escala na lista) sai do checklist do comum, substituído por `S20`; `H06` (escala impressa =
escala real) continua HARD.

Com D37, **HARD não bloqueia download**: falha de HARD marca a versão como "não conforme" (selo na
UI, `conforme=0` no banco, aviso no `LEIA-ME.txt`) e a IA explica e oferece corrigir.

`H01` e `H13` (que pedem ArcMap) passam a ter equivalentes sem ArcMap: `H20` e `H19`. No
servidor, `H01`/`H13` aparecem como `n/a (sem ArcMap; ver H19/H20)`; no G4 do Windows eles rodam
de verdade.

`validacao.json` por versão (o formato existente de `validacao/relatorio.py`, acrescido):

```json
{
  "conforme": false,
  "motor": "binario",
  "folha": { "formato": "A3", "orientacao": "paisagem" },
  "enquadramento": { "crs": "EPSG:31982", "escala": 25000, "aproveitamento": 0.71, "alternativas": [ … ] },
  "hard": [ { "id": "H17", "ok": false, "mensagem": "Área do perímetro 1.240,5498 ha × recibo 1.240,8810 ha (Δ 0,3312 ha; 0,027%)",
              "o_que_fazer": "Confira se o ATP.shp é o mesmo do recibo enviado." } ],
  "soft": [ … ],
  "nao_se_aplica": [ "H01", "H13" ]
}
```

### Explicação no chat

`explicar_validacao` ([W-05](05-chat-agente-web.md)) lê esse JSON. Para cada falha, mensagem
humana + `o_que_fazer`. Textos fixos por check em `validacao/mensagens.py` (novo) — a IA não
redige diagnóstico, só repassa e contextualiza.

## Tarefas agentáveis

- [ ] **W11-01** `motores/enquadramento.py` + testes com geometrias sintéticas: quadrado, retângulo 3:1 deitado e em pé, "L", imóvel minúsculo, imóvel gigante; zonas proibidas do perfil retrato e paisagem.
- [ ] **W11-02** Ligar `enquadrar` em `motores/gerar.py` e no motor binário (extent/escala dos slots); emitir `viewport.foco nivel=enquadramento` com o resultado.
- [ ] **W11-03** `geo/crs.py`: zona 20S (`31980`) + teste com centroide a 60,5° W.
- [ ] **W11-04** Escala redonda por degrau + escala única por série + minimapa (passos 5, 6 e 8) + atualização do comum (`planos/01-padrao-imap-harmonia.md` §Escalas, H05 → S20).
- [ ] **W11-05** `motores/metadados.py` com a tabela de proveniência; `basemap.py` devolve o que usou de fato (id, sensor, data).
- [ ] **W11-06** Calibração do H17/S12: rodar o cálculo em ≥ 3 imóveis do acervo com recibo (no Windows, dado local — **sem** versionar recibo) e registrar a projeção e a tolerância em `docs/calibracao-areas-car.md` (só números agregados, sem CPF/nome).
- [ ] **W11-07** `validacao/saida.py` + `anatomia.py`: H15–H22 e S12–S20; `validacao/mensagens.py`.
- [ ] **W11-11** Regras de imagem por ano e da série Dinâmica (só 2000/2008/atual com quantitativo; hachura AC/AVN; AVN = AIR − AC − massa d'água; desmate autorizado × não autorizado) no `analise/serie.py`, `motores/basemap.py`, `motores/estilos.py` e na galeria.
- [ ] **W11-12** Distâncias em AEQD (`geo/distancia.py`): conferir se já é AEQD/entre bordas; reportar TI e zona de amortecimento separadas; "sobrepõe" para 0.
- [ ] **W11-08** Ajuste da margem por folha com o acervo (`Referencias_IMAP/Mapas/*`): medir o aproveitamento dos PDFs-modelo e fixar `margem` para que o algoritmo reproduza a escala deles em ≥ 80% dos casos.
- [ ] **W11-09** `tools.py::sugerir_enquadramento` usando `Enquadramento.alternativas`.
- [ ] **W11-10** Atualizar `planos/01-padrao-imap-harmonia.md` §Checklist com H15–H20/S12–S17.

## Critérios de aceite

- [ ] Para os PDFs-modelo do acervo com geometria disponível **e para os 18 mapas da Análise PH**: a escala escolhida pelo `enquadrar` é a mesma do modelo em ≥ 80% dos casos e nunca mais afastada que 1 degrau; o bloco da PH sai a 1:50.000 em todos os mapas da série.
- [ ] Nenhum dos 20 mapas da série no `imovel_ficticio` falha H16.
- [ ] Teste de sabotagem do H16: título com 200 caracteres ⇒ H16 reprova (o texto invade o bloco ao lado).
- [ ] Teste do H17: perímetro deslocado/alterado em 1% ⇒ reprova; o idêntico ⇒ passa; sem recibo ⇒ `n/a`.
- [ ] Planet indisponível (mock) ⇒ metadados dizem o fallback e S15 avisa.
- [ ] Imóvel alongado 3:1 deitado em A4 retrato ⇒ S14 sugere paisagem com a escala nova.

## Fora de escopo

- Generalização cartográfica automática (simplificar feição para a escala) além da simplificação de palco.
- Posicionamento ótimo de rótulos por algoritmo de rotulagem completa (S16 só detecta).
- Rotação do data frame.

## Anti-padrões

- Arredondar escala para baixo "para ficar mais bonito" (corta o imóvel).
- Escrever `Data da imagem` pelo que foi **pedido** e não pelo que foi **usado**.
- Comparar área com o recibo numa projeção diferente da do SIMCAR e "compensar" na tolerância.
- Dar HARD ao S12 (decisão P9: sempre SOFT).
- Centrar o conteúdo no quadro inteiro em vez da faixa útil (o título tapa o topo do imóvel).
- Escalas diferentes entre mapas da mesma série do mesmo imóvel.
