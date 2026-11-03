/**
 * Store do job de geração (W6-03).
 *
 * Guarda etapa, percentual, log e artefatos do job em curso — todos **de evento real** do
 * núcleo (`job.progresso`, `job.log`, `job.artefato_parcial`). Nada aqui avança por timer:
 * é a regra que a Fase 1 já pagou caro para aprender (animação sem evento real é mentira).
 */

import { create } from 'zustand';

import type { Evento } from '../api/tipos';

export interface EtapaJob {
  nome: string;
  pct: number | null;
  iniciada_em: string;
  fim_em: string | null;
}

export interface LojaJob {
  jobId: string | null;
  etapas: EtapaJob[];
  pct: number;
  log: string[];
  artefatos: Record<string, string>;
  erro: string | null;
  aplicarEvento: (evento: Evento) => void;
  limpar: () => void;
}

const LIMITE_LOG = 200;

export const useJob = create<LojaJob>((set) => ({
  jobId: null,
  etapas: [],
  pct: 0,
  log: [],
  artefatos: {},
  erro: null,

  aplicarEvento: (evento) => {
    if (evento.evento === 'job.progresso') {
      const d = evento.dados as {
        etapa?: unknown;
        pct?: unknown;
        mensagem?: unknown;
      };
      const etapa = typeof d.etapa === 'string' ? d.etapa : 'gerando';
      const pct = typeof d.pct === 'number' ? Math.max(0, Math.min(100, d.pct)) : null;
      set((atual) => {
        const outras = atual.etapas.filter((e) => e.nome !== etapa);
        const anterior = atual.etapas.find((e) => e.nome === etapa);
        const nova: EtapaJob = {
          nome: etapa,
          pct: pct ?? anterior?.pct ?? null,
          iniciada_em: anterior?.iniciada_em ?? new Date().toISOString(),
          fim_em: pct === 100 ? new Date().toISOString() : null,
        };
        return {
          jobId: evento.job_id ?? atual.jobId,
          etapas: [...outras, nova],
          pct: pct ?? atual.pct,
        };
      });
      return;
    }
    if (evento.evento === 'job.log') {
      const texto = String((evento.dados as { mensagem?: unknown }).mensagem ?? '');
      if (!texto) return;
      set((atual) => ({ log: [...atual.log, texto].slice(-LIMITE_LOG) }));
      return;
    }
    if (evento.evento === 'job.artefato_parcial') {
      const tipo = (evento.dados as { tipo?: unknown }).tipo;
      const caminho = (evento.dados as { caminho?: unknown }).caminho;
      if (typeof tipo === 'string' && typeof caminho === 'string') {
        set((atual) => ({ artefatos: { ...atual.artefatos, [tipo]: caminho } }));
      }
      return;
    }
    if (evento.evento === 'nucleo.res' && (evento.dados as { ok?: unknown }).ok === false) {
      set({ erro: 'A geração falhou. Veja o log do job.' });
    }
  },

  limpar: () => set({ jobId: null, etapas: [], pct: 0, log: [], artefatos: {}, erro: null }),
}));
