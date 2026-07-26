# Fase 2 — Site de engenharia florestal e mapas

Site com backend rodando **neste PC** (Linux, Cuiabá-MT), exposto por **Cloudflare Tunnel**
dedicado. Dá ao Mapas Fácil o que o desktop não tem sozinho: espaço de trabalho persistente com
memória, histórico de projetos entre máquinas, mapa por número do CAR sem instalar nada, e uma
vitrine pública.

Esta fase começa **depois** da [Fase 1](../Fase_1_Desktop/README.md) validada. Reusa o núcleo
Python e o `MapSpec` do desktop, mas roda de forma independente.

> **Login do desktop não depende desta fase.** D10 revisada (2026-07-26): o app usa **conta
> local** (e-mail + senha em SQLite) — [F1-14](../Fase_1_Desktop/planos/14-auth-e-conta.md).
> [F2-05](planos/05-auth-e-memoria.md) (conta nuvem / memória) é **pós-M11** e **não** bloqueia
> o M5.

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
| **F2-05 — conta nuvem / memória** | reescrito: **adiado pós-M11**; **não** bloqueia M5 (login = F1-14 local) |
| Planos | F2-00…F2-06 presentes; 01/02/04/06 ainda legado (a reescrever) |
| Código | não iniciado — `backend/` e `web/` só têm `README.md` |
