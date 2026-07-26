# 05 — Segurança, segredos e privacidade

Vale para as duas fases. Aqui ficam: o cofre de chaves, o que pode e o que não pode sair do PC
do usuário, o modelo de ameaças e o registro do incidente de chaves de 2026-07-25.

## Incidente 2026-07-25 — chaves dentro dos `.mxd`

**O que aconteceu.** Os 24 `.mxd` de `Referencias_IMAP/MXD/` foram commitados e publicados no
repositório **público** `github.com/alvaro209890/mapas-facil`. Um `.mxd` guarda a URL completa
das camadas de serviço, com a chave na query string. Resultado: **566 ocorrências de três
segredos** em texto claro num repositório público.

| Segredo | Onde | Ocorrências |
|---|---|---|
| Planet `api_key` (atual, prefixo `PLAK…`) | camada WMTS `tiles.planet.com/.../{mosaico}/gmap/...` | 310 |
| Planet `api_key` (anterior, hex de 32) | mesma camada, mosaicos até `2024_07` | 64 |
| SEMA `authkey` (UUID) | conexão WMS `geo.sema.mt.gov.br/geoserver/ows` | 192 |

**Decisão do dono do produto:** manter o repositório público e **não rotacionar** por ora, mas
tirar as chaves dos arquivos versionados e mantê-las funcionando neste PC de desenvolvimento.

**O que foi feito.**

1. As três chaves foram substituídas nos 24 `.mxd` por placeholders de **exatamente o mesmo
   comprimento**, em UTF-16LE, byte a byte.
2. As chaves reais ficaram em `secrets.local.json` — gitignored, só neste PC.
3. `ferramentas/chaves_mxd.py` faz o caminho de volta (`restaurar`) e de ida (`limpar`), com
   round-trip verificado byte a byte.

**Por que a substituição precisa ter o mesmo comprimento.** Um `.mxd` é um *Compound File Binary*
(OLE): o cabeçalho traz a tabela de setores e o tamanho de cada stream. Trocar N bytes por N
bytes não move nada. Trocar por um tamanho diferente corromperia o documento inteiro.

**Erro cometido e corrigido no caminho** (vale como lição): a primeira leva de placeholders usava
zeros — `PLAK000…0` (36) e `000…0` (32). O placeholder de 32 zeros virou substring do de 36, e
`restaurar` teria escrito a chave nova dentro da antiga. Os placeholders definitivos são
inequívocos, e `chaves_mxd.py verificar` **falha** se um for substring de outro.

### Estado atual e dívida

- [x] Chaves fora dos arquivos versionados
- [x] Ferramenta de restauração local, com round-trip testado
- [x] `secrets.local.json` no `.gitignore`
- [x] Varredura de `.mxd` recursiva sobre todo o acervo (2026-07-26)
- [x] Recibos do CAR com CPF/CNPJ fora do git (2026-07-26)
- [ ] **Rotacionar a `authkey` da SEMA** — decisão adiada pelo dono
- [ ] **Rotacionar as `api_key` do Planet** — idem
- [ ] Hook de pre-commit rodando `chaves_mxd.py verificar`
- [ ] `gitleaks` no CI, com regra para `.mxd` (UTF-16)

As chaves antigas continuam no histórico do git (commits `a81c1f4` até o commit que as zerou).
Rotacionar é a única forma de matá-las de fato. Enquanto não for feito, o risco é: qualquer
pessoa que clone o repositório consegue consumir a cota Planet e o WMS da SEMA em nome do dono.

### Quase-repetição 2026-07-25

Pasta nova de referência (o material que hoje é `Referencias_IMAP/Mapas/06/`) chegou ao acervo
com o **mesmo padrão de chave real embutida** (`planet_api_key_antiga`, 4 ocorrências no
`.mxd`) — `chaves_mxd.py` só olhava `Referencias_IMAP/MXD/`, então não pegou automaticamente.
Detectado antes do commit por grep manual da chave real, **não pelo hook — porque o hook nunca
foi implementado** (ver dívida acima). Os outros ~30 `.mxd` que vieram na mesma leva também
tinham chave real e ficaram fora daquele commit.

