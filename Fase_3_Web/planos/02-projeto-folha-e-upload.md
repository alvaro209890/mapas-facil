# W-02 — Projeto, folha e importação do `.zip`

## Objetivo

Definir o que é um **projeto** (no banco e no disco), como ele nasce com **folha** e
**orientação**, e como **um `.zip`** enviado pelo navegador vira uma pasta de trabalho que o
núcleo indexa — com segurança contra ZIP malicioso, sem perder byte e com progresso real.

## Estado atual vs alvo

| Item | Hoje | Alvo |
|---|---|---|
| Projeto | no desktop é "a pasta conectada" (`electron/projetos.ts`) | linha em `projetos` + pasta `dados/projetos/<id>/` |
| Folha | só A4, fixa pelo template (`MANIFEST.json → formato_pagina`) | escolhida na criação, gravada no projeto e no `MapSpec.folha` (D36) |
| Entrada | pasta do PC; o núcleo lê `.shp`, `.zip` do SIMCAR, recibo PDF | um `.zip` enviado; extraído em `entrada/`; o núcleo lê igual |
| Indexação | `workspace.abrir` + `workspace/indice.py`, `papeis.py`, `recibo_car.py`, `zip_simcar.py` | **a mesma**, chamada pela ponte |

## Dependências

[W-01](01-arquitetura.md) (pastas e env), [W-04](04-ponte-nucleo-servidor.md) (worker sobe e
indexa), [W-11](11-seguranca-contas-e-lgpd.md) (dono do projeto, CPF).

## Contratos

### Folhas

Série ISO 216 A. Medidas em mm, **retrato** (largura × altura). Paisagem troca os dois.

| `formato` | Retrato (mm) | Fator `k` sobre a A4 (D31) | Uso típico |
|---|---|---|---|
| `A4` | 210 × 297 | 1 | laudo, anexo de processo SEMA (padrão) |
| `A3` | 297 × 420 | √2 ≈ 1,4142 | anexo ampliado, imóvel alongado |
| `A2` | 420 × 594 | 2 | prancha de escritório |
| `A1` | 594 × 841 | 2√2 ≈ 2,8284 | prancha de parede |
| `A0` | 841 × 1189 | 4 | painel, imóvel muito grande com detalhe |

`k` é calculado como `largura_folha_mm / 210` (retrato) e é o fator que o perfil derivado usa
([W-09](09-motor-pdf-nativo-e-folhas.md)). Tolerância de página (check H15): ±1 mm em cada eixo.

Bloco `folha` no `MapSpec` v3 (D36) — o mesmo objeto é gravado no projeto:

```json
"folha": { "formato": "A3", "orientacao": "paisagem", "escala_elementos": "proporcional" }
```

| Campo | Tipo | Regra |
|---|---|---|
| `formato` | enum `A4`,`A3`,`A2`,`A1`,`A0` | obrigatório |
| `orientacao` | enum `retrato`,`paisagem` | obrigatório |
| `escala_elementos` | enum `proporcional` | só esse valor na v1 (reservado para `legivel` no futuro; D31) |

Larguras/alturas **não** vão no `MapSpec`: são derivadas da tabela acima por uma função única
`folha_mm(formato, orientacao) -> (largura, altura)` em `mapasfacil_nucleo/motores/folhas.py`
(nova, W1). Servidor e web importam/espelham essa tabela; o teste `test_folhas_espelho` compara
o JSON exportado pelo núcleo (`python -m mapasfacil_nucleo folhas --json`) com a constante da web.

### Banco — tabelas do projeto (SQLite, `banco/migracoes/0001_inicial.sql`)

