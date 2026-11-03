/**
 * W6-05 — lista de projetos.
 *
 * Protege o que o plano prometeu: busca com debounce de 250 ms (uma chamada, não uma por
 * tecla), selos de folha e estado com o código do erro, silhueta na proporção do formato,
 * busca vazia com convite honesto e o menu de renomear/lixeira/restaurar.
 */

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { Projeto } from '../api/tipos';
import { useProjetos } from '../estado/projetos';
import { CartaoProjeto, Projetos } from './Projetos';

const fetchFalso = vi.fn();

function projeto(extra: Partial<Projeto> = {}): Projeto {
  return {
    id: 'p1',
    nome: 'Boa Vista',
    estado: 'pronto',
    folha: { formato: 'A3', orientacao: 'paisagem' },
    imovel: { nome: 'Fazenda Boa Vista', car: 'MT-1', municipio: 'Querência', uf: 'MT' },
    versao_atual: 2,
    miniatura: null,
    atualizado_em: '2026-11-03T12:00:00-03:00',
    ...extra,
  } as Projeto;
}

function resposta(corpo: unknown, status = 200): Response {
  return new Response(JSON.stringify(corpo), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

beforeEach(() => {
  vi.stubGlobal('fetch', fetchFalso);
  fetchFalso.mockReset();
  useProjetos.setState({ itens: [], busca: '', filtro: 'ativos', proximo: null, carregando: false, erro: null });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe('grade de projetos', () => {
  it('mostra nome, imóvel com município/UF, selo de folha e selo de estado', async () => {
    fetchFalso.mockResolvedValue(resposta({ itens: [projeto()], proximo: null }));
    render(
      <MemoryRouter>
        <Projetos />
      </MemoryRouter>,
    );

    expect(await screen.findByText('Boa Vista')).toBeInTheDocument();
    expect(screen.getByText('Fazenda Boa Vista · Querência/MT')).toBeInTheDocument();
    expect(screen.getByText('A3 · paisagem')).toBeInTheDocument();
    expect(screen.getByText('pronto')).toBeInTheDocument();
  });

  it('projeto com erro mostra o código do servidor ao lado do estado', () => {
    render(
      <MemoryRouter>
        <CartaoProjeto
          projeto={projeto({ estado: 'erro', erro_codigo: 'SV-110' })}
          naLixeira={false}
          aoAbrir={() => {}}
          aoRenomear={() => {}}
          aoApagar={() => {}}
          aoRestaurar={() => {}}
        />
      </MemoryRouter>,
    );
    expect(screen.getByText(/SV-110/)).toBeInTheDocument();
  });

  it('sem miniatura desenha a silhueta na proporção do formato', () => {
    const { container } = render(
      <MemoryRouter>
        <CartaoProjeto
          projeto={projeto({ folha: { formato: 'A4', orientacao: 'retrato' } })}
          naLixeira={false}
          aoAbrir={() => {}}
          aoRenomear={() => {}}
          aoApagar={() => {}}
          aoRestaurar={() => {}}
        />
      </MemoryRouter>,
    );
    const silhueta = container.querySelector('[class*="silhueta"]') as HTMLElement | null;
    expect(silhueta).not.toBeNull();
    // A4 retrato: 88 de altura, largura = 88 * (210/297) ≈ 62
    expect(silhueta?.style.height).toBe('88px');
    expect(parseInt(silhueta?.style.width ?? '0', 10)).toBeGreaterThan(55);
    expect(parseInt(silhueta?.style.width ?? '0', 10)).toBeLessThan(70);
  });

  it('lista vazia chama o primeiro mapa, e não mostra cartão fantasma', async () => {
    fetchFalso.mockResolvedValue(resposta({ itens: [], proximo: null }));
    render(
      <MemoryRouter>
        <Projetos />
      </MemoryRouter>,
    );
    expect(await screen.findByText('Crie seu primeiro mapa')).toBeInTheDocument();
  });

  it('lixeira vazia fala de lixeira, não de primeiro mapa', async () => {
    fetchFalso.mockResolvedValue(resposta({ itens: [], proximo: null }));
    render(
      <MemoryRouter initialEntries={['/projetos']}>
        <Projetos />
      </MemoryRouter>,
    );
    await screen.findByText('Crie seu primeiro mapa');
    fireEvent.click(screen.getByRole('tab', { name: 'Lixeira' }));
    expect(await screen.findByText('A lixeira está vazia')).toBeInTheDocument();
  });
});

describe('busca com debounce', () => {
  it('três teclas viram uma chamada só, depois de 250 ms', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    fetchFalso.mockResolvedValue(resposta({ itens: [], proximo: null }));
    render(
      <MemoryRouter>
        <Projetos />
      </MemoryRouter>,
    );
    fetchFalso.mockClear();

    const campo = screen.getByLabelText('Buscar projetos');
    fireEvent.change(campo, { target: { value: 'b' } });
    fireEvent.change(campo, { target: { value: 'bo' } });
    fireEvent.change(campo, { target: { value: 'boa' } });
    expect(fetchFalso).not.toHaveBeenCalled();

    vi.advanceTimersByTime(260);
    await waitFor(() => expect(fetchFalso).toHaveBeenCalledTimes(1));
    const url = decodeURIComponent(String(fetchFalso.mock.calls[0]?.[0]).replace(/\+/g, ' '));
    expect(url).toContain('busca=boa');
  });
});

describe('ações do cartão', () => {
  it('renomear faz PATCH e atualiza o nome na tela', async () => {
    fetchFalso.mockResolvedValue(resposta({ itens: [projeto()], proximo: null }));
    vi.stubGlobal('prompt', vi.fn(() => 'Boa Vista II'));
    render(
      <MemoryRouter>
        <Projetos />
      </MemoryRouter>,
    );
    await screen.findByText('Boa Vista');

    fireEvent.click(screen.getByRole('button', { name: 'Ações de Boa Vista' }));
    fetchFalso.mockResolvedValueOnce(resposta({ projeto: projeto({ nome: 'Boa Vista II' }) }));
    fireEvent.click(screen.getByRole('menuitem', { name: 'Renomear' }));

    expect(await screen.findByText('Boa Vista II')).toBeInTheDocument();
    const [url, opcoes] = fetchFalso.mock.calls.at(-1) as [string, RequestInit];
    expect(url).toContain('/projetos/p1');
    expect(opcoes.method).toBe('PATCH');
  });

  it('mandar para a lixeira faz DELETE e tira o cartão dos ativos', async () => {
    fetchFalso.mockResolvedValue(resposta({ itens: [projeto()], proximo: null }));
    vi.stubGlobal('confirm', vi.fn(() => true));
    render(
      <MemoryRouter>
        <Projetos />
      </MemoryRouter>,
    );
    await screen.findByText('Boa Vista');

    fireEvent.click(screen.getByRole('button', { name: 'Ações de Boa Vista' }));
    fetchFalso.mockResolvedValueOnce(new Response(null, { status: 204 }));
    fireEvent.click(screen.getByRole('menuitem', { name: 'Mandar para a lixeira' }));

    await waitFor(() => expect(screen.queryByText('Boa Vista')).not.toBeInTheDocument());
    const [url, opcoes] = fetchFalso.mock.calls.at(-1) as [string, RequestInit];
    expect(url).toContain('/projetos/p1');
    expect(opcoes.method).toBe('DELETE');
  });

  it('na lixeira o menu oferece restaurar, não apagar', () => {
    render(
      <MemoryRouter>
        <CartaoProjeto
          projeto={projeto({ estado: 'lixeira' })}
          naLixeira
          aoAbrir={() => {}}
          aoRenomear={() => {}}
          aoApagar={() => {}}
          aoRestaurar={() => {}}
        />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Ações de Boa Vista' }));
    expect(screen.getByRole('menuitem', { name: 'Restaurar' })).toBeInTheDocument();
    expect(screen.queryByRole('menuitem', { name: 'Mandar para a lixeira' })).not.toBeInTheDocument();
  });
});
