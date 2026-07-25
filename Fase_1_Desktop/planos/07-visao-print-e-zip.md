# F1-07 — "Olha esse print e faz igual"

Requisito explícito do produto: o app tem de ser **muito bom em olhar um print de um mapa e
reproduzir a mesma lógica** com os dados da pasta atual. Também vale para um `.zip` ou um `.mxd`
de uma análise anterior.

O caso de uso real é o da Harmonia: *"copiei os `.mxd` de outra análise do mesmo cliente e mesmo
município, e adaptei."* O que o técnico faz com dois dias de trabalho, o app faz olhando o
modelo.

## Três formas de dar a referência

| Entrada | O que o app extrai | Confiança |
|---|---|---|
| **Print / PDF de um mapa** | layout, formato de página, cores, blocos, legenda, título, escala | média-alta |
| **`.mxd` de uma análise anterior** | camadas, nomes, definition queries, extent, escala, textos, elementos | **alta** |
| **`.zip` de projeto** | o `.mxd` de dentro + os shapefiles + estrutura de pasta | alta |

O `.mxd` é a melhor entrada porque é estrutura, não pixel. O print é o mais conveniente, e é o
que o usuário tem à mão quando manda uma foto do WhatsApp.

## Caminho 1 — print ou PDF

```
imagem  →  pré-processamento (deskew, normalização, recorte de margem)
        →  análise determinística   (o que dá para medir, mede-se)
        →  análise por LLM de visão (o que precisa de interpretação)
        →  MapSpec proposto
        →  usuário confirma, ajusta ou recusa
```

### O que é medido, não perguntado

Muita coisa é geometria pura e não precisa de modelo nenhum:

| Medida | Como |
|---|---|
| Formato e orientação da página | proporção da imagem → retrato ou paisagem |
| Retângulo do quadro do mapa | detecção da moldura escura (mesma técnica usada para calibrar o padrão) |
| Faixa inferior e seus blocos | segmentação por regiões de fundo claro |
| Paleta das camadas | amostragem de cor nos swatches da legenda |
| Texto (título, metadados, legenda, escala) | OCR ou, em PDF, extração direta |
| Nº de rótulos DMS por eixo | contagem dos textos nas bordas |

Medir primeiro é o que torna o resultado **verificável**: o app mostra o que mediu, e o usuário
corrige um número, não um mapa inteiro.

### O que vai para o modelo de visão

Só o que exige interpretação:

- Qual mapa da série é este? (Dinâmica de que ano? Tipologia? Embargos?)
- O que cada entrada de legenda significa em termos de camada do catálogo?
- Que estilo do catálogo é o mais próximo de cada cor amostrada?
- Há algo fora do padrão (bloco extra, inset, linha de distância)?

O prompt recebe a imagem **e as medidas já feitas**, e é instruído a não contradizer medida —
só interpretar.

### Resposta esperada

```json
{
  "mapa_da_serie": "dinamica",
  "ano": 2026,
  "template_sugerido": "dinamica_retrato",
  "confianca": 0.86,
  "camadas": [
    { "legenda_lida": "Área Derivada de Desmate Após 2008",
      "cor_amostrada": "#FF8000", "estilo_sugerido": "auas", "confianca": 0.93 },
    { "legenda_lida": "Fazenda Harmonia",
      "cor_amostrada": "#FFFF00", "estilo_sugerido": "perimetro_imovel", "confianca": 0.97 }
  ],
  "metadados_lidos": [
    { "rotulo": "Satélite/Sensor", "valor": "PLANET" },
    { "rotulo": "Escala", "valor": "1:60.000" }
  ],
  "tabela_presente": true,
  "observacoes": ["tabela na base do quadro do mapa, cabeçalho azul"]
}
```

### Como isso vira mapa

O app **não** copia o print. Ele traduz o print para um `MapSpec` e preenche com **os dados da
pasta conectada**:

