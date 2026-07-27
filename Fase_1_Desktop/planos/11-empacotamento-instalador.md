# F1-11 — Empacotamento e instalador

Como o app desktop vira um `.exe` instalável no Windows 10/11. Cobre o Electron, o sidecar Python,
a decisão de empacotamento (P1), auto-update (P2), assinatura/SmartScreen e a meta de tamanho
(P5). Sem Vercel, Render nem qualquer infraestrutura de nuvem — tudo roda no PC do usuário.

Referências: [arquitetura](01-arquitetura.md), [segurança](../../planos/05-seguranca-e-segredos.md),
[testes anel 3](10-testes-e-qa.md#anel-3--windows).

## Visão geral

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  MapasFacil-Setup-1.0.0.exe  (NSIS, assinado)                               │
│  ├─ Mapas Facil.exe              Electron main + renderer (React)           │
│  ├─ resources\                                                              │
│  │  ├─ app.asar                  UI empacotada                                │
│  │  └─ nucleo\                   PyInstaller onedir (decisão P1)            │
│  │     ├─ nucleo.exe             sidecar Python 3.12                          │
│  │     ├─ _internal\             shapely, pyproj, fiona, matplotlib…        │
│  │     └─ shared\                catálogo, schema MapSpec, templates        │
│  ├─ arcpy_job.py                 copiado ao lado; invocado pelo ArcMap 2.7   │
│  └─ uninstall.exe                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

O instalador entrega **um produto só**: Electron e núcleo sobem juntos, com `versao_nucleo`
conferida no boot (`UI-010` se incompatível). Não há matriz de compatibilidade entre versões
do shell e do núcleo.

## Stack de empacotamento

| Componente | Ferramenta | Notas |
|---|---|---|
| UI (React) | `electron-vite` ou equivalente | bundle no `app.asar` |
| App Electron | `electron-builder` | NSIS no Windows; gera `.exe` + `latest.yml` |
| Núcleo Python | **PyInstaller onedir** | ver decisão P1 abaixo |
| Instalador | NSIS via `electron-builder` | atalho, desinstalador, `%APPDATA%` na primeira execução |
| Auto-update | `electron-updater` | canal `stable` / `beta`; feed assinado |
| Assinatura | Authenticode (certificado EV ou OV) | ver SmartScreen |

## P1 — PyInstaller: onedir vs onefile

| Critério | *onedir* | *onefile* |
|---|---|---|
| Tamanho no disco | ~120–150 MB (núcleo) | ~90 MB (arquivo único) |
| Tempo de boot do sidecar | < 2 s (direto) | 5–15 s (extrai para `%TEMP%` a cada execução) |
| Antivírus | menos falso positivo | mais falso positivo (extração em runtime) |
| Atualização parcial | possível trocar só `nucleo/` | impossível — troca o blob inteiro |
| Debug em campo | pasta visível, logs legíveis | extração opaca |

**Decisão: onedir.** O sidecar sobe a cada abertura de pasta e a cada job de mapa; latência de
boot pesa mais que ~30 MB a menos no instalador. O núcleo fica em
`resources/nucleo/` ao lado do `.exe`, não num único blob.

Se o instalador passar de 250 MB (P5), cortar primeiro: remover wheels não usados, comprimir
templates, LFS fora do bundle — não voltar para onefile.

### O que entra no bundle do núcleo

| Incluir | Excluir |
|---|---|
| `shapely`, `pyproj`, `fiona`, `rasterio`, `matplotlib`, `PyMuPDF`, `openpyxl`, `httpx`, `lxml` | `arcpy` (vem do ArcMap do usuário) |
| `shared/` (catálogo, schema, perfil Harmonia) | `Referencias_IMAP/` inteiro — só templates referenciados no manifesto |
| `arcpy_job.py` (script isolado, não empacotado no PyInstaller) | fixtures de teste, `secrets.*`, código de dev |

`arcpy_job.py` **não** passa pelo PyInstaller: é um `.py` puro copiado pelo instalador e invocado
pelo Python 2.7 do ArcMap com argumentos fixos e payload em JSON.

## Artefatos do instalador

### Saída do build

| Artefato | Uso |
|---|---|
| `MapasFacil-Setup-<semver>.exe` | distribuição manual e auto-update |
| `MapasFacil-Setup-<semver>.exe.blockmap` | delta update (`electron-updater`) |
| `latest.yml` | metadados do feed (versão, sha512, data) |
| `sha256.txt` | hash publicado na release do GitHub — verificação manual |
| `MapasFacil-<semver>-win-x64.zip` | portátil, **sem** auto-update; só para suporte |

### Estrutura pós-instalação

```
C:\Program Files\Mapas Facil\
├─ Mapas Facil.exe
├─ resources\
│  ├─ app.asar
│  └─ nucleo\
│     ├─ nucleo.exe
│     ├─ _internal\
│     └─ shared\
├─ arcpy_job.py
└─ uninstall.exe

%APPDATA%\MapasFacil\              ← dados do usuário (roaming)
├─ config.json
├─ projetos\<hash>\
│  ├─ conversas.sqlite
│  ├─ mapspecs.sqlite
│  └─ jobs.sqlite
└─ logs\                           rotacionado, 7 dias

%LOCALAPPDATA%\MapasFacil\         ← cache e trabalho temporário
├─ cache\                          WFS, WMS, tiles, malha IBGE
└─ tmp\<job_id>\                   trabalho do ArcPy; limpo ao final
```

| Path | O que guarda | Backup? |
|---|---|---|
| `%APPDATA%\MapasFacil\` | preferências, histórico de chat, versões de MapSpec | sim — é o que o usuário perde ao desinstalar sem exportar |
| `%LOCALAPPDATA%\MapasFacil\` | cache e tmp | não — recriável |
| Pasta do projeto (escolhida pelo usuário) | shapes, mapas gerados, `.mxd`, `.pdf` | responsabilidade do usuário |

Na desinstalação: NSIS pergunta se apaga `%APPDATA%\MapasFacil\`. `%LOCALAPPDATA%` sempre
apagado.

## Credential Manager

Segredos **nunca** vão para `config.json`, registro nem arquivo texto. O fluxo:

```
1. Primeira execução (ou Doctor) detecta chave ausente
2. UI pede a chave → IPC → main process grava no Credential Manager
3. Núcleo chama cofre.definir / cofre.testar via JSON-RPC
4. Main lê do Credential Manager e injeta no sidecar sob demanda
5. Valor nunca volta para o renderer nem para log
```

| Chave | Target no Credential Manager | Obrigatória? |
|---|---|---|
| `deepseek_api_key` | `MapasFacil/deepseek_api_key` | não — modo determinístico sem IA |
| `sema_authkey` | `MapasFacil/sema_authkey` | não — WFS público onde existir; aviso se faltar |
| `planet_api_key` | `MapasFacil/planet_api_key` | não — basemap Esri ou sem basemap |

Regras (de [`05-seguranca-e-segredos.md`](../../planos/05-seguranca-e-segredos.md)):

- default vazio, sempre — chave ausente → erro claro, nunca fallback embutido;
- redator de URL antes de qualquer log;
- aviso na primeira geração de `.mxd` com basemap autenticado (chave do usuário no arquivo).

Testes no anel 3: gravar, confirmar existência, apagar, sobreviver a reinício do app.

## Assinatura e SmartScreen

Sem certificado Authenticode, o Windows SmartScreen exibe *"O Windows protegeu seu PC"* e a
maioria dos técnicos desiste na instalação. Isso é S1 de adoção, não cosmético.

| Item | Detalhe |
|---|---|
| Certificado | OV (~US$ 200/ano) no mínimo; EV elimina o aviso imediato mas custa mais |
| O que assinar | o `.exe` do setup **e** o `Mapas Facil.exe` + `nucleo.exe` |
| Timestamp | RFC 3161 — assinatura válida após expiração do certificado |
| `sha256` público | publicado na release do GitHub; suporte pode pedir ao usuário para conferir |
| Ameaça A8 | instalador adulterado → mitigado por assinatura + hash publicado |

**Dívida aceita na v1 beta:** distribuir sem assinatura para piloto interno, com instrução
*"Mais informações → Executar mesmo assim"*. Release pública exige certificado.

## P2 — Auto-update

`electron-updater` com feed hospedado na release do GitHub (ou bucket próprio). O núcleo vai
**dentro** do instalador — não há update separado do Python.

| Abordagem | Prós | Contras |
|---|---|---|
| Substituir o `.exe` inteiro | simples; sem drift de versão | download maior (~200 MB) |
| Delta via `.blockmap` | download de 20–40 MB em patch | mais complexo; testar bem |

**Decisão provisória: delta quando possível, fallback para full.** O `electron-updater` já faz
isso com o `.blockmap`. O núcleo onedir entra no mesmo pacote — não há update parcial só do
`nucleo.exe` na v1 (evita `UI-010` por metade atualizada).

Fluxo:

```
1. App verifica latest.yml no boot (ou a cada 24 h)
2. Se há versão nova e canal compatível → notifica o usuário
3. Download em background → verifica assinatura
4. Na próxima reinicialização: instala e relança
5. Se o núcleo não subir após update → rollback automático para a versão anterior
```

Canal `beta` para piloto; `stable` para release. Usuário escolhe em `config.json`.

## P5 — Meta de tamanho: < 250 MB

Orçamento estimado do instalador comprimido:

| Componente | Tamanho estimado |
|---|---|
| Electron + Chromium + React | ~80 MB |
| Núcleo Python onedir (libs geo) | ~120 MB estimado; **~247 MB** medido no Linux (matplotlib/shapely/pymupdf) — NSIS comprime |
| Templates `.mxd` + manifesto | ~15 MB |
| `arcpy_job.py` + assets | < 1 MB |
| **Total** | **medir no 1º build CI** (meta P5 &lt; 250 MB comprimido) |

Se passar de 250 MB:

1. `pip install` auditado — remover dependências não usadas no runtime.
2. Templates: só os referenciados no manifesto da v1 (não os 24 do acervo).
3. UPX no `nucleo.exe` — testar impacto em antivírus antes de adotar.
4. Não usar onefile para "economizar" — troca tamanho por latência.

## Ciclo de vida do sidecar

```
boot do app
  → main spawna nucleo.exe com stdio pipe
  → handshake: {"metodo":"doctor.rodar"} → confere versao_nucleo
  → sidecar fica vivo enquanto o app estiver aberto
  → ao fechar pasta / app: SIGTERM → timeout 5 s → kill

job de mapa
  → mesmo sidecar; job.progresso via evt
  → subprocesso ArcPy separado (Python 2.7), com timeout próprio
  → tmp em %LOCALAPPDATA%\MapasFacil\tmp\<job_id>\
```

Se o núcleo morrer no meio de um job (P4 da arquitetura): marcar job como falho (`NU-0xx`),
mostrar na UI com opção de retry — **não** retomar etapa parcial na v1.

## Checklist de aceite

### Build

- [ ] `MapasFacil-Setup-<semver>.exe` instala em `C:\Program Files\Mapas Facil\` sem admin elevado
      quando possível (per-user install como fallback)
- [ ] Atalho no menu Iniciar e opcional na área de trabalho
- [ ] Desinstalação limpa: remove arquivos do programa; pergunta sobre `%APPDATA%`
- [ ] Instalador + binários assinados (release pública) ou documentado como exceção (piloto)
- [ ] `sha256.txt` publicado na release

### Runtime

- [ ] App abre, núcleo sobe, `doctor.rodar` responde em < 5 s
- [ ] `versao_nucleo` conferida — mismatch → `UI-010` com instrução de reinstalar
- [ ] Caminho com acento e espaço funciona em todo o pipeline
- [ ] Credential Manager: gravar chave DeepSeek, reiniciar app, chave persiste
- [ ] Primeira pasta aberta cria `%APPDATA%\MapasFacil\projetos\<hash>\`
- [ ] Cache em `%LOCALAPPDATA%\MapasFacil\cache\` com TTL respeitado
- [ ] T2 completo roda numa máquina **sem ArcMap** após instalação limpa

### Auto-update

- [ ] `latest.yml` aponta para a versão correta
- [ ] Update de N→N+1 instala e o app abre normalmente
- [ ] Update com núcleo incompatível faz rollback ou bloqueia com mensagem clara
- [ ] Canal `beta` não oferece update `stable` e vice-versa

### Segurança

- [ ] Nenhum segredo em `config.json`, registro ou log
- [ ] `fsguard` ativo no núcleo empacotado (não só no dev)
- [ ] Modo determinístico funciona sem chave DeepSeek após instalação limpa

## Riscos

| Risco | Impacto | Mitigação |
|---|---|---|
| PyInstaller quebra import dinâmico de lib geo | alto | `hiddenimports` explícito; smoke test `doctor.rodar` no CI Windows |
| Instalador > 250 MB | médio | auditoria de deps; templates mínimos |
| SmartScreen bloqueia adoção | alto | certificado Authenticode antes da release pública |
| Antivírus marca `nucleo.exe` | médio | assinatura; evitar UPX; submeter falso positivo aos vendors |
| Delta update corrompe instalação | alto | verificação de assinatura; rollback; full update como fallback |
| `%LOCALAPPDATA%` cheio por tmp órfão | baixo | limpeza no boot de tmp com mais de 24 h |
| Usuário instala em drive sem espaço para cache WFS | médio | Doctor verifica espaço livre; aviso antes do primeiro download grande |
| ArcMap em path não padrão | médio | Doctor detecta; usuário aponta manualmente em `config.json` |

## Pendências

| # | Questão |
|---|---|
| P1 | ~~onedir vs onefile~~ — **decidido: onedir** |
| P2 | Provedor do certificado (OV vs EV) e data da primeira release assinada |
| P3 | Per-user install vs all-users como padrão |
| P4 | Hospedar feed de update só no GitHub Releases ou mirror próprio |
| P5 | Medir tamanho real do primeiro build e ajustar o orçamento |
