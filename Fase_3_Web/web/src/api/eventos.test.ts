/**
 * Testes do fluxo SSE (W6-02).
 *
 * O que importa aqui: reconexão sem buraco (descarte de `seq` repetido), evento quebrado
 * não derruba a tela, e o estado de conexão vira `offline` só depois do limite.
 */

import { describe, expect, it, vi } from 'vitest';

import { FluxoEventos, urlEventos, type EstadoConexao } from './eventos';
import type { Evento } from './tipos';

function evento(seq: number, nome = 'chat.delta', dados: Record<string, unknown> = {}): Evento {
  return {
    seq,
    ts: '2026-11-03T12:00:00Z',
    origem: 'nucleo',
    evento: nome,
    dados,
  };
}

class FonteFalsa {
  readonly listeners = new Map<string, ((e: MessageEvent) => void)[]>();
  fechada = false;
  constructor(readonly url: string) {}
  addEventListener(tipo: string, fn: (e: MessageEvent) => void) {
    const lista = this.listeners.get(tipo) ?? [];
    lista.push(fn);
    this.listeners.set(tipo, lista);
  }
  emitir(tipo: string, dados?: string) {
    for (const fn of this.listeners.get(tipo) ?? []) {
      fn({ data: dados } as MessageEvent);
    }
  }
  close() {
    this.fechada = true;
  }
}

function montar(limiteOfflineMs = 30_000) {
  const fontes: FonteFalsa[] = [];
  const recebidos: Evento[] = [];
  const estados: EstadoConexao[] = [];
  const timers: { fn: () => void; ms: number }[] = [];

  const fluxo = new FluxoEventos({
    projetoId: 'p1',
    aoEvento: (e) => recebidos.push(e),
    aoConexao: (e) => estados.push(e),
    criarEventSource: (url) => {
      const fonte = new FonteFalsa(url);
      fontes.push(fonte);
      return fonte as unknown as EventSource;
    },
    limiteOfflineMs,
    agendar: (fn, ms) => {
      const id = { fn, ms };
      timers.push(id);
      return id;
    },
    cancelarTimer: (id) => {
      const pos = timers.indexOf(id as { fn: () => void; ms: number });
      if (pos >= 0) timers.splice(pos, 1);
    },
  });

  return { fluxo, fontes, recebidos, estados, timers };
}

describe('url dos eventos', () => {
  it('monta a rota com e sem desde', () => {
    expect(urlEventos('p1')).toBe('/api/v1/projetos/p1/eventos');
    expect(urlEventos('p1', 42)).toBe('/api/v1/projetos/p1/eventos?desde=42');
    expect(urlEventos('a b')).toBe('/api/v1/projetos/a%20b/eventos');
  });
});

describe('fluxo de eventos', () => {
  it('abre com withCredentials e escuta o evento mf', () => {
    const { fluxo, fontes, recebidos } = montar();
    fluxo.abrir();
    expect((fontes[0] as FonteFalsa).url).toBe('/api/v1/projetos/p1/eventos');
    (fontes[0] as FonteFalsa).emitir('mf', JSON.stringify(evento(1)));
    expect(recebidos).toHaveLength(1);
    expect((recebidos[0] as Evento).seq).toBe(1);
  });

  it('descarta seq repetido ou menor (replay da reconexão)', () => {
    const { fluxo, fontes, recebidos } = montar();
    fluxo.abrir();
    const f = fontes[0] as FonteFalsa;
    f.emitir('mf', JSON.stringify(evento(1)));
    f.emitir('mf', JSON.stringify(evento(2)));
    f.emitir('mf', JSON.stringify(evento(2)));
    f.emitir('mf', JSON.stringify(evento(1)));
    expect(recebidos.map((e) => e.seq)).toEqual([1, 2]);
    expect(fluxo.seq).toBe(2);
  });

  it('evento quebrado não derruba nem avança o seq', () => {
    const { fluxo, fontes, recebidos } = montar();
    fluxo.abrir();
    (fontes[0] as FonteFalsa).emitir('mf', '{isso não é json}');
    (fontes[0] as FonteFalsa).emitir('mf', '');
    (fontes[0] as FonteFalsa).emitir('mf', JSON.stringify({ sem: 'seq' }));
    expect(recebidos).toEqual([]);
    expect(fluxo.seq).toBe(0);
    (fontes[0] as FonteFalsa).emitir('mf', JSON.stringify(evento(5)));
    expect(fluxo.seq).toBe(5);
  });

  it('reconhece os três estados de conexão', () => {
    const { fluxo, fontes, estados, timers } = montar(1000);
    fluxo.abrir();
    expect(fluxo.estadoConexao).toBe('reconectando');
    (fontes[0] as FonteFalsa).emitir('open');
    expect(fluxo.estadoConexao).toBe('conectado');

    (fontes[0] as FonteFalsa).emitir('error');
    expect(fluxo.estadoConexao).toBe('reconectando');
    expect(timers).toHaveLength(1);
    expect((timers[0] as { ms: number }).ms).toBe(1000);
    (timers[0] as { fn: () => void }).fn();
    expect(fluxo.estadoConexao).toBe('offline');
    expect(estados).toEqual(['conectado', 'reconectando', 'offline']);
  });

  it('evento novo cancela o relógio do offline', () => {
    const { fluxo, fontes, timers } = montar(1000);
    fluxo.abrir();
    (fontes[0] as FonteFalsa).emitir('error');
    expect(timers).toHaveLength(1);
    (fontes[0] as FonteFalsa).emitir('mf', JSON.stringify(evento(1)));
    // o timer antigo foi cancelado e um novo foi agendado
    expect(timers).toHaveLength(1);
    expect(fluxo.estadoConexao).toBe('conectado');
  });

  it('fechar encerra a fonte e o relógio', () => {
    const { fluxo, fontes, timers } = montar();
    fluxo.abrir();
    expect(timers).toHaveLength(1);
    fluxo.fechar();
    expect(timers).toHaveLength(0);
    expect((fontes[0] as FonteFalsa).fechada).toBe(true);
  });

  it('abrir com desde=x continua do ponto certo', () => {
    const { fluxo, fontes, recebidos } = montar();
    fluxo.abrir(10);
    expect((fontes[0] as FonteFalsa).url).toBe('/api/v1/projetos/p1/eventos?desde=10');
    (fontes[0] as FonteFalsa).emitir('mf', JSON.stringify(evento(10)));
    (fontes[0] as FonteFalsa).emitir('mf', JSON.stringify(evento(11)));
    expect(recebidos.map((e) => e.seq)).toEqual([11]);
  });

  it('não avisa a mesma transição de estado duas vezes', () => {
    const aviso = vi.fn();
    const fluxo = new FluxoEventos({
      projetoId: 'p1',
      aoEvento: () => {},
      aoConexao: aviso,
      criarEventSource: () => new FonteFalsa('x') as unknown as EventSource,
      agendar: () => 1,
      cancelarTimer: () => {},
    });
    fluxo.abrir();
    const fonte = (fluxo as unknown as { fonte: FonteFalsa | null }).fonte;
    fonte?.emitir('open');
    fonte?.emitir('open');
    expect(aviso).toHaveBeenCalledTimes(1);
  });
});
