/**
 * Guarda de contrato (W6-02): o vocabulário de eventos do web tem que ser exatamente o do
 * servidor. Lê `eventos/vocabulario.py` e compara com `EVENTOS_NUCLEO`/`EVENTOS_SERVIDOR`.
 *
 * Se este teste falhar, não é bug do teste: um dos dois lados ganhou evento novo e o outro
 * precisa acompanhar.
 */

import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

import { EVENTOS_NUCLEO, EVENTOS_SERVIDOR } from './tipos';

const CAMINHO_VOCABULARIO = resolve(
  __dirname,
  '../../../servidor/mapasfacil_servidor/eventos/vocabulario.py',
);

/**
 * Extrai a lista de um `NOME: frozenset[str] = frozenset({ "a", "b" })`.
 *
 * Recorte por índice, sem regex com quebra de linha: o arquivo do servidor é CRLF.
 */
function lerLista(fonte: string, nome: string): string[] {
  const inicio = fonte.indexOf(`${nome}:`);
  if (inicio < 0) throw new Error(`não achei ${nome} em vocabulario.py`);
  const abre = fonte.indexOf('frozenset(', inicio);
  const fecha = fonte.indexOf(')', abre);
  if (abre < 0 || fecha < 0) throw new Error(`${nome} não tem um frozenset(...) fechado`);
  const corpo = fonte.slice(abre, fecha);
  return [...corpo.matchAll(/"([^"]+)"/g)].map((m) => m[1] ?? "");
}

describe('vocabulário de eventos', () => {
  const fonte = readFileSync(CAMINHO_VOCABULARIO, 'utf8');

  it('lê as duas listas do servidor', () => {
    expect(lerLista(fonte, 'EVENTOS_NUCLEO')).toContain('chat.delta');
    expect(lerLista(fonte, 'EVENTOS_SERVIDOR')).toContain('versao.criada');
  });

  it('eventos do núcleo são os mesmos do servidor', () => {
    expect([...EVENTOS_NUCLEO].sort()).toEqual(lerLista(fonte, 'EVENTOS_NUCLEO').sort());
  });

  it('eventos do servidor são os mesmos do servidor', () => {
    expect([...EVENTOS_SERVIDOR].sort()).toEqual(lerLista(fonte, 'EVENTOS_SERVIDOR').sort());
  });

  it('nenhum evento aparece nos dois lados', () => {
    const nucleo = new Set<string>(EVENTOS_NUCLEO);
    expect(EVENTOS_SERVIDOR.filter((e) => nucleo.has(e))).toEqual([]);
  });
});
