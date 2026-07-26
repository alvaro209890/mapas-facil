# Mapas/05 — Mapa de AEP (área que será desmatada)

Um único `.mxd`, sem PDF exportado: `MXD/MAPA_AEP.mxd`.

É o **mapa de AEP** — a área que será desmatada sob autorização. Não existe equivalente em
nenhum outro acervo do repositório, e é um tipo de entrega que a série IMAP da Harmonia não
cobre.

## O que o `.mxd` contém

Camadas e elementos identificados por leitura direta dos streams do arquivo:

| Elemento | Valor no arquivo |
|---|---|
| Camada de destaque | `Área que será desmatada (AEP)` |
| Camada de contexto | `Área total da propriedade` (fonte `Area_Total`) |
| Camadas auxiliares | `area_1`, `area_cons` (área consolidada), `matricula` |
| Limite municipal | `Limite municipal` sobre `lml_municipio_a` |
| Tabela de áreas | `PICTURE_ELEMENT` apontando para `quadro_areas.png` |

## Por que importa para o produto

1. **Confirma o padrão da tabela como imagem.** Assim como a Harmonia injeta
   `tabela_quantitativos.png` num `PICTURE_ELEMENT`, aqui o analista gerou `quadro_areas.png`
   por fora e colou no layout. É a mesma mecânica que
   [`../../../Fase_1_Desktop/planos/08-planilhas-e-relatorios.md`](../../../Fase_1_Desktop/planos/08-planilhas-e-relatorios.md)
   automatiza — a evidência de que não é um capricho de um único analista.
2. **Vocabulário novo de camada.** `AEP` não está no catálogo
   ([`../../../shared/catalog/camadas.json`](../../../shared/catalog/camadas.json)) nem entre os
   papéis reconhecidos pelo indexador (`ATP`, `AVN`, `AC`, `AUAS`, `APP`, `ARL`). Adicionar um
   modelo de galeria de AEP exige antes decidir o papel — ver
   [`../../../Fase_1_Desktop/planos/15-galeria-de-modelos.md`](../../../Fase_1_Desktop/planos/15-galeria-de-modelos.md).
3. **Mostra o retrabalho de origem.** As fontes apontam para `C:\Users\User\Downloads\` — o
   shapefile e o PNG da tabela ficavam na pasta de downloads do analista. É o cenário que o
   `fsguard` e o `caminhos_relativos: true` existem para eliminar.

## Limites

- **Sem PDF de referência.** Não serve como baseline de diff raster; só como referência de
  estrutura de `.mxd`.
- Formato de página não confirmado (exigiria abrir no ArcMap).
- Chaves de API zeradas por placeholder — `ferramentas/chaves_mxd.py restaurar` para abrir com
  basemap.
