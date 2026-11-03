# W-03 — API HTTP e stream de eventos

## Objetivo

Contrato completo entre o navegador e o servidor: rotas REST, formato de erro, autenticação por
cookie, e o **stream de eventos** (SSE) com replay — incluindo os três eventos novos que
alimentam o palco (`viewport.foco`, `camada.renderizada`, `layout.elemento`).

## Estado atual vs alvo

| Item | Hoje | Alvo |
|---|---|---|
| API HTTP | ausente | `/api/v1/*` em `Fase_3_Web/servidor/mapasfacil_servidor/api/` |
| Vocabulário de eventos do núcleo | 10 eventos (`protocolo.py::EVENTOS`) | 13: +`viewport.foco`, `camada.renderizada`, `layout.elemento` (W7) |
| Eventos do servidor | ausente | `projeto.estado`, `importacao.progresso`, `worker.estado`, `mensagem.criada`, `versao.criada`, `nucleo.res`, `sse.heartbeat` |
| Replay | ausente (o Electron entrega ao vivo) | `Last-Event-ID` / `?desde=` sobre `.servidor/eventos.ndjson` |

## Dependências

[W-01](01-arquitetura.md), [W-04](04-ponte-nucleo-servidor.md) (de onde vêm os eventos do núcleo),
[W-11](11-seguranca-contas-e-lgpd.md) (cookie, CSRF, permissões).

## Contratos

### Convenções

- Base: `https://<host>/api/v1`. JSON UTF-8. Datas ISO-8601 UTC com `Z`. IDs ULID.
- Autenticação: cookie `mf_sessao` (HttpOnly, Secure, SameSite=Lax, Path=/). Toda rota exige,
  salvo `POST /auth/cadastrar`, `POST /auth/entrar` e `GET /saude`.
- CSRF: rotas que mudam estado (`POST/PUT/PATCH/DELETE`) exigem header `X-MF-CSRF` igual ao
  valor devolvido por `GET /auth/eu` (ligado à sessão). Falta/errado → `403 SV-020`.
- Permissão: o usuário só vê o que é dele; admin vê tudo em leitura (P4). Projeto de outro →
  `404 SV-031` (não `403`, para não confirmar que existe).
- Paginação por cursor: `?antes=<id>&limite=50` (máx. 200).
- Erro: corpo `{"erro": {codigo, mensagem, porque, o_que_fazer, detalhes}}` ([W-01](01-arquitetura.md) §Prefixos).

### Rotas

#### Autenticação e conta

| Método e rota | Corpo | Resposta | Erros |
|---|---|---|---|
| `POST /auth/cadastrar` | `{nome, email, senha}` | `201 {usuario}` + cookie (já entra; sem confirmação de e-mail — D27) | `409 SV-012` e-mail já cadastrado; `400 SV-010` senha fraca; `400 SV-013` e-mail inválido |
| `POST /auth/entrar` | `{email, senha}` | `200 {usuario}` + cookie | `401 SV-001` credencial; `403 SV-003` conta bloqueada pelo admin; `429 SV-005` muitas tentativas |
| `POST /auth/sair` | — | `204`, cookie apagado | — |
| `GET /auth/eu` | — | `200 {usuario:{id,email,nome,papel,trocar_senha}, csrf}` | `401 SV-002` sem sessão |
| `POST /auth/senha` | `{senha_atual, senha_nova}` | `204` | `400 SV-010` fraca (< 10 caracteres ou na lista comum); `401 SV-001` |

#### Administração (papel `admin`)

| Método e rota | Corpo | Resposta |
|---|---|---|
| `GET /admin/usuarios` | — | lista |
| `POST /admin/usuarios` | `{email, nome, papel:"usuario"|"admin"}` | `201 {usuario, senha_temporaria}` — a senha aparece **uma vez** (uso raro: o cadastro é aberto) |
| `PATCH /admin/usuarios/{id}` | `{ativo?, papel?, redefinir_senha?:true}` | `200` (+ `senha_temporaria` se redefiniu). `ativo:false` **bloqueia** a conta e derruba todas as sessões dela na hora |
| `GET /admin/auditoria?antes=&limite=` | — | eventos de auditoria ([W-11](11-seguranca-contas-e-lgpd.md)) |
| `GET /admin/saude` | — | workers vivos, vagas ocupadas, fila, disco, versão do núcleo |

