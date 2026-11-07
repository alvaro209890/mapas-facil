# Contrato de Layout v2 — LayoutSpec e PDF-first

**Autor:** Subagente Layout / PDF-first (2026-11-06)  
**Status:** Vigente (Fase 1 / Fase 3)  
**Arquivo:** `planos/contrato-layout-v2.md`

Este documento define o contrato oficial da arquitetura **PDF-first** e do **LayoutSpec versionado**, descolando o layout visual e cartográfico da dependência de arquivos binários `.mxd` do ArcMap.

---

## 1. Princípios da Arquitetura PDF-first

1. **O PDF é a fonte da verdade cartográfica**: toda renderização cartográfica de alta fidelidade é realizada pelo motor nativo (`motores/nativo.py`), orientada por perfis medidos milimétricos dos mapas de referência (acervo IMAP Harmonia).
2. **LayoutSpec declarativo e versionado**: a geometria do layout (caixas do mapa, título, rosa dos ventos, minimapa, metadados, legenda, logo e tabela), assim como a tipografia e o CRS padrão, são especificados em JSON independente de software proprietário.
3. **Saídas padrão sem MXD**: as saídas default de geração são `["pdf", "png", "xlsx"]`. O arquivo `.mxd` só é gerado se explicitamente solicitado **E** autorizado pela variável de ambiente `MF_MXD=1`.
4. **Pacote de entrega limpo**: o arquivo ZIP de entrega (`montar_pacote_zip` e `montar_pacote_do_projeto`) é montado com as pastas `Mapas/` (PDF/PNG), `SHP/` (vetoriais auditados), `XLSX/` (planilhas de quantitativos) e `LEIA-ME.txt`. A pasta `MXD/` é estritamente omitida por padrão, a menos que `incluir_mxd=True` e `MF_MXD=1`.

---

## 2. Estrutura do LayoutSpec (Schema `shared/schemas/layoutspec.schema.json`)

