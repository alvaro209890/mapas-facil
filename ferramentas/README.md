# Ferramentas do repositório

Utilitários de manutenção do acervo versionado. Não fazem parte do produto — servem ao
desenvolvedor que trabalha com os `.mxd` de referência.

## `chaves_mxd.py`

Remove ou reinjeta as chaves de API embutidas nos 24 `.mxd` de [`Referencias_IMAP/MXD/`](../Referencias_IMAP/MXD/).

### Contexto

Os `.mxd` do acervo IMAP guardam, dentro das camadas WMTS (Planet) e WMS (GeoServer da SEMA), a
chave de API em texto claro — **566 ocorrências** no total. O repositório é público, então a
versão versionada dos `.mxd` tem as chaves zeradas por **placeholders do mesmo comprimento**.

Substituição de mesmo comprimento é a única segura: `.mxd` é um documento composto OLE (Compound
File Binary). Trocar N bytes por N bytes não move nada; trocar por tamanho diferente corromperia o
arquivo.

### Comandos

```bash
python3 ferramentas/chaves_mxd.py verificar    # mostra o estado atual
python3 ferramentas/chaves_mxd.py restaurar    # placeholder → chave real
python3 ferramentas/chaves_mxd.py limpar       # chave real → placeholder
```

- `restaurar` lê as chaves de `secrets.local.json` (gitignored). Use quando precisar abrir um
  `.mxd` de referência no ArcMap com o basemap Planet e o WMS da SEMA funcionando.
- **`limpar` antes de qualquer commit.**

Crie `secrets.local.json` a partir de [`secrets.example.json`](../secrets.example.json).

### Placeholders

| Chave em `secrets.local.json` | Placeholder |
|---|---|
| `planet_api_key` | `PLAK_CHAVE_REMOVIDA_VER_FERRAMENTAS_` |
| `planet_api_key_antiga` | `PLANET_ANTIGA_CHAVE_REMOVIDA_VER` |
| `sema_authkey` | `5ema4key-0000-0000-0000-remov1da0000` |

Cada placeholder tem exatamente o mesmo comprimento da chave real. O comando `verificar` confere
que nenhum placeholder é substring de outro.

### Incidente 2026-07-25

Os `.mxd` foram commitados com chaves em texto claro num repositório público. A decisão foi
manter o repo público, tirar as chaves dos arquivos versionados e documentar o procedimento.

Detalhes completos — segredos expostos, modelo de ameaças, LGPD — em
[`planos/05-seguranca-e-segredos.md`](../planos/05-seguranca-e-segredos.md#incidente-2026-07-25--chaves-dentro-dos-mxd).