#### Projetos

| Método e rota | Corpo | Resposta |
|---|---|---|
| `GET /projetos?busca=&estado=&antes=&limite=` | — | `{itens:[ProjetoResumo], proximo}` |
| `POST /projetos` | `{nome, folha:{formato, orientacao}}` | `201 {projeto}` (`estado:"aguardando_zip"`) |
| `GET /projetos/{id}` | — | `{projeto, resumo, versoes:[VersaoResumo]}` |
| `PATCH /projetos/{id}` | `{nome?}` | `200 {projeto}` |
| `DELETE /projetos/{id}` | — | `204` (vai para a lixeira) |
| `POST /projetos/{id}/restaurar` | — | `200 {projeto}` |
| `POST /projetos/{id}/importacao` | `{upload_id}` | `202 {importacao_id}` |
| `GET /projetos/{id}/resumo` | — | resumo do imóvel ([W-02](02-projeto-folha-e-upload.md) §Indexação) |

`ProjetoResumo`:

```json
{ "id": "01JBX…", "nome": "Boa Vista — Dinâmica", "estado": "pronto",
  "folha": { "formato": "A4", "orientacao": "retrato" },
  "imovel": { "nome": "Fazenda Boa Vista", "car": "MT123456/2019", "municipio": "Querência", "uf": "MT" },
  "versao_atual": 3, "miniatura": "/api/v1/projetos/01JBX…/arquivos/Mapas/v003/miniatura.png",
  "atualizado_em": "2026-11-03T14:02:11Z" }
```

#### Uploads

As 4 rotas de [W-02](02-projeto-folha-e-upload.md) §Upload por partes. Limite por parte:
`MF_UPLOAD_PARTE_MB` + 1 KiB; maior → `413 SV-103`.

#### Chat

| Método e rota | Corpo | Resposta |
|---|---|---|
| `GET /projetos/{id}/mensagens?antes=&limite=` | — | `{itens:[Mensagem], proximo}` (vem do `chat.carregar_anteriores` do núcleo, via ponte) |
| `POST /projetos/{id}/mensagens` | `{texto, resposta?:{pergunta_id, opcao_id?, texto_livre?}}` | `202 {req_id}` — o conteúdo chega pelo SSE |
| `POST /projetos/{id}/cancelar` | `{req_id}` | `202` (chama `chat.cancelar`/`mapa.cancelar`) |

Regras: um turno por vez por projeto. `POST /mensagens` com turno em andamento → `409 SV-210`
("a IA ainda está respondendo — cancele ou espere"). `texto` de 1 a 8.000 caracteres (`SV-011`).

#### Versões e arquivos

| Método e rota | Resposta |
|---|---|
| `GET /projetos/{id}/versoes` | `[VersaoResumo]` |
| `GET /projetos/{id}/versoes/{n}` | `{versao, mapspec, validacao, artefatos}` |
| `GET /projetos/{id}/versoes/{n}/diff/{m}` | saída do `mapspec.diff` do núcleo |
| `GET /projetos/{id}/versoes/{n}/pacote.zip` | ZIP em streaming, **sempre disponível** para versão com artefatos (D37): `MXD/` + `SHP/` + `Mapas/` + `LEIA-ME.txt` ([W-08](08-motor-mxd-binario.md) §Pacote). Versão não conforme ou com gate do `.mxd` falho continua baixável; o `LEIA-ME.txt` e o `Mapas/validacao.json` dizem o que falhou |
| `GET /projetos/{id}/arquivos/{caminho}` | arquivo do projeto; **só** prefixos `Mapas/` e `MXD/`; `Range` suportado; `Content-Disposition` com nome amigável. Fora da allowlist → `404 SV-401`. Caminho com `..` → `400 SV-402` |
| `GET /projetos/{id}/palco/{job_id}/{resto}` | GeoJSON/PNG de `Mapas/.preview/<job_id>/<resto>` para o palco (cache 1 h, privado). A web monta a URL tirando o prefixo `Mapas/.preview/<job_id>/` do `caminho` do evento (`web/src/api/eventos.ts::urlPalco`); `caminho` fora desse prefixo num evento de palco é bug (`WB-010`, ignorado e logado) |

