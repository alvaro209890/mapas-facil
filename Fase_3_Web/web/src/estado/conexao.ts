/**
 * Store de conexão com o servidor (W6-03).
 *
 * Guarda o estado do `EventSource` e o último `seq` aplicado. É ela que liga o banner
 * "sem conexão — tentando de novo" e que permite a tela dizer honestamente se o que está
 * vendo pode estar velho.
 */

import { create } from 'zustand';

import type { EstadoConexao } from '../api/eventos';

interface LojaConexao {
  estado: EstadoConexao | 'parado';
  ultimoSeq: number;
  aoMudar: (estado: EstadoConexao) => void;
  aoAplicar: (seq: number) => void;
  parar: () => void;
}

export const useConexao = create<LojaConexao>((set) => ({
  estado: 'parado',
  ultimoSeq: 0,
  aoMudar: (estado) => set({ estado }),
  aoAplicar: (seq) => set({ ultimoSeq: seq }),
  parar: () => set({ estado: 'parado' }),
}));

/** `true` quando a tela deve avisar que o dado pode estar atrasado. */
export function desconectado(estado: LojaConexao['estado']): boolean {
  return estado === 'offline';
}
