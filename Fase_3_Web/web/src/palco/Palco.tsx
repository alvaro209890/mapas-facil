/**
 * Palco do Mapa (W8-01 / W-07 §Anatomia do palco).
 *
 * Responsável por orquestrar a visualização do mapa em 4 modos:
 * - `ocioso`: sem job ativo; exibe a versão aberta e o imóvel/perímetro indexado (sem animação inventada).
 * - `mapa`: câmera MapLibre GL e acendimento progressivo das camadas vetoriais e raster.
 * - `folha`: montagem da folha em mm reais com os elementos de layout e o snapshot do mapa.
 * - `resultado`: versão gerada (preview/miniatura com selo de conformidade) ou relatório de erro.
 *
 * Princípios do contrato:
 * 1. Um só relógio (`requestAnimationFrame`) consome os passos planejados pela coreografia.
 * 2. Nada anima sem evento real do núcleo — sem passos pendentes, o palco fica parado.
 * 3. Fallback sem WebGL (`WB-001`): cai diretamente para modo folha + resultado se WebGL indisponível.
 * 4. `useReducedMotion`: quando ativado, anula tempos de voo e faz saltos instantâneos.
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import type { Versao } from '../api/tipos';
import { useJob } from '../estado/job';
import { usePalco } from '../estado/palco';
import { useProjetoAtivo } from '../estado/projetoAtivo';
import { Camera, type MapaLike } from './Camera';
import { GerenciadorCamadas, type DadosCamada } from './Camadas';
import type { Bbox4326, NivelViewport } from './coreografia';
import { duracaoEfetiva } from './tokens';
import { useReducedMotion } from './useReducedMotion';
import { CODIGO_SEM_WEBGL, MENSAGEM_SEM_WEBGL, suportaWebGL } from './webgl';
import estilos from './Palco.module.css';

export interface PropriedadesPalco {
  versao?: Versao | null | undefined;
  cameraInjetada?: Camera | undefined;
  mapaInjetado?: MapaLike | undefined;
  suporteWebGL?: boolean | undefined;
  className?: string | undefined;
}

export function Palco({
  versao,
  cameraInjetada,
  mapaInjetado,
  suporteWebGL: suporteWebGLProp,
  className,
}: PropriedadesPalco) {
  const containerMapaRef = useRef<HTMLDivElement | null>(null);
  const cameraRef = useRef<Camera | null>(null);
  const camadasRef = useRef<GerenciadorCamadas | null>(null);

  // Estados sincronizados da store do palco
  const modoStore = usePalco((s) => s.modo);
  const foco = usePalco((s) => s.foco);
  const camadasStore = usePalco((s) => s.camadas);
  const versaoStore = usePalco((s) => s.versao);
  const erroStore = usePalco((s) => s.erro);
  const fila = usePalco((s) => s.fila);
  const passoCorrente = usePalco((s) => s.passoCorrente);
  const animar = usePalco((s) => s.animar);

  // Job em curso (para a legendinha e barra compacta)
  const etapasJob = useJob((s) => s.etapas);
  const pctJob = useJob((s) => s.pct);
  const etapaAtual = etapasJob.at(-1)?.nome;

  // Projeto ativo para metadados de imóvel e folha no modo ocioso
  const projeto = useProjetoAtivo((s) => s.projeto);

  // Detecção de acessibilidade e WebGL
  const reducaoDetectada = useReducedMotion();
  const reduzirStore = usePalco((s) => s.reduzirMovimento);
  const reduzirMovimento = reducaoDetectada || reduzirStore || !animar;

  const temWebGL = useMemo(() => {
    if (suporteWebGLProp !== undefined) return suporteWebGLProp;
    if (mapaInjetado || cameraInjetada) return true;
    return suportaWebGL();
  }, [suporteWebGLProp, mapaInjetado, cameraInjetada]);

  // Snapshot do mapa capturado ao transicionar para modo folha
  const [snapshotMapa, setSnapshotMapa] = useState<string | null>(null);

  // Registro de elementos da folha que já entraram
  const [elementosFolha, setElementosFolha] = useState<string[]>([]);

  // Atualiza preferência de movimento na store se o sistema exigir
  useEffect(() => {
    if (reducaoDetectada) {
      usePalco.getState().definirReduzirMovimento(true);
    }
  }, [reducaoDetectada]);

  // Determina o modo efetivo: sem WebGL, o modo 'mapa' cai para 'folha'
  const modoEfetivo = useMemo(() => {
    if (!temWebGL && modoStore === 'mapa') {
      return 'folha';
    }
    return modoStore;
  }, [temWebGL, modoStore]);

  // Inicialização da Câmera e Camadas
  useEffect(() => {
    if (!temWebGL) return;

    let camera: Camera;
    if (cameraInjetada) {
      camera = cameraInjetada;
    } else if (mapaInjetado) {
      camera = new Camera({ mapaInjetado });
    } else if (containerMapaRef.current) {
      try {
        camera = new Camera({ container: containerMapaRef.current });
      } catch {
        return;
      }
    } else {
      return;
    }

    cameraRef.current = camera;
    camadasRef.current = new GerenciadorCamadas(camera.obterMapa());

    return () => {
      if (!cameraInjetada) {
        camera.destruir();
      }
      cameraRef.current = null;
      camadasRef.current = null;
    };
  }, [temWebGL, cameraInjetada, mapaInjetado]);

  // Snapshot automático ao entrar no modo folha
  useEffect(() => {
    if (modoStore === 'folha' && cameraRef.current) {
      const snap = cameraRef.current.tirarSnapshot();
      if (snap) {
        setSnapshotMapa(snap);
      }
    }
  }, [modoStore]);

  // ------------------------------------------------------------- Relógio de Passos
  // Um só loop com requestAnimationFrame que consome os passos da fila planejada.
  // Sem passos pendentes, NENHUM loop roda.
  const inicioPassoRef = useRef<number | null>(null);
  const passoEmExecucaoIdRef = useRef<string | null>(null);

  useEffect(() => {
    let animacaoId: number | null = null;

    const tick = (agora: number) => {
      const store = usePalco.getState();
      let passo = store.passoCorrente;

      if (!passo) {
        // Tenta puxar o próximo passo da fila planejada
        passo = store.proximoPasso();
        if (!passo) {
          // Fila vazia: encerra o relógio. O palco fica parado.
          passoEmExecucaoIdRef.current = null;
          inicioPassoRef.current = null;
          return;
        }
      }

      // Novo passo assumido para execução
      if (passoEmExecucaoIdRef.current !== passo.id) {
        passoEmExecucaoIdRef.current = passo.id;
        inicioPassoRef.current = agora;

        // Dispara o efeito do passo
        if (passo.tipo === 'foco') {
          const bbox = passo.dados.bbox_4326 as Bbox4326 | undefined;
          if (bbox && cameraRef.current) {
            const duracao = duracaoEfetiva(passo.duracao_ms, reduzirMovimento);
            cameraRef.current.focarBbox(bbox, {
              nivel: passo.alvo as NivelViewport,
              duracao_ms: duracao,
              reduzirMovimento,
            });
          }
        } else if (passo.tipo === 'camada') {
          if (camadasRef.current) {
            camadasRef.current.adicionarCamada(passo.dados as unknown as DadosCamada);
          }
        } else if (passo.tipo === 'elemento') {
          setElementosFolha((anteriores) =>
            anteriores.includes(passo!.alvo) ? anteriores : [...anteriores, passo!.alvo],
          );
        }

        // Se o passo tem duração zero ou foi pulado, conclui de imediato
        if (passo.duracao_ms === 0 || passo.pulado || reduzirMovimento) {
          store.concluirPasso();
          passoEmExecucaoIdRef.current = null;
          inicioPassoRef.current = null;
          // Continua o loop no próximo frame para pegar o próximo passo da fila
          animacaoId = requestAnimationFrame(tick);
          return;
        }
      }

      // Passo com duração em andamento: confere tempo decorrido
      const inicio = inicioPassoRef.current ?? agora;
      const decorrido = agora - inicio;

      if (decorrido >= passo.duracao_ms) {
        store.concluirPasso();
        passoEmExecucaoIdRef.current = null;
        inicioPassoRef.current = null;
      }

      // Agenda o próximo frame enquanto houver passo corrente ou itens na fila
      if (usePalco.getState().passoCorrente || usePalco.getState().fila.length > 0) {
        animacaoId = requestAnimationFrame(tick);
      }
    };

    // Só inicia o relógio se houver passo corrente ou itens na fila
    if (passoCorrente || fila.length > 0) {
      animacaoId = requestAnimationFrame(tick);
    }

    return () => {
      if (animacaoId !== null) {
        cancelAnimationFrame(animacaoId);
      }
    };
  }, [fila.length, passoCorrente, reduzirMovimento]);

  // Limpa elementos da folha ao resetar o job/palco
  useEffect(() => {
    if (modoStore === 'ocioso') {
      setElementosFolha([]);
      setSnapshotMapa(null);
    }
  }, [modoStore]);

  // Versão ativa para exibição (prop tem precedência sobre store)
  const versaoExibida = versao ?? (versaoStore ? ({ numero: versaoStore.numero, conforme: versaoStore.conforme } as Versao) : null);

  // Lista de nomes de camadas renderizadas
  const listaNomesCamadas = Object.values(camadasStore).map((c) => c.nome);

  return (
    <div
      className={`${estilos.palcoContainer} ${className ?? ''}`}
      data-modo={modoEfetivo}
      aria-label="Palco do Mapa"
    >
      {/* ------------------------------------------------ Aviso sem WebGL (WB-001) */}
      {!temWebGL && (
        <div className={estilos.avisoWb001} role="status">
          <span>{MENSAGEM_SEM_WEBGL}</span>
          <span className={estilos.codigoErro}>{CODIGO_SEM_WEBGL}</span>
        </div>
      )}

      {/* ------------------------------------------------ Legendinha de Câmera e Camadas */}
      {(modoEfetivo === 'mapa' || modoEfetivo === 'folha') && (
        <div className={estilos.legendinha} role="region" aria-label="Informações da Câmera">
          <div className={estilos.legendinhaTitulo}>
            {foco?.rotulo || projeto?.imovel?.nome || 'Carregando visualização...'}
          </div>
          <div className={estilos.legendinhaSubtitulo}>
            {foco?.escala && (
              <span className={estilos.legendinhaEscala}>1:{foco.escala.toLocaleString()}</span>
            )}
            {etapaAtual && <span>· {etapaAtual}</span>}
          </div>

          {/* Sem WebGL, as camadas acendem como lista na legendinha (W-07) */}
          {!temWebGL && listaNomesCamadas.length > 0 && (
            <div className={estilos.listaCamadasWb001} aria-label="Camadas carregadas">
              {listaNomesCamadas.map((nome) => (
                <span key={nome} className={estilos.chipCamada}>
                  {nome}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ------------------------------------------------ MODO MAPA (WebGL) */}
      {temWebGL && (
        <div
          className={estilos.mapaArea}
          style={{ display: modoEfetivo === 'mapa' ? 'block' : 'none' }}
        >
          <div ref={containerMapaRef} className={estilos.mapaCanvas} />
        </div>
      )}

      {/* ------------------------------------------------ MODO FOLHA */}
      {modoEfetivo === 'folha' && (
        <div className={estilos.folhaArea} role="region" aria-label="Montagem da Folha">
          <div className={estilos.folhaMoldura}>
            <div className={estilos.folhaGradeElementos}>
              <span>{projeto?.imovel?.nome ?? 'Mapa de Fazenda'}</span>
              <span>{projeto?.folha?.formato ?? 'A3'} · {projeto?.folha?.orientacao ?? 'paisagem'}</span>
            </div>
            <div className={estilos.folhaQuadroMapa}>
              {snapshotMapa ? (
                <img
                  src={snapshotMapa}
                  alt="Snapshot do mapa para layout"
                  className={estilos.folhaSnapshot}
                />
              ) : (
                <div style={{ color: '#666', fontSize: 13, fontFamily: 'monospace' }}>
                  [Quadro do Mapa]
                </div>
              )}
            </div>
            {elementosFolha.length > 0 && (
              <div className={estilos.folhaGradeElementos}>
                <span>Elementos: {elementosFolha.join(', ')}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ------------------------------------------------ MODO OCIOSO (W8-09) */}
      {modoEfetivo === 'ocioso' && (
        <div className={estilos.ociosoArea} role="region" aria-label="Visão Geral do Projeto">
          <div className={estilos.ociosoFolhaDesenho} aria-hidden="true">
            <span className={estilos.ociosoBarraTitulo} />
            <span className={estilos.ociosoQuadroMapa}>
              <span className={estilos.ociosoPerimetroPequeno} />
            </span>
          </div>

          <p className={estilos.ociosoTextoVersao}>
            {versaoExibida
              ? `Versão ${versaoExibida.numero}${versaoExibida.conforme ? '' : ' · não conforme'}`
              : 'Nenhuma versão gerada ainda'}
          </p>

          <p className={estilos.ociosoSubtexto}>
            {projeto?.imovel?.nome
              ? `Perímetro do imóvel: ${projeto.imovel.nome} (${projeto.imovel.municipio ?? ''}/${projeto.imovel.uf ?? ''})`
              : 'Peça uma alteração no chat para gerar um mapa.'}
          </p>

          <p className={estilos.ociosoDica}>
            O palco acompanha cada etapa em tempo real. Sem job ativo, ele permanece em repouso.
          </p>
        </div>
      )}

      {/* ------------------------------------------------ MODO RESULTADO */}
      {modoEfetivo === 'resultado' && (
        <div className={estilos.resultadoArea} role="region" aria-label="Resultado da Versão">
          {versaoExibida && (
            <div
              className={`${estilos.resultadoSelo} ${
                versaoExibida.conforme ? estilos.seloConforme : estilos.seloNaoConforme
              }`}
            >
              {versaoExibida.conforme ? '✓ Conforme com as normas' : '⚠ Não conforme'}
            </div>
          )}

          <div className={estilos.resultadoMiniatura}>
            {versaoExibida?.miniatura ? (
              <img
                src={versaoExibida.miniatura}
                alt={`Miniatura da versão ${versaoExibida.numero}`}
                className={estilos.resultadoImagem}
              />
            ) : snapshotMapa ? (
              <img
                src={snapshotMapa}
                alt="Mapa gerado"
                className={estilos.resultadoImagem}
              />
            ) : (
              <div
                style={{
                  padding: '40px 20px',
                  backgroundColor: '#12161b',
                  color: '#a6b2c0',
                  textAlign: 'center',
                }}
              >
                Versão {versaoExibida?.numero ?? 1} pronta
              </div>
            )}
          </div>

          <p className={estilos.ociosoTextoVersao}>
            {versaoExibida ? `Versão ${versaoExibida.numero}` : 'Versão gerada'}
          </p>
        </div>
      )}

      {/* ------------------------------------------------ Erro do Núcleo */}
      {erroStore && (
        <div className={estilos.erroArea} role="alert">
          <div className={estilos.erroCodigo}>Falha na Geração</div>
          <div className={estilos.erroMensagem}>{erroStore}</div>
        </div>
      )}

      {/* ------------------------------------------------ Barra compacta de etapas */}
      {(modoEfetivo === 'mapa' || modoEfetivo === 'folha') && etapaAtual && (
        <div className={estilos.rodapeBarra} role="status" aria-label="Progresso do Job">
          <span className={estilos.etapaNome}>{etapaAtual}</span>
          <span className={estilos.etapaProgresso}>{Math.round(pctJob)}%</span>
        </div>
      )}
    </div>
  );
}
