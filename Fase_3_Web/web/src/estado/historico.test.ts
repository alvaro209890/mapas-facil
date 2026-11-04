/**
 * Recarregar a página não perde o chat (caso real do teste_22, 04/11/2026).
 *
 * O servidor devolvia `conteudo` e a store lia `texto`: o `.trim()` de `undefined` quebrava o
 * `carregar` e o chat abria vazio. E mesmo com o texto, um turno que só chamou `perguntar`
 * voltava vazio (o texto dele é ""), sem a pergunta nem os cartões das tools.
 */

import { beforeEach, describe, expect, it } from 'vitest';

import type { Evento, Mensagem } from '../api/tipos';
import { blocosDoHistorico, perguntaDoTrace, useChat } from './chat';

function msg(parcial: Partial<Mensagem> & Pick<Mensagem, 'seq' | 'papel'>): Mensagem {
  return {
    message_id: `m${parcial.seq}`,
    texto: '',
    criada_em: '2026-11-04T13:00:00Z',
    ...parcial,
  };
}

const PERGUNTA = JSON.stringify({
  pergunta: 'Qual modelo você quer?',
  opcoes: [
    { id: 'dinamica', rotulo: 'Dinâmica de uso do solo' },
    { id: 'app', rotulo: 'APP' },
  ],
});

beforeEach(() => useChat.getState().limpar());

describe('histórico do chat', () => {
  it('aceita a linha crua do núcleo (`conteudo`) sem quebrar', () => {
    const crua = { message_id: 'x', seq: 1, papel: 'usuario', conteudo: 'oi', criado_em: 'agora' };
    useChat.getState().carregar([crua as unknown as Mensagem]);
    const blocos = useChat.getState().blocos;
    expect(blocos).toHaveLength(1);
    expect(blocos[0]).toMatchObject({ tipo: 'usuario', texto: 'oi' });
  });

  it('turno que só perguntou volta com a pergunta, já respondida pela fala seguinte', () => {
    const blocos = blocosDoHistorico([
      msg({
        seq: 1,
        papel: 'assistente',
        tool_traces: [
          { trace_id: 't1', tool: 'listar_modelos_galeria', ok: true, args_resumo: '{}' },
          { trace_id: 't2', tool: 'perguntar', ok: true, args_resumo: PERGUNTA },
        ],
      }),
      msg({ seq: 2, papel: 'usuario', texto: 'Dinâmica de uso do solo' }),
    ]);
    expect(blocos.map((b) => b.tipo)).toEqual(['tools', 'pergunta', 'usuario']);
    const pergunta = blocos[1];
    expect(pergunta?.tipo === 'pergunta' && pergunta.respondida).toBe(true);
    expect(pergunta?.tipo === 'pergunta' && pergunta.dados.opcoes.map((o) => o.rotulo)).toEqual([
      'Dinâmica de uso do solo',
      'APP',
    ]);
    // `perguntar` não vira cartão de tool — já é o cartão da pergunta.
    const tools = blocos[0];
    expect(tools?.tipo === 'tools' && tools.tools.map((t) => t.tool)).toEqual(['listar_modelos_galeria']);
  });

  it('a última pergunta, sem resposta, continua clicável', () => {
    const blocos = blocosDoHistorico([
      msg({
        seq: 1,
        papel: 'assistente',
        tool_traces: [{ trace_id: 't', tool: 'perguntar', ok: true, args_resumo: PERGUNTA }],
      }),
    ]);
    const ultimo = blocos.at(-1);
    expect(ultimo?.tipo).toBe('pergunta');
    expect(ultimo?.tipo === 'pergunta' && ultimo.respondida).toBeFalsy();
  });

  it('argumentos cortados em 500 caracteres ainda dão a pergunta e as opções', () => {
    const cortado = PERGUNTA.slice(0, PERGUNTA.length - 12);
    const dados = perguntaDoTrace({ trace_id: 't', tool: 'perguntar', args_resumo: cortado });
    expect(dados?.pergunta).toBe('Qual modelo você quer?');
    expect(dados?.opcoes.map((o) => o.rotulo)).toEqual(['Dinâmica de uso do solo']);
  });

  it('tools que falharam voltam marcadas e o texto final vem depois delas', () => {
    const blocos = blocosDoHistorico([
      msg({ seq: 1, papel: 'usuario', texto: 'gera o mapa' }),
      msg({
        seq: 2,
        papel: 'assistente',
        texto: 'Pronto, o mapa está na versão 1.',
        tool_traces: [
          { trace_id: 'a', tool: 'ler_recibo_car', ok: false, resultado_resumo: '{"ok": false}' },
          { trace_id: 'b', tool: 'gerar_mapa', ok: true, ms: 1200 },
        ],
      }),
    ]);
    expect(blocos.map((b) => b.tipo)).toEqual(['usuario', 'tools', 'texto']);
    const tools = blocos[1];
    expect(tools?.tipo === 'tools' && tools.tools.map((t) => [t.tool, t.fase, t.ok])).toEqual([
      ['ler_recibo_car', 'fim', false],
      ['gerar_mapa', 'fim', true],
    ]);
  });
});

describe('turno em andamento depois de recarregar', () => {
  function evento(nome: string, dados: Record<string, unknown>, seq: number): Evento {
    return { seq, ts: '2026-11-04T13:00:00Z', origem: 'nucleo', evento: nome, dados, req_id: 'srv-1' };
  }

  it('o replay do SSE reabre o turno com o req_id do servidor (o "Parar" volta a valer)', () => {
    useChat.getState().carregar([msg({ seq: 1, papel: 'usuario', texto: 'gera o mapa' })]);
    useChat.getState().aplicarEvento(
      evento('chat.tool', { trace_id: 'g', tool: 'gerar_mapa', fase: 'inicio' }, 10),
    );
    expect(useChat.getState().turnoEmCurso).toBe('srv-1');
    expect(useChat.getState().pensando).toBe(true);
    // A fala do usuário que o replay reenvia não duplica a do histórico.
    useChat
      .getState()
      .aplicarEvento(evento('mensagem.criada', { mensagem: { papel: 'usuario', texto: 'gera o mapa' } }, 9));
    expect(useChat.getState().blocos.filter((b) => b.tipo === 'usuario')).toHaveLength(1);
    useChat.getState().aplicarEvento(evento('nucleo.res', { ok: true }, 11));
    expect(useChat.getState().turnoEmCurso).toBeNull();
  });

  it('definirTurno troca o id local pelo do servidor só com turno aberto', () => {
    useChat.getState().definirTurno('srv-2');
    expect(useChat.getState().turnoEmCurso).toBeNull();
    useChat.getState().enviarLocal('oi', 'web-1');
    useChat.getState().definirTurno('srv-2');
    expect(useChat.getState().turnoEmCurso).toBe('srv-2');
  });

  it('chat.tool de `perguntar` não desenha cartão de tool', () => {
    useChat.getState().aplicarEvento(evento('chat.tool', { trace_id: 'p', tool: 'perguntar', fase: 'inicio' }, 1));
    expect(useChat.getState().blocos).toHaveLength(0);
  });
});
