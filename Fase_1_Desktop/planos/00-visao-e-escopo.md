# F1-00 — Visão e escopo do app desktop

## Objetivo

Um aplicativo **nativo Windows** onde o usuário faz login, conecta uma pasta e obtém os mapas da
série IMAP por duas portas equivalentes: uma **galeria de modelos** e um **chat com um agente de
engenharia florestal**. O modelo mental é o do Cursor / Codex / Claude Code, trocando código por
cartografia. Este documento fixa o escopo da v1 e os critérios de aceite verificáveis; cada
capacidade tem um plano dedicado.

## Estado atual vs alvo

| Capacidade | Estado | Plano |
|---|---|---|
| Núcleo Python (MapSpec, workspace, quantitativos, PDF nativo, fsguard) | **parcial — v0.3.6, CI verde** | [F1-03](03-nucleo-python.md) |
| Motor `.mxd` | **parcial** — T2 copia template; T1 esqueleto; B1 pendente | [F1-04](04-motor-mxd.md) |
| App Electron / qualquer UI | **ausente** (`app/` vazia) | [F1-02](02-ui-chat-e-workspace.md) |
| Design system dark + animações | **ausente** | [F1-16](16-design-system-dark.md) |
| Galeria de modelos | **ausente** | [F1-15](15-galeria-de-modelos.md) |
| Conta e login Google | **ausente** | [F1-14](14-auth-e-conta.md) |
| Persistência de conversas | **ausente** | [F1-17](17-persistencia-de-conversas.md) |
| Agente DeepSeek + compressão de contexto | **ausente** | [F1-06](06-agente-eng-florestal.md) |
| Instalador | **ausente** | [F1-11](11-empacotamento-instalador.md) |

Ordem de implementação e o que cada marco fecha: [F1-12](12-roadmap.md) e
[`../../AGENT_BRIEF.md`](../../AGENT_BRIEF.md).

## O produto em uma tela

```
┌─ topo-app ───────────────────────────────────────────────────────────────────────┐
│  MAPAS FÁCIL   Fazenda Harmonia · Vila Rica/MT          ◍ conta   ⚙   ─ □ ✕      │
├─ barra-chats ─┬─ painel-workspace ─┬─ painel-chat ──────┬─ painel-direito ───────┤
│ + novo chat   │ 📁 Harmonia        │ você               │  preview │galeria│spec │
│ HOJE          │ ▪ ATP.shp          │ faz a Dinâmica 2026│  ┌───────────────────┐ │
│ ▸ Dinâmica 26 │   3.823,9033 ha    │                    │  │ ▪ perímetro    ✓  │ │
│ ▸ Tipologia   │ ▪ AVN.shp          │ Ana                │  │ ▪ AUAS         ✓  │ │
│ 7 DIAS        │ ▪ AUAS.shp         │ ▸ ler_recibo  1,2s │  │ ▪ AVN          ◐  │ │
│ ▸ Embargos    │ ▪ CAR-Emissao.pdf  │ ▸ usar_modelo 0,3s │  │ ▫ tabela       ○  │ │
│               │ ─────────────────  │ ▸ gerar_mapa   68s │  └───────────────────┘ │
│               │ ArcMap ✓  IA ✓     │ ▓▓▓▓▓▓▓░░ 70%      │  ◀ v1 ● v2 v3 ▶       │
│               │ SEMA ✓  Planet ✓   │ [ escreva…     ] ▶ │  3 arquivos gerados    │
└───────────────┴────────────────────┴────────────────────┴────────────────────────┘
```

## Por que desktop, e por que primeiro

| Razão | Detalhe |
|---|---|
| **O `.mxd` só existe no Windows** | `arcpy` é Windows-only e exige licença ArcGIS. Rodar em servidor implicaria licença de servidor — custo proibitivo |
| **Os dados já estão lá** | os shapefiles do CAR, o recibo, os projetos anteriores. Subir tudo para a nuvem é atrito e risco |
| **A SEMA bloqueia IP estrangeiro** | o PC do usuário está no Brasil; resolve de graça um problema que derrubou o backend do NexoGeo em nuvem |
| **O NexoGeo falhou exatamente aqui** | lá o `.mxd` ficou como "quando ArcMap estiver disponível" e nunca saiu do papel. Inverter a prioridade é a lição |

