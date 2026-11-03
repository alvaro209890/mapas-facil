/**
 * Store do chat do projeto (W6-03).
 *
 * A timeline é a **herdada** do desktop (`herdados/timeline.ts`) — as regras de agrupamento
 * de deltas e de tools são as mesmas, e é isso que faz a bolha não piscar. O que muda é a
 * fonte: aqui os eventos chegam do SSE (`chat.*`, `mensagem.criada`, `nucleo.res`), não do
 * IPC do Electron.
 */

import { create } from 'zustand';

import type { Evento, Mensagem, Sugestao } from '../api/tipos';
import type { DadosChatPergunta, DadosChatTool } from '../herdados/tipos';
import {
  aplicarEventoTimeline,
  cancelarPendentesTimeline,
  type BlocoTurno,
} from '../herdados/timeline';

interface LojaChat {
  mensagens: Mensagem[];
  blocos: BlocoTurno[];
  turnoEmCurso: string | null;
  pensando: boolean;
  sugestoes: Sugestao[];
  erro: string | null;
  carregar: (
    itens: Mensagem[],
    sugestoes?: Sugestao[],
  ) => void;
  enviarLocal: (texto: string, reqId: string) => void;
  aplicarEvento: (evento: Evento) => void;
  encerrarTurno: () => void;
  definirErro: (erro: string | null) => void;
  limpar: () => void;
}

/**
 * `mensagem.criada` chega do servidor com o essencial (`papel`, `texto`).
 *
 * O `message_id`/`seq` só existem quando a mensagem volta do banco do núcleo — na hora do
 * envio o servidor manda o mínimo. Por isso a chave local é o `seq` do evento: recusar
 * mensagem sem id faria a fala do usuário **nunca** aparecer na tela.
 */
function mensagemDoEvento(evento: Evento): Mensagem | null {
  const bruta = (evento.dados as { mensagem?: unknown }).mensagem;
  if (!bruta || typeof bruta !== 'object') return null;
  const m = bruta as Partial<Mensagem>;
  if (!m.papel || typeof m.texto !== 'string') return null;
  return {
    message_id: m.message_id ?? `evt-${evento.seq}`,
    seq: Number(m.seq ?? evento.seq),
    papel: m.papel,
    texto: m.texto,
    criada_em: String(m.criada_em ?? evento.ts),
  };
}

export const useChat = create<LojaChat>((set, get) => ({
  mensagens: [],
  blocos: [],
  turnoEmCurso: null,
  pensando: false,
  sugestoes: [],
  erro: null,

  carregar: (itens, sugestoes = []) =>
    set({
      mensagens: itens,
      // A timeline começa com as mensagens já trocadas (sem os deltas, que não voltam).
      blocos: itens.reduce<BlocoTurno[]>((acc, m, indice) => {
        if (m.papel === 'assistente') {
          return aplicarEventoTimeline(acc, {
            tipo: 'texto',
            dados: { texto: m.texto },
          });
        }
        return aplicarEventoTimeline(acc, {
          tipo: 'texto',
          dados: { texto: `**${m.papel === 'usuario' ? 'Você' : 'Sistema'}:** ${m.texto}` },
        }).map((bloco, i) => ({ ...bloco, id: `${m.message_id}-${i}-${indice}` }));
      }, []),
      sugestoes,
    }),

  enviarLocal: (_texto, reqId) => set({ turnoEmCurso: reqId, pensando: true, erro: null }),

  aplicarEvento: (evento) => {
    switch (evento.evento) {
      case 'mensagem.criada': {
        const mensagem = mensagemDoEvento(evento);
        if (!mensagem) return;
        set((atual) => ({ mensagens: [...atual.mensagens, mensagem] }));
        return;
      }
      case 'chat.delta': {
        const texto = String((evento.dados as { texto?: unknown }).texto ?? '');
        if (!texto) return;
        set((atual) => ({
          blocos: aplicarEventoTimeline(atual.blocos, { tipo: 'texto', dados: { texto } }),
          pensando: false,
        }));
        return;
      }
      case 'chat.raciocinio': {
        const texto = String((evento.dados as { texto?: unknown }).texto ?? '');
        if (!texto) return;
        set((atual) => ({
          blocos: aplicarEventoTimeline(atual.blocos, { tipo: 'raciocinio', dados: { texto } }),
          pensando: true,
        }));
        return;
      }
      case 'chat.tool': {
        set((atual) => ({
          blocos: aplicarEventoTimeline(atual.blocos, {
            tipo: 'tool',
            dados: evento.dados as unknown as DadosChatTool,
          }),
        }));
        return;
      }
      case 'chat.pergunta': {
        set((atual) => ({
          blocos: aplicarEventoTimeline(atual.blocos, {
            tipo: 'pergunta',
            dados: evento.dados as unknown as DadosChatPergunta,
          }),
          pensando: false,
        }));
        return;
      }
      case 'nucleo.res': {
        const ok = (evento.dados as { ok?: unknown }).ok;
        if (ok === false) {
          set((atual) => ({
            erro: 'A IA não conseguiu concluir o turno.',
            blocos: cancelarPendentesTimeline(atual.blocos),
          }));
        }
        get().encerrarTurno();
        return;
      }
      default:
        return;
    }
  },

  encerrarTurno: () => set({ turnoEmCurso: null, pensando: false }),

  definirErro: (erro) => set({ erro }),

  limpar: () =>
    set({ mensagens: [], blocos: [], turnoEmCurso: null, pensando: false, sugestoes: [], erro: null }),
}));
