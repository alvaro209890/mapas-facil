# 00 — Visão e escopo

## O problema

A produção cartográfica de uma consultoria ambiental em Mato Grosso é repetitiva e cara:

1. Abrir o `.mxd` modelo da série (Dinâmica 2008, Dinâmica 2019, Embargos IBAMA, Alertas
   MapBiomas, Tipologia Vegetal).
2. Repontar cada camada para os shapefiles do imóvel da vez (lotes, AVN, AC, AUAS).
3. Ajustar extent, escolher uma escala "bonita" (1:20.000, 1:22.000, 1:30.000…), conferir a
   grade DMS.
4. Corrigir legenda, rótulos dos lotes ("Fazenda Trevisol (Lote 65) / Matrícula 13.533").
5. Preencher METADADOS IMAGEM (satélite, órbita/ponto, data, datum).
6. Recalcular a tabela de quantitativos por lote × classe.
7. Exportar o PDF, conferir visualmente, arquivar `.mxd` + `.pdf`.

Entre 20 e 40 minutos por mapa, dezenas de mapas por mês, e o resultado varia conforme quem fez.

## A proposta

Um chat que faz esses sete passos. O usuário descreve o mapa; o sistema entrega **`.mxd` +
`.pdf` no PC dele**, com o padrão IMAP garantido por validação automática, não por disciplina
humana.

### O `.mxd` é o produto, não um extra

Essa é a diferença central em relação ao NexoGeo Ambiental, onde o `.mxd` ficou como
"quando ArcMap estiver disponível" e nunca saiu do papel. Aqui:

- O `.mxd` é o critério de aceite de todo milestone que envolve geração de mapa.
- O renderizador nativo (matplotlib) existe **só** como preview rápido e fallback, nunca como
  entregável principal.
- Nenhuma feature de layout entra no produto sem ter equivalente em `arcpy.mapping` /
  `arcpy.mp`. Se não dá para fazer no ArcMap, não vai para o `MapSpec`.

### Por que "no PC do usuário" e não na nuvem

Três razões, em ordem de peso:

1. **Licença.** `arcpy` exige ArcMap/ArcGIS Pro licenciado e é Windows-only. Rodar isso em
   servidor implicaria licença de servidor ArcGIS, custo proibitivo para o porte do produto.
2. **Dados.** Os shapefiles do imóvel são dados de cliente (matrícula, CAR, geometria). Não
   subir isso para a nuvem elimina de uma vez a maior parte da superfície de risco e da
   conversa sobre LGPD. Além disso, `sema.mt.gov.br` **bloqueia IP fora do Brasil** — o
   backend na nuvem (Render/Vercel) nem consegue baixar WFS da SEMA; o agente no PC do
   usuário resolve isso de graça (lição do GeoForest/Cerebro).
3. **Fluxo de trabalho.** O técnico quer o `.mxd` na pasta do projeto dele, ao lado dos
   shapefiles, para abrir e ajustar. Download de ZIP é atrito.

### Linhagem técnica

