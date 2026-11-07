# Agente V2 — Arquitetura e Contrato Operacional

*(Mapas Fácil — Núcleo Cartográfico v2)*

## 1. Visão Geral

O **Agente V2** do Mapas Fácil evolui o motor de inteligência e automação cartográfica para um modelo modular, extensível e seguro. Ele substitui switches monolíticos de ferramentas por um registro extensível, implementa rastreamento em tempo real por eventos canônicos, garante persistência de estado em disco (`.agente/estado.json`) e aplica barreiras rígidas de proteção de dados e integridade do sistema de arquivos.

---

## 2. Contrato de Eventos do Agente

O Agente V2 comunica seu progresso, arquivos gerados e estados de aprovação exclusivamente através do vocabulário oficial de eventos no `protocolo.py`:

| Evento | Payload | Descrição |
|---|---|---|
| `agente.plano` | `{passos: [{id, titulo, status}]}` | Emite o planejamento macro com a lista ordenada de etapas. |
| `agente.passo` | `{id, titulo, status, resumo?}` | Notifica início, progresso ou conclusão de um passo do plano. |
| `agente.arquivo` | `{caminho, acao}` | Registra leitura, escrita, movimentação ou exclusão de arquivo. Caminho sempre relativo. |
| `agente.preview` | `{caminho, pagina?}` | Indica geração de prévia raster (PNG/SVG) de prancha ou PDF. |
| `agente.aprovacao` | `{acao, caminho, motivo}` | Solicita confirmação explícita do usuário para ação destrutiva. |
| `agente.fim` | `{status, resumo?, versao?}` | Encerramento do ciclo de trabalho do agente. |

### Status Válidos de Passo e Execução
- `pendente`
- `em_andamento`
- `aguardando_aprovacao`
- `aguardando_pergunta`
- `concluido`
- `erro`
- `cancelado`

---

## 3. Registro Extensível de Ferramentas (`registro.py`)

Em vez de um switch único gigante, as ferramentas são organizadas em submódulos funcionais e registradas de forma desacoplada no `RegistroFerramentas`:

### Categorias de Ferramentas:
1. **`workspace`** (`tools_workspace.py`):
   - `workspace_listar`: Lista diretórios e arquivos com caminhos relativos e metadados.
   - `workspace_ler`: Lê arquivos de texto respeitando teto de segurança (bounded I/O de até 100.000 bytes no disco). Suporta leitura de PDFs versionados para inspeção.
   - `workspace_escrever`: Grava arquivos com criação automática de backup prévio em `.agente/backups/`.
   - `workspace_mover`: Move ou renomeia arquivos dentro do workspace.
   - `workspace_apagar`: Operação destrutiva protegida por token de aprovação.
   - `workspace_estat`: Metadados de arquivos (tamanho, existência, data de modificação).
2. **`geo`** (`tools_geo.py`):
   - `geo_inspecionar`: Extração de CRS/EPSG, bounding box, campos e tipos de feição.
   - `geo_area`: Cálculo preciso de áreas poligonais em hectares (`ha`), m² ou km².
   - `geo_recortar`: Clip espacial de shapefile por camada delimitadora.
   - `geo_dissolver`: União geométrica (`unary_union`) de polígonos adjacentes/sobrepostos.
   - `geo_intersectar`: Interseção espacial booleana entre duas camadas.
   - `geo_reprojetar`: Conversão de coordenadas entre datums e projeções (ex.: SAD69 → SIRGAS 2000 UTM).
3. **`layout`** (`tools_layout.py`):
   - `layout_ler`: Leitura das dimensões da prancha e elementos visuais.
   - `layout_editar`: Ajuste de posições, visibilidade e tamanhos em mm de página.
   - `layout_medir`: Medição de caixas delimitadoras e áreas ocupadas no papel.
   - `layout_validar`: Auditoria de elementos fora da folha e sobreposições indesejadas.
   - `layout_renderizar`: Disparo de prévia real do layout gerando PDF físico e emitindo evento `agente.preview` somente com arquivo existente.
4. **`pdf`** (`tools_pdf.py`):
   - `pdf_preview`: Renderização raster de alta resolução de páginas PDF via PyMuPDF.
   - `pdf_texto`: Extração de texto estruturado por página.
   - `pdf_unir`: Concatenação de múltiplos PDFs em prancha ou dossiê consolidado.
