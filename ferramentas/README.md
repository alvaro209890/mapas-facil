# Ferramentas do repositório

Utilitários de manutenção do acervo versionado. **Não** fazem parte do produto instalado —
servem ao desenvolvedor.

**No Windows com ArcMap:** o roteiro completo (quando rodar cada script) está em
[`../Fase_1_Desktop/GUIA_WINDOWS.md`](../Fase_1_Desktop/GUIA_WINDOWS.md).

Scripts presentes:

| Script | Função |
|---|---|
| `chaves_mxd.py` | remove/reinjeta chaves de API nos `.mxd` versionados |
| `deepseek_smoke.py` | smoke manual da chave DeepSeek (dev local; **não** roda no CI) |
| `inspecionar_mxd_arcpy.py` | diagnóstico de layout (requer ArcMap) |
| `normalizar_mxd_arcpy.py` | B1 automatizado parcial (renomear elementos) |
| `preparar_sentinelas_arcpy.py` | sentinelas de extent/escala para offsets |
| `inspecionar_mxd_offsets.py` | lê offsets/sentinelas do `.mxd` |
| `registrar_template.py` | grava sha256/offsets no MANIFEST |
| `recuperar_zip_truncado.py` | recupera ZIP sem diretório central |
| `remover_planet_mxd_arcpy.py` | remove camadas Planet/WMTS quebradas dos `.mxd` (ArcMap 10.8) |
| `fechar_dialogs_gis.ps1` | cancela o diálogo *GIS Server Connection* automaticamente |
| `salvar_mxd_gui.ps1` | abre cada `.mxd`, fecha diálogos, salva na GUI do ArcMap |

Procedimento completo (remoção + salvar na GUI para a janelinha não voltar):
[`../docs/remocao-planet-mxd.md`](../docs/remocao-planet-mxd.md).

## `chaves_mxd.py`

Remove ou reinjeta as chaves de API embutidas nos `.mxd` do acervo. Cobre
[`Referencias_IMAP/MXD/`](../Referencias_IMAP/MXD/) e
[`Referencias_IMAP/Mapas/`](../Referencias_IMAP/Mapas/) — **recursivamente** desde 2026-07-26,
então uma pasta `Mapas/NN/` nova já entra sozinha e ninguém precisa lembrar de editar
`MXD_DIRS`. O que **ninguém pode esquecer** é de *rodar* o comando: todo `.mxd` que chega do
escritório traz chave real embutida.

Histórico que motivou o modo recursivo: em 2026-07-25 a varredura era rasa e por pasta
listada; chave real (`planet_api_key_antiga`) estava embutida nos 31 `.mxd` do material novo e
só a de `Divisão de talhões` foi limpa a tempo. Em 2026-07-26, ao organizar o acervo em
`Mapas/04–06`, os outros 30 `.mxd` foram limpos de uma vez — **177 ocorrências** de
`planet_api_key_antiga` e `sema_authkey`.



### Contexto

Os `.mxd` do acervo IMAP guardam, dentro das camadas WMTS (Planet) e WMS (GeoServer da SEMA), a
chave de API em texto claro — 566 ocorrências no achado original (24 `.mxd` de
`Referencias_IMAP/MXD/`), mais 177 no material organizado em 2026-07-26, **747 no total**. O
repositório é público, então a versão versionada dos `.mxd` tem as chaves zeradas por
**placeholders do mesmo comprimento**.

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

| Chave em `secrets.local.json` | Placeholder / nota |
|---|---|
| `planet_api_key` | `PLAK_CHAVE_REMOVIDA_VER_FERRAMENTAS_` |
| `planet_api_key_antiga` | `PLANET_ANTIGA_CHAVE_REMOVIDA_VER` |
| `deepseek_api_key` | não tem placeholder em `.mxd`; chave de teste só em `secrets.local.json` neste PC — ver [`AGENT_BRIEF.md`](../AGENT_BRIEF.md) §DeepSeek |
| `sema_authkey` | `5ema4key-0000-0000-0000-remov1da0000` |

Cada placeholder tem exatamente o mesmo comprimento da chave real. O comando `verificar` confere
que nenhum placeholder é substring de outro.

### Incidente 2026-07-25

Os `.mxd` foram commitados com chaves em texto claro num repositório público. A decisão foi
manter o repo público, tirar as chaves dos arquivos versionados e documentar o procedimento.

Detalhes completos — segredos expostos, modelo de ameaças, LGPD — em
[`planos/05-seguranca-e-segredos.md`](../planos/05-seguranca-e-segredos.md#incidente-2026-07-25--chaves-dentro-dos-mxd).

## `deepseek_smoke.py`

Smoke **manual** da chave de teste em `secrets.local.json`. Não faz parte do pytest nem do CI
(o GitHub Actions não tem a chave; M7 usará provedor fake — ver F1-10 §anel 2).

```bash
python3 ferramentas/deepseek_smoke.py
```

Saída esperada: `OK — modelo=deepseek-v4-flash …`. Não imprime a chave. Estado dos testes
automatizados: [`AGENT_BRIEF.md`](../AGENT_BRIEF.md) §Testes que dependem da chave.

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