Um `LayoutSpec` segue o schema JSON Schema Draft 2020-12:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://mapasfacil.local/schemas/layoutspec.schema.json",
  "title": "LayoutSpec",
  "contract_version": 1,
  "versao": 1,
  "id": "harmonia_dinamica_retrato",
  "nome": "Harmonia Dinâmica Retrato",
  "perfil": "harmonia",
  "orientacao": "retrato",
  "folha_padrao": {
    "formato": "A4",
    "orientacao": "retrato"
  },
  "dimensoes_mm": {
    "largura": 210.0,
    "altura": 297.0
  },
  "elementos": {
    "mapa": { "x0": 7.0, "y0": 5.0, "x1": 203.5, "y1": 257.0 },
    "titulo": { "x0": 61.98, "y0": 7.11, "x1": 134.55, "y1": 21.68 },
    "rosa": { "x0": 186.3, "y0": 4.0, "x1": 202.0, "y1": 27.0 },
    "minimapa": { "x0": 0.0, "y0": 262.0, "x1": 62.0, "y1": 297.0 },
    "metadados": { "x0": 64.9, "y0": 265.2, "x1": 120.0, "y1": 291.2 },
    "legenda": { "x0": 131.8, "y0": 266.0, "x1": 172.0, "y1": 295.0 },
    "logo": { "x0": 175.0, "y0": 265.0, "x1": 208.0, "y1": 292.0 },
    "tabela": { "x0": 67.1, "y0": 236.3, "x1": 203.0, "y1": 256.3 }
  },
  "tipografia": {
    "pt_titulo": 24.0,
    "pt_metadados": 9.0,
    "pt_legenda": 8.0,
    "pt_grade": 7.7,
    "pt_legenda_titulo": 0.0,
    "titulo_legenda": "Legenda",
    "titulo_metadados": "METADADOS IMAGEM",
    "fonte_grade": ["Cambria", "Liberation Serif", "Times New Roman", "DejaVu Serif"]
  },
  "crs_padrao": "EPSG:31982"
}
```

### Elementos obrigatórios:
- `mapa`: caixa principal do quadro de coordenadas (área geográfica).
- `titulo`: caixa delimitadora da moldura de título.
- `rosa`: caixa da rosa dos ventos.
- `minimapa`: caixa do mapa de localização/situação regional.
- `metadados`: caixa do bloco de texto com metadados do sensor/satélite/data/fonte/datum/escala.
- `legenda`: caixa do bloco de convenções cartográficas.
- `logo`: caixa da marca institucional.
- `tabela`: caixa reservada para sobreposição de tabela de quantitativos (se presente no mapa).

Todas as coordenadas em `x0, y0, x1, y1` são números em milímetros (`mm`), com origem `(0, 0)` no canto superior-esquerdo da página (`y` crescendo para baixo).

---

## 3. API do Pacote `mapasfacil_nucleo.layout`

O novo pacote `mapasfacil_nucleo.layout` disponibiliza a interface canônica para consumo por outros agentes (orquestrador, ferramentas de IA e servidor):

```python
from mapasfacil_nucleo.layout import (
    LayoutSpec,
    carregar,
    de_perfil,
    validar,
    medir,
    perfil_do_layout,
    obter_layout,
    listar_layouts,
)
```

### Funções:

1. **`carregar(origem: dict | str | Path) -> LayoutSpec`**
   - Carrega um `LayoutSpec` a partir de um dicionário, caminho de arquivo JSON ou ID de layout registrado em `shared/layouts/`.
   - Normaliza tipos e caixas (`Caixa(x0, y0, x1, y1)`).

2. **`de_perfil(perfil: PerfilPagina, id: str = ..., nome: str = ...) -> LayoutSpec`**
   - Converte uma instância existente de `PerfilPagina` (como `RETRATO`, `PAISAGEM` ou perfis medidos de `anatomia_serie.json`) para a estrutura declarativa `LayoutSpec`.

3. **`validar(dados: dict | LayoutSpec) -> dict[str, Any]`**
   - Valida a conformidade da estrutura contra `shared/schemas/layoutspec.schema.json`.
   - Retorna `{"valido": bool, "erros": list[str]}`.

4. **`medir(caminho_pdf: Path | str, id: str = "medido", nome: str = "Layout Medido", pagina: int = 0) -> LayoutSpec`**
   - Analisa diretamente um arquivo PDF de referência utilizando extração vetorial e de texto (`PyMuPDF`), detectando as caixas reais do quadro, título desenhado, metadados, legenda e rótulos DMS.
   - Gera um `LayoutSpec` medido diretamente da referência física.

5. **`perfil_do_layout(layout: dict | LayoutSpec, folha: dict | None = None) -> PerfilPagina`**
   - Converte um `LayoutSpec` em uma instância de `PerfilPagina`, aplicando fator de escala ISO proporcional (A4 a A0) se uma folha maior for informada.
   - É a ponte direta consumida por `motores/nativo.py`.

6. **`obter_layout(id_ou_template: str, folha: dict | None = None) -> LayoutSpec`**
   - Resolve o layout apropriado para um template (ex: `serie_dinamica_2026`, `tipologia_paisagem`) ou ID de layout pré-definido, com fallback transparente para os perfis medidos.

7. **`listar_layouts() -> list[dict[str, Any]]`**
   - Lista todos os layouts declarativos disponíveis na pasta `shared/layouts/` e perfis medidos conhecidos.

---

## 4. Contrato de Integração com MapSpec

O MapSpec consome o LayoutSpec de duas formas:
1. **Implícita (padrão)**: via campo `template` (ex: `"template": "serie_dinamica_2026"` ou `"template": "dinamica_retrato"`). O motor nativo busca automaticamente o `LayoutSpec` correspondente através de `layout.obter_layout(mapspec["template"])`.
2. **Explícita (campo `layout_spec`)**: quando um agente ou usuário customiza caixas milimétricas, o objeto `layout_spec` pode ser embutido diretamente na raiz do `MapSpec`:
   ```json
   {
     "titulo": "Dinâmica 2026",
     "template": "dinamica_retrato",
     "layout_spec": {
       "id": "custom_imovel_43",
       "elementos": { ... }
     }
   }
   ```
   *Nota para outros agentes:* A inclusão do campo `layout_spec` no schema do MapSpec é responsabilidade da trilha multi-imóvel/pai; o motor nativo já aceita e consome o dicionário se fornecido.

---

## 5. Contrato do Pacote de Entrega (`OpcoesPacote`)

A classe `OpcoesPacote` em `mxd_binario/pacote.py` (núcleo) e `servidor/mapasfacil_servidor/pacote.py` (servidor) segue o contrato estrito:

```python
@dataclass
class OpcoesPacote:
    nome_imovel: str = "Imovel"
    nome_template: str = "Mapa"
    versao: int = 1
    mxd_doc: DocumentoMxd | None = None
    mxd_conforme: bool = True
    incluir_mxd: bool = False             # Padrão PDF-first: NÃO inclui MXD
    codigo_aviso_mxd: str | None = None
    datum: str = "SIRGAS 2000 / UTM zone 22S"
    data_imagem: str = "2026-10"
    checks_reprovados: list[str] | None = None
```

### Regra de Inclusão do MXD:
O arquivo `.mxd` só é gravado dentro do ZIP se a seguinte condição for satisfeita:
```python
def _mxd_habilitado(opcoes: OpcoesPacote) -> bool:
    return opcoes.incluir_mxd and opcoes.mxd_conforme and os.environ.get("MF_MXD") == "1"
```

Se `_mxd_habilitado` for falso:
- A pasta `MXD/` não existe no arquivo `.zip`.
- O arquivo `LEIA-ME.txt` esclarece que o pacote segue o padrão PDF-first (mapas finais de alta resolução em PDF/PNG e shapefiles em `SHP/`), e que o `.mxd` pode ser gerado sob demanda.
- Os arquivos `.xlsx` são organizados na pasta `XLSX/` (ou `Mapas/`), sem nenhum arquivo `.mxd` solto.
