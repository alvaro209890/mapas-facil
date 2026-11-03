# Rodada 2026-11-03 — W4: upload por partes, extração segura e importação

Marco: **W4** (plano [W-02](../Fase_3_Web/planos/02-projeto-folha-e-upload.md))
Branch: `planos/fase3-web-chat` · executor: Hermes-windows · delegação: nenhuma

## Feito

| Tarefa | Arquivo | O que ficou |
|---|---|---|
| W4-01 | `importacao/upload.py` | criar upload (parte de `MF_UPLOAD_PARTE_MB`), `PUT` de parte com `X-Parte-SHA256` (idempotente), estado com `partes_ok`/`faltam` para retomada, `concluir` que recalcula `hash_partes` e grava o arquivo com sha256 em streaming |
| W4-02 / W4-05 | `api/importacao.py` | `POST /uploads`, `PUT /uploads/{u}/partes/{n}`, `GET /uploads/{u}`, `POST /uploads/{u}/concluir`, `POST /projetos/{id}/importacao` (202 + background), `GET /importacoes/{id}`, `GET /projetos/{id}/resumo` |
| W4-04 | `importacao/extrair.py` | `verificar` + `extrair` na ordem do plano: zip-slip (`SV-104`), symlink (`SV-105`), zip-bomba por soma (`SV-106`) e por razão 200:1 (`SV-107`), contagem (`SV-108`), ZIP inválido (`SV-110`), extensão fora da allowlist vira aviso (`SV-120`), duplicata ignorada (`SV-122`), nome cp437/cp850 normalizado NFC, `entrada/` marcado 0440/0550 |
| W4-06 | `importacao/servico.py` | `importar()`: transiciona `importando → indexando → pronto`, copia `entrada.zip`, guarda `entrada.anterior/<carimbo>` na reimportação (W4-07), chama `workspace.abrir` pela ponte quando há pool, grava resumo, e **sempre** deixa o projeto em `erro` com código quando falha |
| W4-08 | `fixtures/gerar_zip_sintetico.py` | ZIP sintético com `.shp/.shx/.dbf/.prj/.cpg` escritos à mão em SIRGAS 2000/UTM 22S + recibo PDF vazio — `zipfile.testzip()` devolve `None` |
| W4-09 | `tests/test_importacao.py` | CPF fictício dentro do PDF e de um `.txt` do pacote; varre as respostas da API e as tabelas `projetos`, `importacoes` e `auditoria` |
| — | `manutencao.py` | uploads com mais de 24 h e lixeira com mais de 30 dias são apagados por `limpar-lixeira` |

## Comandos e resultados

```
cd Fase_3_Web/servidor
.venv/Scripts/python.exe -m pytest -q tests/     → 97 testes, 0 falhas
python Fase_3_Web/fixtures/gerar_zip_sintetico.py --destino /tmp/imovel_ficticio.zip
                                                 → ZIP válido (testzip() None), 7 entradas
```

## Decisões de implementação

1. **Nome do módulo de upload é `upload.py`**, não `partes.py` como dizia o plano — ele
   cobre o ciclo inteiro (criar, partes, estado, concluir), não só as partes.
2. **`hash_partes` = sha256 da concatenação dos hex das partes.** É o único jeito de o
   navegador provar integridade sem hash incremental (`crypto.subtle.digest` não faz).
3. **Erro em background não sobe como exceção.** O Starlette estoura "response already
   started"; o erro já está em `importacoes.erro_codigo` e no estado do projeto, então o
   handler engole depois de registrar. O usuário vê `SV-110` no projeto e no `GET`.
4. **Extensão fora da allowlist não derruba a importação**: vira aviso `SV-120` e o arquivo
   é ignorado — perder o pacote inteiro por causa de um `.exe` perdido seria pior.

## Pendências

- 🟠 **W1-10 (`doctor.py`)** continua bloqueada pela ordem do Álvaro.
- 🟡 **W4-10 (SAD69 → SIRGAS 2000)**: o núcleo só trata EPSG:4326/4674. Sem reprojeção o
  imóvel cai ~60 m. Falta `geo/crs.py` com a transformação Helmert oficial **e** um `.zip`
  real do SIMCAR para medir o deslocamento antes de ligar.
- 🟡 **W4-03 (`web/src/api/upload.ts`)**: trilha B, ainda não iniciada.
- 🟡 **Progresso da importação** hoje é polling por `GET /importacoes/{id}`; o SSE chega no W5.

## Próximo

W5 — stream de eventos (SSE) + chat relay (plano `05-chat-agente-web.md`).
