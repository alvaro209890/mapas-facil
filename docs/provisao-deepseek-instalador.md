# Provisão DeepSeek no instalador (piloto)

Para o `.exe` já sair com chat liberado no login:

1. Neste PC Acer a chave de teste vive em `secrets.local.json` (gitignored).
2. No boot, o Electron espelha para:
   `Documentos/database/MapasFacil/provisao.local.json`
3. No empacotamento Windows, copie esse arquivo para
   `resources/provisao.local.json` (extraResources do electron-builder).
   **Nunca** commite `provisao.local.json`.

No login (`conta.criar` / `conta.entrar`), o núcleo grava a chave no
Credential Manager e o chat usa a API do projeto automaticamente.