A exceção a "desktop não depende de servidor": **o login** (D10). O backend de identidade é a
única peça de servidor que a Fase 1 exige — ver [F1-14](14-auth-e-conta.md).

## As duas portas de entrada

O produto não é "um chat que gera mapa". São duas entradas para o **mesmo contrato**:

```
     GALERIA                         CHAT
  escolhe o modelo              "faz a Dinâmica 2026"
        │                              │
        │                       agente chama usar_modelo_da_galeria
        └───────────┬──────────────────┘
                    ▼
          galeria.montar_mapspec   (determinístico, 13 passos)
                    ▼
             mapspec.validar       (rejeita, nunca corrige em silêncio)
                    ▼
               mapa.gerar          (.mxd · .pdf · .png · .xlsx · validacao.json)
```

A galeria funciona **sem chave de IA**; o chat funciona **em cima da galeria**. Nenhuma das duas
tem caminho privilegiado — é o que garante que o modo determinístico seja de primeira classe e
testável em CI.

## O agente

É um **agente de domínio**, não um chat genérico. Ele:

- lê o recibo do CAR e sabe o que cada número significa;
- reconhece ATP, AVN, AC, AUAS, APP, ARL pelos nomes e pelo conteúdo;
- sabe que área se calcula em UTM, e qual zona usar para aquele imóvel;
- consulta os portais da SEMA para tipologia, embargo, UC, TI e uso consolidado;
- percebe que a soma das sub-áreas não fecha com a ATP e **avisa antes de gerar o mapa**;
- sabe que o mapa de Terras Indígenas precisa da distância até a TI mais próxima;
- olha um print de um mapa antigo e reproduz o mesmo layout com os dados novos;
- e conversa sobre tudo isso em português, com números em hectare.

Modelo: **DeepSeek V4 Pro**, chave do próprio usuário (BYOK), com orçamento de contexto e
compressão obrigatórios — [F1-06](06-agente-eng-florestal.md).

## Entregáveis por mapa

| Arquivo | Motor | Sempre? |
|---|---|---|
| `<Nome>.mxd` | ArcPy, ou patch de template quando não há ArcMap | quando `mxd` está em `saidas` |
| `<Nome>.pdf` | ArcMap, ou renderizador nativo Python | sempre |
| `<Nome>.png` | preview | sempre |
| `Quantitativos.xlsx` | openpyxl | quando há tabela |
| `validacao.json` | validador | sempre |

## Escopo da v1

### Dentro

- [ ] **Conta**: login obrigatório com Google, via site → app; sessão renovável; sem limites de uso
- [ ] **Galeria** de modelos com preview real, status por pasta e montagem determinística de `MapSpec`
- [ ] **Chat** com streaming, tools visíveis, cancelamento e versionamento de `MapSpec`
- [ ] **Histórico de conversas** local, reabrível, com busca, renomear, arquivar e ramificar
- [ ] **Interface dark** com tipografia embarcada e animações amarradas a eventos reais do núcleo
- [ ] Conectar pasta, indexar e observar mudanças
- [ ] Ler recibo do CAR, `.zip` do SIMCAR e shapefiles
- [ ] Consultar WFS/WMS de SEMA, IBAMA, FUNAI, MapBiomas, INCRA, IBGE
- [ ] Gerar a série IMAP no perfil Harmonia: Dinâmica (retrato) e temáticos (paisagem)
- [ ] `.mxd` com caminhos relativos e camadas materializadas ao lado
- [ ] Troca automática de definition query de município e UF
- [ ] Minimapa com retângulo recentrado e linha-guia
- [ ] Tabela de quantitativos como PNG de alta resolução + `.xlsx`
- [ ] Modo "olha esse print/zip e faz igual"
- [ ] Validação de conformidade com bloqueio em falha HARD
- [ ] Doctor do ambiente
- [ ] Instalador Windows

### Fora da v1 (vinculante)

Incluir qualquer item desta tabela exige alterar **este documento** e
[`../../planos/00-visao-e-duas-fases.md`](../../planos/00-visao-e-duas-fases.md) no mesmo commit.

