# Agente PDF-first — plano vivo (2026-11-06)

Autor: Hermes-windows/default. Pedido: evoluir o app web sem apagar projetos nem o export MXD opcional.
Backup do HEAD inicial 0b43da3 fora do repo: cache/scratch/mapas-facil-pre-agente-v2-0b43da3.zip.
Arquivo alheio preservado: Referencias_IMAP/MXD/Dinamica_retrato_pre_projeto.mxd (untracked).

## Checkpoints

- [x] F1 — LayoutSpec versionado, perfis medidos, medição/validação, PDF-first e pacote Mapas/SHP/XLSX; testes e golden/anatomia.
- [x] F2 — registro de ferramentas, workspace/geo/PDF/memória/skills, plano e eventos persistidos, cancelamento; Python livre desligado se isolamento não comprovado.
- [x] F3 — QA visual real + dois imóveis sintéticos, migração aditiva, mapas individuais e tabela combinada; E2E.
- [x] F4 — revisão independente, suítes núcleo/servidor/web, UI desktop/mobile, backup/deploy/rollback, smoke público, docs/vault, commits separados e push main/CI.

## Contratos de integração

Eventos agente.plano {passos:[{id,titulo,status}]}; agente.passo {id,titulo,status,resumo?}; agente.arquivo {caminho,acao}; agente.preview {caminho,pagina?}; agente.aprovacao {acao,caminho,motivo}; agente.fim {status,resumo?,versao?}. Caminhos relativos somente. Status de passo: pendente/em_andamento/concluido/erro/cancelado. Nunca produzir sucesso sintético.

MapSpec mantém imovel para compatibilidade e ganha imoveis[] aditivo. Cada geração continua versionada. LayoutSpec é dado versionado sem qualquer dependência de MXD. MF_MXD=1 libera somente export explicitamente pedido.

python_exec: fail-closed por padrão; não chamar audit hook de sandbox seguro. Sem liberação pública sem prova de isolamento OS, sem rede, sem segredos e limites de recursos.

## Divisão de trabalho sem colisões

- Layout: motores nativo/perfil/gerar, pacote, galeria, LayoutSpec/schema próprio, testes próprios. Não editar MapSpec schema (responsável multi-imóvel).
- Agente: agente/, protocolo.py, shared/skills, testes próprios; não editar motores/schema/server/web.
- Multi-imóvel: núcleo multi_imovel.py e workspace, MapSpec schema, importação/db/migração/APIs servidor, testes próprios. Integração geração posterior pelo pai.
- Web: Fase_3_Web/web/src exclusivamente; checklist/eventos/reload/preview/cancelamento, termos PDF.
- Pai: integração entre trilhas, docs, deploy, testes ponta a ponta, revisão e commits.

## Evidências e pendências

- Probe SSH sd: SERVER_OK; fila windows contém somente feito/.
- Repo main inicial 0b43da3; AGENTS.md ausente na raiz; global C:/Users/Usuario/AGENTS.md lido.
- Baseline núcleo: `pytest tests -o addopts='' -q` → **1119 passed, 149 warnings, 510.27 s**, exit 0. Há `PytestUnhandledThreadExceptionWarning` de reader subprocess UTF-8/byte 0x80 (watcher); não equivale a saída limpa.
- Baseline servidor: `Fase_3_Web/.venv-teste/Scripts/python.exe -m pytest tests -o addopts='' -q` → **231 passed, 1 warning, 82.98 s**. O `servidor/.venv` está incompleto (PIL ausente); usar `.venv-teste` para essa suíte.
- Delegação corrigida fora do produto: provider ninerouter explicitamente pinado; smoke real PONG_9ROUTER e verificador com pai Codex (6 gates) aprovados. Quatro frentes relançadas.
- Saúde do app antes da implementação: serviço e túnel active, schema 3, público 200. Marcador VERSAO_COMMIT ainda 67bd477 apesar de patches posteriores copiados: não usar marcador sozinho como prova.
- Backup de produção consistente antes da migração: `/home/server/mapasfacil/backups/pre-agente-v2-20261106-160911/` (`mapasfacil.sqlite` integrity_check ok; 1 usuário/1 projeto preservados; codigo.tar.gz 12 MB).
- Pacote web PDF-first (integração do pai): testes RED→GREEN, 4 passed em 1.31 s incluindo dois legados. OpcoesPacote.incluir_mxd=False + MF_MXD=1; XLSX separado; .mxd solto não sai via Mapas/. Integração da API/revisão/suíte completa ainda pendentes.
- Browser Use inicial bloqueado por CDP dedicado 9311 indisponível; Chrome de teste iniciou em IPv6 porque IPv4 da porta está ocupado. Não tocar no listener alheio nem em abas pessoais. QA visual ainda não realizado.
- Ainda não se afirma nenhum aceite implementado.

## Integração e revisão — checkpoint intermediário

- Lote corrigido `deleg_c366207f` terminou pela rota 9Router; os relatos foram revisados, não tratados como aceite.
- Revisão independente reprovou: escala dupla em A3+, conflito de índice único no backfill 0004, nome de ZIP sem sanitização, validação de layout engolindo exceção, entre outros. Correções de layout/servidor estão em frentes isoladas; nada foi implantado por causa disso.
- Suíte integrada diagnóstica do núcleo: **1194 passed, 2 failed, 15 errors, 160 warnings, 369.77 s**; os 15 erros derivam da fixture de minimapa/escala em folhas maiores. XML fora do repo: `cache/scratch/mapasfacil-v2-nucleo.xml`. Não é suíte verde.
- Pai corrigiu com regressões RED→GREEN: caixas inválidas do LayoutSpec não podem virar fallback silencioso; abas XLSX com barras/colisões; vínculo ambíguo recibo/ATP; CAR/área do principal não são herdados por outro imóvel; prompt v3 PDF-first; visão usa o provider configurado do servidor; QA pode ler PDF versionado sem editar a versão; Geo não sobrescreve fonte; aprovação UI obtém token por GET autenticado e manda a decisão no contrato correto; erro de cancelamento não vira cancelado fictício.
- Focados do núcleo após os últimos guards: **18 passed, 9 warnings, 7.31 s**. Multi-imóvel/integridade: **11 passed, 2 warnings, 23.69 s**. Web focado: **24 passed**; typecheck/build corrigidos e aprovados depois de remover parâmetro de teste não utilizado (Vite mantém aviso de bundle >500 kB).
- Browser recuperado sem tocar CDP/abas pessoais: Playwright Python 3.11, Chrome dedicado. Landing ATUAL de produção em desktop 1440×1000 e mobile 390×844: HTTP 200, sem erro JS/overflow, inspeção visual nativa sem cortes. É baseline pré-deploy, não prova de UI nova nem login/importação.
- Prova local corrigida de dois imóveis: **8,00 s**, PDFs Alfa/Beta de 1 página, atlas consolidado de **2 páginas**, XLSX combinado com 4 abas; varredura física `sem_mxd=true`. Saídas explícitas PDF/PNG/XLSX, escala automática e metadados sintéticos. Artefatos fora do repo em `cache/scratch/mapasfacil-multi-prova-pdf/`; isto prova núcleo, não E2E LLM/browser/produção. O fixture canônico histórico pedia MXD explicitamente e foi retirado dessa prova. Regressão de logs/escala PDF-first: **12 passed, 8 warnings, 20.26 s**.
- Continuam pendentes: revisão final de segurança, suítes finais, E2E real com LLM/browser/importação/download/recarga, deploy, commits/push/CI, documentação final e vault. Produção segue preservada no estado anterior.