| Fonte | O que entra no Mapas Fácil |
|---|---|
| [NexoGeo Ambiental](https://github.com/alvaro209890/NexoGeo-Ambiental) | chat → `MapSpec` → PDF IMAP, tool calling, versionamento; o `.mxd` ficou incompleto |
| **GeoForest-IA** | cliente WFS/WMS de produção: BBOX+clip local, authkey SEMA, fallbacks de paginação, PAMGIA, INCRA GML |
| **Cerebro-Geo-IA** | catálogo (`camadas.json`, `servicos_geo.json`), receitas e gotchas (2026-07) |

Receitas WFS detalhadas: [`13-wfs-e-servicos-geo.md`](13-wfs-e-servicos-geo.md).
Catálogo já versionado: [`../shared/catalog/`](../shared/catalog/).

## Escopo da v1

### Dentro

- Chat multi-conversa com histórico persistente, streaming e tool calls visíveis (estilo Cursor).
- Geração de `.mxd` + `.pdf` no PC via agente local, a partir dos templates da série IMAP.
- `MapSpec` como contrato declarativo único entre IA, backend e agente.
- Edição conversacional do mapa: cada edição gera **nova versão**, nunca sobrescreve.
- Camadas locais (shapefiles do imóvel) e camadas externas do catálogo (WFS SEMA-MT, IBGE).
- Validação automática de conformidade IMAP, com bloqueio de entrega quando um check *hard*
  falha.
- Pareamento seguro navegador ↔ agente local, com escopo de pastas explícito.
- Doctor: diagnóstico do ambiente do usuário (ArcMap achado? Python 2.7? templates? licença?).
- Instalador Windows do agente.

### Fora (e por quê)

| Fora da v1 | Motivo |
|---|---|
| Linux/macOS no agente | `arcpy` não existe nessas plataformas |
| Edição de geometria (desenhar/cortar polígono) | é trabalho de GIS, não de cartografia; usa-se o ArcMap |
| Análises ambientais (sobreposição, pareceres, laudos) | escopo do NexoGeo Ambiental; aqui só mapa |
| Multiusuário simultâneo no mesmo agente | um agente = uma máquina = um usuário na v1 |
| Cobrança/billing | depois da validação com usuários reais |
| Camadas 3D, séries temporais animadas | não fazem parte do padrão IMAP |
| Suporte a QGIS (`.qgz`) | pode entrar na v2 se houver demanda |

## Usuários

| Perfil | O que precisa | Como mede valor |
|---|---|---|
| Técnico de GIS (usuário principal) | mapa da série pronto, `.mxd` editável, sem retrabalho | minutos por mapa |
| Coordenador | consistência entre mapas de entregas diferentes | número de mapas devolvidos por erro de padrão |
| Cliente final (fazendeiro/consultoria) | PDF legível e no padrão que já conhece | reclamações |

## Critérios de sucesso da v1

1. Um mapa da série Dinâmica sai do prompt ao `.mxd` + `.pdf` corretos em **menos de 3 minutos**,
   sem intervenção manual.
2. O PDF gerado passa por **100% dos checks *hard*** de conformidade IMAP
   ([`06-padrao-imap.md`](06-padrao-imap.md)).
3. Um técnico que nunca viu o sistema produz seu primeiro mapa válido em menos de 15 minutos,
   incluindo instalação do agente.
4. O `.mxd` entregue abre no ArcMap do usuário **sem camadas quebradas** (nenhum `!` vermelho).
5. Zero shapefile de cliente trafegando para a nuvem — auditável no log do agente.

## Riscos principais

| Risco | Impacto | Mitigação |
|---|---|---|
| `arcpy` do ArcMap é Python 2.7, sem `f-string`, sem `pathlib`, encoding frágil | alto | script ArcPy isolado, comunicação por JSON UTF-8 em arquivo/env var, nunca `argv` com acento ([`04`](04-agente-local.md)) |
| Templates `.mxd` reais precisam existir e ser mantidos | alto | manifesto versionado em `shared/templates/`, smoke test por template ([`05`](05-motor-mxd-pdf.md)) |
| Usuário sem ArcMap instalado | médio | doctor explícito + fallback PDF nativo, com aviso claro de que não há `.mxd` |
| IA inventar camada/template inexistente | médio | validador rejeita `MapSpec` fora do catálogo ([`07`](07-ia-e-tools.md)) |
| Agente local não conectado quando o job é criado | médio | job fica `pending` com fila e aviso na UI, não erro |
| WFS da SEMA cair ou mudar layer | médio | cache local por bbox + catálogo versionado com data de verificação |
| Escopo virar "NexoGeo 2" | alto | tabela "Fora da v1" acima é vinculante; qualquer inclusão exige atualizar este documento |

## Decisões já tomadas

| # | Decisão | Alternativas descartadas |
|---|---|---|
| D1 | Site na nuvem + agente local Windows | app desktop puro (sem colaboração/histórico); 100% nuvem (impossível com `arcpy`) |
| D2 | Frontend Next.js 16 + Tailwind + shadcn/ui, deploy Vercel | React+Vite (menos SSR/auth pronto) |
| D3 | Backend FastAPI (Python 3.11) em pasta separada | Node/Express (perderia reuso do ecossistema geo Python) |
| D4 | `MapSpec` JSON validado por schema como contrato único | IA gerando código Python arbitrário (insegurável) |
| D5 | Tool calling com tools atômicas, IA nunca reescreve o spec inteiro | spec inteiro por resposta (regressões silenciosas) |
| D6 | Repositório público `mapas-facil` | privado |