| Fora da v1 | Motivo |
|---|---|
| **Cobrança, planos, trial** | v1 valida o produto, não o modelo de negócio |
| **Quota, rate limit de produto, feature flag de cobrança** | D18: autenticado = ilimitado (AP-05) |
| **Sync de conversas para a nuvem** | D20: local-only; o espelho é Fase 2 e opt-in |
| Linux e macOS | `arcpy` não existe; o núcleo roda, mas sem `.mxd` |
| ArcGIS Pro como caminho primário | Pro 3.x **não salva `.mxd`** — sem volta para o ArcMap |
| Edição de geometria | é trabalho de GIS; usa-se ArcMap ou QGIS |
| Pareceres e laudos | escopo do NexoGeo e do GeoForest Oráculo |
| Escrita no SIMCAR | domínio do GeoForest Oráculo |
| Login em portal da SEMA | a sessão técnica é única e derruba o usuário do navegador |
| Colaboração multiusuário, times, organizações | é a Fase 2, e nem lá na v1 |
| Marketplace/compartilhamento de modelos de galeria | modelo novo exige template preparado no ArcMap |
| Multi-conta simultânea | uma conta por instalação |

## Critérios de aceite da Fase 1

Cada critério é verificável por um agente, com o comando ou o assert ao lado.

### Produto

1. **Análise completa da Harmonia** (pasta real, CAR real) produz os 19 mapas em **< 10 minutos**
   com ArcMap — cronometrado no smoke do anel 4 e registrado na release.
2. Os PDFs gerados batem com os PDFs-modelo por comparação de raster, **diferença < 0,3%**
   (`validacao.comparar_pdf` contra `Referencias_IMAP/Mapas/01/`).
3. O `.mxd` gerado abre no ArcMap **de outro PC**: todas as camadas resolvem, ou resolvem com um
   único passo óbvio de vinculação da pasta `SHP/`.
4. Nenhum texto de análise anterior sobrevive no mapa (check `S11` verde em todos).
5. Sem ArcMap na máquina, o app ainda entrega `.mxd` (patch de template) + PDF nativo, e o
   `validacao.json` declara `confianca: "estrutural"` honestamente.
6. **Sem internet e com sessão válida em cache**, o app gera o mapa com os shapes locais e o
   cache, com aviso de idade. *(Revisado por D11: antes dizia "sem internet" sem a condição de
   sessão — ver [F1-14](14-auth-e-conta.md).)*
7. Sem chave DeepSeek, a galeria gera a série inteira, com aviso de modo determinístico.

### Conta

8. Instalação limpa exige login antes de qualquer painel; a `tela-login` é a primeira viewport.
9. Depois de logado, **nenhuma** operação é recusada por limite de uso — `grep -rn "quota\|rate_limit\|paywall" app/ nucleo/` não retorna código de restrição de produto.
10. Sessão expirada: leitura do workspace e das conversas continua; `mapa.gerar` recusa com
    `AUTH-030` e a UI oferece "Entrar".
11. Backend de conta fora do ar com token válido: o app funciona inteiro, com chip "offline".

### Interface

12. Tema escuro por padrão numa instalação limpa (`dataset.tema === "escuro"`).
13. Ao menos **3 animações** ligadas a eventos reais (`chat.delta`, `chat.tool`, `job.progresso`),
    provadas por teste com evento injetado — nenhuma usa timer sozinho.
14. `painel-preview` reage à geração: `job.progresso` com `item` acende a camada correspondente.
15. `prefers-reduced-motion: reduce` zera translações e escalas; nada acima de 80 ms.
16. `axe-core` sem violação de contraste nas telas login, vazia, com job e com erro.

### Conversas

17. Criar conversa → fechar o app → reabrir → histórico íntegro, com tool traces.
18. Conversa de 200 mensagens abre em **< 300 ms**, trazendo 30 mensagens + `compact_summary`.
19. `grep -a "123.456.789" chats.sqlite` vazio depois de escrever um CPF no chat.

### Agente

