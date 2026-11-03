# Piloto interno da Fase 3 (W12-07)

*(autor: Hermes-windows/default | 2026-11-03)*

Três pessoas do escritório, **5 imóveis reais cada**. O dado do cliente fica **só no server** —
aqui entram apenas: quem participou, o que quebrou (sem nome de cliente, sem CPF, sem CAR) e o
tempo gasto.

## Quem

| # | Pessoa | Papel no escritório | Começou | Terminou | Observação |
|---|---|---|---|---|---|
| 1 | Pamera | responsável técnica | ⏳ | ⏳ | assina o que sai |
| 2 | Manu | rotina do dia 20 | ⏳ | ⏳ | |
| 3 | Ellen | rotina de análise | ⏳ | ⏳ | |

> Bruno (triagem federal) e Cris entram só se o piloto dos três primeiros fechar.

## O que cada um faz, por imóvel

1. entra no site e cria o projeto (folha A4 retrato na primeira vez);
2. sobe o `.zip` do imóvel;
3. pede no chat a dinâmica do ano que interessa;
4. confere o mapa no palco antes de baixar;
5. baixa o `.zip` da versão e **abre no ArcMap**;
6. diz o que faltou/sobre e quanto tempo levou.

## O que eu meço (por imóvel, sem dado de cliente)

| # | Imóvel (apelido) | Login → PDF (min) | Conforme (H*)? | Achados no chat | Abriu no ArcMap? | Tempo total (min) |
|---|---|---|---|---|---|---|
| 1 | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ |
| 2 | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ |
| 3 | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ |
| 4 | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ |
| 5 | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ |

*mínimo para o critério do W-00: 3 imóveis abaixo de 10 min, com H* verdes.*

## Problemas (o material que vira tarefa)

| # | O que aconteceu | Gravidade | Vira tarefa? |
|---|---|---|---|
| A | ⏳ | ⏳ | ⏳ |

Regra: problema **sem** nome de cliente, sem CAR e sem CPF. Se precisar do caso real para
reproduzir, o caminho do projeto no server basta — quem investiga abre lá.

## Antes de começar

- [ ] `preflight.sh` verde (as duas chaves geo ainda faltam — ver `deploy/PEDIDOS-AO-ALVARO.md`)
- [ ] app no ar em `mapasfacil-app.cursar.space` com a tag `web-v0.1.0` (ou a que estiver)
- [ ] conta de teste `teste@mapasfacil.local` criada e um projeto sintético gerado sem erro
- [ ] `varrer-pii` rodado depois de importar o `imovel_ficticio.zip` → **zero** achados
- [ ] `sonda-saude` e `backup` rodando como timer (`systemctl --user list-timers`)
