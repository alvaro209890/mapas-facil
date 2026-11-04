/**
 * Store do chat do projeto (W6-03).
 *
 * A timeline é a **herdada** do desktop (`herdados/timeline.ts`) — as regras de agrupamento
 * de deltas e de tools são as mesmas, e é isso que faz a bolha não piscar. O que muda é a
 * fonte: aqui os eventos chegam do SSE (`chat.*`, `mensagem.criada`, `nucleo.res`), não do
 * IPC do Electron.
 */

import { create } from 'zustand';

import type { Evento, Mensagem, Sugestao, TraceMensagem } from '../api/tipos';
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
  /** O servidor devolveu o `req_id` real do turno (é o que o "Parar" precisa mandar). */
  definirTurno: (reqId: string) => void;
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

/** Tools que não viram cartão: `perguntar` já aparece como o cartão da pergunta. */
const TOOLS_SEM_CARTAO = new Set(['perguntar']);

function textoDe(m: Mensagem): string {
  const bruto = (m as { texto?: unknown; conteudo?: unknown }).texto ?? (m as { conteudo?: unknown }).conteudo;
  return typeof bruto === 'string' ? bruto : '';
}

function desescapar(valor: string): string {
  try {
    return JSON.parse(`"${valor}"`) as string;
  } catch {
    return valor;
  }
}

/**
 * Pergunta de um turno passado, lida dos argumentos do `perguntar`.
 *
 * O núcleo guarda os argumentos cortados em 500 caracteres; quando o JSON não fecha, a
 * pergunta e os rótulos ainda saem por expressão regular.
 */
export function perguntaDoTrace(trace: TraceMensagem): DadosChatPergunta | null {
  const bruto = trace.args_resumo ?? '';
  if (!bruto) return null;
  try {
    const args = JSON.parse(bruto) as {
      pergunta?: unknown;
      opcoes?: { id?: unknown; rotulo?: unknown }[];
      permite_texto_livre?: unknown;
    };
    if (typeof args.pergunta === 'string' && args.pergunta.trim()) {
      return {
        pergunta: args.pergunta,
        opcoes: (Array.isArray(args.opcoes) ? args.opcoes : [])
          .map((o, i) => ({
            id: typeof o.id === 'string' ? o.id : `op-${i}`,
            rotulo: typeof o.rotulo === 'string' ? o.rotulo : '',
          }))
          .filter((o) => o.rotulo),
        permite_texto_livre: args.permite_texto_livre !== false,
      };
    }
  } catch {
    // argumentos cortados: cai para a leitura tolerante abaixo
  }
  const pergunta = /"pergunta"\s*:\s*"((?:[^"\\]|\\.)*)"/.exec(bruto)?.[1];
  if (!pergunta) return null;
  const opcoes = [...bruto.matchAll(/"rotulo"\s*:\s*"((?:[^"\\]|\\.)*)"/g)].map((m, i) => ({
    id: `op-${i}`,
    rotulo: desescapar(m[1] ?? ''),
  }));
  return { pergunta: desescapar(pergunta), opcoes, permite_texto_livre: true };
}

/** Histórico do banco → blocos da timeline (fala, cartões das tools, resposta, pergunta). */
export function blocosDoHistorico(itens: Mensagem[]): BlocoTurno[] {
  let blocos: BlocoTurno[] = [];
  for (const m of itens) {
    const texto = textoDe(m);
    if (m.papel === 'usuario') {
      if (!texto.trim() || ehMensagemDeSistema(texto)) continue;
      blocos = aplicarEventoTimeline(blocos, { tipo: 'usuario', dados: { texto } });
      continue;
    }
    let pergunta: DadosChatPergunta | null = null;
    for (const t of m.tool_traces ?? []) {
      if (!t || typeof t.tool !== 'string') continue;
      if (t.tool === 'perguntar') {
        pergunta = perguntaDoTrace(t) ?? pergunta;
        continue;
      }
      if (TOOLS_SEM_CARTAO.has(t.tool)) continue;
      blocos = aplicarEventoTimeline(blocos, {
        tipo: 'tool',
        dados: {
          trace_id: t.trace_id || `${m.message_id}-${t.tool}`,
          tool: t.tool,
          fase: 'fim',
          ...(t.args_resumo ? { args_resumo: t.args_resumo } : {}),
          ...(t.resultado_resumo ? { resultado_resumo: t.resultado_resumo } : {}),
          ...(typeof t.ms === 'number' ? { ms: t.ms } : {}),
          ok: t.ok !== false,
        },
      });
    }
    if (texto.trim() && !ehMensagemDeSistema(texto)) {
      const md = m.papel === 'assistente' ? texto : `**Sistema:** ${texto}`;
      blocos = aplicarEventoTimeline(encerrarStreaming(blocos), { tipo: 'texto', dados: { texto: md } });
    }
    if (pergunta) {
      blocos = aplicarEventoTimeline(encerrarStreaming(blocos), { tipo: 'pergunta', dados: pergunta });
    }
  }
  return encerrarStreaming(blocos);
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
      mensagens: itens.map((m) => ({ ...m, texto: textoDe(m) })),
      // A timeline começa com as mensagens já trocadas — com os cartões das tools e a
      // pergunta de cada turno (os deltas não voltam; o texto final está no banco).
      blocos: blocosDoHistorico(itens),
      sugestoes,
    }),

  definirTurno: (reqId) =>
    set((atual) => (atual.turnoEmCurso ? { turnoEmCurso: reqId } : {})),

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
          turnoEmCurso: atual.turnoEmCurso ?? evento.req_id ?? null,
        }));
        return;
      }
      case 'chat.raciocinio': {
        const texto = String((evento.dados as { texto?: unknown }).texto ?? '');
        if (!texto) return;
        set((atual) => ({
          blocos: aplicarEventoTimeline(atual.blocos, { tipo: 'raciocinio', dados: { texto } }),
          pensando: true,
          // Página recarregada no meio do turno: o replay do SSE reabre o turno em curso.
          turnoEmCurso: atual.turnoEmCurso ?? evento.req_id ?? null,
        }));
        return;
      }
      case 'chat.tool': {
        const dados = evento.dados as unknown as DadosChatTool;
        set((atual) => ({
          blocos: TOOLS_SEM_CARTAO.has(dados.tool)
            ? atual.blocos
            : aplicarEventoTimeline(atual.blocos, { tipo: 'tool', dados }),
          pensando: dados.fase === 'inicio' ? true : atual.pensando,
          turnoEmCurso: atual.turnoEmCurso ?? evento.req_id ?? null,
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
