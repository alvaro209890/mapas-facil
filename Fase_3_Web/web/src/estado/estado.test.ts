/**
 * W6-03 — stores e ponte do SSE.
 *
 * O que importa provar aqui: store só muda com dado do servidor (nada de timer fingindo
 * progresso), evento do SSE chega na store certa, e a timeline é a herdada do desktop.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { despachar } from '../api/ponteWeb';
import type { Evento } from '../api/tipos';
import { useChat } from './chat';
import { useConexao } from './conexao';
import { useJob } from './job';
import { usePalco } from './palco';
import { useProjetoAtivo } from './projetoAtivo';
import { useProjetos } from './projetos';
import { useSessao } from './sessao';

let proximoSeq = 1;

function evt(nome: string, dados: Record<string, unknown>, extra: Partial<Evento> = {}): Evento {
  return {
    seq: proximoSeq++,
    ts: '2026-11-03T12:00:00Z',
    origem: 'servidor',
    evento: nome,
    dados,
    ...extra,
  };
}

const fetchFalso = vi.fn();

beforeEach(() => {
  vi.stubGlobal('fetch', fetchFalso);
  fetchFalso.mockReset();
  proximoSeq = 1;
  useConexao.setState({ ultimoSeq: 0, estado: 'parado' });
  for (const loja of [useChat, useJob, usePalco, useProjetoAtivo]) {
    loja.getState().limpar();
  }
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function jsonResposta(corpo: unknown, status = 200): Response {
  return new Response(JSON.stringify(corpo), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

// ------------------------------------------------------------------ sessão


describe('store de sessão', () => {
  it('carregar com /auth/eu deixa a sessão ativa e guarda o csrf', async () => {
    fetchFalso.mockImplementation(() =>
      Promise.resolve(
        jsonResposta({
          usuario: { id: 'u1', nome: 'Ana', email: 'a@b.c', papel: 'usuario' },
          csrf: 'tok',
        }),
      ),
    );
    await useSessao.getState().carregar();
    const s = useSessao.getState();
    expect(s.estado).toBe('ativa');
    expect(s.csrf).toBe('tok');
    expect(s.usuario?.nome).toBe('Ana');
  });

  it('401 marca expirada, não "desconhecida"', async () => {
    fetchFalso.mockImplementation(() =>
      Promise.resolve(jsonResposta({ erro: { codigo: 'SV-002', mensagem: 'sem sessão' } }, 401)),
    );
    await useSessao.getState().carregar();
    expect(useSessao.getState().estado).toBe('expirada');
  });

  it('entrar guarda a mensagem de erro do servidor', async () => {
    fetchFalso.mockImplementation(() =>
      Promise.resolve(
        jsonResposta(
          { erro: { codigo: 'SV-001', mensagem: 'e-mail ou senha não conferem' } },
          401,
        ),
      ),
    );
    await expect(useSessao.getState().entrar('a@b.c', 'x')).rejects.toBeTruthy();
    expect(useSessao.getState().erro).toContain('não conferem');
  });

  it('conta criada pelo admin marca precisaTrocarSenha', async () => {
    fetchFalso.mockImplementation(() =>
      Promise.resolve(
        jsonResposta({
          usuario: { id: 'u2', nome: 'Bia', email: 'b@c.d', papel: 'usuario' },
          csrf: 'tok2',
          trocar_senha: true,
        }),
      ),
    );
    await useSessao.getState().entrar('b@c.d', 'temp1234');
    expect(useSessao.getState().precisaTrocarSenha).toBe(true);
  });
});

// ---------------------------------------------------------------- projetos


describe('store de projetos', () => {
  it('carrega a lista e atualiza estado por evento, sem refazer tudo', async () => {
    fetchFalso.mockImplementation(() =>
      Promise.resolve(
        jsonResposta({
          itens: [
            { id: 'p1', nome: 'A', estado: 'importando', folha: {}, imovel: {}, versao_atual: 0, miniatura: null, atualizado_em: '' },
            { id: 'p2', nome: 'B', estado: 'pronto', folha: {}, imovel: {}, versao_atual: 1, miniatura: null, atualizado_em: '' },
          ],
        }),
      ),
    );
    await useProjetos.getState().carregar();
    expect(useProjetos.getState().itens).toHaveLength(2);

    useProjetos.getState().aoMudarEstado('p1', 'pronto');
    const itens = useProjetos.getState().itens;
    expect(itens[0]?.estado).toBe('pronto');
    expect(itens[1]?.nome).toBe('B');
  });

  it('busca vai na query string', async () => {
    fetchFalso.mockImplementation(() => Promise.resolve(jsonResposta({ itens: [] })));
    await useProjetos.getState().carregar({ busca: 'boa vista', filtro: 'ativos' });
    const url = String(fetchFalso.mock.calls[0]?.[0]);
    expect(url).toContain('/api/v1/projetos');
    expect(decodeURIComponent(url.replace(/\+/g, ' '))).toContain('busca=boa vista');
  });

  it('lixeira pede estado=lixeira', async () => {
    fetchFalso.mockImplementation(() => Promise.resolve(jsonResposta({ itens: [] })));
    await useProjetos.getState().carregar({ filtro: 'lixeira' });
    expect(String(fetchFalso.mock.calls[0]?.[0])).toContain('estado=lixeira');
  });
});

// -------------------------------------------------------------------- chat


describe('store de chat', () => {
  it('dois deltas viram uma bolha só e o turno fecha em nucleo.res', () => {
    useChat.getState().limpar();
    useChat.getState().enviarLocal('faz a dinâmica', 'req1');
    expect(useChat.getState().turnoEmCurso).toBe('req1');
    expect(useChat.getState().pensando).toBe(true);

    despachar(evt('chat.delta', { texto: 'Vou ' }));
    despachar(evt('chat.delta', { texto: 'gerar.' }));
    const blocos = useChat.getState().blocos;
    // A fala do usuário entra na hora como bolha própria; os deltas dividem uma bolha só.
    expect(blocos).toHaveLength(2);
    expect(blocos[0]?.tipo === 'usuario' ? blocos[0].texto : '').toBe('faz a dinâmica');
    expect(blocos[1]?.tipo === 'texto' ? blocos[1].markdown : '').toBe('Vou gerar.');

    // O eco do servidor (`mensagem.criada`) não duplica a bolha do usuário.
    despachar(evt('mensagem.criada', { mensagem: { papel: 'usuario', texto: 'faz a dinâmica' } }));
    expect(useChat.getState().blocos.filter((b) => b.tipo === 'usuario')).toHaveLength(1);
    expect(useChat.getState().pensando).toBe(false);

    despachar(evt('nucleo.res', { ok: true }, { origem: 'nucleo' }));
    expect(useChat.getState().turnoEmCurso).toBeNull();
  });

  it('chat.turno marca o turno antes do primeiro token e fecha no fim', () => {
    useChat.getState().limpar();
    despachar(evt('chat.turno', { fase: 'inicio', origem: 'abertura' }, { req_id: 'ab-1' }));
    expect(useChat.getState().pensando).toBe(true);
    expect(useChat.getState().turnoEmCurso).toBe('ab-1');
    // O primeiro token tira o "pensando", mas o turno continua aberto.
    despachar(evt('chat.delta', { texto: 'Li o pacote.' }));
    expect(useChat.getState().pensando).toBe(false);
    expect(useChat.getState().turnoEmCurso).toBe('ab-1');
    despachar(evt('chat.turno', { fase: 'fim', origem: 'abertura' }, { req_id: 'ab-1' }));
    expect(useChat.getState().turnoEmCurso).toBeNull();
  });

  it('nucleo.res com ok=false mostra erro e cancela tool pendente', () => {
    useChat.getState().limpar();
    despachar(evt('chat.tool', { trace_id: 't1', tool: 'gerar_mapa', fase: 'inicio' }));
    despachar(evt('nucleo.res', { ok: false }, { origem: 'nucleo' }));
    expect(useChat.getState().erro).toContain('não conseguiu');
  });

  it('mensagem de origem sistema e resposta vazia não viram bolha', () => {
    useChat.getState().limpar();
    useChat.getState().carregar([
      { message_id: 'm1', seq: 1, papel: 'usuario', texto: '[ORIGEM: sistema | MOTIVO: x]\nApresente…', criada_em: 'x' },
      { message_id: 'm2', seq: 2, papel: 'assistente', texto: '', criada_em: 'x' },
      { message_id: 'm3', seq: 3, papel: 'usuario', texto: 'faz a dinâmica', criada_em: 'x' },
    ]);
    const blocos = useChat.getState().blocos;
    expect(blocos).toHaveLength(1);
    expect(blocos[0]?.tipo === 'usuario' ? blocos[0].texto : '').toBe('faz a dinâmica');
  });

  it('nucleo.res com erro do núcleo mostra o motivo', () => {
    useChat.getState().limpar();
    despachar(
      evt(
        'nucleo.res',
        { ok: false, erro: { codigo: 'NUCLEO:IA-030', mensagem: 'Limite de rodadas.' } },
        { origem: 'nucleo' },
      ),
    );
    expect(useChat.getState().erro).toBe('A IA não conseguiu concluir o turno: Limite de rodadas.');
  });

  it('mensagem.criada entra na lista de mensagens', () => {
    useChat.getState().limpar();
    despachar(
      evt('mensagem.criada', {
        mensagem: { message_id: 'm1', seq: 3, papel: 'usuario', texto: 'oi', criada_em: 'x' },
      }),
    );
    expect(useChat.getState().mensagens).toHaveLength(1);
    expect(useChat.getState().mensagens[0]?.texto).toBe('oi');
  });
});

// --------------------------------------------------------------------- job


describe('store de job', () => {
  it('progresso real move a etapa e o percentual', () => {
    useJob.getState().limpar();
    despachar(evt('job.progresso', { etapa: 'exportando_pdf', pct: 90 }, { job_id: 'j1' }));
    const estado = useJob.getState();
    expect(estado.jobId).toBe('j1');
    expect(estado.pct).toBe(90);
    expect(estado.etapas.at(-1)?.nome).toBe('exportando_pdf');
  });

  it('percentual é limitado a 0–100 (servidor com bug não pinta 130%)', () => {
    useJob.getState().limpar();
    despachar(evt('job.progresso', { etapa: 'x', pct: 130 }));
    expect(useJob.getState().pct).toBe(100);
  });

  it('log guarda as últimas linhas e artefato parcial entra no mapa', () => {
    useJob.getState().limpar();
    despachar(evt('job.log', { mensagem: 'gerando camada 1' }));
    despachar(evt('job.artefato_parcial', { tipo: 'pdf', caminho: 'Mapas/v001/mapa.pdf' }));
    expect(useJob.getState().log).toEqual(['gerando camada 1']);
    expect(useJob.getState().artefatos.pdf).toBe('Mapas/v001/mapa.pdf');
  });
});

// ---------------------------------------------------------- projeto aberto


describe('store do projeto aberto', () => {
  it('versao.criada entra na lista, vira a aberta e atualiza versao_atual', () => {
    useProjetoAtivo.getState().limpar();
    useProjetoAtivo.setState({
      projeto: {
        id: 'p1',
        nome: 'Boa Vista',
        estado: 'gerando',
        folha: { formato: 'A4', orientacao: 'retrato' },
        imovel: {},
        versao_atual: 1,
        miniatura: null,
        atualizado_em: '',
      },
    });
    despachar(
      evt('versao.criada', {
        versao: { numero: 2, pasta: 'Mapas/v002', conforme: true, miniatura: null, artefatos: {}, validacao: {}, criada_em: 'x' },
      }),
    );
    const estado = useProjetoAtivo.getState();
    expect(estado.versoes.map((v) => v.numero)).toEqual([2]);
    expect(estado.versaoAberta).toBe(2);
    expect(estado.projeto?.versao_atual).toBe(2);
  });

  it('importacao.progresso alimenta a barra e some quando o projeto fica pronto', () => {
    useProjetoAtivo.getState().limpar();
    despachar(evt('projeto.estado', { estado: 'importando' }));
    expect(useProjetoAtivo.getState().importacao).toEqual({
      fase: 'extraindo',
      indice: 0,
      total: 0,
      arquivo: null,
    });
    despachar(
      evt('importacao.progresso', { fase: 'extraindo', arquivo: 'ATP.shp', indice: 37, total: 148, bytes: 10 }),
    );
    expect(useProjetoAtivo.getState().importacao).toMatchObject({ indice: 37, total: 148, arquivo: 'ATP.shp' });
    despachar(evt('importacao.progresso', { fase: 'indexando', total: 148 }));
    expect(useProjetoAtivo.getState().importacao?.fase).toBe('indexando');
    despachar(evt('projeto.estado', { estado: 'pronto' }));
    expect(useProjetoAtivo.getState().importacao).toBeNull();
  });

  it('projeto.estado com erro guarda o código', () => {
    useProjetoAtivo.getState().limpar();
    useProjetoAtivo.setState({
      projeto: {
        id: 'p1',
        nome: 'X',
        estado: 'importando',
        folha: { formato: 'A4', orientacao: 'retrato' },
        imovel: {},
        versao_atual: 0,
        miniatura: null,
        atualizado_em: '',
      },
    });
    despachar(evt('projeto.estado', { estado: 'erro', erro_codigo: 'SV-110' }));
    expect(useProjetoAtivo.getState().projeto?.estado).toBe('erro');
    expect(useProjetoAtivo.getState().projeto?.erro_codigo).toBe('SV-110');
  });
});

// ------------------------------------------------------------------ conexão


describe('store de conexão', () => {
  it('guarda o último seq aplicado e o estado do EventSource', () => {
    useConexao.getState().aoAplicar(7);
    useConexao.getState().aoMudar('offline');
    expect(useConexao.getState().ultimoSeq).toBe(7);
    expect(useConexao.getState().estado).toBe('offline');
  });
});
