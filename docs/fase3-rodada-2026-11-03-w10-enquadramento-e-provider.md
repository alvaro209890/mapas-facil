# Rodada 2026-11-03 — W-10 (enquadramento) + W5-16/W5-20 medidos

*(autor: Hermes-windows/default | 2026-11-03)*

Duas coisas que a revisão do Claude apontou, encaixadas depois do W6:
**(1)** o `enquadramento.py` estava fora do plano W-10; **(2)** a chave do 9Router podia ser
criada por mim — e os smokes W5-16/W5-20 estavam pendentes. As duas estão fechadas com número.

---

## 1. Enquadramento fora do plano — corrigido

Antes: `MARGEM = 0.08` e escala tirada da lista fixa `config.ESCALAS_PERMITIDAS`.
Agora `motores/enquadramento.py` implementa os 10 passos do W-10:

| Passo do W-10 | Como está no código |
|---|---|
| Faixa útil **abaixo do título** | `faixa_util(perfil)` = maior retângulo do quadro que não toca título, rosa, minimapa, metadados, legenda, logo (recorte em profundidade; a `tabela` só conta quando o MapSpec pede, senão engolia 2 cm do quadro em todo mapa) |
| Margem de **15 %** | `MARGEM = 0.15` (7,5 % por lado) |
| Escala redonda **para cima** por degraus | `escala_redonda()`: até 1:10.000 → múltiplo de 500 · 1:10.000–1:200.000 → 5.000 · 1:200.000–1:1.000.000 → 50.000 · acima → 100.000 |
| Mesma escala em toda a série | `escala_da_serie()` + `com_escala()`; a série em `analise/executar.py` calcula **uma** escala do grupo base e passa em cada `montar_mapspec(escala=…)`; mapas de contexto (folga 3,0/6,0) mantêm a própria |
| Caixas `imovel` / `imovel_mais_alvo` / `area_tematica` | `caixa_de_conteudo()` — `area_tematica` sem a feição do tema cai no imóvel em vez de devolver caixa vazia |
| Escala pedida não pode cortar | `NU-310` diz quanto cortaria e qual a menor escala que cabe (não corta em silêncio) |
| CRS pela zona do centroide | `31980` (20 S) / `31981` (21 S) / `31982` (22 S) |
| Tabela folha × orientação | `sugerir()` / `melhor()` — 10 combinações A4–A0, ordenadas por aproveitamento |

**Prova do aceite (o exemplo do Álvaro):** 12,1 km × 1,15 = 13.915 m em 285,5 mm de faixa →
**1:48.737** → degrau de 5.000 → **1:50.000**.
`tests/test_enquadramento.py::test_ph_sai_a_1_50000` e `test_conta_da_ph_antes_do_arredondamento`
(46 testes no arquivo, todos verdes).

**Ajuste da tool (`W5-12`):** `sugerir_enquadramento` agora aceita `caixa` e `escala_fixa`, devolve
a tabela por folha **e** o enquadramento resolvido da folha atual (escala, extent, deslocamento da
faixa, aproveitamento). Escala pedida que não cabe volta como `NU-310` com o motivo, não como erro
genérico.

**Efeito colateral necessário:** `mapspec/validar.py` passou a aceitar escala de degrau
(`escala_valida()`), senão o próprio validador recusaria 1:65.000 ou 1:850.000 produzidos pelo
cálculo. A lista fechada continua valendo para a escolha do **usuário** (`definir_escala`).

---

## 2. Chave do 9Router — criada e gravada (sem aparecer em lugar nenhum)

| Item | Valor |
|---|---|
| Nome da chave | `mapasfacil-app` |
| ID | `caaadc95-d1ca-4bf9-b661-9d89544b3517` |
| Onde mora o valor | `/home/server/segredos-mapasfacil/servidor.env` (ext4, **600**, `server:server`, dir 700) |
| Caminho documentado (symlink) | `/home/server/mapasfacil/segredos/servidor.env` |
| No vault | só o nome da chave e o caminho do arquivo |

⚠️ **Achado:** `MF_RAIZ` (`/media/server/HD Backup`) é `fuseblk` com `default_permissions` — ali
`chmod` **não pega** (tudo sai 777). Por isso o arquivo real ficou no ext4 do home e o caminho
dentro do `MF_RAIZ` é symlink: o `MF_SEGREDOS`/preflight continua encontrando, o valor fica
protegido.

Variáveis gravadas no mesmo arquivo (nomes só; valores são segredo):

```
MAPASFACIL_PROVEDOR_CHAVE     (35 chars)
MAPASFACIL_PROVEDOR=openai_compat
MAPASFACIL_PROVEDOR_URL=http://100.104.255.35:20128/v1
MAPASFACIL_MODELO_CHAT=ag/gemini-3.8-flash-high
MAPASFACIL_RACIOCINIO=high
MAPASFACIL_CONTEXTO_MAX=40000
MAPASFACIL_MODELO_VISAO=ag/gemini-3.8-flash-high
```

---

## 3. W5-16 — smoke ao vivo (`ferramentas/provedor_smoke.py --9router`)

Ferramenta nova: `ferramentas/provedor_smoke.py` (chave por `--env arquivo` **ou** `--env -` por
pipe de SSH; nunca imprime o valor). Resultado medido com a chave `mapasfacil-app`:

| Bloco | Resultado |
|---|---|
| `tools` | 32 schemas enviados · `finish_reason=tool_calls` · `listar_versoes` com argumentos JSON válidos |
| `paralelo` | `estado_do_projeto` + `listar_versoes` **no mesmo turno** (a UI mostra as duas juntas) |
| `longo` | resultado de tool de **6.257 chars**; o modelo achou a camada marcada no meio do texto |
| `raciocinio` | `reasoning_content` chega (1.000 chars) e a resposta foi **1:50.000** — a mesma conta do W-10 |
| `stream` | 46 pedaços, 5.465 chars, `finish_reason=stop`, não truncado |
| `contexto` | prompt de **180.000 chars** aceito (≈45 mil tokens reais) |

**Cuidado medido:** `usage.prompt_tokens` do 9Router é **inflado** (14.842 para um prompt de ~900
tokens; 104.701 para os 180.000 chars). Não serve para dimensionar nada. Por isso
`MAPASFACIL_CONTEXTO_MAX=40000` é margem **medida** (tudo que testamos passou), não o 1.048.576 que
o catálogo anuncia — a mesma desconfiança que o plano já registrava sobre o número anunciado.

---

## 4. W5-20 — visão pelo mesmo Gemini (obrigatória)

Print **sintético** de mapa (1.400×990, 16 KB, "CARTA SINTÉTICA — SEM DADO DE CLIENTE"):
`image_url` em base64 → **200** e o modelo descreveu imóvel em verde, área "TI" em bege, escala e
legenda. Ou seja: **o 9Router repassa imagem** e `MAPASFACIL_MODELO_VISAO=ag/gemini-3.8-flash-high`
funciona. `openai_compat.modelo_visao()` entrou para o servidor não repetir a regra.

---

## 5. Estado dos testes

| Suíte | Resultado |
|---|---|
| núcleo (desktop + servidor) | **628 passando**, 0 falha |
| servidor (Fase 3) | **164 passando** |
| `tests/test_enquadramento.py` | **46 passando** |

Pendências que continuam: W1-10 (`doctor.py`, esperando autorização), W4-10 (SAD69 precisa de ZIP
real do SIMCAR), W5-17 (`web_hard` só nasce no W7/W9), W6-10 já commitado, W7 em diante.
