# Arquitetura de Layout PDF-first e LayoutSpec no Mapas Fácil

**Data:** 06 de novembro de 2026  
**Status:** Implementado (Fase 1 / Fase 3)  
**Módulos:** `mapasfacil_nucleo.layout`, `motores.nativo`, `mxd_binario.pacote`

---

## 1. Visão Geral e Motivação

Até a Fase 2, o Mapas Fácil dependia primordialmente de templates `.mxd` do ArcMap para definir o posicionamento visual de caixas de mapa, legendas, títulos e metadados. Essa abordagem impunha restrições severas:
- Dependência de ambiente Windows e do runtime ArcGIS Desktop 10.8 para geração do layout visual original;
- Fragilidade no servidor Linux de produção (onde ArcMap não roda), exigindo motores binários de injeção direta de blocos OLE2 (`cfbf.py`/`blocos.py`);
- Dificuldade em estender ou customizar dinamicamente o layout via chat ou IA sem corromper estruturas binárias proprietárias.

A **Arquitetura PDF-first com LayoutSpec** estabelece o renderizador nativo (`motores/nativo.py`) como a **fonte primária da verdade visual e cartográfica**. O layout agora é uma estrutura **declarativa, versionada e milimétrica** (JSON), independente do ArcMap.

---

## 2. Estrutura do LayoutSpec

O schema formal é versionado em `shared/schemas/layoutspec.schema.json` (Draft 2020-12).

### Componentes Principais:
1. **Identificação e Proveniência**:
   - `id`: identificador estável (ex: `harmonia_dinamica_retrato`, `serie_dinamica_2026`);
   - `nome`: rótulo legível para humanos e UI;
   - `perfil`: padrão visual de cores e estilo (`harmonia`);
   - `orientacao`: `"retrato"` ou `"paisagem"`.
2. **Dimensões e Folha**:
   - `dimensoes_mm`: largura e altura físicas do papel em milímetros (ex: 210 × 297 mm para A4);
   - `folha_padrao`: formato ISO (`A4` a `A0`) e orientação.
3. **Elemento Caixas (`elementos`)**:
   Todas as coordenadas `[x0, y0, x1, y1]` em mm, com origem no topo-esquerdo da página:
   - `mapa`: área geográfica útil de dados e grade;
   - `titulo`: caixa delimitadora da moldura branca de título;
   - `rosa`: rosa dos ventos (indicador de norte);
   - `minimapa`: inset de localização municipal/estadual;
   - `metadados`: bloco de dados técnicos (satélite, sensor, data, fonte, datum, escala);
   - `legenda`: convenções cartográficas das camadas ativas;
   - `logo`: marca institucional IMAP;
   - `tabela`: espaço reservado para tabela de quantitativos (quando aplicável).
4. **Tipografia e Estilo**:
   - `pt_titulo`, `pt_metadados`, `pt_legenda`, `pt_grade`, `pt_legenda_titulo`;
   - `titulo_legenda`, `titulo_metadados`;
   - `fonte_grade`: fontes serifadas ou sans priorizadas.
5. **CRS Padrão**:
   - EPSG projetado do data frame (ex: `EPSG:31982` para UTM 22S na série Dinâmica, `EPSG:3857` para temáticos).

---

## 3. Pacote `mapasfacil_nucleo.layout`

O novo pacote isola todas as operações de layout:

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

### Funções da API:
- **`carregar(origem)`**: carrega de dicionário, arquivo `.json` ou busca direta em `shared/layouts/<id>.json`.
- **`de_perfil(perfil, id, nome)`**: converte uma instância em memória de `PerfilPagina` para `LayoutSpec`.
- **`validar(layout)`**: valida estritamente a conformidade contra `shared/schemas/layoutspec.schema.json`.
- **`medir(pdf_path)`**: extrai em tempo de execução as caixas de um PDF de referência real através de PyMuPDF, gerando um `LayoutSpec` fiel com `pdf_origem` em basename relativo (sem caminhos absolutos).
- **`perfil_do_layout(layout, folha)`**: converte o `LayoutSpec` em `PerfilPagina`, aplicando fator de escala ISO proporcional para folhas A3, A2, A1 ou A0.
- **`obter_layout(id_ou_template, folha)`**: resolvedor central que busca em presets `shared/layouts/`, nos perfis medidos de `anatomia_serie.json`, ou nos templates do `MANIFEST.json` (`layout_ref`). Falhas disparam erro `NU-234` fail-closed. Escala para folhas maiores (A3..A0) é idempotente.
- **`listar_layouts()`**: enumera os presets disponíveis em disco.

---

## 4. Consumo no Motor Nativo (`motores/nativo.py`)

No fluxo de geração de PDF (`gerar_pdf_minimo`):
1. `_perfil_do_mapspec(mapspec)` inspeciona se há um `layout_spec` explícito no `mapspec`;
2. Se presente, carrega diretamente via `layout.carregar(mapspec["layout_spec"])`;
3. Se omitido, resolve automaticamente pelo template (`layout.obter_layout(mapspec["template"])`);
4. O `PerfilPagina` gerado orienta toda a montagem da figura Matplotlib/Cairo;
5. O dicionário de retorno de artefatos inclui `"layout_spec"`, garantindo rastreabilidade do layout exato utilizado.

---

## 5. Política de Pacote de Entrega e MXD Opcional

A geração e empacotamento seguem a diretriz PDF-first:
- **Saídas padrão:** `["pdf", "png", "xlsx"]`.
- **Inclusão de MXD:** O arquivo `.mxd` só entra no pacote ZIP se **ambas** as condições forem atendidas:
  1. Solicitado explicitamente com `incluir_mxd=True` (ou `"mxd" in saidas`);
  2. Autorizado pelo ambiente via `MF_MXD=1`.
- **Estrutura do ZIP (`mxd_binario/pacote.py`):**
  - `Mapas/`: arquivos `.pdf`, `.png` e `validacao.json`;
  - `SHP/`: shapefiles auditados;
  - `XLSX/`: planilhas de quantitativos;
  - `LEIA-ME.txt`: orientações claras de uso;
  - `MXD/`: incluída **apenas** quando explicitamente solicitada e habilitada.