```sql
CREATE TABLE projetos (
  id               TEXT PRIMARY KEY,              -- ULID
  dono_id          TEXT NOT NULL REFERENCES usuarios(id),
  nome             TEXT NOT NULL CHECK (length(nome) BETWEEN 1 AND 120),
  folha_formato    TEXT NOT NULL CHECK (folha_formato IN ('A4','A3','A2','A1','A0')),
  folha_orientacao TEXT NOT NULL CHECK (folha_orientacao IN ('retrato','paisagem')),
  estado           TEXT NOT NULL CHECK (estado IN
                     ('aguardando_zip','importando','indexando','pronto','erro_importacao','lixeira')),
  erro_codigo      TEXT,                          -- SV-1xx/NU-xxx quando estado = erro_importacao
  imovel_json      TEXT,                          -- resumo SEM CPF: nome, car, municipio, uf, ibge, area_ha
  conversa_id      TEXT,                          -- id da conversa principal no chats.sqlite do projeto
  versao_atual     INTEGER NOT NULL DEFAULT 0,    -- última versão de MapSpec com artefatos
  miniatura        TEXT,                          -- caminho relativo de PNG da última versão
  bytes_entrada    INTEGER NOT NULL DEFAULT 0,
  criado_em        TEXT NOT NULL,                 -- ISO-8601 UTC com Z
  atualizado_em    TEXT NOT NULL,
  lixeira_em       TEXT
);
CREATE INDEX projetos_dono ON projetos(dono_id, estado, atualizado_em DESC);

CREATE TABLE versoes (
  projeto_id    TEXT NOT NULL REFERENCES projetos(id),
  versao        INTEGER NOT NULL,
  mapspec_id    TEXT NOT NULL,
  titulo        TEXT NOT NULL,
  folha_formato TEXT NOT NULL,
  folha_orientacao TEXT NOT NULL,
  conforme      INTEGER NOT NULL,                 -- 1 se todos os HARD passaram
  artefatos_json TEXT NOT NULL,                   -- [{tipo:"pdf",caminho:"Mapas/v003/Dinamica_2026.pdf",bytes,sha256}, …]
  validacao_json TEXT NOT NULL,                   -- resumo HARD/SOFT
  criado_em     TEXT NOT NULL,
  PRIMARY KEY (projeto_id, versao)
);

CREATE TABLE uploads (
  id          TEXT PRIMARY KEY,
  dono_id     TEXT NOT NULL REFERENCES usuarios(id),
  nome        TEXT NOT NULL,
  tamanho     INTEGER NOT NULL,
  sha256      TEXT,                               -- do arquivo montado, calculado pelo servidor no concluir
  parte_bytes INTEGER NOT NULL,
  partes_ok   TEXT NOT NULL DEFAULT '{}',         -- JSON {indice: sha256_hex_da_parte}
  estado      TEXT NOT NULL CHECK (estado IN ('recebendo','completo','consumido','expirado')),
  criado_em   TEXT NOT NULL,
  expira_em   TEXT NOT NULL                       -- +24 h
);
```

Máquina de estados do projeto (qualquer transição fora desta tabela é bug — `SV-090`):

| De | Para | Quem dispara |
|---|---|---|
| — | `aguardando_zip` | `POST /projetos` |
| `aguardando_zip` / `pronto` / `erro_importacao` | `importando` | `POST /projetos/{id}/importacao` |
| `importando` | `indexando` | extração terminou sem erro |
| `importando` | `erro_importacao` | SV-1xx na verificação/extração |
| `indexando` | `pronto` | `workspace.abrir` respondeu `ok` e há perímetro (ATP) reconhecido |
| `indexando` | `erro_importacao` | `workspace.abrir` falhou ou não achou perímetro (`SV-130`) |
| qualquer ≠ `lixeira` | `lixeira` | `DELETE /projetos/{id}` |
| `lixeira` | estado anterior | `POST /projetos/{id}/restaurar` (≤ 30 dias, P3) |

Reimportar com o projeto `pronto` é permitido: a entrada antiga vai para
`entrada.anterior/<carimbo>/`, as versões antigas continuam baixáveis e ganham o selo "entrada
anterior" na linha de versões.

### Pasta do projeto no disco

```
$MF_RAIZ/dados/projetos/<projeto_id>/          ← raiz do workspace do núcleo (fsguard)
├── entrada.zip                  ← original enviado (somente leitura, 0440)
├── entrada/                     ← conteúdo extraído (somente leitura para o núcleo — fora de PASTAS_ESCRITA)
├── entrada.anterior/<carimbo>/  ← só depois de reimportação
├── _extraido/                   ← o núcleo extrai .zip do SIMCAR aninhado aqui (comportamento atual)
├── SHP/                         ← camadas materializadas pelo núcleo (comportamento atual)
├── MXD/                         ← .mxd e dados do pacote ArcMap (comportamento atual)
├── Mapas/
│   ├── v001/ … vNNN/            ← artefatos finais por versão (PDF, XLSX, PNG, validacao.json)
│   └── .preview/<job_id>/       ← GeoJSON/PNG intermediários do palco (W7); limpos 7 dias após o job
├── .estado/                     ← MAPASFACIL_DADOS: chats.sqlite, mapspecs/, índice
└── .servidor/
    ├── projeto.json             ← {id, nome, folha, dono} lido pelo núcleo em modo servidor
    └── eventos.ndjson           ← log de eventos com seq (W-03)
```

