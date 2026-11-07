/**
 * W6-04 — tela de entrada e cadastro.
 *
 * O que este teste protege: erro com o **código do servidor** (nunca "erro ao entrar"),
 * contagem regressiva real do SV-005, abas Entrar/Criar conta e a troca obrigatória de senha
 * para conta criada pela CLI do admin.
 */

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useSessao } from '../estado/sessao';
import { Entrar, problemasSenha } from './Entrar';

const fetchFalso = vi.fn();

beforeEach(() => {
  vi.stubGlobal('fetch', fetchFalso);
  fetchFalso.mockReset();
  useSessao.setState({
    estado: 'expirada',
    usuario: null,
    csrf: null,
    precisaTrocarSenha: false,
    erro: null,
    carregando: false,
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

function resposta(corpo: unknown, status = 200): Response {
  return new Response(JSON.stringify(corpo), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function preencher(email: string, senha: string) {
  fireEvent.change(screen.getByLabelText('E-mail'), { target: { value: email } });
  fireEvent.change(screen.getByLabelText('Senha'), { target: { value: senha } });
}

describe('regra de senha mostrada antes de enviar', () => {
  it('exige 10 caracteres, recusa só números e caractere repetido', () => {
    expect(problemasSenha('curta')).toContain('10');
    expect(problemasSenha('1234567890123')).toContain('só números');
    expect(problemasSenha('aaaaaaaaaaaa')).toContain('repetido');
    expect(problemasSenha('mapaForte2026')).toBeNull();
  });
});

describe('tela de entrada', () => {
  it('apresenta PDF padrão IMAP como produto, sem prometer MXD por padrão', () => {
    render(<Entrar />);
    expect(screen.getByText(/PDF padrão IMAP/)).toBeInTheDocument();
    expect(screen.queryByText(/com MXD, PDF/)).not.toBeInTheDocument();
  });
  it('tem as duas abas e a de criar conta pede nome e repetição', () => {
    render(<Entrar />);
    expect(screen.getByRole('tab', { name: 'Entrar' })).toHaveAttribute('aria-selected', 'true');

    fireEvent.click(screen.getByRole('tab', { name: 'Criar conta' }));
    expect(screen.getByLabelText('Nome')).toBeInTheDocument();
    expect(screen.getByLabelText('Repetir a senha')).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Criar conta' })).toHaveAttribute('aria-selected', 'true');
  });

  it('senha e repetição diferentes seguram o envio', async () => {
    render(<Entrar />);
    fireEvent.click(screen.getByRole('tab', { name: 'Criar conta' }));
    fireEvent.change(screen.getByLabelText('Nome'), { target: { value: 'Ana' } });
    preencher('ana@imap.com.br', 'mapaForte2026');
    fireEvent.change(screen.getByLabelText('Repetir a senha'), { target: { value: 'outraCoisa2026' } });

    expect(screen.getByText('As senhas não conferem.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Criar conta e entrar' })).toBeDisabled();
    expect(fetchFalso).not.toHaveBeenCalled();
  });

  it('erro do servidor aparece com o código (SV-001) e o texto dele', async () => {
    fetchFalso.mockResolvedValueOnce(
      resposta(
        {
          erro: {
            codigo: 'SV-001',
            mensagem: 'e-mail ou senha não conferem',
            o_que_fazer: 'Confira a senha.',
          },
        },
        401,
      ),
    );
    render(<Entrar />);
    preencher('ana@imap.com.br', 'senhaErrada2026');
    fireEvent.click(screen.getByRole('button', { name: 'Entrar' }));

    const alerta = await screen.findByRole('alert');
    expect(alerta).toHaveTextContent('SV-001');
    expect(alerta).toHaveTextContent('e-mail ou senha não conferem');
    expect(alerta).toHaveTextContent('Confira a senha.');
  });

  it('conta bloqueada (SV-003) mostra a mensagem do servidor', async () => {
    fetchFalso.mockResolvedValueOnce(
      resposta({ erro: { codigo: 'SV-003', mensagem: 'esta conta foi bloqueada' } }, 403),
    );
    render(<Entrar />);
    preencher('ana@imap.com.br', 'mapaForte2026');
    fireEvent.click(screen.getByRole('button', { name: 'Entrar' }));

    const alerta = await screen.findByRole('alert');
    expect(alerta).toHaveTextContent('SV-003');
    expect(alerta).toHaveTextContent('bloqueada');
  });

  it('SV-005 com espera_s mostra contagem regressiva e desabilita o botão', async () => {
    fetchFalso.mockResolvedValueOnce(
      resposta(
        {
          erro: {
            codigo: 'SV-005',
            mensagem: 'Muitas tentativas de login. Espere alguns minutos.',
            detalhes: { espera_s: 42 },
          },
        },
        429,
      ),
    );
    render(<Entrar />);
    preencher('ana@imap.com.br', 'mapaForte2026');
    fireEvent.click(screen.getByRole('button', { name: 'Entrar' }));

    await screen.findByText('Tente de novo em 42s');
    expect(screen.getByRole('button', { name: 'Entrar' })).toBeDisabled();
  });

  it('sucesso chama aoEntrar', async () => {
    fetchFalso.mockResolvedValueOnce(
      resposta({
        usuario: { id: 'u1', nome: 'Ana', email: 'ana@imap.com.br', papel: 'usuario' },
        csrf: 'tok',
      }),
    );
    const aoEntrar = vi.fn();
    render(<Entrar aoEntrar={aoEntrar} />);
    preencher('ana@imap.com.br', 'mapaForte2026');
    fireEvent.click(screen.getByRole('button', { name: 'Entrar' }));

    await waitFor(() => expect(aoEntrar).toHaveBeenCalled());
    expect(useSessao.getState().estado).toBe('ativa');
  });
});

describe('troca de senha obrigatória', () => {
  it('conta do admin cai na tela de definir senha, sem formulário de login', () => {
    useSessao.setState({
      estado: 'ativa',
      precisaTrocarSenha: true,
      usuario: { id: 'u2', nome: 'Bia', email: 'bia@imap.com.br', papel: 'usuario', trocar_senha: true },
    });
    render(<Entrar />);
    expect(screen.getByRole('heading', { name: 'Defina sua senha' })).toBeInTheDocument();
    expect(screen.getByLabelText('Senha temporária')).toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: 'Criar conta' })).not.toBeInTheDocument();
  });

  it('troca envia senha atual e nova para /auth/senha', async () => {
    useSessao.setState({
      estado: 'ativa',
      precisaTrocarSenha: true,
      csrf: 'tok',
      usuario: { id: 'u2', nome: 'Bia', email: 'bia@imap.com.br', papel: 'usuario', trocar_senha: true },
    });
    fetchFalso.mockResolvedValueOnce(new Response(null, { status: 204 }));
    render(<Entrar />);
    fireEvent.change(screen.getByLabelText('Senha temporária'), { target: { value: 'temporaria123' } });
    fireEvent.change(screen.getByLabelText('Nova senha'), { target: { value: 'mapaForte2026' } });
    fireEvent.click(screen.getByRole('button', { name: 'Salvar e entrar' }));

    await waitFor(() => expect(fetchFalso).toHaveBeenCalled());
    const [url, opcoes] = fetchFalso.mock.calls[0] as [string, RequestInit];
    expect(url).toContain('/auth/senha');
    expect(String(opcoes.body)).toContain('mapaForte2026');
    await waitFor(() => expect(useSessao.getState().precisaTrocarSenha).toBe(false));
  });
});