20. Suíte de cassetes verde **sem rede e sem chave**.
21. Fixture de 120 turnos monta payload ≤ 60.000 tokens com 8 turnos verbatim.
22. Payload do request nunca casa com WKT, CPF, caminho `C:\Users\` ou `PLAK`.
23. "Faz a Dinâmica 2026" usa `usar_modelo_da_galeria`, e o `MapSpec` resultante é idêntico ao da
    galeria direta em `template`, `camadas[].id` e `elementos_layout`.

### Onboarding

24. Um técnico que nunca viu o sistema instala, faz login e produz o primeiro mapa válido em
    **< 15 minutos**, sem ajuda do desenvolvedor (medido no piloto, M11).
25. Nenhum shapefile de cliente sai do PC dele sem consentimento explícito — auditado pelo
    teste de vazamento (critério 22) e pela lista de exceções de
    [`../../planos/05-seguranca-e-segredos.md`](../../planos/05-seguranca-e-segredos.md).

## O que este desenho deliberadamente não faz

- **Não** manda dado do cliente para servidor nenhum. As exceções (prompt, consulta geoespacial,
  tiles, identidade) estão listadas, são mínimas e controláveis.
- **Não** deixa a IA escrever código. O contrato é `MapSpec` declarativo, validado por schema.
- **Não** depende da Fase 2 para nada, **exceto o serviço de identidade** (D10).
- **Não** limita o usuário autenticado. Sem quota, sem paywall, sem medição para cobrar (D18).
- **Não** tenta ser um SIG. Não desenha, não edita geometria, não faz geoprocessamento — faz
  cartografia de padrão.

## Anti-padrões desta fase

Os anti-padrões vinculantes do repositório estão em
[`../../AGENT_BRIEF.md`](../../AGENT_BRIEF.md#anti-padrões--vinculantes-para-qualquer-agente-implementador).
Os três que mais ameaçam o escopo:

| Não faça | Por quê |
|---|---|
| Reintroduzir "limite de uso" de qualquer forma na v1 | AP-05 / D18 — a conta existe para identidade, não para cobrar |
| Tratar a galeria como enfeite e deixar o chat montar tudo do zero | quebra o modo determinístico, o CI e a paridade |
| Marcar um critério de aceite como atendido sem o comando/assert correspondente | é assim que um repositório passa a mentir |

## Ordem de leitura dos planos

| # | Documento | Por quê |
|---|---|---|
| — | [`../../AGENT_BRIEF.md`](../../AGENT_BRIEF.md) | **primeiro de tudo**: estado real, ordem dos marcos, anti-padrões |
| 01 | [Arquitetura](01-arquitetura.md) | como as peças se encaixam; contratos internos |
| 02 | [UI e workspace](02-ui-chat-e-workspace.md) | os painéis e os estados |
| 16 | [Design system dark](16-design-system-dark.md) | tokens, tipografia, animações |
| 15 | [Galeria de modelos](15-galeria-de-modelos.md) | a porta determinística |
| 14 | [Conta e autenticação](14-auth-e-conta.md) | login Google, tokens, gate |
| 17 | [Persistência de conversas](17-persistencia-de-conversas.md) | histórico local |
| 06 | [Agente](06-agente-eng-florestal.md) | tools, prompt, orçamento de contexto |
| 04 | [Motor `.mxd`](04-motor-mxd.md) | o coração do produto e a parte mais difícil |
| 03 | [Núcleo Python](03-nucleo-python.md) | onde a geo acontece |
| 05 | [Renderizador nativo](05-motor-pdf-nativo.md) | preview e fallback |
| 07 | [Print → mapa](07-visao-print-e-zip.md) | "faz igual a esse aqui" |
| 08 | [Planilhas](08-planilhas-e-relatorios.md) | `.xlsx` de quantitativos |
| 09 | [Validação](09-validacao-conformidade.md) | os checks HARD/SOFT na prática |
| 10 | [Testes](10-testes-e-qa.md) | como se testa isso sem ArcGIS no CI |
| 11 | [Empacotamento](11-empacotamento-instalador.md) | virar `.exe` |
| 12 | [Roadmap](12-roadmap.md) | marcos e critérios de saída |
| 13 | [Checklist de implementação](13-checklist-implementacao.md) | o que fazer agora |
