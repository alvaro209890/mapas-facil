# Referências IMAP

Gabaritos visuais e cartográficos do padrão IMAP (consultoria ambiental, Mato Grosso).

Calibrados contra mapas reais feitos no ArcMap. Qualquer ajuste de layout no Mapas Fácil
deve ser conferido contra estes arquivos.

## Conteúdo

| Pasta | O que é |
|---|---|
| [`Mapas/`](Mapas/) | PDFs-modelo da série (Dinâmica, Tipologia, Embargos, Alertas, etc.) |
| [`MXD/`](MXD/) | Templates `.mxd` reais abertos no ArcMap |

## Uso no projeto

- Spec do padrão: [`../planos/06-padrao-imap.md`](../planos/06-padrao-imap.md)
- Motor que deve reproduzi-los: [`../planos/05-motor-mxd-pdf.md`](../planos/05-motor-mxd-pdf.md)
- Templates operacionais do agente (quando existirem) vão em `shared/templates/`, derivados destes.

## Nota

Estes arquivos são binários grandes (~134 MB no total). Fazem parte do repositório de propósito:
são a fonte da verdade visual. Não apague nem "otimize" sem regenerar a baseline de regressão.
