/**
 * Testes do cliente HTTP (W6-02) — sem rede: `fetch` é substituído.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  api,
  definirCsrf,
  ErroHttp,
  extrairErro,
  registrarExpiracao,
  requisitar,
  resetarExpiracao,
} from './cliente';

const fetchFalso = vi.fn();

function ultimaChamada(): [string, RequestInit] {
  return (fetchFalso.mock.calls.at(-1) ?? ['', {}]) as [string, RequestInit];
}

function resposta(status: number, corpo: unknown = null): Response {
  const texto = corpo === null ? '' : JSON.stringify(corpo);
  return new Response(texto || null, {
    status,
    headers: corpo === null ? {} : { 'Content-Type': 'application/json' },
  });
}

describe('cliente HTTP', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', fetchFalso);
    fetchFalso.mockReset();
    definirCsrf(null);
    registrarExpiracao(null);
    resetarExpiracao();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('manda credentials include e o cabeçalho CSRF nas mutações', async () => {
    definirCsrf('tok-csrf');
    fetchFalso.mockResolvedValue(resposta(201, { projeto: { id: 'p1' } }));

    await api.post('/projetos', { nome: 'Boa Vista' });

    const [url, init] = ultimaChamada();
    expect(url).toBe('/api/v1/projetos');
    expect(init.credentials).toBe('include');
    expect(init.method).toBe('POST');
    const headers = (init.headers ?? {}) as Record<string, string>;
    expect(headers['X-MF-CSRF']).toBe('tok-csrf');
    expect(headers['Content-Type']).toBe('application/json');
    expect(JSON.parse(String(init.body))).toEqual({ nome: 'Boa Vista' });
  });

  it('não manda CSRF em GET', async () => {
    definirCsrf('tok-csrf');
    fetchFalso.mockResolvedValue(resposta(200, { itens: [] }));
    await api.get('/projetos');
    const [, init] = ultimaChamada();
    const headers = (init.headers ?? {}) as Record<string, string>;
    expect(headers['X-MF-CSRF']).toBeUndefined();
  });

  it('erro do servidor vira ErroHttp com codigo, mensagem e o que fazer', async () => {
    fetchFalso.mockImplementation(() =>
      Promise.resolve(
        resposta(409, {
          erro: {
            codigo: 'SV-210',
            mensagem: 'A IA ainda está respondendo',
            porque: 'um turno por projeto',
            o_que_fazer: 'Espere o turno terminar.',
          },
        }),
      ),
    );

    await expect(api.post('/projetos/p1/mensagens', { texto: 'oi' })).rejects.toMatchObject({
      codigo: 'SV-210',
      status: 409,
    });

    const capturado = (await api.post('/x', {}).catch((e: unknown) => e)) as ErroHttp;
    expect(capturado).toBeInstanceOf(ErroHttp);
    expect(capturado.texto).toContain('A IA ainda está respondendo');
    expect(capturado.texto).toContain('Espere o turno terminar.');
  });

  it('401 avisa a sessão uma única vez', async () => {
    const aviso = vi.fn();
    registrarExpiracao(aviso);
    fetchFalso.mockImplementation(() =>
      Promise.resolve(resposta(401, { erro: { codigo: 'SV-002', mensagem: 'sem sessão' } })),
    );

    await expect(api.get('/projetos')).rejects.toBeInstanceOf(ErroHttp);
    await expect(api.get('/projetos')).rejects.toBeInstanceOf(ErroHttp);
    expect(aviso).toHaveBeenCalledTimes(1);
  });

  it('rota pública não dispara aviso de expiração', async () => {
    const aviso = vi.fn();
    registrarExpiracao(aviso);
    fetchFalso.mockResolvedValue(resposta(401, { erro: { codigo: 'SV-001', mensagem: 'x' } }));
    await expect(
      requisitar('/auth/entrar', { metodo: 'POST', corpo: {}, semAvisoDeExpiracao: true }),
    ).rejects.toBeInstanceOf(ErroHttp);
    expect(aviso).not.toHaveBeenCalled();
  });

  it('204 devolve undefined', async () => {
    fetchFalso.mockResolvedValue(new Response(null, { status: 204 }));
    await expect(api.del('/projetos/p1')).resolves.toBeUndefined();
  });

  it('falha de rede vira REDE, não código SV', async () => {
    fetchFalso.mockRejectedValue(new TypeError('Failed to fetch'));
    await expect(api.get('/saude')).rejects.toMatchObject({ codigo: 'REDE', status: 0 });
  });

  it('AbortError sobe como está (cancelamento não é erro de tela)', async () => {
    const abort = Object.assign(new Error('aborted'), { name: 'AbortError' });
    fetchFalso.mockRejectedValue(abort);
    await expect(api.get('/x')).rejects.toBe(abort);
  });

  it('corpo de erro estranho não deixa a tela sem mensagem', () => {
    expect(extrairErro(null, 500).codigo).toBe('HTTP-500');
    expect(extrairErro({ detail: 'Not Found' }, 404).mensagem).toBe('Not Found');
    expect(extrairErro({ erro: { mensagem: 'x' } }, 400).codigo).toBe('HTTP-400');
  });

  it('PUT cru não força Content-Type de JSON', async () => {
    fetchFalso.mockResolvedValue(resposta(204));
    await api.putCru('/uploads/u1/partes/0', new Blob([new Uint8Array([1, 2])]));
    const [, init] = ultimaChamada();
    const headers = (init.headers ?? {}) as Record<string, string>;
    expect(headers['Content-Type']).toBeUndefined();
    expect(init.body).toBeInstanceOf(Blob);
  });
});
