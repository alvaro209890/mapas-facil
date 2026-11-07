# Multi-Imóvel Aditivo — Documentação e Contratos

*Autor: Hermes-windows/default (subagente multi-imóvel) — 2026-11-06*
*Contexto: Evolução do Mapas Fácil Fase 3 Web para múltiplos imóveis, preservando retrocompatibilidade total com o modelo singular existente.*

---

## 1. Visão Geral

O suporte a **Multi-Imóvel** permite que um único projeto no Mapas Fácil gerencie, processe e represente múltiplos imóveis rurais (diferentes CARs, matrículas, perímetros ou glebas) de forma organizada e declarativa, sem quebrar o fluxo de imóvel único existente (*singular compatível*).

### Princípios do Design Aditivo
1. **Preservação de Estado**: Bancos existentes (SQLite), contas de usuário, projetos já criados e versões geradas continuam funcionando sem qualquer alteração destrutiva.
2. **Singular Compatível**: O bloco `imovel` singular permanece válido no `MapSpec` e na tabela `projetos` para garantir que componentes legados e motores existentes continuem operando normalmente. O imóvel marcado com `principal: true` alimenta o bloco singular.
3. **Isolamento de Domínio**: Motores existentes (`motores/gerar.py`) **não foram alterados**. A geração individualizada por imóvel é orquestrada por helper especializado (`multi_imovel.py`) que clona e especializa o spec por imóvel antes de despachar para o motor existente.
4. **Segurança de Acesso (Auth Owner)**: Endpoints de inspeção do estado do agente e aprovação exigem autenticação do proprietário e token CSRF, sem permitir acesso arbitrário a arquivos nem tokens forjados por LLM.

---

## 2. Contrato MapSpec (`shared/schemas/mapspec.schema.json`)

### Propriedades Adicionadas

#### `imoveis` (Array opcional no root)
Array contendo a especificação detalhada de cada imóvel integrante do projeto:
```json
{
  "imoveis": [
    {
      "id": "imovel_1_fazenda_alfa",
      "nome": "Fazenda Alfa",
      "car": "MT102042/2017",
      "matricula": "12.345",
      "area": 250.5,
      "atp": "CAR_Alfa/ATP.shp",
      "principal": true,
      "municipio": {
        "nome": "Querência",
        "uf": "MT"
      },
      "geometria": "local.ATP_Alfa"
    },
    {
      "id": "imovel_2_fazenda_beta",
      "nome": "Fazenda Beta",
      "car": "MT102043/2017",
      "matricula": "54.321",
      "area": 180.0,
      "atp": "CAR_Beta/ATP.shp",
      "principal": false,
      "municipio": {
        "nome": "Querência",
        "uf": "MT"
      },
      "geometria": "local.ATP_Beta"
    }
  ]
}
```

Campos de cada item de `imoveis`:
- `id` (string, obrigatório): Identificador único do imóvel no projeto.
- `nome` (string, obrigatório): Nome descritivo da propriedade / gleba.
- `car` (string ou null): Número de inscrição no CAR (estadual ou recibo federal).
- `matricula` (string ou null): Número da matrícula imobiliária ou posse.
- `area` (number ou null): Área total declarada em hectares.
- `atp` (string ou null): Caminho relativo ou id_local do shapefile de perímetro (ATP/AIR).
- `principal` (boolean): `true` para o imóvel principal do projeto (exatamente um por projeto).
- `municipio` (object opcional): `{ "nome": str, "uf": str, "ibge"?: str }`.
- `geometria` (string opcional): Referência da geometria (`local.*`).

#### `camadas[].imovel_id` (String ou null opcional)
Permite associar uma camada temática específica a um imóvel determinado:
- Se omitido ou `null`: Camada global (compartilhada por todos os imóveis, ex: limites municipais, bioma, hidrografia estadual).
- Se especificado (ex: `"imovel_1_fazenda_alfa"`): Camada pertencente exclusivamente àquele imóvel (ex: Reserva Legal, APP ou Uso Consolidado da Fazenda Alfa).

#### `layout_spec` (Objeto opcional no root)
Permite embutir a especificação declarativa de layout (`LayoutSpec`) diretamente no `MapSpec` para consumo pelo agente de layout:
- Validação automática via loader específico (`mapasfacil_nucleo.layout.validar`). Se o módulo de layout estiver disponível, valida estritamente conformidade com o schema do LayoutSpec (`layoutspec.schema.json`).

---

## 3. Validação Semântica (`mapspec/validar.py`)

Regras validadas:
- **`NU-230`**: Rejeita IDs duplicados dentro de `imoveis`.
- **`NU-231`**: Rejeita quando mais de um imóvel é marcado como `principal: true`.
- **`NU-232`**: Rejeita camadas que referenciam um `imovel_id` inexistente na lista de `imoveis`.
- **`NU-233` / `NU-234`**: Rejeita `layout_spec` que não seja objeto ou que reprove na validação específica do pacote de layout.

---

## 4. Núcleo: `multi_imovel.py` e Integração Workspace

### Detecção Inteligente (`identificar_imoveis`)
Analisa a estrutura do workspace ou pacote ZIP:
1. **Múltiplos Recibos CAR**: Extrai dados de cada PDF que represente recibo CAR oficial (SEMA-MT ou SICAR federal), associando com os respectivos ATPs por subpasta ou similaridade de nome.
2. **Múltiplos Shapefiles de Perímetro**: Detecta múltiplos arquivos com papel `ATP`, `AIR` ou nomes contendo `LOTE`/`PERIMETRO`/`GLEBA`.
3. **Garantia de Unicidade**: Atribui IDs limpos e garante que exatamente um imóvel seja designado como `principal`. Prioriza fontes em `entrada/`, ignora pastas de controle (`.agente`, `.servidor`) e artefatos gerados em `Mapas/`, e deduplica estritamente cópias espelhadas em `SHP/` por hash, sem transformar artefatos em imóveis novos. Não usa fallback indiscriminado que promova camadas de hidrografia/APP a imóveis.
4. **Fallback Transparente**: Em pacotes convencionais com 1 único imóvel, gera a lista unitária com `principal: true` preservando comportamento idêntico.

