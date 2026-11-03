/**
 * W6-07 — tela do projeto: chat, versões, downloads e o espaço do palco.
 *
 * O teste usa um `EventSource` falso para provar que a tela **só mostra o que veio de evento
 * real**: delta vira bolha, tool vira cartão, `versao.criada` entra na faixa, e o download
 * aponta para a rota de arquivos com `?anexo=true`.
 */

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useChat } from '../estado/chat';
import { useConexao } from '../estado/conexao';
import { useProjetoAtivo } from '../estado/projetoAtivo';
import { Projeto } from './Projeto';

const fetchFalso = vi.fn();

/** `EventSource` mínimo: guarda os ouvintes para o teste disparar eventos na hora que quiser. */
class FonteFalsa {
  static ultima: FonteFalsa | null = null;
  readonly url: string;
  readonly ouvintes = new Map<string, Array<(evento: MessageEvent) => void>>();
  fechada = false;

  constructor(url: string) {
    this.url = url;
    FonteFalsa.ultima = this;
  }

  addEventListener(tipo: string, ouvinte: (evento: MessageEvent) => void): void {
    const lista = this.ouvintes.get(tipo) ?? [];
    lista.push(ouvinte);
    this.ouvintes.set(tipo, lista);
  }

  close(): void {
    this.fechada = true;
  }

  disparar(tipo: string, dados?: unknown): void {
    for (const ouvinte of this.ouvintes.get(tipo) ?? []) {
      ouvinte({ data: dados === undefined ? undefined : JSON.stringify(dados) } as MessageEvent);
    }
  }
}

