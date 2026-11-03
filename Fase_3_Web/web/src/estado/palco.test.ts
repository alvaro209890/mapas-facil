/**
 * W8-06 — store do palco (`estado/palco.ts`).
 *
 * O que importa provar aqui:
 *
 * - a **fila** recebe só evento real de palco e sai na ordem (nada é enfileirado por timer);
 * - **trocar de job** ou de **projeto** zera o palco, e evento do job/projeto alheio é ignorado
 *   (senão o palco de um mapa mostraria camada do mapa de outro);
 * - `limpar()` volta ao modo `ocioso` sem sobrar nada;
 * - a store é casca fina da coreografia: `planejar()` e `proximoPasso()` saem do módulo puro;
 * - `versao.criada`/`nucleo.res` o palco **observa** sem roubar do chat e da linha de versões.
 */

import { beforeEach, describe, expect, it } from 'vitest';

import { despachar } from '../api/ponteWeb';
import type { Evento } from '../api/tipos';
import { useConexao } from './conexao';
import { usePalco } from './palco';
import { useProjetoAtivo } from './projetoAtivo';

const BBOX: [number, number, number, number] = [-51.0, -18.088709, -50.962196, -18.052551];

let proximoSeq = 1;

function evt(nome: string, dados: Record<string, unknown>, extra: Partial<Evento> = {}): Evento {
  return {
    seq: proximoSeq++,
    ts: '2026-11-03T12:00:00Z',
    origem: 'nucleo',
    evento: nome,
    dados,
    ...extra,
  };
}

function foco(nivel: string, extra: Record<string, unknown> = {}): Evento {
  return evt('viewport.foco', { nivel, bbox_4326: BBOX, rotulo: 'Fazenda Harmonia', ...extra });
}

beforeEach(() => {
  proximoSeq = 1;
  usePalco.getState().limpar();
  usePalco.setState({
    projetoId: null,
    descartados: 0,
    animar: true,
    reduzirMovimento: false,
  });
  useConexao.setState({ ultimoSeq: 0, estado: 'parado' });
  useProjetoAtivo.getState().limpar();
});

// ------------------------------------------------------------------ fila

describe('fila de eventos do palco', () => {
  it('aplica o estado na hora e enfileira na ordem de chegada', () => {
    const palco = usePalco.getState();
    expect(palco.aplicarEvento(foco('estado'))).toBe(true);
    expect(palco.aplicarEvento(foco('municipio'))).toBe(true);
    expect(
      palco.aplicarEvento(
        evt('camada.renderizada', { camada_id: 'perimetro', nome: 'Fazenda', estado: 'ok' }),
      ),
    ).toBe(true);
    expect(palco.aplicarEvento(evt('layout.elemento', { elemento: 'legenda' }))).toBe(true);

    const depois = usePalco.getState();
    // O estado não espera a animação: ele já está lá (compressão é só tempo).
    expect(depois.foco?.nivel).toBe('municipio');
    expect(Object.keys(depois.camadas)).toEqual(['perimetro']);
    expect(Object.keys(depois.elementos)).toEqual(['legenda']);
    expect(depois.fila.map((item) => item.tipo)).toEqual([
      'viewport.foco',
      'viewport.foco',
      'camada.renderizada',
      'layout.elemento',
    ]);
    expect(depois.ultimoSeq).toBe(4);
  });

  it('evento que não é do palco devolve false e não entra na fila', () => {
    const palco = usePalco.getState();
    expect(palco.aplicarEvento(evt('job.progresso', { etapa: 'camadas', pct: 30 }))).toBe(false);
    expect(palco.aplicarEvento(evt('chat.delta', { texto: 'oi' }))).toBe(false);
    expect(usePalco.getState().fila).toHaveLength(0);
    expect(usePalco.getState().modo).toBe('ocioso');
  });

  it('consumir() tira sempre o primeiro (FIFO) e devolve null no fim', () => {
    const palco = usePalco.getState();
    palco.aplicarEvento(foco('estado'));
    palco.aplicarEvento(foco('municipio'));
    palco.aplicarEvento(foco('imovel'));

    expect(usePalco.getState().consumir()?.tipo).toBe('viewport.foco');
    expect(usePalco.getState().fila).toHaveLength(2);
    usePalco.getState().consumir();
    usePalco.getState().consumir();
    expect(usePalco.getState().consumir()).toBeNull();
    expect(usePalco.getState().fila).toHaveLength(0);
  });

  it('proximoPasso() planeja pela coreografia, marca o corrente e tira o evento da fila', () => {
    const palco = usePalco.getState();
    palco.aplicarEvento(foco('estado'));
    palco.aplicarEvento(foco('municipio'));

    const primeiro = usePalco.getState().proximoPasso();
    expect(primeiro?.alvo).toBe('estado');
    expect(primeiro?.duracao_ms).toBeGreaterThan(0);
    expect(usePalco.getState().passoCorrente?.id).toBe(primeiro?.id);
    expect(usePalco.getState().fila).toHaveLength(1);

    usePalco.getState().concluirPasso();
    expect(usePalco.getState().passoCorrente).toBeNull();
    expect(usePalco.getState().proximoPasso()?.alvo).toBe('municipio');
    expect(usePalco.getState().proximoPasso()).toBeNull();
    expect(usePalco.getState().passoCorrente).toBeNull();
  });
});

