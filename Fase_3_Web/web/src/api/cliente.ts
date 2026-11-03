/**
 * Cliente HTTP do web (W6-02).
 *
 * Regras que vêm de W-03 e W-11 e estão todas testadas em `api/cliente.test.ts`:
 *
 * - `credentials: "include"` sempre — a sessão é cookie `HttpOnly`;
 * - todo método que muda estado leva `X-MF-CSRF` com o token da sessão;
 * - resposta não-2xx vira `ErroApi` com `codigo`, `mensagem`, `o_que_fazer` (o Álvaro não
 *   aceita erro genérico: "Load failed" não serve);
 * - `401` avisa a store de sessão, uma vez só, sem laço;
 * - nada de `fetch` espalhado pelas telas: tudo passa por aqui.
 */

import type { ErroApi } from './tipos';

export const BASE = '/api/v1';

export class ErroHttp extends Error {
  readonly codigo: string;
  readonly status: number;
  readonly porque: string | undefined;
  readonly oQueFazer: string | undefined;
  readonly detalhes: Record<string, unknown> | undefined;

  constructor(status: number, erro: ErroApi) {
    super(erro.mensagem || `HTTP ${status}`);
    this.name = 'ErroHttp';
    this.status = status;
    this.codigo = erro.codigo || `HTTP-${status}`;
    this.porque = erro.porque;
    this.oQueFazer = erro.o_que_fazer;
    this.detalhes = erro.detalhes;
  }

  /** Texto para a tela: mensagem do servidor + o que fazer, quando existe. */
  get texto(): string {
    return this.oQueFazer ? `${this.message} — ${this.oQueFazer}` : this.message;
  }
}

type AoExpirar = () => void;

let aoExpirar: AoExpirar | null = null;
let expiracaoAvisada = false;

/** A store de sessão registra aqui o que fazer quando o servidor disser 401. */
export function registrarExpiracao(fn: AoExpirar | null): void {
  aoExpirar = fn;
  expiracaoAvisada = false;
}

/** Só a primeira chamada depois de cada login avisa expiração (evita 10 modais). */
export function resetarExpiracao(): void {
  expiracaoAvisada = false;
}

let csrfAtual: string | null = null;

export function definirCsrf(token: string | null): void {
  csrfAtual = token;
}

export function csrf(): string | null {
  return csrfAtual;
}

const METODOS_COM_CORPO = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

export interface OpcoesRequisicao {
  metodo?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  corpo?: unknown;
  /** `FormData`/`Blob` vão crus, sem `Content-Type` manual. */
  corpoBruto?: BodyInit;
  sinal?: AbortSignal;
  /** Para download: devolve o `Response` cru em vez de JSON. */
  cru?: boolean;
  /** Rotas públicas (login/cadastro) não disparam o aviso de sessão expirada. */
  semAvisoDeExpiracao?: boolean;
  /** Cabeçalhos extras (ex.: `X-Parte-SHA256` no upload por partes). */
  cabecalhos?: Record<string, string>;
}

