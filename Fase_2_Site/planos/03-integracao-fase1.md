# F2-03 — Integração com a Fase 1

## Objetivo

Definir o único vínculo da v1 entre site e desktop: o site **distribui** o instalador (ou
aponta para ele). Sem reuso runtime do núcleo, sem ponte de jobs de `.mxd`, sem MapSpec no
browser (D21).

## Estado atual vs alvo

| Item | Atual (legado/rascunho antigo) | Alvo v1 |
|---|---|---|
| Reuso de núcleo / MapSpec no site | previsto | **fora** |
| Ponte site → desktop para `.mxd` | rascunho | **adiada** |
| Download do app | implícito | **único contrato** da v1 |

## Dependências

| Precisa de | Plano |
|---|---|
| Escopo distribuição | [F2-00](00-visao-e-escopo.md) |
| Página de download | [F2-04](04-frontend-site.md) |
| Instalador | [F1-11](../../Fase_1_Desktop/planos/11-empacotamento-instalador.md) (M10) |
| Conta | [F1-14](../../Fase_1_Desktop/planos/14-auth-e-conta.md) — só no app |

## O que a v1 integra

| Do desktop | No site |
|---|---|
| Instalador Windows (quando M10 existir) | `NEXT_PUBLIC_DOWNLOAD_URL` / botão Baixar |
| Nome e proposta do produto | copy da landing |
| Requisitos (Windows, ArcMap opcional, BYOK) | página `/requisitos` |

## O que só o desktop faz (não passa pelo site)

| Capacidade | Por quê |
|---|---|
| Login / criar conta | D10 / D21 |
| Gerar `.mxd`, PDF, PNG, xlsx | produto = app |
| Ler pasta, WFS, MapSpec, chat | núcleo Electron + Python |
| Credential Manager / BYOK | nunca no site |

## Ponte desktop ↔ servidor (adiada)

O rascunho antigo (site pede `.mxd` → backend → app Windows) **não** faz parte da v1 do site.
Se o produto pedir no futuro, vira revisão explícita deste plano + [F2-02](02-backend-api.md).

Até lá a regra permanece:

> O site **nunca** promete mapa. Ele promete o **instalador** (ou “em breve”).

## BYOK

| Contexto | Chave DeepSeek |
|---|---|
| Desktop | do usuário (BYOK) |
| Site v1 | **não usa** chave de IA |

## Tarefas agentáveis

- [x] Reduzir este plano ao vínculo download (D21)
- [ ] Na implementação do `web/`: ligar CTA a `NEXT_PUBLIC_DOWNLOAD_URL`
- [ ] Após M10: publicar URL do instalador no env do PC servidor

## Critérios de aceite

- [ ] Planos F2 v1 não exigem import do `mapasfacil_nucleo` no Next.js
- [ ] Nenhuma rota do site dispara geração de mapa
- [ ] Texto de requisitos manda criar conta **no app**, não no site

## Fora de escopo

- Sync de conversas / memória de projeto ([F2-05](05-auth-e-memoria.md))
- Validar MapSpec no servidor
- Upload de shapefile pelo browser

## Anti-padrões

| Não faça | Por quê |
|---|---|
| “Reusar o núcleo no FastAPI do site” na v1 | sem backend; D21 |
| Prometer PDF por CAR na landing | mapa só no desktop |
| OAuth no site para “já deixar a ponte” | login é F1-14 |
