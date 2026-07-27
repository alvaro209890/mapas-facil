# Fase 2 — Site de distribuição do Mapas Fácil

Site público: vitrine, requisitos e **download** do instalador Windows. **Não** tem login,
**não** cria conta e **não** gera mapa. Isso fica no [app desktop](../Fase_1_Desktop/README.md)
([F1-14](../Fase_1_Desktop/planos/14-auth-e-conta.md), D21).

## Stack (v1)

| Camada | Tecnologia | Onde |
|---|---|---|
| Site | Next.js | `mapasfacil.cursar.space` (prod); `localhost` (dev) |
| Backend | **ausente** na v1 | pasta `backend/` só documental |
| Conta / mapa | App desktop | Windows do usuário |

## Estrutura

| Pasta | O que é |
|---|---|
| [`planos/`](planos/README.md) | planos F2-00…F2-06 (reescritos 2026-07-27) |
| [`web/`](web/) | site Next.js/vinext implementado — landing + requisitos + download + contato |
| [`backend/`](backend/) | **fora da v1** — só README |

## Leitura

1. [Documentação completa da implementação](DOCUMENTACAO_FASE_2.md)
2. [Visão comum + D21](../planos/00-visao-e-duas-fases.md)
3. [F2-00 — escopo](planos/00-visao-e-escopo.md)
4. [Índice dos planos](planos/README.md)

## Estado

| Marco | Status |
|---|---|
| Planos | **reescritos** (site = distribuição) |
| Código | **implementado e validado localmente** — hero cinematográfico, mapa fictício, animação completa e contatos do desenvolvedor |
| Conta nuvem (F2-05) | **adiado** |

Fluxo: desenvolver neste PC → publicar com systemd + tunnel dedicado ([deploy/](deploy/README.md), [F2-06](planos/06-deploy-tunnel-neste-pc.md)).

Produção neste PC: `https://mapasfacil.cursar.space` (`mapas-facil-site` + `mapas-facil-tunnel`, sobem no boot).
