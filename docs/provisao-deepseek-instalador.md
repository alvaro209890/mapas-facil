# Provisão de chaves no instalador (piloto)

Para o `.exe` já sair **funcionando no login**, sem o usuário configurar nada:
chat liberado (DeepSeek) **e** camadas do catálogo liberadas (SEMA/Planet).

## Chaves provisionadas

| Chave | Para quê | Sem ela |
|---|---|---|
| `deepseek_api_key` | chat do agente | `IA-001` no chat |
| `sema_authkey` | **30 das 41 camadas** do catálogo (WMS/WFS SEMA) | `NU-102` ao resolver camada |
| `planet_api_key` | basemap WMTS Planet (imagem de fundo do mapa) | mapa sem imagem de fundo |

## Caminho da chave

1. Neste PC Acer as chaves de teste vivem em `secrets.local.json` (gitignored).
2. No boot, o Electron espelha as três para:
   `Documentos/database/MapasFacil/provisao.local.json`
3. No empacotamento Windows, copie esse arquivo para
   `resources/provisao.local.json` (extraResources do electron-builder).
   **Nunca** commite `provisao.local.json` nem `secrets.local.json`.

No login (`conta.criar` / `conta.entrar`), `sincronizar_chave_projeto_no_cofre()`
grava as três no Credential Manager. A partir daí `resolver.py` acha a
`sema_authkey` sozinho e as camadas resolvem sem passar por Preferências.

Ordem de leitura por chave (`agente/provisao.py`):
env var → `MAPASFACIL_PROVISAO_PATH` → `provisao.local.json` → `secrets.local.json`.

| Chave | Env var |
|---|---|
| `deepseek_api_key` | `DEEPSEEK_API_KEY` |
| `sema_authkey` | `MAPASFACIL_SEMA_AUTHKEY` |
| `planet_api_key` | `MAPASFACIL_PLANET_API_KEY` |

## Risco aceito (decisão de 2026-07-27)

Embutir SEMA/Planet no instalador significa que **qualquer usuário consegue
extrair as chaves do `.exe`**. Foi uma decisão consciente para atender o
requisito de zero configuração no piloto. Consequências a acompanhar:

- a quota/cobrança da Planet corre na conta do projeto;
- rotacionar a chave exige republicar o instalador;
- tensiona o `AP-03` (nunca versionar segredo) — o segredo **não** é
  versionado, mas é distribuído no artefato.

Alternativa se isso virar problema: proxy no Acer, com o app chamando o
servidor e as chaves nunca saindo de lá.
