# Diretrizes de Segurança do Agente V2

*(Mapas Fácil — Arquitetura de Proteção e Contenção)*

## 1. Princípios de Segurança

O Agente V2 opera sob o princípio de menor privilégio e contenção estrita no sistema de arquivos, garantindo que a automação por modelos de linguagem não comprometa o ambiente hospedeiro, não altere arquivos sensíveis e não execute ações destrutivas sem consentimento humano explícito.

---

## 2. Contenção de Workspace (`WorkspaceGuard`)

- **Caminhos Relativos**: Todas as operações de leitura, escrita e movimentação exigem e retornam caminhos relativos ao diretório raiz do projeto.
- **Bloqueio de Path Traversal**: Qualquer referência a `..`, componentes vazios ou caminhos que resolvam fora da raiz autorizada é sumariamente rejeitada com erro tipado.
- **Bloqueio de Protocolos de Rede e UNC**: Caminhos iniciados por `\\` ou `//` são terminantemente bloqueados.
- **Arquivos Protegidos**: O agente é impedido de ler ou alterar arquivos de configuração e credenciais, incluindo:
  - `.env` e `servidor.env`
  - `secrets.local.json` e `secrets.json`
  - `auth.json`
  - Diretório `.git/`

---

## 3. Backups Automáticos

Antes de sobrescrever qualquer arquivo existente ou antes de operações de movimentação e exclusão, o Agente V2 copia automaticamente o arquivo original para o diretório de auditoria:
```
<workspace>/.agente/backups/<YYYYMMDD_HHMMSS>_<nome_original>
```
Isso garante recuperação determinística em caso de edição indevida ou falha no processamento.

---

## 4. Governança de Aprovação (Ações Destrutivas)

- **Impossibilidade de Auto-Concessão**: A LLM **não** tem permissão nem capacidade de conceder aprovações a si mesma.
- **Token Criptográfico do Servidor**: Quando uma ferramenta destrutiva (como `workspace_apagar`) é invocada sem autorização prévia:
  1. O núcleo gera token aleatório e grava pedido confiável por projeto em `.servidor/aprovacoes/pedido.json`.
  2. O valor fica fora das tools, do NDJSON e de `.agente/estado.json`; só o GET autenticado do owner o fornece à UI.
  3. O evento `agente.aprovacao` é emitido com `acao`, `caminho` e `motivo` (o token **não** é enviado no evento público nem exposto à LLM).
  4. O turno do agente é encerrado imediatamente com status `aguardando_aprovacao`.
  5. O POST com owner/CSRF confere token em tempo constante, ação, caminho, versão/hash e TTL. Grava atomicamente `decisao.json` no contrato nativo (`aprovado`, `acao`, `caminho`, `hash_alvo`, `timestamp`, `consumido`, `pedido_id`). Preserva o pedido para o núcleo consumir a decisão uma única vez na próxima tool.
  6. `Mapas/vNNN/` é legível para QA/preview, mas não editável/apagável pelas tools. Leitura tem teto no disco; saídas geo usam nome novo e não sobrescrevem fontes.

---

## 5. Execução de Código Python (`python_exec` Fail-Closed)

- **Postura Fail-Closed**: A ferramenta `python_exec` permanece estritamente **DESLIGADA** por padrão, inclusive se flags de ambiente forem definidas.
- **Inadmissibilidade de Execução no Processo Hospedeiro**: `eval()`, `exec()` ou chamadas a `subprocess` sem sandbox de sistema operacional verificado são terminantemente proibidas. Flags locais ou hooks em nível de runtime Python não equivalem a isolamento de SO e não autorizam ativação pública.
- **Exigência de Isolamento de SO**: A execução de código arbitrário só pode ser liberada mediante comprovação formal de isolamento ao nível do sistema operacional (jail, container gVisor sem montagem de diretórios do host, sem rede e sem acesso a segredos). Na ausência de tal infraestrutura verificada, qualquer chamada à ferramenta resulta em rejeição imediata com código `SEC-001`.
