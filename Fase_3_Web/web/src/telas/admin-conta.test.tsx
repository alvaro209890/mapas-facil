/**
 * W6-08 e W6-09 — administração, conta e modal de sessão expirada.
 *
 * O que se prova aqui: a senha temporária aparece **uma vez** e o aviso diz isso; bloqueio
 * manda `ativo` invertido; a conta troca senha com a regra do servidor; e o modal de sessão
 * expirada deixa o trabalho na tela (não navega para `/entrar`).
 */

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useSessao } from '../estado/sessao';
import { Admin } from './Admin';
import { Conta } from './Conta';
import { SessaoExpirada } from './SessaoExpirada';

const fetchFalso = vi.fn();

function resposta(corpo: unknown, status = 200): Response {
  return new Response(JSON.stringify(corpo), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

const USUARIOS = [
  { id: 'u1', nome: 'Pamera', email: 'pamera@imap.com.br', papel: 'admin', bloqueado: false },
  { id: 'u2', nome: 'Manu', email: 'manu@imap.com.br', papel: 'usuario', bloqueado: true },
];

beforeEach(() => {
  vi.stubGlobal('fetch', fetchFalso);
  fetchFalso.mockReset();
  useSessao.setState({
    estado: 'ativa',
    usuario: { id: 'u1', nome: 'Pamera', email: 'pamera@imap.com.br', papel: 'admin' },
    csrf: 'tok',
    jaEntrou: true,
    precisaTrocarSenha: false,
    erro: null,
    carregando: false,
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('administração', () => {
  it('lista contas com situação e saúde do servidor', async () => {
    fetchFalso.mockImplementation((url: string) => {
      const caminho = String(url);
      if (caminho.includes('/admin/usuarios')) return Promise.resolve(resposta({ itens: USUARIOS }));
      if (caminho.includes('/admin/auditoria')) {
        return Promise.resolve(resposta({ itens: [], proximo: null }));
      }
      return Promise.resolve(
        resposta({
          workers: { workers: 2 },
          vagas_livres: 4,
          disco_livre_gb: 1039.4,
          schema: 2,
          nucleo: '0.4.0',
        }),
      );
    });

    render(<Admin />);
    expect(await screen.findByText('Pamera')).toBeInTheDocument();
    expect(screen.getByText('manu@imap.com.br')).toBeInTheDocument();
    expect(screen.getByText('bloqueada')).toBeInTheDocument();
    expect(screen.getByText('1039.4 GB')).toBeInTheDocument();
    expect(screen.getByText('Contas (2)')).toBeInTheDocument();
  });

  it('senha temporária aparece uma vez, com o aviso de que não volta', async () => {
    fetchFalso.mockImplementation((url: string, opcoes?: RequestInit) => {
      const caminho = String(url);
      if (caminho.includes('/admin/usuarios') && opcoes?.method === 'POST') {
        return Promise.resolve(
          resposta(
            {
              usuario: { id: 'u3', nome: 'Ellen', email: 'ellen@imap.com.br', papel: 'usuario' },
              senha_temporaria: 'Temp-9f2a4c',
            },
            201,
          ),
        );
      }
      if (caminho.includes('/admin/usuarios')) return Promise.resolve(resposta({ itens: USUARIOS }));
      if (caminho.includes('/admin/auditoria')) return Promise.resolve(resposta({ itens: [] }));
      return Promise.resolve(resposta({}));
    });

    render(<Admin />);
    await screen.findByText('Pamera');

    fireEvent.change(screen.getByLabelText('Nome'), { target: { value: 'Ellen' } });
    fireEvent.change(screen.getByLabelText('E-mail'), { target: { value: 'ellen@imap.com.br' } });
    fireEvent.click(screen.getByRole('button', { name: 'Criar conta e gerar senha' }));

    const aviso = await screen.findByRole('status');
    expect(aviso).toHaveTextContent('Temp-9f2a4c');
    expect(aviso).toHaveTextContent('uma vez');
  });

  it('bloquear manda ativo=false e desbloquear manda ativo=true', async () => {
    fetchFalso.mockImplementation((url: string) => {
      const caminho = String(url);
      if (caminho.includes('/admin/usuarios')) return Promise.resolve(resposta({ itens: USUARIOS }));
      if (caminho.includes('/admin/auditoria')) return Promise.resolve(resposta({ itens: [] }));
      return Promise.resolve(resposta({}));
    });

    render(<Admin />);
    await screen.findByText('Pamera');

    // Pamera está ativa → botão "bloquear" → ativo=false
    fireEvent.click(screen.getAllByRole('button', { name: 'bloquear' })[0] as HTMLElement);
    await waitFor(() => {
      const patch = fetchFalso.mock.calls.find(([, o]) => (o as RequestInit)?.method === 'PATCH');
      expect(patch).toBeTruthy();
      expect(JSON.parse(String((patch?.[1] as RequestInit).body))).toEqual({ ativo: false });
    });

    // Manu está bloqueada → "desbloquear" → ativo=true
    fetchFalso.mockClear();
    fetchFalso.mockImplementation((url: string) => {
      const caminho = String(url);
      if (caminho.includes('/admin/usuarios')) return Promise.resolve(resposta({ itens: USUARIOS }));
      if (caminho.includes('/admin/auditoria')) return Promise.resolve(resposta({ itens: [] }));
      return Promise.resolve(resposta({}));
    });
    fireEvent.click(screen.getByRole('button', { name: 'desbloquear' }));
    await waitFor(() => {
      const patch = fetchFalso.mock.calls.find(([, o]) => (o as RequestInit)?.method === 'PATCH');
      expect(patch).toBeTruthy();
      expect(JSON.parse(String((patch?.[1] as RequestInit).body))).toEqual({ ativo: true });
    });
  });
});

describe('conta', () => {
  it('troca a senha e confirma na tela', async () => {
    fetchFalso.mockResolvedValueOnce(new Response(null, { status: 204 }));
    render(
      <MemoryRouter>
        <Conta />
      </MemoryRouter>,
    );
    fireEvent.change(screen.getByLabelText('Senha atual'), { target: { value: 'antiga12345' } });
    fireEvent.change(screen.getByLabelText('Senha nova'), { target: { value: 'mapaForte2026' } });
    fireEvent.click(screen.getByRole('button', { name: 'Salvar' }));

    expect(await screen.findByRole('status')).toHaveTextContent('Senha alterada');
    const [url, opcoes] = fetchFalso.mock.calls[0] as [string, RequestInit];
    expect(url).toContain('/auth/senha');
    expect(JSON.parse(String(opcoes.body))).toEqual({
      senha_atual: 'antiga12345',
      senha_nova: 'mapaForte2026',
    });
  });

  it('senha fraca segura o envio antes de bater no servidor', () => {
    render(
      <MemoryRouter>
        <Conta />
      </MemoryRouter>,
    );
    fireEvent.change(screen.getByLabelText('Senha atual'), { target: { value: 'x123456789' } });
    fireEvent.change(screen.getByLabelText('Senha nova'), { target: { value: '123' } });
    expect(screen.getByText(/pelo menos 10 caracteres/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Salvar' })).toBeDisabled();
    expect(fetchFalso).not.toHaveBeenCalled();
  });
});

describe('modal de sessão expirada', () => {
  it('mostra o modal e não sai da tela; entrar de novo reabre a sessão', async () => {
    useSessao.setState({
      estado: 'expirada',
      usuario: { id: 'u1', nome: 'Pamera', email: 'pamera@imap.com.br', papel: 'admin' },
      jaEntrou: true,
    });
    fetchFalso.mockResolvedValueOnce(
      resposta({
        usuario: { id: 'u1', nome: 'Pamera', email: 'pamera@imap.com.br', papel: 'admin' },
        csrf: 'tok2',
      }),
    );

    render(
      <MemoryRouter initialEntries={['/projetos/p1']}>
        <Routes>
          <Route path="/projetos/:id" element={<div>chat com rascunho</div>} />
        </Routes>
        <SessaoExpirada />
      </MemoryRouter>,
    );

    expect(screen.getByText('chat com rascunho')).toBeInTheDocument();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText(/continua aqui/)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/Senha de pamera@imap.com.br/), {
      target: { value: 'mapaForte2026' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Entrar de novo' }));

    await waitFor(() => expect(useSessao.getState().estado).toBe('ativa'));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(screen.getByText('chat com rascunho')).toBeInTheDocument();
  });

  it('não aparece quando a sessão está ativa', () => {
    render(<SessaoExpirada />);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});