### Fechamento 2026-07-26 — acervo organizado e limpo

Ao dissolver o material do OneDrive no esquema `Referencias_IMAP/Mapas/NN/`, os 30 `.mxd`
restantes foram limpos: **177 ocorrências** de `planet_api_key_antiga` e `sema_authkey`
substituídas por placeholder, verificadas por dois caminhos independentes (`chaves_mxd.py
verificar` e varredura direta das chaves de `secrets.local.json` sobre todo `.mxd` do acervo).

Duas mudanças estruturais para a falha não se repetir:

1. **`MXD_DIRS` virou recursivo** (`rglob`) sobre `Referencias_IMAP/MXD/` e
   `Referencias_IMAP/Mapas/`. Pasta `Mapas/NN/` nova entra sozinha — o modo antigo exigia
   lembrar de editar uma lista, e foi exatamente isso que falhou em 2026-07-25.
2. **Recibos do CAR não são versionados.** Os 4 PDFs `CAR - Recibo_*.pdf` que vieram com o
   acervo novo contêm **CPF e CNPJ de proprietários reais**; o repositório é público. Entraram
   no `.gitignore` (`Referencias_IMAP/**/CAR - Recibo*.pdf`) e ficam só no disco local.
   Nenhum recibo jamais foi commitado neste repositório — a regra agora é explícita, não
   acidental.

O item "hook de pre-commit rodando `chaves_mxd.py verificar`" **continua pendente** e continua
sendo a única defesa automática. A varredura recursiva reduz a chance de erro; não elimina.

## Cofre de segredos

### Onde cada segredo vive

| Segredo | Fase 1 (desktop) | Fase 2 (site/backend) | Nunca |
|---|---|---|---|
| `deepseek_api_key` | Windows Credential Manager | variável de ambiente do serviço | no `MapSpec`, no log, no repositório |
| `sema_authkey` | Windows Credential Manager | env do backend | em `.mxd` versionado, em URL de log |
| `planet_api_key` | Windows Credential Manager | env do backend | idem |
| `sccon_bearer` | fora da v1 | fora da v1 | — |
| `senha_hash` da conta local (Argon2id) | só em `%APPDATA%\MapasFacil\contas\contas.sqlite` | — | em claro, no renderer, em log, em `config.json` |
| `access_token` / `refresh_token` de conta **nuvem** | **não na v1 do desktop** (F1-14 local) | se Fase 2 existir: só no servidor | no renderer / instalador |
| Segredos OAuth Google / JWT de identidade nuvem | **não no desktop v1** | só se F2-05 for reaberto pós-M11 | no repositório, no instalador |

Detalhe da conta **local** do desktop: [F1-14](../Fase_1_Desktop/planos/14-auth-e-conta.md).
Conta nuvem / memória (adiada): [F2-05](../Fase_2_Site/planos/05-auth-e-memoria.md).

Neste PC de desenvolvimento, todos vivem em `secrets.local.json` na raiz do repositório —
gitignored, jamais commitado. Template público: `secrets.example.json`.

**DeepSeek (teste local, 2026-07-26).** O campo `deepseek_api_key` em `secrets.local.json` traz a
chave de teste do dono para implementar e exercitar o marco M7 neste Acer. Agentes implementadores:
leia [`AGENT_BRIEF.md`](../AGENT_BRIEF.md) (§Chave DeepSeek para desenvolvimento e testes). O valor
**não** entra em commit, log, `MapSpec` nem prompt de exemplo em markdown versionado.

### Regras invioláveis

1. **Default vazio, sempre.** Nenhum segredo tem valor default no código. Chave ausente →
   erro claro com instrução, nunca fallback silencioso para uma chave embutida.
   *(Dívida conhecida do GeoForest: `geoforest-backend.env.example` tem `authkey` hardcoded.
   Não se replica aqui.)*
2. **Segredo nunca entra no `MapSpec`.** O spec pede `basemap.tipo = "planet_mensal"`; o motor
   busca a chave no cofre e monta a URL. Assim o `MapSpec` pode ser logado, versionado e enviado
   entre máquinas sem risco.
