# Fase 2 — Site de engenharia florestal e mapas

Site com backend rodando **neste PC** (Linux, Cuiabá-MT), exposto por **Cloudflare Tunnel**
dedicado. Dá ao Mapas Fácil o que o desktop não tem sozinho: espaço de trabalho persistente com
memória, histórico de projetos entre máquinas, mapa por número do CAR sem instalar nada, e uma
vitrine pública.

Esta fase começa **depois** da [Fase 1](../Fase_1_Desktop/README.md) validada. Reusa o núcleo
Python e o `MapSpec` do desktop, mas roda de forma independente.

> **Uma peça vem antes: a identidade.** A decisão **D10** tornou o login obrigatório no app
> desktop, e o serviço de identidade descrito em
> [`planos/05-auth-e-memoria.md`](planos/05-auth-e-memoria.md) é **dependência bloqueante do
> marco M5 da Fase 1**. Backend `/auth/*` + site `/login` sobem antes do resto desta fase.

## Stack

| Camada | Tecnologia | Onde roda |
|---|---|---|
| Site | Next.js | `mapasfacil.cursar.space` |
| API | FastAPI + Postgres | **neste PC**, exposto por tunnel |
| Exposição | Cloudflare Tunnel | `mapasfacil-api.cursar.space` |
| Geo | núcleo Python da Fase 1 | consultas WFS/WMS locais (IP em MT) |

## Por que neste PC e não na nuvem

`sema.mt.gov.br` **bloqueia IP fora do Brasil**. Render, Vercel e outros provedores internacionais
não conseguem fazer `GetFeature`. Este PC está em Mato Grosso — a decisão **D7** fixa o backend
aqui, com tunnel dedicado que **não toca nos tunnels existentes** dos outros sistemas.

## O que o site não faz

- **Não gera `.mxd`.** Sem ArcMap no servidor, o `.mxd` continua sendo entregável exclusivo do
  [app desktop](../Fase_1_Desktop/README.md).
- **Não substitui o desktop.** É complemento: memória, histórico, acesso sem instalação.

## Estrutura desta pasta

| Pasta | O que é |
|---|---|
| [`planos/`](planos/README.md) | plano de desenvolvimento da Fase 2 |
| [`web/`](web/) | site Next.js — **só README** (código não iniciado) |
| [`backend/`](backend/) | API FastAPI — **só README** (código não iniciado) |

## Leitura recomendada

1. [Visão e as duas fases](../planos/00-visao-e-duas-fases.md) — contexto e decisão D7
2. [Índice dos planos](planos/README.md) — estado atual (rascunhos D7 + legado)
3. [Fase 1 — App desktop](../Fase_1_Desktop/planos/README.md) — o que o site reusa

## Estado

| Marco | Status |
|---|---|
| **F2-05 — identidade** | reescrito e agentável; **bloqueia o M5 da Fase 1** |
| Planos | F2-00…F2-06 presentes; 01/02/04/06 ainda legado (a reescrever) |
| Código | não iniciado — `backend/` e `web/` só têm `README.md` |