function resposta(corpo: unknown, status = 200): Response {
  return new Response(JSON.stringify(corpo), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

const PROJETO = {
  id: 'p1',
  nome: 'Boa Vista',
  estado: 'pronto',
  folha: { formato: 'A3', orientacao: 'paisagem' },
  imovel: { nome: 'Fazenda Boa Vista', car: 'MT-1', municipio: 'Querência', uf: 'MT' },
  versao_atual: 1,
  miniatura: null,
  atualizado_em: '2026-11-03T12:00:00-03:00',
};

const VERSAO = {
  numero: 1,
  pasta: 'Mapas/v001',
  conforme: true,
  miniatura: null,
  artefatos: { pdf: 'Mapas/v001/mapa.pdf', mxd: 'Mapas/v001/mapa.mxd', zip: 'Mapas/v001/pacote.zip' },
  validacao: { hard_ok: true },
  criada_em: '2026-11-03T12:00:00-03:00',
};

beforeEach(() => {
  vi.stubGlobal('fetch', fetchFalso);
  vi.stubGlobal('EventSource', FonteFalsa);
  fetchFalso.mockReset();
  useChat.getState().limpar();
  useProjetoAtivo.getState().limpar();
  useConexao.setState({ ultimoSeq: 0, estado: 'parado' });
  FonteFalsa.ultima = null;

  fetchFalso.mockImplementation((url: string) => {
    const caminho = String(url);
    if (caminho.endsWith('/projetos/p1')) return Promise.resolve(resposta({ projeto: PROJETO }));
    if (caminho.includes('/resumo')) {
      return Promise.resolve(resposta({ projeto_id: 'p1', estado: 'pronto', resumo: { area_ha: 512.4 } }));
    }
    if (caminho.includes('/versoes')) return Promise.resolve(resposta({ itens: [VERSAO] }));
    if (caminho.includes('/mensagens')) return Promise.resolve(resposta({ itens: [] }));
    if (caminho.includes('/sugestoes')) {
      return Promise.resolve(
        resposta({
          itens: [{ id: 'dinamica', texto: 'Faz a Dinâmica 2023', porque: 'o mapa do ano corrente' }],
        }),
      );
    }
    return Promise.resolve(resposta({}, 200));
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

function montar(rota = '/projetos/p1') {
  return render(
    <MemoryRouter initialEntries={[rota]}>
      <Routes>
        <Route path="/projetos/:id" element={<Projeto />} />
        <Route path="/projetos/:id/versoes/:numero" element={<Projeto />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('carga do projeto', () => {
  it('mostra nome, imóvel, folha e versão aberta', async () => {
    montar();
    expect(await screen.findByRole('heading', { name: 'Boa Vista' })).toBeInTheDocument();
    expect(screen.getByText('Fazenda Boa Vista · Querência/MT')).toBeInTheDocument();
    expect(screen.getByText('A3 · paisagem')).toBeInTheDocument();
    expect(await screen.findByText('Versão 1')).toBeInTheDocument();
    expect(screen.getByText('v001')).toBeInTheDocument();
  });

  it('abre o SSE do projeto e fecha ao desmontar', async () => {
    const { unmount } = montar();
    await screen.findByRole('heading', { name: 'Boa Vista' });
    await waitFor(() => expect(FonteFalsa.ultima).not.toBeNull());
    expect(FonteFalsa.ultima?.url).toContain('/projetos/p1/eventos');
    unmount();
    expect(FonteFalsa.ultima?.fechada).toBe(true);
  });

  it('mostra sugestões quando a conversa está vazia', async () => {
    montar();
    expect(await screen.findByText('Faz a Dinâmica 2023')).toBeInTheDocument();
  });
});

describe('eventos chegam na tela', () => {
  it('chat.delta vira bolha e nucleo.res fecha o turno', async () => {
    montar();
    await waitFor(() => expect(FonteFalsa.ultima).not.toBeNull());
    const fonte = FonteFalsa.ultima as FonteFalsa;
    fonte.disparar('open');

    fonte.disparar('mf', {
      seq: 1,
      ts: '2026-11-03T12:00:00Z',
      origem: 'nucleo',
      evento: 'chat.delta',
      dados: { texto: 'Gerando a **dinâmica** de 2023.' },
    });
    expect(await screen.findByText(/Gerando a/)).toBeInTheDocument();

    fonte.disparar('mf', {
      seq: 2,
      ts: '2026-11-03T12:00:01Z',
      origem: 'nucleo',
      evento: 'nucleo.res',
      dados: { ok: true },
    });
    await waitFor(() => expect(useChat.getState().turnoEmCurso).toBeNull());
  });

  it('chat.tool aparece como cartão de ferramenta', async () => {
    montar();
    await waitFor(() => expect(FonteFalsa.ultima).not.toBeNull());
    (FonteFalsa.ultima as FonteFalsa).disparar('mf', {
      seq: 1,
      ts: '2026-11-03T12:00:00Z',
      origem: 'nucleo',
      evento: 'chat.tool',
      dados: { trace_id: 't1', tool: 'gerar_mapa', fase: 'inicio' },
    });
    const cartao = await screen.findByText(/gerar_mapa/);
    expect(cartao).toBeInTheDocument();
  });

  it('versao.criada entra na faixa e libera os downloads', async () => {
    montar();
    await waitFor(() => expect(FonteFalsa.ultima).not.toBeNull());
    (FonteFalsa.ultima as FonteFalsa).disparar('mf', {
      seq: 1,
      ts: '2026-11-03T12:00:00Z',
      origem: 'servidor',
      evento: 'versao.criada',
      dados: {
        versao: {
          numero: 2,
          pasta: 'Mapas/v002',
          conforme: false,
          miniatura: null,
          artefatos: { pdf: 'Mapas/v002/mapa.pdf' },
          validacao: { hard_ok: false },
          criada_em: '2026-11-03T12:05:00-03:00',
        },
      },
    });
    expect(await screen.findByText('v002')).toBeInTheDocument();
    expect(screen.getByText('não conforme')).toBeInTheDocument();

    const link = await screen.findByRole('link', { name: 'PDF' });
    expect(link).toHaveAttribute(
      'href',
      '/api/v1/projetos/p1/arquivos/Mapas/v002/mapa.pdf?anexo=true',
    );
  });
});

describe('enviar mensagem', () => {
  it('POST /mensagens com o texto, e o botão vira "Parar" enquanto o turno roda', async () => {
    montar();
    await screen.findByRole('heading', { name: 'Boa Vista' });

    const campo = screen.getByLabelText('Mensagem para a IA');
    fireEvent.change(campo, { target: { value: 'faz a dinâmica de 2023' } });
    fireEvent.click(screen.getByRole('button', { name: 'Enviar' }));

    await waitFor(() => {
      const chamada = fetchFalso.mock.calls.find(
        ([url, opcoes]) => String(url).includes('/mensagens') && (opcoes as RequestInit)?.method === 'POST',
      );
      expect(chamada).toBeTruthy();
      const corpo = JSON.parse(String((chamada?.[1] as RequestInit).body)) as { texto: string };
      expect(corpo.texto).toBe('faz a dinâmica de 2023');
    });
    expect(await screen.findByRole('button', { name: 'Parar' })).toBeInTheDocument();
  });

  it('clique na sugestão manda o texto dela', async () => {
    montar();
    const sugestao = await screen.findByText('Faz a Dinâmica 2023');
    fireEvent.click(sugestao);
    await waitFor(() => {
      const chamada = fetchFalso.mock.calls.find(
        ([url, opcoes]) => String(url).includes('/mensagens') && (opcoes as RequestInit)?.method === 'POST',
      );
      expect(chamada).toBeTruthy();
      const corpo = JSON.parse(String((chamada?.[1] as RequestInit).body)) as { texto: string };
      expect(corpo.texto).toBe('Faz a Dinâmica 2023');
    });
  });

  it('erro do servidor aparece com o código', async () => {
    montar();
    await screen.findByRole('heading', { name: 'Boa Vista' });
    fetchFalso.mockImplementation((url: string, opcoes?: RequestInit) => {
      if (String(url).includes('/mensagens') && opcoes?.method === 'POST') {
        return Promise.resolve(
          resposta({ erro: { codigo: 'SV-241', mensagem: 'Espere a importação terminar.' } }, 409),
        );
      }
      return Promise.resolve(resposta({}, 200));
    });

    fireEvent.change(screen.getByLabelText('Mensagem para a IA'), { target: { value: 'oi' } });
    fireEvent.click(screen.getByRole('button', { name: 'Enviar' }));
    const alerta = await screen.findByRole('alert');
    expect(alerta).toHaveTextContent('SV-241');
  });
});
