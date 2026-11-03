# Fase 3 — critérios de sucesso, medidos

*(autor: Hermes-windows/default | 2026-11-03)*

Este arquivo é a **prova** do W-00 §Critérios. Cada linha só recebe número quando a medição foi
feita no app no ar (anel 3, `mapasfacil-app.cursar.space`), com o comando ou o roteiro que a
produziu. Estimativa, benchmark local e "funcionou no meu teste" não entram aqui.

| # | Critério | Como se mede | Resultado |
|---|---|---|---|
| 1 | Do login ao primeiro PDF **conforme** em menos de 10 min | cronômetro do clique em "Entrar" até o download do PDF com `H*` todos verdes, no `imovel_ficticio.zip` e em 3 imóveis reais do piloto | ⏳ a medir |
| 2 | Pacote abre num ArcMap de **outra máquina**, no máximo revinculando os shapes do `SHP/` | abrir o `.zip` num Windows diferente, com ArcMap 10.8, caminho **com espaço e acento**; contar quantos data sources ficaram quebrados (só os de `SHP/` são aceitáveis) | ⏳ a medir |
| 3 | Recarregar a página no meio do job **não perde nada** | F5 no meio da geração: a SSE reconecta, o job continua e a versão aparece pronta; conferir `eventos.ndjson` sem buraco de `seq` | ⏳ a medir |
| 4 | **Nenhum CPF** em log, banco, prompt ou evento | `python -m mapasfacil_servidor varrer-pii` depois de importar o `imovel_ficticio.zip` (que traz CPF fictício no recibo) → zero achados | ⏳ a medir |
| 5 | Escalas da Análise PH reproduzidas | `pytest tests/test_enquadramento.py` (caso 12,1 km × 1,15 → 1:50.000) + as escalas dos 18 mapas da série conferidas contra os PDFs-modelo | 🟡 parcial: o algoritmo e o caso de aceite estão verdes; falta a conferência dos 18 |
| 6 | Visão funcionando com o Gemini | smoke do W5-20: imagem sintética via `image_url` no 9Router → 200 e descrição coerente | ✅ medido em 2026-11-03 (`docs/fase3-rodada-2026-11-03-w10-enquadramento-e-provider.md`) |

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
