# Diagnóstico e Solução: Crash do Map.dll com WMS no ArcMap (0xc0000005)

*(autor: Hermes-windows | 2026-10-14)*

## 1. Resumo Executivo

O crash clássico de violação de acesso (`0xc0000005` / SIGSEGV) em `Map.dll` durante a abertura headless de `.mxd` via `arcpy.mapping.MapDocument` **está resolvido na origem sem alterar nenhuma linha da configuração do GeoServer**.

A causa é o tamanho astronômico do `GetCapabilities` do endpoint global do workspace CBERS (~2,86 MB com >2.400 nós de camadas). O parser XML 32-bit do ArcObjects (`Map.dll`) sofre overflow de buffer/heap ao processar essa árvore em modo headless.

A solução definitiva é o uso dos **serviços virtuais nativos do GeoServer**:
`https://wms.cursar.space/geoserver/cbers/<NOME_DA_CAMADA>/wms?`

O catálogo encolhe de **2.863.502 bytes** para **224.230 bytes** (redução de 92,2%), contendo exclusivamente os 2 nós da cena requerida. O `arcpy.mapping.ExportToPDF` executa com sucesso total, sem proxy intermediário e com imagem raster gerada com perfeição.

---

## 2. Sintomatologia e Histórico

| Ambiente | Comportamento |
|---|---|
| **ArcMap GUI (interativo)** | Abre normal. O ArcMap em modo janela instancia o loop de mensagens Win32, consome memória sob demanda e tolera parsing demorado. |
| **arcpy headless (Py2.7 / ArcObjects)** | **Crash imediato (exit 139 / 0xc0000005) em `Map.dll`**. Ocorre logo na chamada `arcpy.mapping.MapDocument(caminho)` ou no primeiro `ListDataFrames/ExportToPDF`. |

### Contornos Históricos Anteriores
1. **Host "Morto" no binário:** Substituição de `wms.cursar.space` por `wmsXcursarXspace` (mesmo número de bytes) para desativar a camada WMS em lote antes de rodar o `arcpy`. Impedia o crash, mas o mapa saía sem a imagem do satélite.
2. **Proxy Local Filtrador:** Script Python (`_exportar_pdf_serie.py` em Marcos Fabian) subia proxy local em porta efêmera que interceptava `GetCapabilities` e removia 99% das tags `<Layer>`. Funcionava, mas exigia manter um servidor proxy ativo durante a esteira.

---

## 3. Investigação Experimental (Caixa-Preta)

### Comparativo de Endpoints

| Métrica | Endpoint Geral (`/cbers/wms?`) | Serviço Virtual (`/cbers/<layer>/wms?`) |
|---|---|---|
| **URL** | `https://wms.cursar.space/geoserver/cbers/wms?` | `https://wms.cursar.space/geoserver/cbers/landsat_224_069_2004_l5_tm_224069_20040623_c543/wms?` |
| **Tamanho GetCapabilities** | 2.863.502 bytes (~2,86 MB) | 224.230 bytes (~224 KB) |
| **Tags `<Layer>`** | > 2.400 nós | 2 nós (Raiz + Cena) |
| **GetMap HTTP 200** | Sim | Sim (imagem PNG válida de 110 KB) |
| **Headless arcpy.mapping** | ❌ **CRASH (0xc0000005)** | ✅ **SUCESSO (Exit 0)** |

### Prova de Execução Headless
- **Arquivo de teste:** `corpus\AUAS_2004_virtual_test.mxd`
- **Execução:** `C:\Python27\ArcGIS10.8\python.exe -u testes\run_headless.py`
- **Resultado:**
  - `MapDocument` carregou sem travar.
  - Enumerou 5 DataFrames e 32 LayoutElements.
  - `ExportToPDF` gerou `corpus\AUAS_2004_virtual_test.pdf` (316.039 bytes).
  - Inspeção via PyMuPDF confirmou renderização da banda orbital Landsat 5 TM a 1168×1168 pixels.

---

## 4. Onde a Conexão WMS Fica Gravada no MXD

No arquivo binário do MXD (Compound File OLE), a conexão WMS reside na stream **`Maps`**:
- **Objeto ArcObjects:** `esriCarto.WMSMapLayer` (CLSID `{E38A56C0-D5BD-4899-B089-C8ED4E38B77F}`).
- **Propriedades (PropertyBag):**
  - `"URL"`: String UTF-16LE com prefixo de tamanho de 4 bytes contendo a URL base.
  - `"LAYERNAME"`: Nome técnico da camada.
  - `"VERSION"`: Versão WMS (ex.: `1.3.0`).

Como a URL virtual é mais longa do que a URL geral, alterar a URL diretamente no arquivo `.mxd` exige a capacidade de redimensionar a stream e reconstruir o Compound File (resolvido na Parte B com o módulo `cfbf.py`).

---

## 5. Ferramenta de Conversão

Criada em `ferramentas\wms_por_camada.py`:
- Lê o MXD com `cfbf.py`.
- Detecta automaticamente o nome da cena CBERS/Landsat no mapa.
- Substitui a URL WMS global pela URL virtual da camada.
- Recalcula os prefixos de comprimento e tamanhos de bloco.
- Gera um novo `.mxd` pronto para exportação headless direta sem crash.
