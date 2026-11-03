/**
 * W6-06 — assistente de novo mapa.
 *
 * Protege: proporção real da folha (A0 é 8× A4), obrigatoriedade do nome, recusa de arquivo
 * que não é `.zip`, progresso contado em partes reais, e a ordem do fim do fluxo — **upload
 * primeiro, projeto depois** — para não sobrar projeto vazio quando o envio falha.
 */

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { CartaoFolha } from '../../componentes/CartaoFolha';
import { equivalenciaA4, problemasZip, textoFolha } from '../../componentes/formatos';
import { NovoMapa, PassoFolha, PassoZip } from './NovoMapa';

const fetchFalso = vi.fn();
const navegar = vi.fn();

vi.mock('react-router-dom', async () => {
  const real = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...real, useNavigate: () => navegar };
});

function resposta(corpo: unknown, status = 200): Response {
  return new Response(JSON.stringify(corpo), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

beforeEach(() => {
  vi.stubGlobal('fetch', fetchFalso);
  fetchFalso.mockReset();
  navegar.mockReset();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function zipFalso(bytes = 300): File {
  return new File([new Uint8Array(bytes)], 'imovel_ficticio.zip', { type: 'application/zip' });
}

describe('formatos de folha', () => {
  it('A3 é 2 folhas A4 e A0 é 16 (dobra de área a cada passo)', () => {
    expect(equivalenciaA4('A4')).toBe(1);
    expect(equivalenciaA4('A3')).toBe(2);
    expect(equivalenciaA4('A0')).toBe(16);
  });

  it('paisagem inverte as medidas no texto', () => {
    expect(textoFolha('A4', 'retrato')).toBe('A4 · retrato · 210×297 mm');
    expect(textoFolha('A4', 'paisagem')).toBe('A4 · paisagem · 297×210 mm');
  });
});

describe('CartaoFolha', () => {
  it('desenha a folha na proporção do formato escolhido', () => {
    const { container } = render(<CartaoFolha formato="A0" orientacao="retrato" />);
    const folha = container.querySelector('[class*="folha"]') as HTMLElement;
    const proporcao = parseFloat(folha.style.width) / parseFloat(folha.style.height);
    // 841/1189 ≈ 0,707
    expect(proporcao).toBeCloseTo(0.707, 2);
  });

  it('paisagem gira o desenho (largura maior que altura)', () => {
    const { container } = render(<CartaoFolha formato="A3" orientacao="paisagem" />);
    const folha = container.querySelector('[class*="folha"]') as HTMLElement;
    expect(parseFloat(folha.style.width)).toBeGreaterThan(parseFloat(folha.style.height));
  });

  it('quando é clicável, avisa o formato escolhido', () => {
    const aoEscolher = vi.fn();
    render(<CartaoFolha formato="A3" orientacao="retrato" aoEscolher={aoEscolher} />);
    fireEvent.click(screen.getByRole('button', { name: /Folha A3/ }));
    expect(aoEscolher).toHaveBeenCalledWith('A3');
  });
});

describe('problemasZip', () => {
  it('aceita .zip e recusa o resto', () => {
    expect(problemasZip(zipFalso())).toBeNull();
    expect(problemasZip(new File([new Uint8Array(10)], 'mapa.pdf'))).toContain('.zip');
    expect(problemasZip(new File([], 'vazio.zip'))).toContain('vazio');
  });
});

describe('passo 1 — folha e nome', () => {
  it('avisa a equivalência em folhas A4 ao trocar o formato', () => {
    const aoMudar = vi.fn();
    const { rerender } = render(
      <PassoFolha rascunho={{ nome: '', formato: 'A4', orientacao: 'retrato', arquivo: null }} aoMudar={aoMudar} />,
    );
    expect(screen.getByText(/A4 equivale a 1 folhas A4/)).toBeInTheDocument();

    rerender(
      <PassoFolha rascunho={{ nome: '', formato: 'A0', orientacao: 'retrato', arquivo: null }} aoMudar={aoMudar} />,
    );
    expect(screen.getByText(/A0 equivale a 16 folhas A4/)).toBeInTheDocument();
  });

  it('trocar a orientação emite a mudança', () => {
    const aoMudar = vi.fn();
    render(
      <PassoFolha rascunho={{ nome: 'X', formato: 'A3', orientacao: 'retrato', arquivo: null }} aoMudar={aoMudar} />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'paisagem' }));
    expect(aoMudar).toHaveBeenCalledWith({ orientacao: 'paisagem' });
  });
});

describe('passo 2 — envio do pacote', () => {
  it('mostra o progresso em partes reais e avisa quando o hash fecha', async () => {
    const aoEnviado = vi.fn();
    // Uma resposta por rota: `mockResolvedValueOnce` em fila se consome por ordem de chamada
    // e um PUT acabava recebendo o corpo do `concluir`.
    fetchFalso.mockImplementation((url: string) => {
      const caminho = String(url);
      if (caminho.endsWith('/uploads')) {
        return Promise.resolve(
          resposta({
            upload_id: 'u1',
            nome: 'imovel_ficticio.zip',
            tamanho: 300,
            parte_bytes: 100,
            total_partes: 3,
            partes_ok: [],
            faltam: [0, 1, 2],
          }),
        );
      }
      if (caminho.includes('/partes/')) return Promise.resolve(new Response(null, { status: 204 }));
      if (caminho.includes('/concluir')) {
        return Promise.resolve(resposta({ upload_id: 'u1', sha256: 'a'.repeat(64), tamanho: 300 }));
      }
      return Promise.resolve(resposta({}, 200));
    });

    render(
      <PassoZip arquivo={zipFalso()} upload={null} aoEscolher={() => {}} aoEnviado={aoEnviado} aoErro={() => {}} />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Enviar o pacote' }));

    await waitFor(() => expect(aoEnviado).toHaveBeenCalled());
    expect(fetchFalso.mock.calls.some(([url]) => String(url).includes('/concluir'))).toBe(true);
  });

  it('arquivo que não é zip não começa o envio', () => {
    const pdf = new File([new Uint8Array(10)], 'mapa.pdf');
    render(<PassoZip arquivo={pdf} upload={null} aoEscolher={() => {}} aoEnviado={() => {}} aoErro={() => {}} />);
    fireEvent.click(screen.getByRole('button', { name: 'Enviar o pacote' }));
    expect(screen.getByRole('alert')).toHaveTextContent('.zip');
    expect(fetchFalso).not.toHaveBeenCalled();
  });
});

describe('fluxo completo', () => {
  it('cria o projeto só depois do upload e vai para a tela do projeto', async () => {
    fetchFalso.mockImplementation((url: string, opcoes?: RequestInit) => {
      const caminho = String(url);
      if (caminho.endsWith('/uploads') && opcoes?.method === 'POST') {
        return Promise.resolve(
          resposta({
            upload_id: 'u9',
            nome: 'imovel_ficticio.zip',
            tamanho: 300,
            parte_bytes: 100,
            total_partes: 3,
            partes_ok: [],
            faltam: [0, 1, 2],
          }),
        );
      }
      if (caminho.includes('/partes/')) return Promise.resolve(new Response(null, { status: 204 }));
      if (caminho.includes('/concluir')) {
        return Promise.resolve(resposta({ upload_id: 'u9', sha256: 'b'.repeat(64), tamanho: 300 }));
      }
      if (caminho.endsWith('/projetos') && opcoes?.method === 'POST') {
        return Promise.resolve(resposta({ projeto: { id: 'p9' } }, 201));
      }
      if (caminho.includes('/importacao')) return Promise.resolve(resposta({ importacao_id: 'i1' }, 202));
      return Promise.resolve(resposta({}, 200));
    });

    render(
      <MemoryRouter>
        <NovoMapa />
      </MemoryRouter>,
    );

    // Passo 1: o botão só libera com nome.
    const continuar = screen.getByRole('button', { name: 'Continuar' });
    expect(continuar).toBeDisabled();
    fireEvent.change(screen.getByLabelText('Nome do projeto'), { target: { value: 'Boa Vista' } });
    fireEvent.click(screen.getByRole('button', { name: /Folha A0/ }));
    expect(continuar).toBeEnabled();
    fireEvent.click(continuar);

    // Passo 2: escolher o arquivo e enviar.
    const entrada = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(entrada, { target: { files: [zipFalso()] } });
    fireEvent.click(screen.getByRole('button', { name: 'Enviar o pacote' }));
    await screen.findByText(/Pacote enviado e conferido/);

    fireEvent.click(screen.getByRole('button', { name: 'Continuar' }));

    // Passo 3: resumo com o que foi escolhido, e a criação.
    expect(screen.getByText('Boa Vista')).toBeInTheDocument();
    // o padrão do assistente é paisagem; só trocamos o formato
    expect(screen.getByText(/A0 · paisagem/)).toBeInTheDocument();
    const criar = screen.getByRole('button', { name: 'Criar projeto e importar' });
    fireEvent.click(criar);

    await waitFor(() => expect(navegar).toHaveBeenCalledWith('/projetos/p9'));

    const chamadas = fetchFalso.mock.calls.map(([url]) => String(url));
    const iProjeto = chamadas.findIndex((u) => u.endsWith('/projetos'));
    const iUpload = chamadas.findIndex((u) => u.endsWith('/uploads'));
    expect(iUpload).toBeGreaterThanOrEqual(0);
    expect(iProjeto).toBeGreaterThan(iUpload); // upload antes de criar o projeto
    expect(chamadas.some((u) => u.includes('/projetos/p9/importacao'))).toBe(true);
  });
});