#### Bases e saúde

| Método e rota | Resposta |
|---|---|
| `GET /bases/uf/{uf}.geojson` | contorno da UF simplificado (de `shared/bases/ibge`), `Cache-Control: max-age=86400` |
| `GET /bases/municipios/{ibge}.geojson` | contorno do município simplificado |
| `GET /saude` | `{ok, versao, nucleo:{versao, protocolo}, workers, vagas_livres, disco_livre_gb}` — sem dado de usuário |

### Stream de eventos (SSE)

`GET /projetos/{id}/eventos` com `Accept: text/event-stream`.

- Retomada: header `Last-Event-ID: <seq>` (o `EventSource` manda sozinho ao reconectar) ou
  `?desde=<seq>` na primeira conexão. O servidor reenvia tudo com `seq > desde` do
  `.servidor/eventos.ndjson` e depois passa a entregar ao vivo, **sem buraco e sem duplicata**
  (a leitura do arquivo e a inscrição no fan-out acontecem sob o mesmo lock).
- `?desde=0` numa reabertura de página: o servidor **compacta** antes de enviar — para cada job
  já terminado manda só o último `job.progresso`, os `camada.renderizada`, os `layout.elemento`
  e o `nucleo.res`; `chat.delta` de turnos terminados não é reenviado (a mensagem final já está
  em `GET /mensagens`). O job **em andamento** é reenviado inteiro.
- Heartbeat: comentário `: ♥` a cada 15 s (mantém o túnel Cloudflare aberto).
- Headers: `Cache-Control: no-cache`, `X-Accel-Buffering: no`, sem compressão.
- Um projeto pode ter várias abas abertas: todas recebem o mesmo fluxo.

Formato de cada mensagem:

```
id: 1842
event: mf
data: {"seq":1842,"ts":"2026-11-03T14:02:11.482Z","origem":"nucleo","evento":"job.progresso","req_id":"01JBY…","job_id":"01JBZ…","dados":{"etapa":"baixando_externas","pct":30}}
```

| Campo | Regra |
|---|---|
| `seq` | inteiro por projeto, começa em 1, estritamente crescente, gravado antes de enviar |
| `origem` | `nucleo` (veio do worker) ou `servidor` |
| `evento` | nome do vocabulário abaixo — fora dele é bug (`SV-300`) |
| `req_id` | id da requisição NDJSON que originou (eventos do núcleo) |
| `job_id` | quando o evento pertence a um job de geração |
| `dados` | o `dados` original do núcleo, **filtrado** (caminhos absolutos removidos, ver abaixo) |