3. **Log com redação.** Toda URL de serviço passa por um redator que troca
   `api_key=…`/`authkey=…` por `***` antes de escrever em log, telemetria ou mensagem de erro.
4. **`.mxd` gerado leva placeholder ou a chave do próprio usuário** — nunca a chave do
   desenvolvedor. Ver a decisão abaixo.

### O `.mxd` entregue e a chave do basemap

Problema real: o `.mxd` precisa da chave dentro dele para o basemap desenhar no ArcMap do
cliente. Três caminhos, e a escolha:

| Caminho | Consequência |
|---|---|
| Gravar a chave do usuário no `.mxd` | funciona; a chave é dele, e ele decide com quem compartilha o arquivo. **Escolhido**, com aviso explícito na primeira geração |
| Gravar placeholder | `.mxd` abre sem basemap; o cliente vê fundo branco. Vira opção `basemap_sem_chave: true` |
| Não incluir camada de basemap | o PDF sai com fundo (renderizado na geração) mas o `.mxd` não. Confuso |

Decisão: **chave do usuário no `.mxd`, com aviso.** A primeira vez que o app grava um `.mxd` com
basemap autenticado, mostra: *"este `.mxd` contém sua chave Planet. Quem receber o arquivo pode
usá-la."* Com opção de gravar sem a chave.

## Privacidade dos dados do cliente

### Fase 1 — nada sai da máquina

O app desktop é local por construção. Os shapefiles do imóvel, o recibo do CAR e os mapas
gerados **nunca saem do PC**, com exatamente três exceções, todas necessárias e explícitas:

| Sai | Para onde | Conteúdo | Controle |
|---|---|---|---|
| Prompt do chat | `api.deepseek.com` | texto da conversa + resumo estruturado do projeto (nomes de arquivo, campos, áreas em ha, município, nº do CAR) | opt-out por projeto; modo determinístico sem IA |
| Consulta geoespacial | SEMA, IBAMA, FUNAI, IBGE, MapBiomas, INCRA | **bbox** do imóvel e nº do CAR | necessário para o mapa; cache reduz repetição |
| Tiles de basemap | Planet / Esri | coordenadas dos tiles | idem |

**Geometria completa nunca é enviada ao provedor de IA.** O que vai é o resumo: quantas feições,
que campos, área total, bbox arredondado. Suficiente para a IA decidir o mapa, insuficiente para
reconstruir o imóvel.

### O que exatamente vai para a DeepSeek

Contexto montado a cada turno, com teto de tamanho:

```
- Pasta do projeto: nomes de arquivo, tipo de geometria, CRS, contagem de feições, campos
- Imóvel: nome, nº do CAR, município/UF, área total (do recibo)
- Quantitativos já calculados (ha por classe)
- MapSpec atual (sem segredos)
- Histórico da conversa
- Catálogo de camadas, estilos e templates disponíveis
```

Nunca vai: coordenada de vértice, CPF/CNPJ do proprietário, conteúdo integral do recibo, caminho
absoluto do disco (só o caminho relativo à pasta do projeto).

O recibo do CAR **contém CPF do proprietário**. O parser extrai nome do imóvel, município, área e
número do CAR; **o CPF é descartado na entrada**, não apenas omitido do prompt.

### Verificação automática do que vai para a DeepSeek

A regra acima só vale se for testada. `nucleo/tests/test_contexto_vazamento.py` roda sobre o JSON
serializado do request e falha se encontrar:

| Padrão | Regex |
|---|---|
| Geometria | `(MULTI)?POLYGON\s*\(\(` , `"coordinates"\s*:` |
| CPF | `\d{3}\.?\d{3}\.?\d{3}-?\d{2}` |
| Caminho absoluto do Windows | `[A-Za-z]:\\\\Users\\\\` |
| Chave Planet / authkey | `PLAK` , `authkey` |
| Token de sessão | `eyJ` (prefixo de JWT), `Bearer ` |

