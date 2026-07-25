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

### 1. Inspeção inicial

```powershell
# Ver o que falta normalizar (Python 2.7 do ArcMap)
C:\Python27\ArcGIS10.8\python.exe ferramentas/inspecionar_mxd_arcpy.py Referencias_IMAP/MXD/Dinamica_2026.mxd -o inspecao.json
```

O relatório lista data frames, camadas e elementos de layout que ainda não batem com o
contrato (`MAPA`, `PERIMETRO`, `TITULO`, …).

### 2. Normalização automática (sem abrir a GUI do ArcMap)

`arcpy.mapping` permite **renomear** data frames, camadas e elementos de layout (mas não
criar elementos novos) sem abrir a interface do ArcMap. `normalizar_mxd_arcpy.py` faz essa
parte sozinho, sempre numa cópia (nunca sobrescreve a entrada):

```powershell
C:\Python27\ArcGIS10.8\python.exe ferramentas/normalizar_mxd_arcpy.py `
  Referencias_IMAP/MXD/Dinamica_2026.mxd shared/templates/Dinamica_retrato.mxd `
  -o normalizacao_relatorio.json
```

Imprime o que foi aplicado (`relativePaths`, data frames, camadas, `METADADOS`, `NORTE`,
`LOGO`, `LEGENDA`) e o que ficou como **pendência** (precisa da GUI porque exige criar
elemento novo, não só renomear).

> **Cuidado com `save()` travado:** às vezes o `mxd.save()` grava o arquivo certo mas trava
> no cleanup do processo (mesmo sintoma documentado em
> `Referencias_IMAP/MXD/DOCUMENTACAO_MXD_HARMONIA.md` §5). Se o comando não retornar em ~2
> min, **não mate o processo** — espere terminar sozinho (~2-3 min) ou o arquivo pode ficar
> truncado no meio da escrita. Sempre confirme depois com `inspecionar_mxd_arcpy.py`.

### 3. Trabalho manual no ArcMap — só o que sobrou (B1)

Abrir a cópia gerada (`shared/templates/Dinamica_retrato.mxd`; não commitar sem
`chaves_mxd.py limpar` se tiver restaurado chaves) e resolver as pendências listadas pelo
passo 2 — tipicamente:

1. Criar texto `TITULO` (título do mapa) e `ROTULO_IMOVEL` (nome do imóvel) — não existem
   como elementos próprios no acervo.
2. Confirmar visualmente qual `LEGEND_ELEMENT` é a legenda do `MAPA` (o script escolhe a
   maior por heurística; confirmar que não é a do `MINIMAPA`).
3. Nomear entre os `GRAPHIC_ELEMENT` quais são `MINIMAPA_RETANGULO` e `MINIMAPA_GUIA`.
4. Apontar a imagem de `LOGO` (`sourceImage` vazio no acervo).
5. Salvar.

### 4. Calibrar offsets (B2)

```powershell
C:\Python27\ArcGIS10.8\python.exe ferramentas/preparar_sentinelas_arcpy.py shared/templates/Dinamica_retrato.mxd
python ferramentas/inspecionar_mxd_offsets.py shared/templates/Dinamica_retrato.mxd
python ferramentas/registrar_template.py dinamica_retrato shared/templates/Dinamica_retrato.mxd
```

### 5. Validar

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