`PASTAS_ESCRITA` do núcleo (`config.py`: `Mapas`, `MXD`, `SHP`, `_extraido`) **não muda**.
`entrada/` fica de fora de propósito: nem o núcleo nem a IA conseguem alterar o dado de entrada.

> **Atenção (verificar no W1):** os artefatos por versão hoje saem com sufixo `_v2` na própria
> `Mapas/`. A subpasta `vNNN/` é uma mudança do modo servidor — implementar como opção do
> `saida` do MapSpec (`"pasta": "Mapas/v003"`), não como mudança do comportamento do desktop.

### Upload por partes

Motivo: a Cloudflare corta corpo de requisição acima de **100 MB** no plano gratuito, e um `.zip`
com raster de satélite passa disso. O navegador manda partes de `MF_UPLOAD_PARTE_MB` (8 MiB).

| Passo | Rota | Corpo | Resposta |
|---|---|---|---|
| 1 | `POST /api/v1/uploads` | `{nome, tamanho}` | `201 {upload_id, parte_bytes, total_partes}` |
| 2 | `PUT /api/v1/uploads/{u}/partes/{n}` (n = 0…total−1) | bytes crus; header `X-Parte-SHA256` (hex da parte) | `204`; parte com hash diferente do header → `SV-101`; repetir a mesma parte é idempotente |
| 3 | `GET /api/v1/uploads/{u}` | — | `{partes_ok:[…], faltam:[…]}` (retomada após queda) |
| 4 | `POST /api/v1/uploads/{u}/concluir` | `{hash_partes}` | `200 {sha256: "<do arquivo montado>"}` ou `SV-102` |
| 5 | `POST /api/v1/projetos/{id}/importacao` | `{upload_id}` | `202`; progresso por SSE |

Integridade sem carregar o arquivo inteiro na memória do navegador (`crypto.subtle.digest` não
faz hash incremental): o navegador calcula o SHA-256 **de cada parte** (8 MiB cabe na memória) e,
no fim, `hash_partes = sha256(concatenação dos hex das partes, na ordem)`. O servidor recalcula
o mesmo `hash_partes` a partir das partes recebidas — se bater, a montagem está íntegra — e
calcula também o SHA-256 do arquivo montado (streaming, no servidor), que é o que fica gravado.
Partes ficam em `$MF_RAIZ/dados/uploads/<u>/<n>.part`. Upload `expirado` (24 h) é apagado
pelo `limpar-lixeira`.

### Verificação e extração (em `importacao/extrair.py`)

Ordem fixa; parar no primeiro erro:

1. `zipfile.is_zipfile` e abrir com `zipfile.ZipFile` (sem extrair ainda). Falha → `SV-110`.
2. Para cada entrada:
   - nome normalizado: `\` → `/`, sem `..`, sem caminho absoluto, sem letra de drive, sem byte
     nulo → senão `SV-104` (zip-slip);
   - symlink (bits `0o120000` no `external_attr`) → `SV-105`;
   - extensão na **allowlist** → senão ignorar com aviso `SV-120` (não falha):
     `.shp .shx .dbf .prj .cpg .sbn .sbx .qix .xml .zip .pdf .tif .tiff .tfw .jpg .jpeg .jgw .png .pgw .kml .kmz .geojson .json .csv .txt .xlsx .mxd`
   - `.mxd` na entrada é aceito só como **referência** (`analisar_referencia`) e passa por
     `chaves_mxd.py verificar`; se tiver `authkey`, a chave é **removida** na cópia que o núcleo
     lê e o usuário recebe aviso `SV-121`.
3. Soma de `file_size` > `MF_EXTRAIDO_MAX_MB` → `SV-106` (zip-bomba). Razão de compressão de
   qualquer entrada > 200:1 com mais de 50 MB → `SV-107`.
4. Mais de 5.000 entradas → `SV-108`.
5. Extrair entrada a entrada para `entrada/` com `open(..., "xb")`, contando bytes reais (o
   `file_size` declarado pode mentir: abortar ao passar do teto → `SV-106`). Emitir
   `importacao.progresso {arquivo, indice, total, bytes}` a cada arquivo (no máximo 10/s).
6. Nome de arquivo com encoding CP437/CP850 (ZIP feito no Windows sem flag UTF-8): decodificar
   pelo flag `0x800`; sem ele, tentar `cp437 → utf-8` e cair para `cp850`; nome final passa por
   `unicodedata.normalize("NFC")`.
7. `.zip` aninhado **não** é extraído pelo servidor: o núcleo trata (`zip_simcar.py`), igual ao desktop.
8. Shapefile incompleto (falta `.shx`/`.dbf`/`.prj`) não é erro de importação: o índice do núcleo
   já reporta e o resumo mostra o aviso.

Ferramenta existente útil: `ferramentas/recuperar_zip_truncado.py` — se `SV-110` for por
diretório central ausente, oferecer "tentar recuperar" (chama a ferramenta numa cópia).

### Indexação e resumo

Depois de extrair, a ponte:

1. sobe (ou reusa) o worker do projeto;
2. `workspace.abrir {pasta: "<raiz do projeto>"}`;
3. `workspace.inspecionar` → monta o **resumo** sem CPF:

```json
{
  "imovel": { "nome": "Fazenda Boa Vista", "car": "MT123456/2019", "municipio": "Querência",
              "uf": "MT", "ibge": "5107065", "area_recibo_ha": 1240.5512, "area_geometria_ha": 1240.5498 },
  "camadas": [ { "papel": "perimetro", "arquivo": "entrada/CAR/ATP.shp", "feicoes": 1, "crs": "EPSG:4674" },
               { "papel": "avn", "arquivo": "entrada/CAR/AVN.shp", "feicoes": 12, "crs": "EPSG:4674" } ],
  "recibo": { "encontrado": true, "arquivo": "entrada/CAR - Recibo.pdf", "quadro_areas": true },
  "avisos": [ { "codigo": "NU-xxx", "mensagem": "AUAS.shp sem .prj — assumido SIRGAS 2000 (EPSG:4674)" } ]
}
```

Os `papel`s vêm de `workspace/papeis.py` (não inventar outro classificador). O CPF nunca chega
aqui: o parser do recibo já descarta (AP-09); o teste W4-09 garante.

Datum de entrada ([W-17](17-conhecimento-das-skills.md) §6): o pacote **ArquivoGeometria do
SIMCAR vem em SAD69 UTM 22S (EPSG:29192)**. Sem conversão o imóvel cai ~60 m fora do lugar. Na
indexação, `.prj` com `SAD_1969`/EPSG:29192 → reprojetar para SIRGAS 2000 com a transformação
oficial `SAD_1969_To_SIRGAS_2000` (Helmert −67,35 / +3,88 / −38,22) e registrar aviso no resumo
("AVN.shp estava em SAD69 — convertido para SIRGAS 2000"). Conferir antes se `geo/crs.py` já faz
isso (memória `pcf-mxd-sad69-para-sirgas`); se fizer, só ligar o aviso.

Regra do Álvaro "**um processo = um mapa**": o mapa mostra só o imóvel do recibo/processo, nunca o
vizinho, mesmo do mesmo dono ou da mesma matrícula-mãe. Se o `.zip` trouxer dois imóveis, o resumo
avisa e o agente pergunta qual é o do projeto.

## Tarefas agentáveis

- [ ] **W1-01** `Fase_1_Desktop/nucleo/mapasfacil_nucleo/motores/folhas.py`: tabela, `folha_mm`, `fator_k`, `FORMATOS`, `ORIENTACOES`; CLI `python -m mapasfacil_nucleo folhas --json`.
- [ ] **W3-01** `Fase_3_Web/servidor/mapasfacil_servidor/banco/migracoes/0001_inicial.sql` com `usuarios`, `sessoes`, `projetos`, `versoes`, `uploads`, `auditoria` (ver W-11 para as duas últimas).
- [ ] **W3-02** `banco/repositorios.py`: `ProjetosRepo.criar/listar/obter/atualizar/transicionar` — `transicionar` aplica a tabela de estados e levanta `SV-090` fora dela.
- [ ] **W3-03** `api/projetos.py`: `POST/GET/PATCH/DELETE /projetos`, `POST /projetos/{id}/restaurar`; cria a pasta e `.servidor/projeto.json` na criação.
- [ ] **W4-01** `importacao/partes.py`: criar upload, gravar parte (verificando `X-Parte-SHA256`), status, concluir (confere `hash_partes`, monta o arquivo e calcula o SHA-256 dele por streaming).
- [ ] **W4-02** `api/uploads.py`: as 4 rotas de upload; dono do upload = usuário da sessão (`SV-030` se outro).
- [ ] **W4-03** `web/src/api/upload.ts`: fatiar `File` com `slice`, hash por parte (`crypto.subtle`), 3 partes em paralelo, retomada pelo `GET /uploads/{u}`, cancelamento; progresso por bytes confirmados (não por bytes "enviados ao buffer").
- [ ] **W4-04** `importacao/extrair.py`: os 8 passos acima, cada erro com seu `SV-1xx`.
- [ ] **W4-05** `api/projetos.py::importar`: transições `importando → indexando → pronto|erro_importacao`, eventos `importacao.progresso` e `projeto.estado`.
- [ ] **W4-06** Indexação via ponte (`workspace.abrir`, `workspace.inspecionar`), montagem do resumo, gravação de `imovel_json`.
- [ ] **W4-07** Reimportação: mover para `entrada.anterior/<carimbo>/`, marcar versões antigas.
- [ ] **W4-08** `Fase_3_Web/fixtures/gerar_zip_sintetico.py`: gera `imovel_ficticio.zip` (polígonos simples em EPSG:4674 numa área fictícia de MT, ATP/AVN/AREA_CONSOLIDADA/AUAS, recibo PDF **falso** com quadro de áreas e CPF fictício `000.000.000-00` para o teste de descarte) + variantes maliciosas (`zip_slip.zip`, `zip_bomba.zip`, `symlink.zip`, `nomes_cp437.zip`, `truncado.zip`).
- [ ] **W4-09** Teste: importar `imovel_ficticio.zip` e varrer banco, `eventos.ndjson`, `chats.sqlite` e logs procurando o CPF fictício → zero ocorrências.
- [ ] **W4-10** SAD69 → SIRGAS 2000 na indexação + aviso; teste com `imovel_sad69.zip` (mesmo imóvel fictício gravado em EPSG:29192: depois da importação, o bbox bate com o do `imovel_ficticio.zip` em < 1 m).
- [ ] **W6-xx** Telas do assistente "Novo mapa" ([W-06](06-frontend-web-e-design.md)).

## Critérios de aceite

- [ ] `pytest Fase_3_Web/servidor/tests/test_importacao.py` verde, cobrindo: ZIP válido; `SV-104` zip-slip; `SV-105` symlink; `SV-106` bomba (declarada e real); `SV-107` razão; `SV-108` entradas; `SV-110` corrompido; `SV-120` extensão ignorada; nomes CP437 corretos.
- [ ] Upload de um arquivo de 300 MB (gerado em teste) em partes de 8 MiB, com uma parte reenviada e uma queda simulada no meio, termina com `hash_partes` conferido e o `sha256` do servidor igual ao `sha256sum` do arquivo original.
- [ ] Depois da importação do `imovel_ficticio.zip`, `GET /projetos/{id}/resumo` traz `imovel.car`, `municipio`, `area_recibo_ha` e as 4 camadas com `papel` correto — e nenhum campo com CPF.
- [ ] O núcleo não consegue escrever em `entrada/` (teste: tool de edição tentando gravar lá recebe erro do `fsguard`).
- [ ] `test_folhas_espelho` verde.

## Fora de escopo

- Vários `.zip` por projeto (o reenvio substitui).
- Navegador de arquivos do projeto com edição/remoção individual (só leitura no resumo).
- Importar direto do SIMCAR por número do CAR (é escrita/sessão no portal; o desktop também não faz).

## Anti-padrões

- Confiar em `ZipInfo.file_size` como teto (mente em ZIP malicioso) — contar bytes reais.
- Extrair com `ZipFile.extractall` (sem as checagens por entrada).
- Guardar CPF no `imovel_json` "só para mostrar".
- Usar o nome do `.zip` como nome de pasta (colisão, caracteres) — a pasta é o ULID.