5. **`visao`** (`tools_visao.py`):
   - `visao_analisar`: Análise visual multimodal via provedor de visão integrado com tarjamento automático de PII (CPFs/CNPJs/nomes) pré-envio. Ausência do provedor retorna status indisponível.
6. **`mapa`** (`tools_mapa.py`):
   - `mapa_validar`: Validação técnica de MapSpec e conformidade de regras contra `mapspec.schema.json` e regras semânticas fail-closed.
   - `mapa_gerar`: Disparo de compilação real do mapa (sem stubs ou retornos falsos).
   - `versao_listar`: Listagem de versões históricas geradas no workspace.
   - `versao_restaurar`: Restauração real de versões prévias do projeto.
7. **`skills` e `memoria`** (`tools_memoria.py`):
   - `skill_listar`: Descoberta de competências especializadas em `shared/skills/`.
   - `skill_ler`: Injeção de instruções cartográficas específicas sob demanda.
   - `memoria_ler`: Leitura de notas duráveis do projeto em `.agente/memoria.md`.
   - `memoria_gravar`: Atualização persistente da memória de trabalho.
8. **`execucao`** (`tools_exec.py`):
   - `python_exec`: Fail-closed obrigatório (desabilitado sem prova de container isolado).
9. **Ferramentas Preservadas**:
   - `perguntar`, `consultar_catalogo`, `adicionar_camada`, `remover_camada`, etc. mantidas integralmente para compatibilidade.

---

## 4. Integração pública e persistência

A entrada real é HTTP → ponte NDJSON `chat.enviar` → `servico.enviar` →
`orquestrador.executar_turno`. O loop original foi preservado para manter SQLite de conversas,
anexos, resumo, privacidade e cancelamento. `orquestrador_v2.py` fornece o interceptador de
estado e uma classe compatível, mas não substitui o histórico do caminho público.

`schemas_openai()` carrega o catálogo completo mesmo se o registro já contiver tools de plano:
registro não vazio não prova que workspace/geo/PDF/visão foram carregados no primeiro turno.

O QA pós-render usa caixas do perfil real (`_perfil_do_mapspec`) e a dimensão efetiva da folha (`max_rodadas=0`). Ele **não** anuncia
correção aplicada só à memória: avisos remanescentes exigem editar + gerar outra versão.
O agente dispõe das tools para esse ciclo; visão ausente/recusada não é aprovação.

Em multi-imóvel, uma chamada `gerar_mapa` processa o lote e consolida os arquivos. Cada motor
tem seu tracker de etapas; o progresso global é monotônico, reservando os últimos 5% para
consolidação/validação. A validação consolidada inclui HARD/SOFT de todos os imóveis.

- **Teto Configurável de Rodadas**: Padrão de 100 rodadas de ferramenta por turno.
- **Detecção de Falha Repetida**: Se a mesma ferramenta falhar consecutivamente 3 vezes com o mesmo erro, o loop é interrompido imediatamente com código `IA-035`, impedindo consumo inútil de tokens.
- **Cancelamento Cooperativo**: `pedir_cancelamento(conversation_id)` interrompe streams ativas e encerra o ciclo gravando status `cancelado`.
- **Persistência em `.agente/estado.json`**:
  O arquivo registra de forma atômica:
  - `conversation_id`
  - `status` (`iniciando`, `em_andamento`, `aguardando_aprovacao`, `aguardando_pergunta`, `concluido`, `erro`, `cancelado`)
  - `passos` do plano
  - `arquivos` lidos, gravados ou alterados
  - `previews` gerados
  - `aprovacao` pendente
  - `resumo` textual
  - `versao` associada

---

## 5. Limitações e Observações Técnicas

1. **Subprocessos no Windows**: Logs podem emitir warnings benignos de encoding UTF-8 (`cp1252`) em subprocessos auxiliares sem impacto no produto.
2. **Isolamento de Execução**: `python_exec` permanece fail-closed por design.
3. **Imutabilidade de Versões**: Artefatos gerados sob `Mapas/v*` são protegidos contra escrita ou remoção direta por ferramentas do agente.