// ------------------------------------------------------------------ modos

describe('seleção do modo', () => {
  it('ocioso → mapa → folha → resultado, na ordem da vida do job', () => {
    const palco = usePalco.getState();
    expect(usePalco.getState().modo).toBe('ocioso');

    palco.aplicarEvento(foco('estado'));
    palco.aplicarEvento(foco('imovel'));
    expect(usePalco.getState().modo).toBe('mapa');

    palco.aplicarEvento(evt('camada.renderizada', { camada_id: 'avn' }));
    expect(usePalco.getState().modo).toBe('mapa');

    palco.aplicarEvento(foco('folha'));
    expect(usePalco.getState().modo).toBe('folha');

    palco.aplicarEvento(
      evt('versao.criada', { versao: { numero: 1, conforme: true } }),
    );
    expect(usePalco.getState().modo).toBe('resultado');
    expect(usePalco.getState().versao).toEqual({ numero: 1, conforme: true });
  });

  it('o primeiro elemento já muda o palco para `folha`', () => {
    usePalco.getState().aplicarEvento(foco('imovel'));
    usePalco.getState().aplicarEvento(evt('layout.elemento', { elemento: 'grade' }));
    expect(usePalco.getState().modo).toBe('folha');
  });

  it('nucleo.res com falha guarda o erro sem virar `resultado`', () => {
    usePalco.getState().aplicarEvento(foco('imovel'));
    expect(
      usePalco
        .getState()
        .aplicarEvento(evt('nucleo.res', { ok: false, erro: { codigo: 'NU-500', mensagem: 'HARD' } })),
    ).toBe(false); // observado: o despachante ainda entrega ao chat
    expect(usePalco.getState().modo).toBe('mapa');
    expect(usePalco.getState().resultado).toBe(false);
    expect(usePalco.getState().erro).toBe('NU-500: HARD');
  });
});

// ------------------------------------------------------------------ troca de job

describe('guarda de job', () => {
  it('adota o primeiro job, ignora evento de outro job e troca quando mandado', () => {
    const palco = usePalco.getState();
    palco.definirJob('j1');

    palco.aplicarEvento(foco('estado', { job_id: 'j1' }));
    expect(usePalco.getState().foco?.nivel).toBe('estado');
    expect(usePalco.getState().fila).toHaveLength(1);

    // Evento do job de outro mapa: ignorado, sem contaminar estado nem fila.
    palco.aplicarEvento(evt('camada.renderizada', { camada_id: 'alheia', job_id: 'j2' }));
    expect(Object.keys(usePalco.getState().camadas)).toEqual([]);
    expect(usePalco.getState().fila).toHaveLength(1);
    expect(usePalco.getState().descartados).toBe(1);

    // Trocar de job limpa o palco e passa a aceitar o novo.
    usePalco.getState().definirJob('j2');
    expect(usePalco.getState().foco).toBeNull();
    expect(usePalco.getState().fila).toHaveLength(0);
    expect(usePalco.getState().eventos).toHaveLength(0);

    usePalco.getState().aplicarEvento(evt('camada.renderizada', { camada_id: 'nova', job_id: 'j2' }));
    expect(Object.keys(usePalco.getState().camadas)).toEqual(['nova']);
  });

  it('o job também pode vir no envelope do SSE, não só em `dados`', () => {
    usePalco.getState().definirJob('j1');
    usePalco
      .getState()
      .aplicarEvento(evt('viewport.foco', { nivel: 'imovel' }, { job_id: 'j2' }));
    expect(usePalco.getState().foco).toBeNull();
    expect(usePalco.getState().descartados).toBe(1);
  });
});

// ------------------------------------------------------------------ troca de projeto

