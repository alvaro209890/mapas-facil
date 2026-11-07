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
import { useAgente } from '../estado/agente';
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
  useAgente.getState().limpar();
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
    const cartao = await screen.findByText('Gerar mapa');
    expect(cartao).toBeInTheDocument();
  });

  it('importação em curso mostra a barra com o arquivo N de M', async () => {
    montar();
    await waitFor(() => expect(FonteFalsa.ultima).not.toBeNull());
    const fonte = FonteFalsa.ultima as FonteFalsa;
    fonte.disparar('mf', {
      seq: 1,
      ts: '2026-11-04T12:00:00Z',
      origem: 'servidor',
      evento: 'projeto.estado',
      dados: { estado: 'importando' },
    });
    fonte.disparar('mf', {
      seq: 2,
      ts: '2026-11-04T12:00:01Z',
      origem: 'servidor',
      evento: 'importacao.progresso',
      dados: { fase: 'extraindo', arquivo: 'AVN.shp', indice: 74, total: 148, bytes: 1 },
    });
    const barra = await screen.findByRole('progressbar');
    expect(barra).toHaveAttribute('aria-valuenow', '43');
    expect(screen.getByText(/Extraindo 74 de 148 arquivos/)).toBeInTheDocument();
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

    const link = await screen.findByRole('link', { name: /PDF padrão IMAP/i });
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

describe('agente v2 na tela do projeto', () => {
  it('eventos agente.plano e agente.passo renderizam checklist na tela', async () => {
    montar();
    await waitFor(() => expect(FonteFalsa.ultima).not.toBeNull());
    const fonte = FonteFalsa.ultima as FonteFalsa;

    fonte.disparar('mf', {
      seq: 1,
      ts: '2026-11-06T12:00:00Z',
      origem: 'servidor',
      evento: 'agente.plano',
      dados: {
        passos: [
          { id: 'p1', titulo: 'Ler dados vetoriais', status: 'pendente' },
          { id: 'p2', titulo: 'Gerar PDF padrão IMAP', status: 'pendente' },
        ],
      },
    });

    expect(await screen.findByText('Ler dados vetoriais')).toBeInTheDocument();
    expect(screen.getByText('Gerar PDF padrão IMAP')).toBeInTheDocument();

    fonte.disparar('mf', {
      seq: 2,
      ts: '2026-11-06T12:00:01Z',
      origem: 'servidor',
      evento: 'agente.passo',
      dados: {
        id: 'p1',
        titulo: 'Ler dados vetoriais',
        status: 'concluido',
        resumo: 'Perímetro e vértices conferidos',
      },
    });

    expect(await screen.findByText('Perímetro e vértices conferidos')).toBeInTheDocument();
    expect(screen.getByText('Concluído')).toBeInTheDocument();
  });

  it('recupera estado do agente no reload através de GET /api/v1/projetos/:id/agente', async () => {
    fetchFalso.mockImplementation((url: string) => {
      const caminho = String(url);
      if (caminho.endsWith('/agente')) {
        return Promise.resolve(
          resposta({
            status: 'em_andamento',
            passos: [
              { id: '1', titulo: 'Passo recuperado do banco', status: 'concluido', resumo: 'Histórico ativo' },
            ],
            arquivos: [{ caminho: 'Mapas/v001/doc.pdf', acao: 'criado' }],
            previews: [{ caminho: 'Mapas/v001/doc.pdf', pagina: 1 }],
            aprovacao: null,
          }),
        );
      }
      if (caminho.endsWith('/projetos/p1')) return Promise.resolve(resposta({ projeto: PROJETO }));
      if (caminho.includes('/versoes')) return Promise.resolve(resposta({ itens: [VERSAO] }));
      return Promise.resolve(resposta({}, 200));
    });

    montar();

    expect(await screen.findByText('Passo recuperado do banco')).toBeInTheDocument();
    expect(screen.getByText('Histórico ativo')).toBeInTheDocument();
    expect(screen.getAllByText('Mapas/v001/doc.pdf').length).toBeGreaterThanOrEqual(1);
  });

  it('botão Parar cancela o agente e preserva os passos concluídos', async () => {
    montar();
    await waitFor(() => expect(FonteFalsa.ultima).not.toBeNull());
    const fonte = FonteFalsa.ultima as FonteFalsa;

    fonte.disparar('mf', {
      seq: 1,
      ts: '2026-11-06T12:00:00Z',
      origem: 'servidor',
      evento: 'agente.plano',
      dados: {
        passos: [
          { id: 'p1', titulo: 'Passo 1', status: 'concluido' },
          { id: 'p2', titulo: 'Passo 2', status: 'em_andamento' },
        ],
      },
    });

    expect(await screen.findByText('Passo 1')).toBeInTheDocument();

    const btnParar = screen.getByRole('button', { name: /parar agente/i });
    fireEvent.click(btnParar);

    await waitFor(() => {
      const estado = useAgente.getState();
      expect(estado.status).toBe('cancelado');
      expect(estado.passos[0]?.status).toBe('concluido');
      expect(estado.passos[1]?.status).toBe('cancelado');
    });
  });

  it('apresenta termos PDF padrão IMAP e MXD não padrão na tela', async () => {
    montar();
    expect(await screen.findByText(/PDF padrão IMAP e os shapefiles/i)).toBeInTheDocument();
    expect(screen.getByText('PDF padrão IMAP')).toBeInTheDocument();
    expect(screen.getByTitle(/MXD não padrão/i)).toBeInTheDocument();
  });
});
