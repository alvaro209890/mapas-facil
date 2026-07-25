# Referências IMAP

Gabaritos visuais e cartográficos do padrão IMAP (consultoria ambiental, Mato Grosso).

Qualquer ajuste de layout no Mapas Fácil deve ser conferido contra estes arquivos.

## Conteúdo

| Pasta | O que é | Papel |
|---|---|---|
| [`Mapas/01/`](Mapas/01/) | PDFs da **Fazenda Harmonia** (Vila Rica/MT, 2026-07) | **fonte da verdade visual** |
| [`Mapas/02/`](Mapas/02/) | PDFs da **Fazenda Trevisol** (Querência/MT) | contraste — perfil **descartado** |
| [`MXD/`](MXD/) | Templates `.mxd` reais + documentação da adaptação Harmonia | gabarito para o motor |

## Documentação operacional

| Arquivo | Conteúdo |
|---|---|
| [`MXD/DOCUMENTACAO_MXD_HARMONIA.md`](MXD/DOCUMENTACAO_MXD_HARMONIA.md) | receita completa da adaptação manual: arcpy hang, homônimos, scripts, CRS, minimapa |
| [`../planos/01-padrao-imap-harmonia.md`](../planos/01-padrao-imap-harmonia.md) | geometria medida, cores, checks HARD/SOFT |
| [`../Fase_1_Desktop/planos/04-motor-mxd.md`](../Fase_1_Desktop/planos/04-motor-mxd.md) | como o produto reproduz estes mapas |

## Uso no projeto

- Spec do padrão: só o perfil **Harmonia** (`Mapas/01` + `MXD/`).
- `Mapas/02` existe para que ninguém “corrija” o padrão de volta ao Trevisol por engano.
- Templates operacionais (quando existirem) vão em `shared/templates/`, derivados dos `.mxd` deste acervo.
- Chaves de API nos `.mxd` versionados: placeholders — ver [`../ferramentas/`](../ferramentas/README.md).

## Nota

Arquivos binários grandes. Fazem parte do repositório de propósito. Não apague nem "otimize"
sem regenerar a baseline de regressão.

Antes de commit: `python3 ferramentas/chaves_mxd.py verificar` deve reportar **Seguro para commit**.
