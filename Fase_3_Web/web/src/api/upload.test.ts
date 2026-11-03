/**
 * Upload por partes — o teste que importa é o **hash_partes igual ao do servidor**.
 *
 * Se um dos dois lados mudar o cálculo (concatenação dos hex, na ordem), o servidor responde
 * `SV-102` e o usuário perde o envio inteiro. Aqui o mesmo arquivo é fatiado e os hashes são
 * conferidos contra valores calculados pelo próprio Node (`node:crypto`), independente do
 * `crypto.subtle` do browser.
 */

import { createHash } from 'node:crypto';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { hashPartes, sha256Hex, enviarZip } from './upload';

const fetchFalso = vi.fn();

beforeEach(() => {
  vi.stubGlobal('fetch', fetchFalso);
  fetchFalso.mockReset();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function hashNode(dados: Uint8Array | string): string {
  return createHash('sha256').update(dados).digest('hex');
}

function resposta(corpo: unknown, status = 200): Response {
  return new Response(JSON.stringify(corpo), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('sha256Hex', () => {
  it('bate com o node:crypto', async () => {
    const bytes = new TextEncoder().encode('mapas facil');
    expect(await sha256Hex(bytes)).toBe(hashNode(bytes));
  });
});

describe('hashPartes', () => {
  it('é o sha256 da concatenação dos hex, na ordem', async () => {
    const a = hashNode('parte-0');
    const b = hashNode('parte-1');
    expect(await hashPartes([a, b])).toBe(hashNode(a + b));
  });

  it('ordem importa', async () => {
    const a = hashNode('parte-0');
    const b = hashNode('parte-1');
    expect(await hashPartes([a, b])).not.toBe(await hashPartes([b, a]));
  });
});

function arquivoFalso(tamanho: number, nome = 'imovel.zip'): File {
  const bytes = new Uint8Array(tamanho);
  for (let i = 0; i < tamanho; i += 1) bytes[i] = i % 251;
  return new File([bytes], nome, { type: 'application/zip' });
}

describe('enviarZip', () => {
  it('manda todas as partes com X-Parte-SHA256 e conclui com o hash certo', async () => {
    const arquivo = arquivoFalso(10, 'imovel.zip');
    const conteudo = new Uint8Array(await arquivo.arrayBuffer());
    const esperado = [
      hashNode(conteudo.slice(0, 4)),
      hashNode(conteudo.slice(4, 8)),
      hashNode(conteudo.slice(8, 10)),
    ];

    fetchFalso
      .mockResolvedValueOnce(
        resposta({
          upload_id: 'u1',
          nome: 'imovel.zip',
          tamanho: 10,
          parte_bytes: 4,
          total_partes: 3,
          partes_ok: [],
          faltam: [0, 1, 2],
        }),
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(resposta({ upload_id: 'u1', sha256: hashNode(conteudo), tamanho: 10 }));

    const progresso: Array<[number, number]> = [];
    const resultado = await enviarZip(arquivo, { aoProgresso: (e, t) => progresso.push([e, t]) });

    expect(resultado.sha256).toBe(hashNode(conteudo));

    const puts = fetchFalso.mock.calls.filter(([, opcoes]) => (opcoes as RequestInit)?.method === 'PUT');
    expect(puts).toHaveLength(3);
    const enviados = puts.map(([url, opcoes]) => ({
      url: String(url),
      hash: ((opcoes as RequestInit).headers as Record<string, string>)['X-Parte-SHA256'],
    }));
    expect(enviados.map((e) => e.hash)).toEqual(esperado);
    expect(enviados[0]?.url).toContain('/uploads/u1/partes/0');

    // O `concluir` leva o hash das partes, não o do arquivo.
    const conclusao = fetchFalso.mock.calls.at(-1) as [string, RequestInit];
    expect(String(conclusao[0])).toContain('/uploads/u1/concluir');
    const corpo = JSON.parse(String(conclusao[1].body)) as { hash_partes: string };
    expect(corpo.hash_partes).toBe(hashNode(esperado.join('')));

    expect(progresso.at(-1)).toEqual([3, 3]);
  });

  it('retoma: só manda as partes que faltam, mas conclui com o hash de todas', async () => {
    const arquivo = arquivoFalso(10);
    const conteudo = new Uint8Array(await arquivo.arrayBuffer());
    const hashes = [
      hashNode(conteudo.slice(0, 4)),
      hashNode(conteudo.slice(4, 8)),
      hashNode(conteudo.slice(8, 10)),
    ];

    // 1ª chamada: estado do upload já existente (parte 0 e 2 estão lá).
    fetchFalso
      .mockResolvedValueOnce(
        resposta({
          upload_id: 'u2',
          nome: 'imovel.zip',
          tamanho: 10,
          parte_bytes: 4,
          total_partes: 3,
          partes_ok: [0, 2],
          faltam: [1],
        }),
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(resposta({ upload_id: 'u2', sha256: hashNode(conteudo), tamanho: 10 }));

    await enviarZip(arquivo, {}, 'u2');

    const puts = fetchFalso.mock.calls.filter(([, opcoes]) => (opcoes as RequestInit)?.method === 'PUT');
    expect(puts).toHaveLength(1);
    expect(String(puts[0]?.[0])).toContain('/uploads/u2/partes/1');

    const conclusao = fetchFalso.mock.calls.at(-1) as [string, RequestInit];
    const corpo = JSON.parse(String(conclusao[1].body)) as { hash_partes: string };
    expect(corpo.hash_partes).toBe(hashNode(hashes.join('')));
  });

  it('arquivo com tamanho diferente do que o servidor espera para antes de enviar', async () => {
    fetchFalso.mockResolvedValueOnce(
      resposta({
        upload_id: 'u3',
        nome: 'x.zip',
        tamanho: 999,
        parte_bytes: 4,
        total_partes: 250,
        partes_ok: [],
        faltam: [],
      }),
    );
    await expect(enviarZip(arquivoFalso(10), {}, 'u3')).rejects.toThrow(/recomece o envio/);
    expect(fetchFalso).toHaveBeenCalledTimes(1);
  });

  it('abortar no meio para o envio sem concluir', async () => {
    const arquivo = arquivoFalso(10);
    const controlador = new AbortController();
    fetchFalso
      .mockResolvedValueOnce(
        resposta({
          upload_id: 'u4',
          nome: 'x.zip',
          tamanho: 10,
          parte_bytes: 4,
          total_partes: 3,
          partes_ok: [],
          faltam: [0, 1, 2],
        }),
      )
      .mockImplementationOnce(() => {
        controlador.abort();
        return Promise.resolve(new Response(null, { status: 204 }));
      });

    await expect(enviarZip(arquivo, { sinal: controlador.signal })).rejects.toThrow(/cancelado/);
    const conclusoes = fetchFalso.mock.calls.filter(([url]) => String(url).includes('/concluir'));
    expect(conclusoes).toHaveLength(0);
  });
});
