# F2-03 — Integração com a Fase 1

Como o site reusa o que a Fase 1 já resolveu, e o que só o desktop consegue fazer.

## O que se reusa direto

| Artefato | Origem | Uso na Fase 2 |
|---|---|---|
| `MapSpec` | [`../../planos/02-mapspec-contrato.md`](../../planos/02-mapspec-contrato.md) | contrato único; o backend valida o mesmo schema |
| Padrão Harmonia | [`../../planos/01-padrao-imap-harmonia.md`](../../planos/01-padrao-imap-harmonia.md) | checks HARD/SOFT nos PDFs do site |
| Catálogo WFS | [`../../planos/03-wfs-e-servicos-geo.md`](../../planos/03-wfs-e-servicos-geo.md) | backend neste PC baixa as camadas |
| Núcleo Python (módulos geo) | `Fase_1_Desktop/nucleo/` | importado ou empacotado no FastAPI — **sem** Electron |
| Parser do recibo / xlsx | linhagem NexoGeo | mesmos parsers no backend |

## O que só o desktop faz

| Capacidade | Por quê |
|---|---|
| Gerar `.mxd` | exige ArcMap/`arcpy` ou patch OLE no Windows do usuário |
| Abrir pasta local do cliente | dados nunca sobem sem consentimento |
| Credential Manager BYOK | chave DeepSeek fica no PC do usuário na Fase 1 |

## Ponte desktop ↔ site (rascunho)

Fluxo desejado quando o usuário no site precisa do `.mxd`:

```
Site                         Backend (este PC)              App desktop (Windows)
  │  "quero o .mxd"                │                              │
  ├────────────────────────────────▶│  cria job tipo mxd_remoto    │
  │                                ├─────────────────────────────▶│  recebe MapSpec
  │                                │                              │  gera .mxd local
  │                                │◀─────────────────────────────┤  confirma / path
  │◀───────────────────────────────┤  status + link de download   │  (ou só confirma)
```

Detalhes de autenticação da ponte, fila e timeouts entram na reescrita de
[`02-backend-api.md`](02-backend-api.md). Até lá, este documento só fixa a regra:

> **O servidor nunca promete `.mxd`.** Ele promete PDF/PNG e, opcionalmente, um job
> delegado ao desktop.

## BYOK vs chave no backend

| Contexto | Chave DeepSeek |
|---|---|
| Fase 1 | do usuário (BYOK), Credential Manager |
| Fase 2 (mapa por CAR no site) | chave do serviço neste PC, ou BYOK web se implementado |

Não misturar: um usuário do site não deve herdar a chave do desktop de outro PC.

## Estado

Rascunho alinhado a D1/D7. A implementação depende da reescrita dos planos legado.
