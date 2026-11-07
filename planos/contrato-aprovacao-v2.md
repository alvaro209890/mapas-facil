# Contrato de Aprovação de Ações Críticas v2 — Por Projeto e Confiável

**Autor:** Subagente Ferramentas e Segurança V2 (2026-11-06)  
**Status:** Vigente (Fase 1 / Fase 3)  
**Arquivo:** `planos/contrato-aprovacao-v2.md`  

Este documento define o contrato oficial de **aprovação de ações críticas e destrutivas** do Agente V2 (operações de exclusão de arquivos, sobrescrita de arquivos existentes, movimentação de diretórios protegidos e qualquer execução com impacto irreversível no workspace).

---

## 1. Princípios de Segurança e Não-Autonomia do LLM

1. **Sem Singleton Global**: cada aprovação pertence estritamente ao **projeto/workspace** onde a ação ocorre. Não há estado global em memória compartilhado entre projetos ou processos.
2. **LLM Não Concede Consentimento**: parâmetros como `token_aprovacao` passados pelo LLM nas ferramentas são **estritamente ignorados** como prova de autorização. O consentimento só é válido se proveniente do canal confiável do proprietário (fora do contexto do LLM).
3. **Isolamento de Diretórios de Controle**: os arquivos de solicitação e decisão residem em `<workspace>/.servidor/aprovacoes/`. O Workspace Guard impede qualquer ferramenta do LLM (`workspace_ler`, `workspace_escrever`, `workspace_apagar`, `workspace_mover`, `workspace_listar`) de acessar ou modificar o diretório `.servidor/`.
4. **Token Fora do Prompt e de Eventos Públicos**: o token criptográfico gerado pelo backend nunca é retornado no corpo da resposta da tool e nunca é emitido no evento `agente.aprovacao`. O token é acessado exclusivamente pelo endpoint administrativo do servidor para a UI do usuário humano.
5. **Uso Único (Single-Use)**: uma decisão favorável só pode ser consumida **uma única vez** para aquela exata combinação de ação, caminho relativo e hash do arquivo alvo. Assim que consumida, é marcada como consumida ou removida, impedindo replay attacks.

---

## 2. Estrutura de Arquivos no Workspace

Dentro de cada projeto, o backend gerencia:

```
<workspace>/
  ├── .servidor/
  │   └── aprovacoes/
  │       ├── pedido.json      # Pedido confiável gravado pelo núcleo
  │       └── decisao.json     # Decisão do usuário gravada pelo endpoint do servidor
```

### 2.1 Formato de `pedido.json`

Gravado por `GerenciadorAprovacao.solicitar(...)`:

```json
{
  "pedido_id": "ped_a1b2c3d4e5f6",
  "acao": "apagar",
  "caminho": "Mapas/antigo.pdf",
  "motivo": "Exclusão definitiva do arquivo 'Mapas/antigo.pdf'.",
  "hash_alvo": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "timestamp": 1799292929.123,
  "token": "4f8a9b2c...64_hex_chars...",
  "status": "pendente"
}
```

### 2.2 Formato de `decisao.json`

Gravado pelo endpoint do servidor após confirmação do usuário:

```json
{
  "pedido_id": "ped_a1b2c3d4e5f6",
  "acao": "apagar",
  "caminho": "Mapas/antigo.pdf",
  "hash_alvo": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "aprovado": true,
  "timestamp": 1799292935.456,
  "consumido": false
}
```

---

## 3. Fluxo de Execução

1. **Ação Crítica Requisitada**: o LLM chama `workspace_apagar` ou `workspace_escrever` (quando o arquivo alvo já existe).
2. **Verificação de Decisão Confiável**: a ferramenta verifica se existe decisão aprovada em `.servidor/aprovacoes/decisao.json` para o par `(acao, caminho)` com `consumido: false`.
3. **Se Não Houver Decisão Válida**:
   - O núcleo gera `pedido.json` em `<workspace>/.servidor/aprovacoes/pedido.json`.
   - O núcleo emite o evento `agente.aprovacao` contendo apenas `{pedido_id, acao, caminho, motivo}` (sem token).
   - A ferramenta retorna imediatamente:
     ```json
     {
       "ok": false,
       "aguardando_aprovacao": true,
       "pedido_id": "ped_...",
       "acao": "apagar",
       "caminho": "...",
       "motivo": "...",
       "mensagem": "Operação 'apagar' em '...' requer aprovação explícita do usuário."
     }
     ```
   - O turno de ferramentas encerra e o sistema aguarda a ação do usuário na UI.
4. **Usuário Decide na UI**:
   - A UI consulta o endpoint de aprovação do servidor.
   - O servidor autentica o usuário e grava `<workspace>/.servidor/aprovacoes/decisao.json`.
5. **Retomada e Consumo**:
   - Na próxima tentativa da ação, o núcleo localiza a decisão, valida conformidade de `acao`, `caminho` e integridade do arquivo.
   - O núcleo marca a decisão como `consumido: true` e remove o arquivo para evitar reuso.
   - A operação crítica é executada com backup prévio em local único sem colisão.

---

## 4. Endpoints do Servidor (Contrato para o Agente Servidor)

O agente responsável pelo servidor FastAPI implementa as seguintes rotas baseadas neste contrato:

### `GET /api/v1/projetos/{projeto_id}/aprovacao/pendente`
- **Acesso:** Proprietário autenticado (UI).
- **Comportamento:** Lê `<workspace>/.servidor/aprovacoes/pedido.json`.
- **Resposta:**
  ```json
  {
    "pendente": true,
    "pedido_id": "ped_...",
    "acao": "apagar",
    "caminho": "Mapas/antigo.pdf",
    "motivo": "Exclusão definitiva...",
    "timestamp": 1799292929.123,
    "token": "4f8a9b2c..."
  }
  ```

### `POST /api/v1/projetos/{projeto_id}/aprovacao/decidir`
- **Acesso:** Proprietário autenticado (UI).
- **Body:**
  ```json
  {
    "pedido_id": "ped_...",
    "token": "4f8a9b2c...",
    "aprovado": true
  }
  ```
- **Comportamento:** Valida token contra `pedido.json`. Se válido, grava `decisao.json` com `consumido: false` e atualiza `pedido.json` para `status: "aprovado"` ou `"recusado"`.
- **Resposta:** `{"ok": true, "status": "decidido", "aprovado": true}`.
