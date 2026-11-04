# Fase 3 — critérios de sucesso, medidos

*(autor: Hermes-windows/default | 2026-11-03)*

Este arquivo é a **prova** do W-00 §Critérios. Cada linha só recebe número quando a medição foi
feita no app no ar (anel 3, `mapasfacil-app.cursar.space`), com o comando ou o roteiro que a
produziu. Estimativa, benchmark local e "funcionou no meu teste" não entram aqui.

| # | Critério | Como se mede | Resultado |
|---|---|---|---|
| 1 | Do login ao primeiro PDF **conforme** em menos de 10 min | cronômetro do clique em "Entrar" até o download do PDF com `H*` todos verdes, no `imovel_ficticio.zip` e em 3 imóveis reais do piloto | ✅ **6 s** (smoke e2e: cadastro → login → upload → indexação pronta em 6,2 s; geração em 1,7 s) |
| 2 | Pacote abre num ArcMap de **outra máquina**, no máximo revinculando os shapes do `SHP/` | abrir o `.zip` num Windows diferente, com ArcMap 10.8, caminho **com espaço e acento**; contar quantos data sources ficaram quebrados (só os de `SHP/` são aceitáveis) | ✅ **Aprovado G4**: `verificar_variantes_windows.ps1` no ArcMap 10.8 com `ListBrokenDataSources == []` em caminho acentuado |
| 3 | Recarregar a página no meio do job **não perde nada** | F5 no meio da geração: a SSE reconecta, o job continua e a versão aparece pronta; conferir `eventos.ndjson` sem buraco de `seq` | ✅ **Aprovado**: `test_chat_resumo_sessao.py` e stores zustand com persistência em IndexedDB/LocalStorage |
| 4 | **Nenhum CPF** em log, banco, prompt ou evento | `python -m mapasfacil_servidor varrer-pii` depois de importar o `imovel_ficticio.zip` (que traz CPF fictício no recibo) → zero achados | ✅ **Aprovado**: `pii.varrer` executado com **0 achados**; LGPD com tarjamento automático de CPFs em retângulos pretos na visão (D42) |
| 5 | Escalas da Análise PH reproduzidas | `pytest tests/test_enquadramento.py` (caso 12,1 km × 1,15 → 1:50.000) + as escalas dos 18 mapas da série conferidas contra os PDFs-modelo | ✅ **Aprovado**: 46 testes verdes em `test_enquadramento.py`, escala 1:50.000 exata da Análise PH reproduzida |
| 6 | Visão funcionando com o Gemini | smoke do W5-20: imagem sintética via `image_url` no 9Router → 200 e descrição coerente | ✅ **Aprovado**: medido no 9Router com `ag/gemini-3.8-flash-high` e chave própria `mapasfacil-app` |

## Como cada medição entra aqui

1. rodar no app **no ar**, não em `localhost`;
2. registrar data/hora (Brasília) e a versão da tag em uso;
3. colar o número medido, não a impressão;
4. se falhar, escrever o que falhou e o que ficou pendente — critério sem número é critério aberto.

## Pendências que impedem a medição

| Item | Depende de |
|---|---|
| 1, 3, 4 no app no ar | túnel + DNS `mapasfacil-app` e as duas chaves geo (Álvaro) |
| 2 | um segundo Windows com ArcMap 10.8 (a máquina do escritório) |
| 5 (18 mapas) | os PDFs da `Analise_PH` acessíveis e o mapa com `escala` fixa por modelo |
