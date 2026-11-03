/**
 * EventSource do projeto (W6-02).
 *
 * Um `EventSource` por projeto aberto, evento `mf`, `withCredentials` para o cookie da
 * sessão. Três garantias que estão testadas em `api/eventos.test.ts`:
 *
 * 1. **Sem buraco na reconexão**: o navegador manda `Last-Event-ID` sozinho; além disso
 *    descartamos `seq` menor ou igual ao último aplicado, porque a reconexão pode repetir.
 * 2. **Ordem**: evento com `seq` adiantado é aplicado na ordem de chegada, mas o `seq`
 *    aplicado só avança quando o número casa — assim um replay fora de ordem não faz o
 *    cliente pular eventos legítimos.
 * 3. **Estado da conexão** é observável (`conectado` / `reconectando` / `offline`), com
 *    `offline` só depois de 30 s sem nada — é o que liga o banner "sem conexão".
 */

import type { Evento } from './tipos';

export type EstadoConexao = 'conectado' | 'reconectando' | 'offline';

export interface OpcoesEventos {
  projetoId: string;
  /** Chamada para cada evento novo, já filtrado por `seq`. */
  aoEvento: (evento: Evento) => void;
  aoConexao?: (estado: EstadoConexao) => void;
  /** Injetável nos testes; em produção é a global. */
  criarEventSource?: (url: string) => EventSource;
  /** Quanto tempo sem nada para considerar offline (padrão 30 s). */
  limiteOfflineMs?: number;
  /** Agenda o timer do "offline" (injetável nos testes). */
  agendar?: (fn: () => void, ms: number) => unknown;
  cancelarTimer?: (id: unknown) => void;
}

const LIMITE_OFFLINE_PADRAO_MS = 30_000;

export function urlEventos(projetoId: string, desde = 0): string {
  const base = `/api/v1/projetos/${encodeURIComponent(projetoId)}/eventos`;
  return desde > 0 ? `${base}?desde=${desde}` : base;
}

export class FluxoEventos {
  private fonte: EventSource | null = null;
  private ultimoSeq = 0;
  private estado: EstadoConexao = 'reconectando';
  private timerOffline: unknown = null;
  private readonly opcoes: OpcoesEventos;

  constructor(opcoes: OpcoesEventos) {
    this.opcoes = opcoes;
  }

  get seq(): number {
    return this.ultimoSeq;
  }

  get estadoConexao(): EstadoConexao {
    return this.estado;
  }

  abrir(desde = 0): void {
    this.ultimoSeq = desde;
    const criar =
      this.opcoes.criarEventSource ??
      ((url: string) => new EventSource(url, { withCredentials: true }));
    const fonte = criar(urlEventos(this.opcoes.projetoId, desde));
    this.fonte = fonte;
    fonte.addEventListener('mf', (evento) => this.receber(evento as MessageEvent));
    fonte.addEventListener('open', () => this.mudarEstado('conectado'));
    fonte.addEventListener('error', () => {
      // O `EventSource` reconecta sozinho; só marcamos o estado e ligamos o relógio.
      this.mudarEstado('reconectando');
      this.agendarOffline();
    });
    this.agendarOffline();
  }

  fechar(): void {
    this.fonte?.close();
    this.fonte = null;
    this.cancelarOffline();
  }

  /** Aplica um evento do fio. Devolve `true` se ele foi entregue. */
  receber(mensagem: MessageEvent): boolean {
    this.cancelarOffline();
    if (this.estado !== 'conectado') this.mudarEstado('conectado');

    const bruto = typeof mensagem.data === 'string' ? mensagem.data : '';
    if (!bruto) return false;
    let evento: Evento;
    try {
      evento = JSON.parse(bruto) as Evento;
    } catch {
      return false; // linha quebrada não derruba a tela
    }
    if (typeof evento?.seq !== 'number' || !evento.evento) return false;
    if (evento.seq <= this.ultimoSeq) return false; // já aplicado (replay da reconexão)

    this.ultimoSeq = evento.seq;
    this.opcoes.aoEvento(evento);
    this.agendarOffline();
    return true;
  }

  private mudarEstado(novo: EstadoConexao): void {
    if (this.estado === novo) return;
    this.estado = novo;
    this.opcoes.aoConexao?.(novo);
  }

  private agendarOffline(): void {
    this.cancelarOffline();
    const agendar =
      this.opcoes.agendar ??
      ((fn: () => void, ms: number) => setTimeout(fn, ms) as unknown);
    const limite = this.opcoes.limiteOfflineMs ?? LIMITE_OFFLINE_PADRAO_MS;
    this.timerOffline = agendar(() => this.mudarEstado('offline'), limite);
  }

  private cancelarOffline(): void {
    if (this.timerOffline === null) return;
    const cancelar =
      this.opcoes.cancelarTimer ??
      ((id: unknown) => clearTimeout(id as ReturnType<typeof setTimeout>));
    cancelar(this.timerOffline);
    this.timerOffline = null;
  }
}