### Helper de Geração Individualizada (`gerar_mapas_por_imovel`)
- Itera sobre os imóveis definidos em `mapspec["imoveis"]`.
- Clona o MapSpec para cada imóvel, ajustando o bloco `imovel`, filtrando camadas correspondentes (`imovel_id == imovel.id` ou camadas globais) e prefixando o `nome_base` de saída.
- Despacha para `gerar_mapa(...)` em `mapasfacil_nucleo.motores.gerar` **sem modificar o motor existente**.

### XLSX Combinado Institucional (`gerar_xlsx_combinado`)
Gera planilha Excel (`.xlsx`) consolidada com formatação institucional e paleta oficial:
- **Aba "Resumo Imóveis"**: Tabela de identificação de todos os imóveis, com CAR, matrícula, área (ha), ATP e indicação do principal, incluindo linha de totalização de área.
- **Aba "Quantitativos Combinados"**: Tabela consolidada com todas as classes de todos os imóveis lado a lado.
- **Abas individuais "Q - <Nome>"**: Detalhamento individualizado por propriedade (títulos higienizados contra caracteres inválidos no Excel e truncados até 31 caracteres).

---

## 5. Banco de Dados e Migração `0004_multi_imovel.sql`

### Nova Tabela: `imoveis_projeto`
```sql
CREATE TABLE IF NOT EXISTS imoveis_projeto (
  id            TEXT PRIMARY KEY,
  projeto_id    TEXT NOT NULL REFERENCES projetos(id) ON DELETE CASCADE,
  imovel_id     TEXT NOT NULL,
  nome          TEXT NOT NULL,
  car           TEXT,
  matricula     TEXT,
  area_ha       REAL,
  atp_fonte     TEXT,
  principal     INTEGER NOT NULL DEFAULT 0,
  criado_em     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_imoveis_projeto_proj ON imoveis_projeto(projeto_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_imoveis_projeto_unique ON imoveis_projeto(projeto_id, imovel_id);
```

O `salvar_imoveis()` no repositório utiliza resolução `ON CONFLICT(projeto_id, imovel_id)` preservando integridade com o backfill da migração.

### Backfill Determinístico sem Invenção de Dados
A migração 0004 insere 1 registro em `imoveis_projeto` para todos os projetos existentes que possuam dados de imóvel (`imovel_nome` ou `imovel_car`):
- `id`: `<projeto_id>_principal`
- `imovel_id`: `'imovel_principal'`
- `nome`: `COALESCE(NULLIF(p.imovel_nome, ''), p.nome)`
- `car`: `p.imovel_car`
- `matricula`: `NULL` (não inventa dado)
- `area_ha`: `NULL` (não inventa dado)
- `atp_fonte`: `NULL`
- `principal`: `1`

---

## 6. APIs do Servidor

### `GET /api/v1/projetos/{id}/imoveis`
Retorna a lista de imóveis vinculados ao projeto:
```json
{
  "imoveis": [
    {
      "id": "imovel_1",
      "nome": "Fazenda Alfa",
      "car": "MT102042/2017",
      "matricula": "12.345",
      "area": 250.5,
      "atp": "CAR_Alfa/ATP.shp",
      "principal": true
    }
  ]
}
```

### `GET /api/v1/projetos/{id}` (Detalhar)
Agora inclui `"imoveis": [...]` no corpo da resposta ao lado de `"projeto"` e `"versoes"`.

### `GET /api/v1/projetos/{id}/agente`
Lê o estado de `.agente/estado.json` dentro do workspace do projeto.
- **Autenticação**: Exige login do proprietário ou admin (`SV-031` se pertencer a outro usuário).
- **Contrato neutro garantido**: Caso o arquivo `.agente/estado.json` ainda não exista, devolve:
```json
{
  "passos": [],
  "arquivos": [],
  "previews": [],
  "aprovacao": null,
  "status": "pendente",
  "resumo": null,
  "versao": null
}
```

### `POST /api/v1/projetos/{id}/agente/aprovacao`
Permite ao usuário autenticado aprovar ou rejeitar a proposta do agente com segurança:
- **Corpo**:
  ```json
  {
    "acao": "aprovar", // ou "rejeitar"
    "motivo": "Mapas aprovados para envio"
  }
  ```
- **Segurança**:
  - Exige CSRF (`X-MF-CSRF`).
  - Gravação atômica via arquivo temporário `.tmp` e replace.
  - Registro em tabela de `auditoria` do servidor.
  - Não aceita tokens forjados por LLM.

---

## 7. Status de Integração e Conformidade

1. **Gate PDF-first / MXD no Pacote Zip**:
   - Pacotes ZIP seguem estrutura PDF-first (`Mapas/`, `SHP/`, `XLSX/`), sanitizam o nome do arquivo gerado contra caracteres inválidos e path traversal, e só incluem `.mxd` se explicitamente solicitado via `?mxd=1` (com `MF_MXD=1` ativo).
2. **Interface Web / Palco**:
   - O Palco integra previews PNG e PDF consolidado com o Painel do Agente, exibindo os múltiplos imóveis na síntese e suportando navegação e downloads.
3. **Turno de Abertura Multi-Imóvel**:
   - Abertura inicial lista explicitamente todos os imóveis detectados (nome, CAR e área), mantendo consistência documental.