```
Li o print. É uma Dinâmica no padrão Harmonia, A4 retrato, escala 1:60.000.

Reconheci 4 camadas:
  Fazenda Harmonia (amarelo)              → local.ATP
  Área de vegetação nativa (verde xxx)    → local.AVN
  Área consolidada (magenta xxx)          → local.AREA_CONSOLIDADA
  Área Derivada de Desmate Após 2008 (///) → local.AUAS

Vou usar os shapes desta pasta, não os do print. O imóvel aqui é
Fazenda Harmonia · Vila Rica/MT — o mesmo. Gero?
```

Quando o imóvel da pasta **não** é o do print (caso comum: modelo de outro cliente), o agente
diz isso explicitamente e troca nome, município, áreas e a definition query.

## Caminho 2 — `.mxd` de referência

Muito mais rico, e não precisa de modelo de visão para a estrutura.

O núcleo abre o `.mxd` (com `arcpy` quando há ArcMap; senão, leitura das strings do OLE) e extrai:

| Extraído | Vira |
|---|---|
| Nomes das camadas | mapeamento para `nome_no_mxd` |
| `definitionQuery` de cada camada | detecta o município da análise anterior — e avisa que vai trocar |
| Caminhos dos datasets | quais shapefiles o template espera, e com que nome |
| Textos dos elementos | título, metadados, rótulo, distância |
| CRS do data frame | qual família (UTM ou Web Mercator) |
| Extent e escala | ponto de partida |
| Camadas de serviço (WMS/WMTS) | qual basemap, qual mosaico, qual layer da SEMA |

**É assim que a preparação de template também funciona.** O mesmo extrator serve para
transformar um `.mxd` do acervo em template registrado no manifesto.

Achado que já vale como aviso automático: nos `.mxd` do acervo há definition queries de análises
anteriores (`"nome" = 'Querência'`) convivendo com a atual. O extrator lista todas e o agente
avisa qual vai sobreviver.

## Caminho 3 — `.zip` de projeto

1. Listar sem extrair; mostrar o que tem.
2. Anti *zip slip*.
3. Se houver `.mxd`, seguir o caminho 2.
4. Se houver shapefiles, indexá-los como camadas candidatas.
5. Se houver PDF de mapa, usá-lo como referência visual complementar.

## Limites e honestidade

| Limitação | Como o app lida |
|---|---|
| Print de baixa resolução | avisa a confiança baixa e pede confirmação de cada camada |
| Foto tirada de tela, com reflexo/inclinação | deskew ajuda; abaixo de um limiar, recusa e pede o PDF |
| Cor amostrada entre dois estilos do catálogo | mostra os dois e pergunta |
| Layout fora do perfil Harmonia | diz que não reconhece e oferece o mais próximo — **não** inventa um template |
| Print de mapa de outro escritório | funciona como referência de layout, mas o resultado sai no padrão Harmonia |

Regra: **confiança abaixo de 0,7 em qualquer item vira pergunta, não palpite.**

## Checklist de implementação

- [ ] Pré-processamento de imagem (deskew, recorte, normalização)
- [ ] Detecção de moldura e segmentação de blocos
- [ ] Amostragem de cor nos swatches da legenda
- [ ] OCR para print; extração direta para PDF
- [ ] Contagem de rótulos DMS
- [ ] Prompt de visão recebendo imagem + medidas
- [ ] Mapeamento cor → estilo do catálogo com distância de cor
- [ ] Extrator de `.mxd` (com e sem arcpy)
- [ ] Detecção de definition queries herdadas
- [ ] Leitor de `.zip` reusando o do workspace
- [ ] Tela de confirmação item a item, com confiança
- [ ] Recusa explícita quando o layout não é do perfil

## Pendências

| # | Questão |
|---|---|
| P1 | Confirmar que o modelo DeepSeek V4 com visão está disponível e é bom o suficiente |
| P2 | OCR: Tesseract embarcado (+40 MB) ou deixar para o modelo de visão ler? |
| P3 | Ler strings de `.mxd` sem `arcpy` é frágil (OLE binário). Medir a taxa de acerto no acervo de 24 arquivos |
| P4 | Vale extrair simbologia do `.mxd` de referência para gerar um `.lyr` novo automaticamente? |
| P5 | Limiar de confiança 0,7 é chute — calibrar com os 21 PDFs do acervo como conjunto de teste |
