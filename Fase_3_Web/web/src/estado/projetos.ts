/**
 * Store da lista de projetos (W6-03).
 *
 * Busca com debounce é da tela; aqui só se guarda a página, o filtro e o cursor. O
 * `estado` do projeto (importando/pronto/erro) chega por evento e é atualizado no lugar,
 * sem refazer a lista inteira — o cartão não pode piscar.
 */

import { create } from 'zustand';

import { api } from '../api/cliente';
import type { EstadoProjeto, PaginaProjetos, Projeto } from '../api/tipos';

export type Filtro = 'ativos' | 'lixeira';

interface LojaProjetos {
  itens: Projeto[];
  filtro: Filtro;
  busca: string;
  proximo: string | null;
  carregando: boolean;
  erro: string | null;
  carregar: (opcoes?: { busca?: string; filtro?: Filtro; acumular?: boolean }) => Promise<void>;
  mais: () => Promise<void>;
  aoMudarEstado: (projetoId: string, estado: EstadoProjeto, erroCodigo?: string | null) => void;
  renomearLocal: (projetoId: string, nome: string) => void;
  removerLocal: (projetoId: string) => void;
  limpar: () => void;
}

function consulta(busca: string, filtro: Filtro): string {
  const params = new URLSearchParams();
  if (busca.trim()) params.set('busca', busca.trim());
  if (filtro === 'lixeira') params.set('estado', 'lixeira');
  const qs = params.toString();
  return qs ? `/projetos?${qs}` : '/projetos';
}

export const useProjetos = create<LojaProjetos>((set, get) => ({
  itens: [],
  filtro: 'ativos',
  busca: '',
  proximo: null,
  carregando: false,
  erro: null,

  carregar: async (opcoes = {}) => {
    const busca = opcoes.busca ?? get().busca;
    const filtro = opcoes.filtro ?? get().filtro;
    set({ carregando: true, erro: null, busca, filtro });
    try {
      const pagina = await api.get<PaginaProjetos>(consulta(busca, filtro));
      set((atual) => ({
        itens: opcoes.acumular ? [...atual.itens, ...pagina.itens] : pagina.itens,
        proximo: pagina.proximo ?? null,
        carregando: false,
      }));
    } catch (erro) {
      set({ carregando: false, erro: erro instanceof Error ? erro.message : 'falha ao listar' });
    }
  },

  mais: async () => {
    const { proximo } = get();
    if (!proximo) return;
    set({ carregando: true });
    try {
      const pagina = await api.get<PaginaProjetos>(`/projetos?cursor=${encodeURIComponent(proximo)}`);
      set((atual) => ({
        itens: [...atual.itens, ...pagina.itens],
        proximo: pagina.proximo ?? null,
        carregando: false,
      }));
    } catch {
      set({ carregando: false });
    }
  },

  aoMudarEstado: (projetoId, estado, erroCodigo = null) =>
    set((atual) => ({
      itens: atual.itens.map((p) =>
        p.id === projetoId ? { ...p, estado, erro_codigo: erroCodigo } : p,
      ),
    })),

  renomearLocal: (projetoId, nome) =>
    set((atual) => ({
      itens: atual.itens.map((p) => (p.id === projetoId ? { ...p, nome } : p)),
    })),

  removerLocal: (projetoId) =>
    set((atual) => ({ itens: atual.itens.filter((p) => p.id !== projetoId) })),

  limpar: () => set({ itens: [], proximo: null, erro: null }),
}));