export async function requisitar<T>(caminho: string, opcoes: OpcoesRequisicao = {}): Promise<T> {
  const metodo = opcoes.metodo ?? 'GET';
  const cabecalhos: Record<string, string> = { Accept: 'application/json' };

  if (METODOS_COM_CORPO.has(metodo) && csrfAtual) {
    cabecalhos['X-MF-CSRF'] = csrfAtual;
  }
  if (opcoes.cabecalhos) {
    Object.assign(cabecalhos, opcoes.cabecalhos);
  }
  let corpo: BodyInit | undefined;
  if (opcoes.corpoBruto !== undefined) {
    corpo = opcoes.corpoBruto;
  } else if (opcoes.corpo !== undefined) {
    cabecalhos['Content-Type'] = 'application/json';
    corpo = JSON.stringify(opcoes.corpo);
  }

  // `exactOptionalPropertyTypes`: `body`/`signal` só entram quando existem.
  const init: RequestInit = {
    method: metodo,
    headers: cabecalhos,
    credentials: 'include',
    ...(corpo !== undefined ? { body: corpo } : {}),
    ...(opcoes.sinal ? { signal: opcoes.sinal } : {}),
  };

  let resposta: Response;
  try {
    resposta = await fetch(BASE + caminho, init);
  } catch (erro) {
    if ((erro as Error)?.name === 'AbortError') throw erro;
    // Falha de rede não é erro de API: a tela mostra "sem conexão", não um código SV-xxx.
    throw new ErroHttp(0, {
      codigo: 'REDE',
      mensagem: 'Sem conexão com o servidor do Mapas Fácil.',
      o_que_fazer: 'Verifique a internet; o trabalho em curso continua no servidor.',
    });
  }

  if (resposta.status === 401 && !opcoes.semAvisoDeExpiracao) {
    if (!expiracaoAvisada) {
      expiracaoAvisada = true;
      aoExpirar?.();
    }
  }

  if (opcoes.cru) {
    if (!resposta.ok) throw await erroDaResposta(resposta);
    return resposta as unknown as T;
  }

  if (resposta.status === 204) return undefined as T;

  const texto = await resposta.text();
  const dados = texto ? (JSON.parse(texto) as unknown) : null;

  if (!resposta.ok) {
    throw new ErroHttp(resposta.status, extrairErro(dados, resposta.status));
  }
  return dados as T;
}

async function erroDaResposta(resposta: Response): Promise<ErroHttp> {
  let dados: unknown = null;
  try {
    dados = await resposta.json();
  } catch {
    dados = null;
  }
  return new ErroHttp(resposta.status, extrairErro(dados, resposta.status));
}

/** O servidor responde `{erro: {...}}`; corpo estranho não pode virar `undefined`. */
export function extrairErro(dados: unknown, status: number): ErroApi {
  const envelope = (dados as { erro?: Partial<ErroApi> } | null)?.erro;
  if (envelope && typeof envelope === 'object') {
    return {
      codigo: String(envelope.codigo ?? `HTTP-${status}`),
      mensagem: String(envelope.mensagem ?? `Falha HTTP ${status}.`),
      porque: envelope.porque,
      o_que_fazer: envelope.o_que_fazer,
      detalhes: envelope.detalhes,
    };
  }
  const detalhe = (dados as { detail?: unknown } | null)?.detail;
  return {
    codigo: `HTTP-${status}`,
    mensagem: typeof detalhe === 'string' ? detalhe : `Falha HTTP ${status}.`,
  };
}

// ------------------------------------------------------------------ atalhos

export const api = {
  get: <T>(caminho: string, opcoes?: Omit<OpcoesRequisicao, 'metodo'>) =>
    requisitar<T>(caminho, { ...opcoes, metodo: 'GET' }),
  post: <T>(caminho: string, corpo?: unknown, opcoes?: Omit<OpcoesRequisicao, 'metodo'>) =>
    requisitar<T>(caminho, { ...opcoes, metodo: 'POST', corpo }),
  patch: <T>(caminho: string, corpo?: unknown, opcoes?: Omit<OpcoesRequisicao, 'metodo'>) =>
    requisitar<T>(caminho, { ...opcoes, metodo: 'PATCH', corpo }),
  del: <T>(caminho: string, opcoes?: Omit<OpcoesRequisicao, 'metodo'>) =>
    requisitar<T>(caminho, { ...opcoes, metodo: 'DELETE' }),
  putCru: <T>(caminho: string, corpo: BodyInit, opcoes?: Omit<OpcoesRequisicao, 'metodo'>) =>
    requisitar<T>(caminho, { ...opcoes, metodo: 'PUT', corpoBruto: corpo }),
  put: <T>(caminho: string, corpo: unknown, opcoes?: Omit<OpcoesRequisicao, 'metodo'>) =>
    requisitar<T>(caminho, { ...opcoes, metodo: 'PUT', corpo }),
};
