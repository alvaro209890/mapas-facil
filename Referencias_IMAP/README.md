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

- Spec do padrão: [`../planos/01-padrao-imap-harmonia.md`](../planos/01-padrao-imap-harmonia.md)
- Motor que deve reproduzi-los: [`../Fase_1_Desktop/planos/04-motor-mxd.md`](../Fase_1_Desktop/planos/04-motor-mxd.md)
- Templates operacionais (quando existirem) vão em `shared/templates/`, derivados destes.
- Chaves de API nos `.mxd` versionados: placeholders — ver [`../ferramentas/`](../ferramentas/README.md).

## Nota

Estes arquivos são binários grandes. Fazem parte do repositório de propósito: são a fonte da
verdade visual. Não apague nem "otimize" sem regenerar a baseline de regressão.

Antes de commit: `python3 ferramentas/chaves_mxd.py verificar` deve reportar **Seguro para commit**.