describe('guarda de projeto e limpeza', () => {
  it('trocar de projeto zera o palco e recusa evento do projeto antigo', () => {
    const palco = usePalco.getState();
    palco.definirProjeto('p1');
    palco.aplicarEvento(foco('imovel'));
    usePalco.getState().aplicarEvento(evt('layout.elemento', { elemento: 'legenda' }));
    expect(usePalco.getState().modo).toBe('folha');
    expect(usePalco.getState().fila).toHaveLength(2);

    usePalco.getState().definirProjeto('p2');
    expect(usePalco.getState().foco).toBeNull();
    expect(usePalco.getState().fila).toHaveLength(0);
    expect(usePalco.getState().modo).toBe('ocioso');

    // Evento que se declara do projeto antigo não passa.
    usePalco.getState().aplicarEvento(foco('estado', { projeto_id: 'p1' }));
    expect(usePalco.getState().foco).toBeNull();
    expect(usePalco.getState().descartados).toBe(1);

    // Nem o que chega por contexto do projeto errado.
    usePalco
      .getState()
      .aplicarEvento(foco('estado'), { projetoId: 'p1' });
    expect(usePalco.getState().foco).toBeNull();
    expect(usePalco.getState().descartados).toBe(2);

    // Do projeto certo, passa.
    usePalco.getState().aplicarEvento(foco('estado'), { projetoId: 'p2' });
    expect(usePalco.getState().foco?.nivel).toBe('estado');
  });

  it('definirProjeto com o mesmo id não joga o trabalho fora', () => {
    usePalco.getState().definirProjeto('p1');
    usePalco.getState().aplicarEvento(foco('imovel'));
    usePalco.getState().definirProjeto('p1');
    expect(usePalco.getState().foco?.nivel).toBe('imovel');
    expect(usePalco.getState().fila).toHaveLength(1);
  });

  it('limpar() volta ao ocioso sem sobrar evento, passo nem versão', () => {
    const palco = usePalco.getState();
    palco.aplicarEvento(foco('folha'));
    palco.aplicarEvento(evt('camada.renderizada', { camada_id: 'perimetro' }));
    palco.aplicarEvento(evt('layout.elemento', { elemento: 'titulo_caixa' }));
    palco.aplicarEvento(evt('versao.criada', { versao: { numero: 3, conforme: true } }));
    usePalco.getState().proximoPasso();
    expect(usePalco.getState().modo).toBe('resultado');

    usePalco.getState().limpar();
    const limpo = usePalco.getState();
    expect(limpo.foco).toBeNull();
    expect(limpo.camadas).toEqual({});
    expect(limpo.elementos).toEqual({});
    expect(limpo.fila).toHaveLength(0);
    expect(limpo.eventos).toHaveLength(0);
    expect(limpo.passoCorrente).toBeNull();
    expect(limpo.versao).toBeNull();
    expect(limpo.resultado).toBe(false);
    expect(limpo.erro).toBeNull();
    expect(limpo.ultimoSeq).toBe(0);
    expect(limpo.modo).toBe('ocioso');
    // A preferência do usuário não é trabalho: sobrevive ao `limpar`.
    expect(limpo.animar).toBe(true);
  });
});

// ------------------------------------------------------------------ coreografia

describe('a store é casca fina da coreografia', () => {
  it('reduced motion zera as durações mantendo a ordem dos passos', () => {
    const palco = usePalco.getState();
    palco.aplicarEvento(foco('estado'));
    palco.aplicarEvento(evt('camada.renderizada', { camada_id: 'perimetro' }));

    const normal = usePalco.getState().planejar();
    expect(normal).toHaveLength(2);
    expect(normal.every((passo) => passo.duracao_ms > 0)).toBe(true);

    usePalco.getState().definirReduzirMovimento(true);
    const reduzido = usePalco.getState().planejar();
    expect(reduzido.map((passo) => passo.alvo)).toEqual(normal.map((passo) => passo.alvo));
    expect(reduzido.every((passo) => passo.duracao_ms === 0)).toBe(true);
  });

  it('desligar a animação esvazia a fila, mas não o estado já aplicado', () => {
    const palco = usePalco.getState();
    palco.aplicarEvento(foco('estado'));
    palco.aplicarEvento(foco('municipio'));
    expect(usePalco.getState().fila).toHaveLength(2);

    usePalco.getState().definirAnimar(false);
    expect(usePalco.getState().fila).toHaveLength(0);
    expect(usePalco.getState().planejar()).toHaveLength(0);
    // O estado continua completo: o palco para de animar, não de mostrar.
    expect(usePalco.getState().foco?.nivel).toBe('municipio');

    usePalco.getState().definirAnimar(true);
    usePalco.getState().aplicarEvento(foco('imovel'));
    expect(usePalco.getState().fila).toHaveLength(1);
    expect(usePalco.getState().planejar()[0]?.alvo).toBe('imovel');
  });
});

// ------------------------------------------------------------------ ponte

describe('convivência com o despachante do SSE', () => {
  it('evento de palco chega pela ponte e é tratado só aqui', () => {
    expect(despachar(foco('estado'))).toBe(false);
    expect(usePalco.getState().foco?.nivel).toBe('estado');
    expect(usePalco.getState().fila).toHaveLength(1);
  });

  it('versao.criada o palco observa sem roubar da linha de versões', () => {
    despachar(evt('versao.criada', { versao: { numero: 2, conforme: true, criada_em: 'x' } }));
    expect(usePalco.getState().modo).toBe('resultado');
    expect(useProjetoAtivo.getState().versoes.map((v) => v.numero)).toEqual([2]);
  });
});