Orçamento, compressão e a lista fechada do que nunca entra no contexto:
[F1-06](../Fase_1_Desktop/planos/06-agente-eng-florestal.md#orçamento-de-contexto-vinculante).

### Conversas gravadas no disco do usuário

O histórico local (`%APPDATA%\MapasFacil\chats\chats.sqlite`) é dado do usuário, não do produto:

| Regra | Como se cumpre |
|---|---|
| Sem CPF e sem chave no transcript | redator aplicado **antes do INSERT**, nunca só na exibição |
| Sem sincronização para nuvem na v1 | D20 — não existe código de upload; `grep -rn "https://" nucleo/.../conversas/` tem de ficar vazio |
| Logout não apaga o histórico | D14 — apagar é ação explícita "Sair e esquecer este PC", com confirmação digitada |
| Não gravar dentro da pasta do cliente | o `.zip` de entrega não pode levar o histórico junto |

Detalhe: [F1-17](../Fase_1_Desktop/planos/17-persistencia-de-conversas.md).

### Fase 2 — o mínimo no servidor

O backend guarda: conta, projetos, conversas, `MapSpec`, metadados de job e — só com opt-in
explícito — o `preview.png`. Shapefile de cliente **não** é armazenado; quando o usuário sobe um
`.zip` para gerar um mapa pelo site, ele é processado em pasta temporária e apagado ao fim do
job, com TTL máximo de 24 h.

## Modelo de ameaças

| # | Ameaça | Vetor | Mitigação |
|---|---|---|---|
| A1 | Execução de código arbitrário no PC do usuário | IA ou backend mandando script para o núcleo executar | o núcleo **só** aceita `MapSpec` declarativo validado por schema; não existe caminho que execute string vinda de fora |
| A2 | Leitura/escrita fora da pasta autorizada | caminho malicioso no `MapSpec` (`../../`) | `fsguard`: todo caminho é resolvido (`realpath`) e conferido contra a allowlist do workspace **antes** de qualquer I/O. Symlink que aponta para fora é recusado |
| A3 | SSRF via camada de catálogo | `fonte` com URL arbitrária | `fonte` é `local.<id>` ou `catalogo.<id>`; URL só existe dentro do catálogo versionado |
| A4 | Injeção de SQL no `definitionQuery` | filtro livre vindo da IA | filtro é objeto `{campo, operador, valor}`; campo validado contra o schema do shapefile, operador contra allowlist, valor escapado |
| A5 | Prompt injection via arquivo da pasta | nome de arquivo, campo de `.dbf` ou texto de PDF instruindo a IA | conteúdo de arquivo entra no prompt como **dado delimitado**, com instrução explícita de não obedecer; nenhuma tool destrutiva existe |
| A6 | Vazamento de chave por log | URL com `authkey` num traceback | redator de URL antes de qualquer escrita de log |
| A7 | Backend da Fase 2 comprometido vira RCE no desktop | backend manda job malicioso | o desktop não aceita comando remoto na v1. Se a ponte existir, ela transporta `MapSpec` validado localmente de novo |
| A8 | Instalador adulterado | download de terceiro | binário assinado + `sha256` publicado; atualização só por canal assinado |
| A9 | Exposição do backend pelo tunnel | Cloudflare Tunnel publica o serviço | tunnel dedicado, só as duas hostnames do Mapas Fácil; backend com auth em todas as rotas exceto healthcheck e o fluxo OAuth |
| A10 | **Senha de conta vazando** | senha/`senha_hash` no renderer, log ou `config.json` | auth só via IPC→núcleo; teste: senha de fixture ausente de `contas.sqlite` em claro e de `app/src/` |
| A11 | **Dump de `contas.sqlite`** | cópia do perfil do usuário | hash Argon2id (não reversível); sem senha em claro; backup do perfil é risco aceito do SO |
| A12 | **Sessão/conta no renderer além do necessário** | store React guarda hash ou senha | renderer só `{estado, conta:{id,email,nome}}` |

### A1 em detalhe

É a ameaça que decide a arquitetura. Se a IA pudesse mandar código para o núcleo executar,
comprometer a conta DeepSeek ou o backend significaria comprometer todos os PCs dos usuários.

Por isso: **o núcleo Python não tem `eval`, `exec`, `subprocess` com string de fora, nem
importação dinâmica por nome vindo de dado.** O único subprocesso é o Python 2.7 do ArcMap, com
argumentos fixos e o payload num arquivo JSON no disco.

## Superfície da Fase 2

- HTTPS obrigatório (o tunnel já termina TLS).
- Autenticação em todas as rotas, exceto `/health`.
- CORS restrito à origem do site.
- Rate limit por conta e por IP.
- Cabeçalhos: `Content-Security-Policy`, `X-Content-Type-Options`, `Referrer-Policy`,
  `Strict-Transport-Security`.
- Upload: tipo e tamanho validados, `.zip` inspecionado antes de extrair (anti *zip slip*).
- Nada de `eval` sobre entrada, nada de template string em SQL — só query parametrizada.

## Auditoria

`audit_log` append-only na Fase 2, e log local rotacionado na Fase 1:

| Evento | Registrado |
|---|---|
| Pasta de trabalho autorizada/revogada | sempre |
| Job de mapa criado / concluído / falhado | sempre, com `MapSpec` id e versão |
| Chamada a serviço externo | endpoint, layer, bbox, contagem — **URL redigida** |
| Prompt enviado à IA | tamanho e hash, não o conteúdo |
| Chave lida do cofre | qual chave, nunca o valor |
| Arquivo escrito em disco | caminho relativo à pasta do projeto |

## Checklist de segurança pré-release

### Fase 1

- [ ] `fsguard` com suíte de testes cobrindo `..`, caminho absoluto, symlink, UNC, drive
      diferente, nome reservado do Windows (`CON`, `NUL`, `AUX`)
- [ ] Nenhum `eval`/`exec`/`subprocess(shell=True)` no núcleo — verificado por lint
- [ ] Redator de URL cobrindo `api_key`, `authkey`, `token`, `Bearer`
- [ ] Chaves só no Windows Credential Manager; nunca em arquivo texto do usuário
- [ ] CPF descartado na entrada do parser de recibo
- [ ] Aviso de chave embutida antes de gravar `.mxd` com basemap autenticado
- [ ] Instalador assinado; `sha256` publicado
- [ ] Modo determinístico sem IA funciona de ponta a ponta
- [ ] Senha de conta nunca em claro no SQLite nem no renderer; `grep` da senha de teste = 0 em `contas.sqlite` e em `app/src/`
- [ ] Redator cobre `Authorization`, `Bearer` e nunca loga campo `senha`
- [ ] Teste de vazamento de contexto verde (regexes da tabela acima)
- [ ] Redator de CPF aplicado **antes do INSERT** em `chats.sqlite`; `grep -a` do CPF no arquivo vazio
- [ ] Nenhum caminho de rede em `nucleo/mapasfacil_nucleo/conversas/`

### Fase 2 (pós-M11 — se/quando conta nuvem existir)

- [ ] Rotas autenticadas conforme o desenho **então** vigente (não copiar OAuth antigo às cegas)
- [ ] Nenhuma tabela de quota/plano/cobrança (D18 / AP-05)
- [ ] Tunnel dedicado; configs de outros sistemas **intocados**
- [ ] Segredos só em env do serviço, permissão restrita
- [ ] Upload de `.zip` com verificação anti *zip slip*
- [ ] Backup do Postgres com segredo fora do dump

### Repositório

- [ ] `chaves_mxd.py verificar` no pre-commit
- [ ] `gitleaks` no CI, com regra UTF-16 para `.mxd`
- [ ] `secrets.local.json`, `.env*`, `*.pem`, `*.key` no `.gitignore` — conferido
- [ ] Nenhum caminho absoluto de PC de desenvolvedor em arquivo versionado

## Pendências

| # | Questão |
|---|---|
| P1 | Rotacionar as três chaves — decisão adiada; enquanto não, elas vivem no histórico do git |
| P2 | Assinatura de código Windows custa ~US$ 200/ano. Sem ela, o SmartScreen assusta o usuário |
| P3 | Telemetria opt-in: quais métricas justificam o custo de privacidade? |
| P4 | Um `.mxd` gerado com a chave do usuário e compartilhado com o cliente vaza a chave. Documentar em texto de contrato, não só em aviso de UI |
| P5 | LGPD: o recibo do CAR tem dado pessoal. Definir política de retenção do PDF na pasta de trabalho |
