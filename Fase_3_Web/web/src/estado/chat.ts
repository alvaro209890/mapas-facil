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
  encerrarStreaming,
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

/**
 * Mensagem que o servidor mandou ao agente em nome do sistema (ex.: abertura automática
 * depois da importação). Fica no histórico da IA, mas não é fala do usuário: não aparece.
 */
export function ehMensagemDeSistema(texto: string): boolean {
  return texto.trimStart().startsWith('[ORIGEM: sistema');
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
      // A fala do usuário tem bolha própria; a do sistema entra como texto com rótulo.
      blocos: encerrarStreaming(
        itens.reduce<BlocoTurno[]>((acc, m) => {
          if (!m.texto.trim() || ehMensagemDeSistema(m.texto)) return acc;
          if (m.papel === 'usuario') {
            return aplicarEventoTimeline(acc, { tipo: 'usuario', dados: { texto: m.texto } });
          }
          const texto = m.papel === 'assistente' ? m.texto : `**Sistema:** ${m.texto}`;
          return aplicarEventoTimeline(encerrarStreaming(acc), { tipo: 'texto', dados: { texto } });
        }, []),
      ),
      sugestoes,
    }),

  enviarLocal: (texto, reqId) =>
    set((atual) => ({
      // A bolha do usuário aparece na hora (otimista); o `mensagem.criada` que volta do
      // servidor com o mesmo texto não duplica (ver `aplicarEvento`).
      blocos: aplicarEventoTimeline(atual.blocos, { tipo: 'usuario', dados: { texto } }),
      turnoEmCurso: reqId,
      pensando: true,
      erro: null,
    })),

  aplicarEvento: (evento) => {
    switch (evento.evento) {
      case 'mensagem.criada': {
        const mensagem = mensagemDoEvento(evento);
        if (!mensagem) return;
        set((atual) => {
          const mensagens = [...atual.mensagens, mensagem];
          if (mensagem.papel !== 'usuario' || ehMensagemDeSistema(mensagem.texto)) return { mensagens };
          // Já desenhada pelo `enviarLocal`? Então só registra. Se veio de outra aba/dispositivo,
          // entra na timeline agora.
          const ultimaDoUsuario = [...atual.blocos].reverse().find((b) => b.tipo === 'usuario');
          if (ultimaDoUsuario?.tipo === 'usuario' && ultimaDoUsuario.texto === mensagem.texto) {
            return { mensagens };
          }
          return {
            mensagens,
            blocos: aplicarEventoTimeline(atual.blocos, {
              tipo: 'usuario',
              dados: { texto: mensagem.texto },
            }),
          };
        });
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
        const dados = evento.dados as { ok?: unknown; erro?: { mensagem?: unknown } | null };
        if (dados.ok === false) {
          // Mostra o motivo que o núcleo deu (ex.: limite de rodadas) — "não conseguiu" sozinho
          // não diz ao usuário o que fazer.
          const motivo =
            dados.erro && typeof dados.erro.mensagem === 'string' ? dados.erro.mensagem : '';
          set((atual) => ({
            erro: motivo
              ? `A IA não conseguiu concluir o turno: ${motivo}`
              : 'A IA não conseguiu concluir o turno.',
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

  encerrarTurno: () =>
    set((atual) => ({
      turnoEmCurso: null,
      pensando: false,
      blocos: encerrarStreaming(atual.blocos),
    })),

  definirErro: (erro) => set({ erro }),

  limpar: () =>
    set({ mensagens: [], blocos: [], turnoEmCurso: null, pensando: false, sugestoes: [], erro: null }),
}));
