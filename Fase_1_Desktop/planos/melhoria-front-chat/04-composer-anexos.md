# 04 — Composer moderno + anexos + colar imagem

## Objetivo

Substituir o form cru (`textarea` + `Enviar`) por `CampoEntrada` alinhado a F1-02/F1-16/F1-17: uma superfície só, dark, com anexos first-class.

## Layout

```
┌─ campo-entrada ─────────────────────────────────────────────┐
│ [chip.pdf ×] [preview.png ×]                                │  ← só se houver anexos
│                                                             │
│  [+]   Mensagem (Ctrl+Enter)…                      [➤]/ │
└─────────────────────────────────────────────────────────────┘
         ↑ file picker / drop zone implícita          enviar
                                                    (Parar se enviando)
```

- Container: `--mf-superficie-2`, borda `--mf-borda`, radius `--mf-raio-3`, padding `--mf-e3`.
- Focus-within: borda `--mf-acento` ou `--mf-borda-forte` (escolher uma; evitar glow).
- Botão `+`: `lucide` `Paperclip` ou `Plus`; `aria-label="Anexar arquivo"`.
- Enviar: ícone `Send` / texto “Enviar” — manter atalho **Ctrl/Cmd+Enter**; **Esc** cancela turno (já existe).
- Durante `enviando`: botão vira **Parar** (comportamento atual).

## Anexos — contrato com o núcleo

F1-17 já define:

- Pasta `chats/anexos/<conversation_id>/`
- Limite **20 MB**/anexo
- Tabela `anexos` + `chat.enviar({ anexos? })`

### UI → IPC (proposta)

No rascunho local, antes do send:

```ts
type AnexoRascunho = {
  id: string;           // uuid local
  nome: string;
  mime: string;
  bytes: number;
  /** data URL ou path temporário escrito pelo preload */
  origem: { tipo: "path"; path: string } | { tipo: "buffer"; base64: string };
  previewUrl?: string;  // object URL para imagens
};
```

No `chat.enviar`, serializar para o formato que o núcleo já espera (verificar `agente/servico.py` / handlers — **ler contrato real na implementação**; não inventar campos divergentes).

Se o núcleo hoje só aceita paths: o preload grava temp em `anexos/` ou pasta temp da app e envia path.

## Tipos aceitos (v1)

| Tipo | Extensões | Preview |
|---|---|---|
| Imagem | png, jpg, jpeg, webp | thumbnail no chip |
| PDF | pdf | ícone + nome |
| Texto / planilha leve | txt, csv, md | ícone + nome |
| GIS comum (opcional v1.1) | zip shapefile? | só se núcleo processar — **não** fingir visão |

DeepSeek V4 **sem visão** (AGENT_BRIEF / IA-060): imagens anexadas ainda devem:

1. Persistir no histórico (auditoria / contexto humano).
2. Ser descritas no prompt como “[anexo imagem: nome, N KB]” **ou** caminho — **sem** prometer OCR/visão.
3. UI não mostrar “a IA vê a imagem” se o provedor não vê.

Se no futuro houver provedor com visão, o mesmo chip serve.

## Interações

| Ação | Comportamento |
|---|---|
| Clique `+` | `<input type="file" multiple>` oculto |
| Drag & drop no composer | `preventDefault`; adiciona arquivos |
| Paste (`Ctrl+V`) | se `clipboardData.files` ou item `image/*` → anexo; senão texto normal |
| Remover chip | revoga `previewUrl`, tira da lista |
| Limite | bloquear >20 MB com erro inline (`IA-…` ou mensagem local) |
| Máx. anexos/turno | sugerido **5** (calibrar; documentar constante) |

## Acessibilidade

- Chips com botão remover focável.
- Composer `aria-label` / label visual “Mensagem”.
- Drop zone: `aria-dropeffect` / anúncio de “N arquivos anexados”.

## Extração de `PainelChat`

Hoje o form vive dentro de `PainelChat`. Extrair:

```
CampoEntrada
  props: { disabled, enviando, cancelando, onEnviar(texto, anexos), onCancelar }
```

`PainelChat` só orquestra estado e API.

## Testes

- Paste de `File` image mock → chip aparece.
- Send chama API com `anexos` no payload (mock ponte).
- Arquivo >20 MB → não entra; mensagem de erro.
- Drop de texto puro não quebra textarea.

## Fora do escopo v1

- Galeria de anexos da conversa em painel separado.
- Edição de imagem.
- Paste de HTML rico / screenshots multi-frame.
- Microfone / comandos `/`.