Filtro de saída (`eventos/sse.py`): qualquer string em `dados` que pareça caminho absoluto
(`/home/`, `/media/`, `C:\`) é bug do emissor — o servidor substitui por `"<caminho removido>"`,
registra `SV-310` no log técnico e **não** quebra o stream.

### Vocabulário

#### Eventos do núcleo (repassados)

| Evento | Já existe | Uso na web |
|---|---|---|
| `job.progresso` | sim | barra de etapas do palco; etapa em curso = a seguinte à última concluída |
| `job.log` | sim | log técnico colapsado |
| `job.artefato_parcial` | sim | preview PNG/PDF e tabela no palco |
| `workspace.mudou` | sim | recarregar resumo |
| `chat.delta` / `chat.raciocinio` / `chat.tool` / `chat.pergunta` | sim | chat |
| `mapspec.atualizado` | sim | linha de versões |
| `aviso` | sim | toast + item no chat |
| `viewport.foco` | **novo (W7)** | câmera do palco |
| `camada.renderizada` | **novo (W7)** | acendimento das camadas |
| `layout.elemento` | **novo (W7)** | montagem da folha |

#### Eventos do servidor

| Evento | `dados` |
|---|---|
| `projeto.estado` | `{estado, erro_codigo?, resumo?}` |
| `importacao.progresso` | `{fase:"verificando"|"extraindo"|"indexando", arquivo?, indice?, total?, bytes?}` |
| `worker.estado` | `{estado:"iniciando"|"pronto"|"ocioso_encerrado"|"caido", codigo?}` |
| `mensagem.criada` | `{mensagem}` — eco da mensagem do usuário para as outras abas |
| `versao.criada` | `{versao: VersaoResumo}` — depois que a ponte registra a versão no banco |
| `nucleo.res` | `{req_id, ok, erro?}` — fim de uma requisição ao núcleo |

### Os três eventos novos do núcleo (contrato que o W7 implementa)

Todos entram em `protocolo.py::EVENTOS` **e** em `Fase_1_Desktop/planos/01-arquitetura.md`
§Eventos no mesmo commit (regra do próprio `protocolo.py`). Validação de `dados` em
`mapasfacil_nucleo/motion.py` (novo), no mesmo estilo de `artefatos.py`: função pura
`montar_dados_*` que levanta `ValueError` em dado fora do contrato — é erro de programação.

#### `viewport.foco`

Emitido quando o núcleo **passa a saber** onde está o assunto do mapa.

```json
{
  "job_id": "01JBZ…",
  "nivel": "estado",
  "bbox_4326": [-61.63, -18.04, -50.22, -7.35],
  "rotulo": "Mato Grosso",
  "origem": "ibge",
  "etapa": "validando_spec",
  "escala": null,
  "crs_mapa": null,
  "quadro_mm": null
}
```

| Campo | Regra |
|---|---|
| `job_id` | `null` quando emitido fora de job (indexação na importação) |
| `nivel` | `estado` → `municipio` → `imovel` → `enquadramento` → `folha`. Dentro de um job a sequência **não volta** (pode pular). Fora de job só `estado`/`municipio`/`imovel` |
| `bbox_4326` | `[oeste, sul, leste, norte]` em graus, `oeste<leste`, `sul<norte`, dentro de [-180,180]×[-90,90] |
| `rotulo` | texto curto para a legenda da câmera ("Querência/MT", "Fazenda Boa Vista") |
| `origem` | `ibge` (base local), `recibo_car`, `geometria_local`, `calculo_escala`, `perfil_pagina` |
| `etapa` | uma das 10 etapas de `job.progresso` (ou `null` fora de job) |
| `escala` | só em `enquadramento`: o denominador escolhido (ex.: `40000`) |
| `crs_mapa` | só em `enquadramento`: `EPSG:31981`/`31982`/… |
| `quadro_mm` | só em `enquadramento`/`folha`: `{largura, altura}` do quadro do mapa na folha |

Pontos de emissão (todos reais):

| `nivel` | Onde no núcleo | Quando |
|---|---|---|
| `estado` | `motores/gerar.py`, logo depois de `validando_spec` | UF do `MapSpec.imovel.municipio` conhecida |
| `municipio` | idem, ao entrar em `resolvendo_camadas_locais` | município do `MapSpec` (ou do `analise/identidade.py` na série) |
| `imovel` | `camadas/materializar.py`, quando a camada de papel `perimetro` é lida | bbox real da geometria |
| `enquadramento` | onde a escala `auto` é resolvida (W11 move para `motores/enquadramento.py`) | escala e extent decididos |
| `folha` | `motores/nativo.py`, no início de `aplicando_layout` | a câmera sai do mapa e mostra a folha |
| `imovel` (sem job) | `workspace/servico.py`, ao terminar a indexação | perímetro achado no `.zip` |

#### `camada.renderizada`

Emitido quando uma camada **ficou pronta para desenhar** (lida, recortada, reprojetada).

```json
{
  "job_id": "01JBZ…",
  "camada_id": "avn",
  "papel": "avn",
  "nome": "Área de vegetação nativa",
  "geometria": "poligono",
  "sequencia": 2,
  "total": 6,
  "ordem_desenho": 30,
  "caminho": "Mapas/.preview/01JBZ…/camadas/avn.geojson",
  "bbox_4326": [-52.41, -12.71, -52.33, -12.64],
  "estilo": { "preenchimento": "#3A7D2C99", "contorno": "#2B5E20", "espessura_pt": 0.6, "padrao": "solido" },
  "n_feicoes": 12,
  "area_ha": 812.4410,
  "etapa": "resolvendo_camadas_locais"
}
```

| Campo | Regra |
|---|---|
| `papel` | o de `workspace/papeis.py` (`perimetro`, `avn`, `ac`, `auas`, `app`, `arl`, `hidrografia`, …) ou `externa`/`basemap` |
| `geometria` | `poligono` \| `linha` \| `ponto` \| `raster` |
| `sequencia` / `total` | ordem de acendimento dentro do job, 1-based; `total` pode crescer quando entram as externas (a UI aceita) |
| `caminho` | relativo à pasta do projeto, sob `Mapas/.preview/<job_id>/`; GeoJSON em EPSG:4326 **simplificado** (ver abaixo) ou PNG para `raster` |
| `bbox_4326` | obrigatório para `raster` (onde encaixar o PNG); opcional para vetor |
| `estilo` | traduzido do estilo do `MapSpec` (`motores/estilos.py`) para cores hex **com alfa**; é o mesmo estilo que o PDF vai usar |
| `area_ha` | só polígonos, em CRS projetado (regra do padrão), 4 casas |

Ordem de emissão garantida pelo núcleo (é a ordem pedida pelo Álvaro e também a ordem de pintura
do padrão): **perímetro (ATP) → AVN → AC → hidrografia → AUAS → demais locais → externas
(WFS) → basemap**. Para isso `camadas/materializar.py` passa a resolver as camadas locais
ordenadas por `PRIORIDADE_PAPEL` (constante nova em `motion.py`); externas saem na ordem em que
chegam da rede — é real, não se reordena.

Simplificação do GeoJSON de palco (não afeta PDF nem `.mxd`): `shapely.simplify(tol,
preserve_topology=True)` com `tol = diagonal_do_bbox_do_imovel / 4000` (em graus), coordenadas
com 6 casas, teto de **2 MB por arquivo** e **20.000 vértices**; se passar, dobra `tol` até caber
e grava `"simplificado": true` nas `properties` da coleção.

#### `layout.elemento`

Emitido pelo motor nativo **quando posiciona** cada elemento da folha.

```json
{
  "job_id": "01JBZ…",
  "elemento": "minimapa",
  "sequencia": 6,
  "total": 11,
  "folha": { "formato": "A4", "orientacao": "retrato", "largura_mm": 210, "altura_mm": 297 },
  "caixa_mm": { "x0": 136.2, "y0": 18.9, "x1": 199.0, "y1": 80.4 },
  "conteudo": null,
  "caminho": "Mapas/.preview/01JBZ…/layout/minimapa.png",
  "etapa": "aplicando_layout"
}
```

| Campo | Regra |
|---|---|
| `elemento` | `moldura`, `mapa`, `grade`, `titulo`, `norte`, `minimapa`, `legenda`, `metadados`, `tabela`, `logo`, `escala_grafica`, `rotulos` |
| `caixa_mm` | mesma convenção de `motores/perfil_pagina.py::Caixa` (origem no topo-esquerda, `y` para baixo), já escalada para a folha |
| `conteudo` | resumo textual leve: `titulo` → `{texto}`, `legenda` → `{itens:[{rotulo, cor}]}`, `metadados` → `{linhas:[{rotulo, valor}]}`, `tabela` → `{linhas: n}`; nunca CPF |
| `caminho` | recorte PNG do elemento (opcional; o palco pode desenhar só a caixa) |
| `etapa` | `aplicando_layout` ou `gerando_tabela` |

A ordem real de desenho do `motores/nativo.py` é a ordem dos eventos — o palco não reordena.

## Tarefas agentáveis

- [ ] **W3-10** `servidor/mapasfacil_servidor/app.py` + `api/*.py` com as rotas acima, modelos Pydantic em `api/modelos.py`.
- [ ] **W3-11** `erros.py` + handler global que converte `ErroServidor` e `ErroNucleo` no corpo padrão.
- [ ] **W5-01** `eventos/log.py`: `registrar(projeto_id, origem, evento, dados, req_id, job_id) -> seq` com append atômico (`O_APPEND` + `fsync` a cada 50 eventos ou 1 s) e índice de offset por seq a cada 1.000 linhas.
- [ ] **W5-02** `eventos/sse.py`: replay + ao vivo sem buraco (lock), compactação para `desde=0`, heartbeat, filtro de caminho absoluto, desconexão limpa.
- [ ] **W5-03** `eventos/vocabulario.py`: `EVENTOS_SERVIDOR` + importa `EVENTOS` do núcleo; teste que o conjunto da web (`web/src/api/tipos.ts`) é igual.
- [ ] **W7-01** `mapasfacil_nucleo/motion.py`: `montar_dados_viewport`, `montar_dados_camada`, `montar_dados_layout`, `PRIORIDADE_PAPEL`, `NIVEIS_VIEWPORT`; testes de contrato.
- [ ] **W7-02** `protocolo.py::EVENTOS` + `Fase_1_Desktop/planos/01-arquitetura.md` §Eventos com os 3 novos.
- [ ] **W7-03** `progresso.py::RastreadorProgresso`: métodos `foco(...)`, `camada(...)`, `elemento(...)` (o rastreador já é o canal de eventos do job — mesmo motivo do `artefato`).
- [ ] **W7-04** Pontos de emissão listados acima em `gerar.py`, `materializar.py`, `nativo.py`, `workspace/servico.py`.
- [ ] **W7-05** Rota `GET /projetos/{id}/palco/{job_id}/{caminho}` + limpeza de `.preview` > 7 dias.

## Critérios de aceite

- [ ] `pytest servidor/tests/test_sse.py`: (a) 500 eventos gravados, conexão com `desde=250` recebe 251–500 e depois ao vivo; (b) reconexão com `Last-Event-ID` não duplica; (c) `desde=0` com 3 jobs terminados recebe a versão compactada; (d) heartbeat chega em ≤ 16 s.
- [ ] `pytest Fase_1_Desktop/nucleo/tests/test_motion_contrato.py`: `nivel` voltando dentro do job levanta; `bbox` invertido levanta; caminho absoluto em `caminho` levanta; `elemento` fora da lista levanta.
- [ ] Um job real de Dinâmica no `imovel_ficticio.zip` emite, em ordem: `viewport.foco` estado → município → imóvel → enquadramento → folha; `camada.renderizada` com `papel` na ordem perímetro, avn, ac, auas; `layout.elemento` cobrindo todos os elementos ligados em `elementos_layout`.
- [ ] Nenhum evento SSE contém `/home/`, `/media/` ou `C:\` (teste varre o `eventos.ndjson` do job real).
- [ ] O desktop continua verde (`pnpm test` no `Fase_1_Desktop/app` e `pytest` no núcleo): eventos novos são ignorados pelo renderer antigo sem erro.

## Fora de escopo

- API pública para terceiros, tokens de API, webhooks.
- GraphQL.
- WebSocket (D29).

## Anti-padrões

- Gerar `seq` em memória sem gravar antes (replay perde evento num reinício).
- Mandar o GeoJSON dentro do `dados` do evento (AW-04).
- Reordenar no servidor eventos do núcleo "para ficar mais bonito" — a ordem é a verdade do job.
