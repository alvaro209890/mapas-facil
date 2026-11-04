/**
 * Store do projeto aberto (W6-03).
 *
 * Junta o que a tela do projeto precisa saber sem perguntar ao servidor: projeto, resumo do
 * imóvel, versões e qual versão está aberta no palco. Alimentada por `GET /projetos/:id`,
 * `GET /projetos/:id/versoes` e pelos eventos `projeto.estado`, `versao.criada` e
 * `importacao.progresso` (a barra da importação).
 */

import { create } from 'zustand';

import { api } from '../api/cliente';
import type { Evento, Projeto, ResumoProjeto, Versao } from '../api/tipos';

/** Onde a importação do `.zip` está — alimenta a barra de progresso da tela. */
export interface ProgressoImportacao {
  fase: 'extraindo' | 'indexando';
  /** Arquivos já extraídos (1-based, como o servidor manda). */
  indice: number;
  total: number;
  arquivo: string | null;
}

interface LojaProjetoAtivo {
  projeto: Projeto | null;
  importacao: ProgressoImportacao | null;
  resumo: Record<string, unknown> | null;
  versoes: Versao[];
  versaoAberta: number | null;
  carregando: boolean;
  erro: string | null;
  carregar: (projetoId: string) => Promise<void>;
  abrirVersao: (numero: number | null) => void;
  aplicarEvento: (evento: Evento) => void;
  renomearLocal: (nome: string) => void;
  limpar: () => void;
}

export const useProjetoAtivo = create<LojaProjetoAtivo>((set, get) => ({
  projeto: null,
  importacao: null,
  resumo: null,
  versoes: [],
  versaoAberta: null,
  carregando: false,
  erro: null,

  carregar: async (projetoId) => {
    set({ carregando: true, erro: null });
    try {
      const [projeto, resumo, versoes] = await Promise.all([
        api.get<{ projeto: Projeto }>(`/projetos/${projetoId}`),
        api
          .get<ResumoProjeto>(`/projetos/${projetoId}/resumo`)
          .catch(() => ({ projeto_id: projetoId, estado: 'pronto' as const, resumo: null })),
        api.get<{ itens: Versao[] }>(`/projetos/${projetoId}/versoes`).catch(() => ({ itens: [] })),
      ]);
      set({
        projeto: projeto.projeto,
        resumo: resumo.resumo ?? null,
        versoes: versoes.itens,
        carregando: false,
        // A versão aberta é a mais recente, salvo se a rota pediu outra.
        versaoAberta: get().versaoAberta ?? (projeto.projeto.versao_atual || null),
      });
    } catch (erro) {
      set({
        carregando: false,
        erro: erro instanceof Error ? erro.message : 'falha ao abrir o projeto',
      });
    }
  },

  abrirVersao: (numero) => set({ versaoAberta: numero }),

  aplicarEvento: (evento) => {
    if (evento.evento === 'importacao.progresso') {
      const dados = evento.dados as {
        fase?: unknown;
        indice?: unknown;
        total?: unknown;
        arquivo?: unknown;
      };
      const total = typeof dados.total === 'number' ? dados.total : 0;
      set({
        importacao: {
          fase: dados.fase === 'indexando' ? 'indexando' : 'extraindo',
          indice: typeof dados.indice === 'number' ? dados.indice : dados.fase === 'indexando' ? total : 0,
          total,
          arquivo: typeof dados.arquivo === 'string' ? dados.arquivo : null,
        },
      });
      return;
    }
    if (evento.evento === 'projeto.estado') {
      const novo = (evento.dados as { estado?: unknown }).estado;
      if (novo === 'importando') set({ importacao: { fase: 'extraindo', indice: 0, total: 0, arquivo: null } });
      else if (novo !== 'indexando') set({ importacao: null });
      const estado = (evento.dados as { estado?: unknown }).estado;
      const erroCodigo = (evento.dados as { erro_codigo?: unknown }).erro_codigo;
      set((atual) =>
        atual.projeto && typeof estado === 'string'
          ? {
              projeto: {
                ...atual.projeto,
                estado: estado as Projeto['estado'],
                erro_codigo: typeof erroCodigo === 'string' ? erroCodigo : atual.projeto.erro_codigo ?? null,
              },
            }
          : {},
      );
      const resumo = (evento.dados as { resumo?: unknown }).resumo;
      if (resumo && typeof resumo === 'object') {
        set({ resumo: resumo as Record<string, unknown> });
      }
      return;
    }
    if (evento.evento === 'versao.criada') {
      const versao = (evento.dados as { versao?: unknown }).versao;
      if (versao && typeof versao === 'object') {
        const nova = versao as Versao;
        set((atual) => ({
          versoes: [...atual.versoes.filter((v) => v.numero !== nova.numero), nova],
          versaoAberta: nova.numero,
          projeto: atual.projeto ? { ...atual.projeto, versao_atual: nova.numero } : null,
        }));
      }
    }
  },

  renomearLocal: (nome) =>
    set((atual) => ({ projeto: atual.projeto ? { ...atual.projeto, nome } : null })),

  limpar: () =>
    set({ projeto: null, importacao: null, resumo: null, versoes: [], versaoAberta: null, erro: null }),
}));
