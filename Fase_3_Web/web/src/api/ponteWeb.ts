/**
 * Ponte entre o SSE do servidor e as stores do web (W6-03).
 *
 * O desktop tem uma `ApiMapasFacil` que chama o núcleo por nome de método — na web isso **não existe**
 * (AW-02): não há RPC para o núcleo. Esta ponte implementa só o que faz sentido aqui:
 * `aoEvento` (um evento do SSE → todas as stores interessadas) e `aoEstadoNucleo`
 * (`worker.estado`). Quem precisa de dado do núcleo chama a rota REST equivalente.
 *
 * Ela também desconecta na saída da tela: um `EventSource` órfão segura conexão e o
 * servidor fica com assinante fantasma.
 */

import { FluxoEventos, type EstadoConexao } from '../api/eventos';
import type { Evento } from '../api/tipos';
import { useChat } from '../estado/chat';
import { useConexao } from '../estado/conexao';
import { useJob } from '../estado/job';
import { usePalco } from '../estado/palco';
import { useProjetoAtivo } from '../estado/projetoAtivo';
import { useProjetos } from '../estado/projetos';
import { useAgente } from '../estado/agente';

/**
 * Despacha um evento do SSE para as stores.
 *
 * `seq` repetido é **ignorado**: na reconexão o servidor reenvia desde o último `seq`, e
 * sem esta guarda a bolha duplicaria o texto já escrito. Devolve `true` se nada foi
 * aplicado por já ter sido visto.
 */
export function despachar(evento: Evento): boolean {
  if (evento.seq > 0 && evento.seq <= useConexao.getState().ultimoSeq) return true;
  // O `seq` aplicado é registrado **antes** de despachar: se o mesmo evento chegar duas
  // vezes na reconexão, ele já está marcado e é descartado.
  if (evento.seq > 0) useConexao.getState().aoAplicar(evento.seq);
  if (usePalco.getState().aplicarEvento(evento)) return false;
  switch (evento.evento) {
    case 'chat.delta':
    case 'chat.raciocinio':
    case 'chat.tool':
    case 'chat.pergunta':
    case 'chat.turno':
    case 'mensagem.criada':
    case 'nucleo.res':
      useChat.getState().aplicarEvento(evento);
      if (evento.evento === 'nucleo.res') useJob.getState().aplicarEvento(evento);
      return false;
    case 'projeto.estado': {
      useProjetoAtivo.getState().aplicarEvento(evento);
      const estado = (evento.dados as { estado?: unknown }).estado;
      const projetoId = (evento.dados as { projeto_id?: unknown }).projeto_id;
      if (typeof estado === 'string' && typeof projetoId === 'string') {
        useProjetos
          .getState()
          .aoMudarEstado(
            projetoId,
            estado as Parameters<ReturnType<typeof useProjetos.getState>['aoMudarEstado']>[1],
            (evento.dados as { erro_codigo?: string | null }).erro_codigo ?? null,
          );
      }
      return false;
    }
    case 'versao.criada':
    case 'importacao.progresso':
      useProjetoAtivo.getState().aplicarEvento(evento);
      return false;
    case 'job.progresso':
    case 'job.log':
    case 'job.artefato_parcial':
      useJob.getState().aplicarEvento(evento);
      return false;
    case 'agente.plano':
    case 'agente.passo':
    case 'agente.arquivo':
    case 'agente.preview':
    case 'agente.aprovacao':
    case 'agente.fim':
      useAgente.getState().aplicarEvento(evento);
      return false;
    case 'worker.estado':
    case 'sse.heartbeat':
      // `worker.estado` alimenta o indicador de saúde do admin. Nada a fazer nas stores
      // do usuário.
      return false;
    default:
      return false;
  }
}

export interface Ligacao {
  fechar: () => void;
  fluxo: FluxoEventos;
}

/** Abre o SSE de um projeto e liga tudo. Fora da tela, chame `fechar()`. */
export function ligarProjeto(projetoId: string, desde = 0): Ligacao {
  // Replay desde o começo: o `seq` visto antes é de outro projeto (ou de outra conexão).
  if (desde === 0) useConexao.setState({ ultimoSeq: 0 });
  const fluxo = new FluxoEventos({
    projetoId,
    aoEvento: (evento) => {
      if (evento.evento === 'sse.heartbeat') return;
      despachar(evento);
    },
    aoConexao: (estado: EstadoConexao) => useConexao.getState().aoMudar(estado),
  });
  fluxo.abrir(desde);
  return {
    fluxo,
    fechar: () => {
      fluxo.fechar();
      useConexao.getState().parar();
    },
  };
}
