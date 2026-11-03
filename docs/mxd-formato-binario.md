# Especificação do Formato Binário do ArcGIS Map Document (.mxd)

*(autor: Hermes-windows | 2026-10-14)*

## 1. Visão Geral

O arquivo `.mxd` do ArcGIS Desktop (versões 8.x até 10.8.2) não é um formato de arquivo monolítico proprietário simples, mas sim um **Compound File Binary Format (CFBF)** — a especificação [MS-CFB] da Microsoft para documentos estruturados OLE2 (idêntica à estrutura de arquivos legados `.doc`, `.xls` e `.ppt` do Office 97-2003).

Internamente, ele funciona como um "sistema de arquivos virtual" composto por setores de 512 bytes, contendo diretórios e fluxos de dados nomeados (*streams*). Dentro dessas streams, o motor ArcObjects serializa seu grafo de objetos COM via `IPersistStream` e `IPersistVariantStream`.

---

## 2. Estrutura Física: Compound File (MS-CFB v3)

### Cabeçalho (Offset 0 a 512)
- **Offset 0x00 (8 bytes):** Assinatura mágica `D0 CF 11 E0 A1 B1 1A E1`.
- **Offset 0x08 (16 bytes):** Header CLSID (geralmente zerado).
- **Offset 0x18 (2 bytes):** Minor Version (`0x003E`).
- **Offset 0x1A (2 bytes):** Major Version (`0x0003` para setores de 512 bytes).
- **Offset 0x1C (2 bytes):** Byte Order (`0xFFFE` = Little Endian).
- **Offset 0x1E (2 bytes):** Sector Shift (`0x0009` -> $2^9 = 512$ bytes).
- **Offset 0x20 (2 bytes):** Mini Sector Shift (`0x0006` -> $2^6 = 64$ bytes).
- **Offset 0x22 (6 bytes):** Reservado (zeros).
- **Offset 0x28 (4 bytes):** Número de setores de diretório (sempre 0 no v3).
- **Offset 0x2C (4 bytes):** Número total de setores FAT.
- **Offset 0x30 (4 bytes):** Primeiro setor da Directory Stream.
- **Offset 0x34 (4 bytes):** Transaction Signature Number (0).
- **Offset 0x38 (4 bytes):** Mini Stream Cutoff Size (`0x00001000` = 4.096 bytes).
- **Offset 0x3C (4 bytes):** Primeiro setor da MiniFAT.
- **Offset 0x40 (4 bytes):** Número de setores da MiniFAT.
- **Offset 0x44 (4 bytes):** Primeiro setor da DIFAT (Double Indirect FAT) se $> 109$ setores FAT.
- **Offset 0x48 (4 bytes):** Número de setores da DIFAT.
- **Offset 0x4C (436 bytes):** Array de 109 entradas DIFAT iniciais apontando para setores FAT.

### Árvore de Diretórios (Directory Entries)
Cada entrada no diretório ocupa exatamente **128 bytes**:
- **0x00 (64 bytes):** Nome da entrada codificado em UTF-16LE, terminado em nulo.
- **0x40 (2 bytes):** Tamanho do nome em bytes (incluindo o terminador nulo).
- **0x42 (1 byte):** Tipo de entrada (`0x01` = Storage, `0x02` = Stream, `0x05` = Root Entry).
- **0x43 (1 byte):** Cor do nó na árvore rubro-negra (`0x00` = Red, `0x01` = Black).
- **0x44 (4 bytes):** ID do nó filho à esquerda (SID).
- **0x48 (4 bytes):** ID do nó filho à direita (SID).
- **0x4C (4 bytes):** ID do nó raiz da sub-árvore (Child SID).
- **0x50 (16 bytes):** CLSID do storage.
- **0x60 (4 bytes):** User Flags / State.
- **0x64 (8 bytes):** Creation Time (Windows FILETIME).
- **0x6C (8 bytes):** Modification Time (Windows FILETIME).
- **0x74 (4 bytes):** Setor inicial (`isectStart`).
- **0x78 (8 bytes):** Tamanho da stream em bytes (`ulSize`).

Streams com tamanho $< 4.096$ bytes residem na **Mini Stream** (cujo container físico é o Root Entry) e são alocadas em blocos de 64 bytes indexados pela **MiniFAT**. Streams $\ge 4.096$ bytes são alocadas em setores de 512 bytes indexados pela **FAT regular**.

---

## 3. Principais Streams do MXD

| Stream | Propósito | Formato / Classes |
|---|---|---|
| **`PageLayout`** | Contém todo o layout cartográfico: folhas, margens, molduras de mapa, réguas, legendas, nortes, barras de escala e elementos de texto. | Objeto raiz `esriCarto.PageLayout` (`{DD94D76E-836D-11D0-87EC-080009EC732A}`). |
| **`Maps`** | Contém a coleção de DataFrames (`esriCarto.Map`), camadas geográficas (`FeatureLayer`, `RasterLayer`, `WMSMapLayer`), conexões a workspaces, simbologias e extensões geográficas (`Envelope`). | Serialização em cascata de `esriCarto.Map`. |
| **`\x05SummaryInformation`** | Metadados padrão OLE (Título, Assunto, Autor, Palavras-chave, etc.). | OLE PropertySet padrão. |
| **`\x05DocumentSummaryInformation`** | Metadados estendidos OLE (Empresa, Categoria, etc.). | OLE PropertySet padrão. |
| **`CustomProperties`** | Pares chave/valor customizados associados ao documento. | `IPropertySet`. |

