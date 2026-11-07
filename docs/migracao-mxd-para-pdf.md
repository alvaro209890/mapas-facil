# Guia de Migração: Do Fluxo Baseado em MXD para PDF-first

**Data:** 06 de novembro de 2026  
**Status:** Vigente  
**Público:** Desenvolvedores, agentes de código e operadores do Mapas Fácil

---

## 1. Por que Migrar para PDF-first?

Nas primeiras fases do projeto, o fluxo de geração girava em torno do arquivo `.mxd` do ArcGIS Desktop. No servidor Linux ou em ambientes sem ArcMap instalado, esse fluxo exigia operações binárias complexas em arquivos OLE2/CFBF (`CompoundFile`) e patches em streams binárias, tornando o pipeline propenso a erros de compatibilidade e lentidão.

Com a consolidação do **renderizador nativo Python** (baseado em Matplotlib, PyMuPDF, Shapely, PyProj e Pillow) e da especificação declarativa **`LayoutSpec`**, o sistema agora gera mapas cartográficos com precisão milimétrica de forma autônoma:
- **10x mais rápido**: geração de PDF e PNG em 2 a 5 segundos, sem spawn de processos pesados;
- **100% Linux nativo**: roda no `server-desktop` sem nenhuma dependência de ArcMap ou Wine;
- **Auditoria rigorosa**: todas as caixas de layout, rótulos DMS e elementos são verificados matematicamente em milímetros de papel;
- **Layout sob medida**: IA e usuários podem alterar posições ou estilos sem tocar em estruturas binárias de software legado.

---

## 2. Como Funciona a Migração de um Template Existente

Para migrar um mapa que antes dependia exclusivamente de um arquivo `.mxd` para o padrão PDF-first:

### Passo 1: Obter o PDF de Referência
Tenha em mãos o PDF oficial de referência gerado no padrão desejado (como os do acervo `Referencias_IMAP/Mapas/01/`).

### Passo 2: Medir o Layout Automaticamente
Utilize o módulo `medir` do pacote `layout`:

```python
from pathlib import Path
from mapasfacil_nucleo.layout import medir

pdf_ref = Path("Referencias_IMAP/Mapas/01/Dinamica_2026_quantitativos.pdf")
spec = medir(pdf_ref, id="harmonia_dinamica_2026", nome="Dinâmica 2026 Medida")
```

A função analisa o PDF vetorialmente, localiza o quadro principal, detecta o retângulo desenhado do título (abaixo dos rótulos de grade), a coluna de metadados, o bloco da legenda e a distribuição de rótulos DMS.

### Passo 3: Salvar e Registrar o LayoutSpec
Salve o dicionário JSON retornado em `shared/layouts/<id>.json`:

```python
import json
with open(f"shared/layouts/{spec.id}.json", "w", encoding="utf-8") as f:
    json.dump(spec.para_dict(), f, indent=2, ensure_ascii=False)
```

Valide com `mapasfacil_nucleo.layout.validar(spec)` para assegurar conformidade total com `shared/schemas/layoutspec.schema.json`.

### Passo 4: Apontar o Template no MANIFEST.json
No arquivo `shared/templates/MANIFEST.json`, adicione o campo de metadados `"layout_ref"` no template correspondente:

```json
{
  "id": "dinamica_retrato",
  "nome": "Dinâmica de uso do solo — A4 retrato",
  "layout_ref": "harmonia_dinamica_retrato",
  ...
}
```

A partir desse momento, qualquer chamada a `gerar_mapa` ou `gerar_pdf_minimo` que use esse template consumirá diretamente o LayoutSpec medido.

---

## 3. Compatibilidade Reversa e Exportação Opcional de MXD

A transição para PDF-first **não removeu nem quebrou** o suporte ao ArcMap:
- Os 26 templates `.mxd` e os motores binários (`cfbf.py`, `blocos.py`, `slots.py`, `patch_mxd.py`) continuam operacionais;
- Quando o usuário ou cliente explicitamente necessitar do arquivo `.mxd` para abrir no ArcGIS Desktop:
  1. A requisição deve conter `"mxd"` na lista de `saidas` (ex: `saidas: ["pdf", "mxd"]`);
  2. A variável de ambiente `MF_MXD=1` deve estar configurada;
  3. No pacote de entrega, passe `OpcoesPacote(..., incluir_mxd=True)`. Na API web, o download do ZIP exige o parâmetro explícito `?mxd=1`.

Se `MF_MXD` não estiver ativo, o motor atua em modo seguro PDF-first, gerando os PDFs, PNGs e shapefiles sem interrupção e registrando no `LEIA-ME.txt` que a versão segue a entrega padronizada PDF-first.
