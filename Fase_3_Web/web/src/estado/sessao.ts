/**
 * Store de sessão (W6-03).
 *
 * Fonte de verdade: `GET /auth/eu`. O cliente HTTP avisa aqui quando o servidor responde
 * 401 — é o gancho que abre o modal "sua sessão expirou" sem perder o texto do chat.
 */

import { create } from 'zustand';

import { api, definirCsrf, ErroHttp, registrarExpiracao } from '../api/cliente';
import type { Sessao, Usuario } from '../api/tipos';

export type EstadoSessao = 'desconhecida' | 'ativa' | 'expirada';

interface LojaSessao {
  estado: EstadoSessao;
  usuario: Usuario | null;
  csrf: string | null;
  /** Conta criada pelo admin: o primeiro acesso exige senha nova. */
  precisaTrocarSenha: boolean;
  /**
   * Já houve sessão nesta aba. Serve para distinguir "nunca entrou" (vai para `/entrar`) de
   * "sessão expirou no meio do trabalho" (modal por cima, rascunho preservado — W6-09).
   */
  jaEntrou: boolean;
  erro: string | null;
  carregando: boolean;
  carregar: () => Promise<void>;
  entrar: (email: string, senha: string) => Promise<void>;
  cadastrar: (nome: string, email: string, senha: string) => Promise<void>;
  sair: () => Promise<void>;
  /** Troca a senha. Conta criada pelo admin: a "atual" é a temporária que ele usou. */
  trocarSenha: (senhaAtual: string, senhaNova: string) => Promise<void>;
  aoExpirar: () => void;
}

function aplicarSessao(sessao: Sessao): Partial<LojaSessao> {
  definirCsrf(sessao.csrf);
  return {
    estado: 'ativa',
    usuario: sessao.usuario,
    csrf: sessao.csrf,
    precisaTrocarSenha: Boolean(sessao.usuario.trocar_senha ?? sessao.trocar_senha),
    jaEntrou: true,
    erro: null,
  };
}

export const useSessao = create<LojaSessao>((set, get) => ({
  estado: 'desconhecida',
  usuario: null,
  csrf: null,
  precisaTrocarSenha: false,
  jaEntrou: false,
  erro: null,
  carregando: false,

  aoExpirar: () => {
    definirCsrf(null);
    set({ estado: 'expirada', usuario: null, csrf: null });
  },

  carregar: async () => {
    set({ carregando: true });
    try {
      const sessao = await api.get<Sessao>('/auth/eu', { semAvisoDeExpiracao: true });
      set({ ...aplicarSessao(sessao), carregando: false });
    } catch (erro) {
      const expirada = erro instanceof ErroHttp && erro.status === 401;
      definirCsrf(null);
      registrarExpiracao(get().aoExpirar);
      set({
        estado: expirada ? 'expirada' : 'desconhecida',
        usuario: null,
        csrf: null,
        carregando: false,
      });
    }
  },

  entrar: async (email, senha) => {
    set({ carregando: true, erro: null });
    try {
      const sessao = await api.post<Sessao>(
        '/auth/entrar',
        { email, senha },
        { semAvisoDeExpiracao: true },
      );
      registrarExpiracao(get().aoExpirar);
      set({ ...aplicarSessao(sessao), carregando: false });
    } catch (erro) {
      set({ carregando: false, erro: mensagemDe(erro) });
      throw erro;
    }
  },

  cadastrar: async (nome, email, senha) => {
    set({ carregando: true, erro: null });
    try {
      const sessao = await api.post<Sessao>(
        '/auth/cadastrar',
        { nome, email, senha },
        { semAvisoDeExpiracao: true },
      );
      registrarExpiracao(get().aoExpirar);
      set({ ...aplicarSessao(sessao), carregando: false });
    } catch (erro) {
      set({ carregando: false, erro: mensagemDe(erro) });
      throw erro;
    }
  },

  sair: async () => {
    try {
      await api.post('/auth/sair', {});
    } catch {
      // Sair é best-effort: se o servidor não responder, a sessão local morre do mesmo jeito.
    }
    definirCsrf(null);
    // `jaEntrou` continua `true`: o modal de sessão expirada assume, sem trocar a tela.
    set({ estado: 'expirada', usuario: null, csrf: null, precisaTrocarSenha: false });
  },

  trocarSenha: async (senhaAtual, senhaNova) => {
    await api.post('/auth/senha', { senha_atual: senhaAtual, senha_nova: senhaNova });
    set({ precisaTrocarSenha: false });
  },
}));

function mensagemDe(erro: unknown): string {
  if (erro instanceof ErroHttp) return erro.texto;
  return 'Não foi possível falar com o servidor.';
}