---

## 4. Mecanismo de Serialização ArcObjects

Dentro das streams `PageLayout` e `Maps`, os dados são gerados pelas rotinas de persistência dos objetos ArcObjects:

1. **Assinatura de Objeto:**
   Todo objeto COM serializado inicia com:
   - **16 bytes:** CLSID da classe COM (ex.: `{C84598B1-C4BE-4203-9132-ADA2BE57F30C}` para `esriCarto.ParagraphTextElement`).
   - **4 bytes:** Identificador sequencial de instância (`ObjectID`).
   - **2 bytes:** Versão interna da persistência daquele objeto.

2. **Blocos Envolventes (Payload Bounding Blocks):**
   Agrupamentos de alto nível e elementos gráficos possuem um delimitador de tamanho antes do payload:
   - `0xFF 0xFF 0xFF 0xFF` (4 bytes marcadores).
   - `uint64` (8 bytes little-endian) com o tamanho exato em bytes do bloco subsequente.
   *Atenção:* Se o conteúdo interno crescer ou encolher, esse valor deve ser ajustado para que o parser do ArcObjects não pule para a posição errada da stream.

3. **Codificação de Textos:**
   - Textos são gravados em **UTF-16LE** (2 bytes por caractere).
   - O terminador nulo `\x00\x00` é obrigatório.
   - O prefixo de tamanho é um `uint32` (4 bytes little-endian) representando o comprimento total em bytes:
     $$\text{Tamanho em Bytes} = (\text{nº de caracteres} + 1) \times 2$$

---

## 5. Anatomia dos Alvos de Edição

### A. Elementos de Texto no Layout (`PageLayout`)
Em mapas do ArcGIS, textos formatados (títulos, notas, caixas de metadados) são instâncias de `esriCarto.ParagraphTextElement` ou `esriCarto.TextElement`:
- **Texto Formatado (com tags XML):** Fica dentro de uma `IPropertyBag` sob a propriedade `"Text"`. É precedido por `uint32` de comprimento e contém marcações como `<BOL><FNT name="Cambria" size="20">Texto</FNT></BOL>\0`.
- **Texto Puro (Raw):** Fica armazenado no campo direto do elemento logo após os atributos de fonte, também precedido por `uint32` de comprimento.
- **Regra de Expansão:** Ao alterar um texto com $\Delta$ bytes de diferença:
  1. Atualizar o texto puro e seu `uint32`.
  2. Atualizar o texto formatado e seu `uint32`.
  3. Incrementar o `uint64` do bloco envolvente em $2 \times \Delta$ bytes.
  4. Salvar via `CompoundFilePacker`, que recalcula o tamanho da stream `PageLayout`.

### B. Conexões WMS (`Maps`)
- **Classe:** `esriCarto.WMSMapLayer` (`{E38A56C0-D5BD-4899-B089-C8ED4E38B77F}`).
- **Propriedades:** `IPropertySet` contendo a chave `"URL"` (string UTF-16LE com `uint32` de tamanho) e a chave `"LAYERNAME"`.
- **Regra de Alteração:** Atualizar a string da URL, o prefixo `uint32` e o bloco envolvente de `WMSMapLayer`.

### C. Nomes de Camadas no TOC (`Maps`)
- **Classe:** `esriCarto.FeatureLayer` (`{E663A651-8AAD-11D0-BEC7-00805F7C4268}`) ou `esriCarto.RasterLayer`.
- **Estrutura:** Logo após o CLSID (16B) e ObjectID (4B), há o marcador `0x0022`, seguido do `uint32` do comprimento da string em bytes e a string em UTF-16LE.

### D. Extensão e Escala de DataFrames (`Maps`)
- **Extensão:** Representada pela interface `IEnvelope` (`esriGeometry.Envelope`).
  Armazena 4 números de ponto flutuante de dupla precisão IEEE-754 (64 bits, little-endian):
  - `XMin` (8 bytes)
  - `YMin` (8 bytes)
  - `XMax` (8 bytes)
  - `YMax` (8 bytes)
- **Escala:** Representada por 1 double IEEE-754 (8 bytes little-endian).
- **Vantagem:** Ocupa tamanho fixo ($32$ bytes para o envelope, $8$ bytes para a escala). A substituição pode ser feita in-place sem alterar o tamanho da stream `Maps`.

### E. Caminhos de Camadas Vetoriais e Raster (`Maps`)
- **Classe:** `IWorkspaceName` (`Shapefile Data`, `Raster File`).
- **Estrutura:** Armazena o caminho relativo/absoluto do diretório de workspace (ex.: `..\CAR_Digital_Aprovado`) e o nome do dataset (ex.: `APPD.shp`), ambos com prefixo `uint32` e UTF-16LE.
