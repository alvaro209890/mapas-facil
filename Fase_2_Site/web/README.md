# web/

Site do Mapas Fácil — Next.js (App Router), TypeScript, Tailwind.

**Status:** esqueleto. Só depois da Fase 1 validada. Planos em
[`../planos/README.md`](../planos/README.md).

> Os planos `04-frontend-site.md` ainda estão em formato **legado** (assumiam Vercel + chat
> acoplado a agente WS). Destino: site em `mapasfacil.cursar.space` consumindo a API neste PC.

## Quando existir código

```
web/
  app/
    (marketing)/
    (app)/
      chat/[id]/
      projetos/
      configuracoes/
  components/
  lib/
  package.json
```

Deploy previsto: host apontando para `mapasfacil.cursar.space` (não Render/Vercel como
caminho primário da API — ver D7).
