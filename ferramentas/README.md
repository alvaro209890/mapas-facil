# Ferramentas do repositório

Utilitários de manutenção do acervo versionado. Não fazem parte do produto — servem ao
desenvolvedor que trabalha com os `.mxd` de referência.

## `chaves_mxd.py`

Remove ou reinjeta as chaves de API embutidas nos `.mxd` de [`Referencias_IMAP/MXD/`](../Referencias_IMAP/MXD/).



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

## Preparação de template (B1/B2 — requer ArcMap)

Fluxo para o primeiro template (`dinamica_retrato`, a partir de `Dinamica_2026.mxd`).
Plano: [`Fase_1_Desktop/planos/04-motor-mxd.md`](../Fase_1_Desktop/planos/04-motor-mxd.md).

### 1. Chaves e inspeção inicial

```powershell
# Restaurar chaves Planet/SEMA para o basemap abrir (gitignored)
python ferramentas/chaves_mxd.py restaurar

# Ver o que falta normalizar (Python 2.7 do ArcMap)
C:\Python27\ArcGIS10.8\python.exe ferramentas/inspecionar_mxd_arcpy.py Referencias_IMAP/MXD/Dinamica_2026.mxd -o inspecao.json
```

O relatório lista data frames, camadas e elementos de layout que ainda não batem com o
contrato (`MAPA`, `PERIMETRO`, `TITULO`, …).

### 2. Trabalho manual no ArcMap (B1)

No `Dinamica_2026.mxd` (cópia de trabalho; não commitar até `chaves_mxd.py limpar`):

1. Renomear data frames → `MAPA` (principal, UTM 31982) e `MINIMAPA` (inset, 3857).
2. Renomear camadas para os nomes canônicos (tabela em F1-04).
3. Apontar shapefiles para `.\SHP\<nome>.shp` ao lado do `.mxd`.
4. **File → Map Document Properties → Store relative pathnames**.
5. Renomear elementos de layout (`TITULO`, `METADADOS`, `LEGENDA`, `NORTE`, …).
6. Padding nos textos patcháveis (slots de 64 / 320 caracteres).
7. Salvar como `shared/templates/Dinamica_retrato.mxd` (versão mínima 10.6).

### 3. Calibrar offsets (B2)

```powershell
C:\Python27\ArcGIS10.8\python.exe ferramentas/preparar_sentinelas_arcpy.py shared/templates/Dinamica_retrato.mxd
python ferramentas/inspecionar_mxd_offsets.py shared/templates/Dinamica_retrato.mxd
python ferramentas/registrar_template.py dinamica_retrato shared/templates/Dinamica_retrato.mxd
```

### 4. Validar

```powershell
cd Fase_1_Desktop/nucleo
pip install -e ".[dev]"
python -m mapasfacil_nucleo doctor --json
```

`doctor` deve reportar ArcMap 10.8, `motor_preferido: arcpy` e template `dinamica_retrato`
com `status: pronto`.

## `inspecionar_mxd_offsets.py`

Recupera arquivos de um ZIP **sem diretório central** (download OneDrive/cortado).

```bash
python3 ferramentas/recuperar_zip_truncado.py arquivo.zip -o pasta_saida
# exit 2 se o ZIP estiver truncado (mesmo com arquivos recuperados)
```

Usado em 2026-07-25 para `Referencias_IMAP/Mapas/03/OneDrive_1_25-07-2026 (1).zip`
(faltava só `PRODES_Até_2007.mxd`). Ver [`Referencias_IMAP/Mapas/03/README.md`](../Referencias_IMAP/Mapas/03/README.md).
