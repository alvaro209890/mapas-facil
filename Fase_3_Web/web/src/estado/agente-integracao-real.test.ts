import { beforeEach, afterEach, expect, it, vi } from 'vitest';
import { useAgente } from './agente';
const resposta = (dados: unknown, status = 200) => new Response(JSON.stringify(dados), { status, headers: { 'Content-Type': 'application/json' } });
const fetchSpy = vi.fn();
beforeEach(() => { vi.stubGlobal('fetch', fetchSpy); fetchSpy.mockReset(); useAgente.getState().limpar(); });
afterEach(() => vi.unstubAllGlobals());

it('obtém token fora do SSE e envia decisão compatível com API após clique humano', async () => {
  useAgente.setState({ aprovacao: { acao: 'apagar_arquivo', caminho: 'rascunho.txt', motivo: 'Solicitado' } });
  fetchSpy.mockImplementation((_url: string, init?: RequestInit) => {
    if (init?.method === 'POST') return Promise.resolve(resposta({ ok: true }));
    return Promise.resolve(resposta({ agente: { aprovacao: { acao: 'apagar_arquivo', caminho: 'rascunho.txt', motivo: 'Solicitado', token: 'fixture-token-nao-real' } } }));
  });
  await useAgente.getState().decidirAprovacao('proj-sintetico', true);
  const post = fetchSpy.mock.calls.find(([, init]) => init?.method === 'POST');
  expect(post).toBeDefined();
  expect(JSON.parse(post![1].body)).toMatchObject({ acao: 'aprovar', action: 'apagar_arquivo', path: 'rascunho.txt', token: 'fixture-token-nao-real' });
  expect(fetchSpy.mock.calls[0]![0]).toContain('/agente');
  expect(useAgente.getState().aprovacao?.resolvida).toBe(true);
});

it('cancelamento recusado não inventa estado cancelado no browser', async () => {
  useAgente.setState({ status: 'em_andamento' });
  fetchSpy.mockImplementation(() => Promise.resolve(resposta({ erro: { codigo: 'SV-240', mensagem: 'Worker não confirmou o cancelamento' } }, 503)));
  await useAgente.getState().cancelar('proj-sintetico');
  expect(useAgente.getState().status).toBe('em_andamento');
  expect(useAgente.getState().erro).toContain('Worker');
});
