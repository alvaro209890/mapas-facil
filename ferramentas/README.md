# Ferramentas do repositório

Utilitários de manutenção do acervo versionado. **Não** fazem parte do produto instalado —
servem ao desenvolvedor.

Scripts presentes:

| Script | Função |
|---|---|
| `chaves_mxd.py` | remove/reinjeta chaves de API nos `.mxd` versionados |
| `inspecionar_mxd_arcpy.py` | diagnóstico de layout (requer ArcMap) |
| `normalizar_mxd_arcpy.py` | B1 automatizado parcial (renomear elementos) |
| `preparar_sentinelas_arcpy.py` | sentinelas de extent/escala para offsets |
| `inspecionar_mxd_offsets.py` | lê offsets/sentinelas do `.mxd` |
| `registrar_template.py` | grava sha256/offsets no MANIFEST |
| `recuperar_zip_truncado.py` | recupera ZIP sem diretório central |

## `chaves_mxd.py`

Remove ou reinjeta as chaves de API embutidas nos `.mxd` do acervo — hoje cobre
[`Referencias_IMAP/MXD/`](../Referencias_IMAP/MXD/) e
[`Referencias_IMAP/OneDrive_1_25-07-2026 (1)/Divisão de talhões e mapa retrato/`](<../Referencias_IMAP/OneDrive_1_25-07-2026 (1)/Divisão de talhões e mapa retrato/>)
(lista em `MXD_DIRS`, `ferramentas/chaves_mxd.py`). **Toda pasta nova de referência com
`.mxd` que for versionada precisa entrar em `MXD_DIRS` antes do primeiro commit** — 2026-07-25
achamos chave real (`planet_api_key_antiga`) embutida em todos os 31 `.mxd` da pasta nova
`OneDrive_1_25-07-2026 (1)/`; só a de `Divisão de talhões` foi limpa e versionada (as outras
30, em `Analise de Area/` e `AEP/`, ficaram de fora deste commit — ver nota abaixo).



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
`LOGO`, `LEGENDA`, e — desde 2026-07-25 — `TITULO`/`ROTULO_IMOVEL`/`MINIMAPA_RETANGULO`/
`MINIMAPA_GUIA` via reaproveitamento de elemento existente) e o que ficou como
**pendência** (heurística ambígua ou realmente exige a GUI — ver passo 3). Use
`--logo <caminho.png>` pra apontar outra variante do logo; o default é
`Referencias_IMAP/Logos IMAP/LOGOTIPO SEM FUNDO/TOM ESCURO.png`.

> **Ainda não testado**: as 4 heurísticas novas (título, rótulo do imóvel, gráficos do
> minimapa, logo) foram escritas sem acesso a arcpy/ArcMap neste ambiente. Rode e confira o
> relatório antes de assumir que fecharam — ver detalhes em
> [`../Fase_1_Desktop/nucleo/docs/bloco-b-sem-arcmap.md`](../Fase_1_Desktop/nucleo/docs/bloco-b-sem-arcmap.md).

> **Cuidado com `save()` travado:** às vezes o `mxd.save()` grava o arquivo certo mas trava
> no cleanup do processo (mesmo sintoma documentado em
> `Referencias_IMAP/MXD/DOCUMENTACAO_MXD_HARMONIA.md` §5). Se o comando não retornar em ~2
> min, **não mate o processo** — espere terminar sozinho (~2-3 min) ou o arquivo pode ficar
> truncado no meio da escrita. Sempre confirme depois com `inspecionar_mxd_arcpy.py`.

### 3. Trabalho manual no ArcMap — só o que sobrar depois do passo 2 (B1)

Abrir a cópia gerada (`shared/templates/Dinamica_retrato.mxd`; não commitar sem
`chaves_mxd.py limpar` se tiver restaurado chaves) e resolver as pendências que o **relatório
do passo 2** listar — não é mais uma lista fixa de 4 itens. Na pior hipótese ainda são
estes, mas cada um só precisa de GUI se a heurística correspondente não fechar sozinha:

1. `TITULO`/`ROTULO_IMOVEL` sem candidato — só acontece se este `.mxd` não tiver a caixa
   balão "Ano: NNNN" nem rótulo solto sobrando; nesse caso sim precisa criar elemento novo.
2. Confirmar visualmente qual `LEGEND_ELEMENT` é a legenda do `MAPA` (o script escolhe a
   maior por heurística; confirmar que não é a do `MINIMAPA`) — sempre manual, é só
   confirmação visual rápida.
3. `MINIMAPA_RETANGULO`/`MINIMAPA_GUIA` sem candidato inequívoco — a heurística
   (geometria + posição) já tenta; só sobra pra GUI se ficar ambíguo.
4. `LOGO.sourceImage` — só precisa da GUI se `PictureElement.sourceImage` não for gravável
   nesta versão do arcpy (o script tenta e avisa no relatório se falhou).
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

`doctor` (Linux) reporta `pronto_para_mxd: false` enquanto houver templates sem sha256 ou
enquanto nenhum template estiver `status: pronto` (offsets). Em Windows com ArcMap, use
`doctor --completo` para sondar licença; o executável é buscado em Desktop10.8 / 10.7 / 10.6.
O MANIFEST de `dinamica_retrato` registra `versao_arcmap: "10.6"` (metadado do arquivo preparado).

## `recuperar_zip_truncado.py`

Recupera arquivos de um ZIP **sem diretório central** (download OneDrive/cortado).

```bash
python3 ferramentas/recuperar_zip_truncado.py arquivo.zip -o pasta_saida
# exit 2 se o ZIP estiver truncado (mesmo com arquivos recuperados)
```

Usado em 2026-07-25 para `Referencias_IMAP/Mapas/03/OneDrive_1_25-07-2026 (1).zip`
(faltava só `PRODES_Até_2007.mxd`). Ver [`Referencias_IMAP/Mapas/03/README.md`](../Referencias_IMAP/Mapas/03/README.md).

## `inspecionar_mxd_offsets.py`

Lê offsets/sentinelas de um `.mxd` preparado (após `preparar_sentinelas_arcpy.py`), para
alimentar `registrar_template.py` / MANIFEST.