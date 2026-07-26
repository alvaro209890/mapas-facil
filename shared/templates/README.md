# shared/templates/

Templates `.mxd` operacionais (após preparação única descrita em F1-04).

| Arquivo | Status |
|---|---|
| [`MANIFEST.json`](MANIFEST.json) | `dinamica_retrato` → `Dinamica_retrato.mxd` (**parcial**, sha256 ok, **offsets vazios**); demais `a_preparar` |
| `Dinamica_retrato.mxd` | Gerado por `ferramentas/normalizar_mxd_arcpy.py` a partir do acervo. Faltam 0-4 elementos de layout (ver abaixo) — rodada 2026-07-25 mostrou que a maioria é reaproveitamento de elemento existente, não criação; falta rodar de novo no ArcMap pra confirmar quantos sobrevivem. |

`dinamica_retrato` — o que a automação (`normalizar_mxd_arcpy.py`) já resolveu sem GUI:

- `relativePaths = True`
- Data frames `Layers`/`Layers` → `MAPA` (UTM 31982) / `MINIMAPA` (Web Mercator)
- Camadas `Fazenda Harmonia`→`PERIMETRO`, `Uso Consolidado`→`AC`, `Limite municipal`→`MUNICIPIOS`,
  `Limite estadual`→`UF`
- Texto de metadados da imagem → `METADADOS`
- `North Arrow` → `NORTE`; imagem única → `LOGO`; legenda maior → `LEGENDA`

O que **pode ainda precisar da GUI do ArcMap** — atualizado 2026-07-25, ver
[`../../Fase_1_Desktop/nucleo/docs/bloco-b-sem-arcmap.md`](../../Fase_1_Desktop/nucleo/docs/bloco-b-sem-arcmap.md#rodada-2026-07-25-2-os-4-pendentes-viraram-reaproveitamento-não-criação):

1. ~~Criar texto `TITULO`/`ROTULO_IMOVEL`~~ — não precisa criar; o acervo já tem uma caixa
   balão ("Ano: 2026") e um rótulo solto ("Vila Rica") reaproveitáveis por script
   (renomear + reposicionar + trocar texto, sem GUI). **A testar no Windows.**
2. Confirmar visualmente que a `LEGENDA` escolhida por heurística de tamanho é mesmo a do
   `MAPA` (há uma segunda, menor, possivelmente do `MINIMAPA`) — continua manual.
3. ~~Identificar entre os 5 `GRAPHIC_ELEMENT` quais são `MINIMAPA_RETANGULO`/
   `MINIMAPA_GUIA`~~ — agora tentado por heurística (geometria fina = guia; dentro do data
   frame `MINIMAPA` = retângulo), só vira pendência se ambíguo. **A testar no Windows.**
4. ~~Apontar a imagem de `LOGO`~~ — agora existe o arquivo (`Referencias_IMAP/Logos IMAP/`);
   `normalizar_mxd_arcpy.py --logo` tenta gravar via script. Único item genuinamente incerto:
   `PictureElement.sourceImage` é somente-leitura em algumas versões do arcpy.mapping — se
   for o caso aqui, sobra 1 clique manual (~30s), não uma criação de elemento.

Depois desses ajustes, rodar de novo `preparar_sentinelas_arcpy.py` +
`registrar_template.py dinamica_retrato` (os offsets calibrados antes desses ajustes ficam
inválidos, pois a estrutura binária do `.mxd` muda ao inserir/mover elementos).

Fonte bruta: [`../../Referencias_IMAP/MXD/`](../../Referencias_IMAP/MXD/).
Baseline PDF: [`../../Referencias_IMAP/Mapas/01/`](../../Referencias_IMAP/Mapas/01/).
