# Mapas Fácil

Chat de IA que gera mapas **`.mxd` (ArcMap) e `.pdf` no computador do usuário**, no padrão
cartográfico IMAP.

O usuário conversa num site (estilo Cursor / Claude / ChatGPT), pede o mapa em linguagem
natural — *"faz a Dinâmica 2026 da Fazenda Trevisol com AVN, AC e AUAS"* — e o arquivo `.mxd`
abrível no ArcMap, mais o `.pdf` pronto para entrega, aparecem numa pasta do PC dele.

> Este repositório contém, neste momento, **apenas o plano de desenvolvimento**. Nenhum código
> de produção foi escrito ainda. Comece por [`planos/`](planos/README.md).

## Por que existe

Hoje o mapa da série IMAP (Dinâmica, Uso Consolidado, Tipologia Vegetal, Embargos, Alertas) é
feito à mão no ArcMap: abrir o `.mxd` modelo, repontar os shapefiles, ajustar extent e escala,
corrigir legenda, preencher metadados da imagem, exportar o PDF. São 20 a 40 minutos por mapa,
repetidos dezenas de vezes por mês, com variação humana entre mapas que deveriam ser idênticos.

O [NexoGeo Ambiental](https://github.com/alvaro209890/NexoGeo-Ambiental) já provou que a parte
difícil é possível: chat → `MapSpec` validado → PDF no padrão IMAP, com tool calling e
versionamento por edição. O que faltou lá foi justamente o **`.mxd` de verdade** — o entregável
que o cliente abre, edita e arquiva.

O Mapas Fácil nasce do zero com o inverso da prioridade: **o `.mxd` é o produto principal**, o
PDF é a consequência, e o chat é só a interface.

## Como funciona (visão de 30 segundos)

```
   Navegador                 Nuvem                      PC do usuário (Windows)
┌──────────────┐      ┌──────────────────┐         ┌───────────────────────────┐
│  web/        │      │  backend/        │         │  agent/                   │
│  Next.js     │─────▶│  FastAPI + LLM   │────────▶│  Agente Local + ArcMap    │
│  chat        │ HTTP │  MapSpec + jobs  │   WS    │  arcpy → .mxd → .pdf      │
│  preview PDF │◀─────│  fila de jobs    │◀────────│  escreve em C:\...        │
└──────────────┘ SSE  └──────────────────┘ eventos └───────────────────────────┘
```

A nuvem **nunca** recebe os shapefiles do cliente e **nunca** escreve no disco dele: ela só
manda um `MapSpec` (JSON declarativo, algumas dezenas de KB) para o agente local, que faz todo o
trabalho pesado na máquina onde o ArcMap e os dados já estão. Detalhes em
[`planos/01-arquitetura.md`](planos/01-arquitetura.md).

## Estrutura do repositório

| Pasta | O que é | Stack |
|---|---|---|
| [`planos/`](planos/README.md) | Plano de desenvolvimento completo (este é o conteúdo atual) | Markdown |
| [`web/`](web/README.md) | Site do chat | Next.js 16, TypeScript, Tailwind, shadcn/ui |
| [`backend/`](backend/README.md) | API, orquestração de IA e fila de jobs | Python 3.11, FastAPI, Postgres |
| [`agent/`](agent/README.md) | Agente local Windows que roda `arcpy` | Python 3.11 + Python 2.7 (ArcMap) |
| [`shared/`](shared/README.md) | Contratos versionados (JSON Schema, catálogo, templates) | JSON |
| [`Referencias_IMAP/`](Referencias_IMAP/README.md) | PDFs-modelo e `.mxd` reais do padrão IMAP | binários |

`web/`, `backend/`, `agent/` e `shared/` são deployados e versionados de forma independente —
o backend fica em pasta separada do site, como pedido, e o agente é distribuído como instalador
`.exe`.

## Estado atual

| Milestone | Status |
|---|---|
| M0 — Plano e contratos | concluído (planos 00–13 + catálogo WFS + esqueleto) |
| M1 — Backend + conversas | não iniciado |
| M2 — Agente local + `.mxd` real | não iniciado |
| M3 — Chat com IA e tools | não iniciado |
| M4 — Conformidade IMAP | não iniciado |

Roadmap com critérios de aceite por milestone em [`planos/10-roadmap.md`](planos/10-roadmap.md).

## Requisitos do usuário final

- Windows 10/11 (o agente local é Windows-only, porque `arcpy` é Windows-only).
- ArcMap 10.6+ com licença válida, **ou** ArcGIS Pro 3.x (`arcpy.mp`).
- Os shapefiles do imóvel em disco (ou um `.zip` deles).
- Navegador atualizado.

Sem ArcMap, o sistema continua entregando o PDF pelo renderizador nativo — mas não o `.mxd`.
Ver [`planos/05-motor-mxd-pdf.md`](planos/05-motor-mxd-pdf.md).

## Licença

A definir antes do primeiro release público.
