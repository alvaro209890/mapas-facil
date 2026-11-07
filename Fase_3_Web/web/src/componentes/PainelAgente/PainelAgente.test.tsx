/**
 * Testes do componente PainelAgente (Checklist plano/passos/status, arquivos, preview PDF, aprovação destrutiva, cancelamento).
 */

import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useAgente } from '../../estado/agente';
import { PainelAgente } from './PainelAgente';

beforeEach(() => {
  useAgente.getState().limpar();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('PainelAgente — Checklist do plano e passos', () => {
  it('renderiza os passos com seus status correspondentes', () => {
    useAgente.setState({
      status: 'em_andamento',
      passos: [
        { id: '1', titulo: 'Ler perímetros do shapefile', status: 'concluido', resumo: 'ATP localizado' },
        { id: '2', titulo: 'Gerar PDF padrão IMAP', status: 'em_andamento', resumo: 'Renderizando páginas' },
        { id: '3', titulo: 'Validar normas SEMA', status: 'pendente' },
      ],
    });

    render(<PainelAgente projetoId="proj-1" />);

    expect(screen.getByText('Ler perímetros do shapefile')).toBeInTheDocument();
    expect(screen.getByText('ATP localizado')).toBeInTheDocument();
    expect(screen.getByText('Gerar PDF padrão IMAP')).toBeInTheDocument();
    expect(screen.getByText('Renderizando páginas')).toBeInTheDocument();
    expect(screen.getByText('Validar normas SEMA')).toBeInTheDocument();

    // Badges de status
    expect(screen.getByText('Concluído')).toBeInTheDocument();
    expect(screen.getAllByText('Executando').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Na fila')).toBeInTheDocument();
  });

  it('exibe o status geral da execução', () => {
    useAgente.setState({
      status: 'concluido',
      resumoFim: 'Entrega finalizada com sucesso',
      passos: [{ id: '1', titulo: 'Etapa única', status: 'concluido' }],
    });

    render(<PainelAgente projetoId="proj-1" />);

    expect(screen.getByText(/Entrega finalizada com sucesso/i)).toBeInTheDocument();
  });
});

describe('PainelAgente — Arquivos tocados e Preview PDF', () => {
  it('exibe a lista de arquivos manipulados', () => {
    useAgente.setState({
      status: 'em_andamento',
      arquivos: [
        { caminho: 'Mapas/v001/mapa_analise.pdf', acao: 'criado' },
        { caminho: 'SHP/perimetro.shp', acao: 'modificado' },
      ],
    });

    render(<PainelAgente projetoId="proj-1" />);

    expect(screen.getByText('Mapas/v001/mapa_analise.pdf')).toBeInTheDocument();
    expect(screen.getByText('criado')).toBeInTheDocument();
    expect(screen.getByText('SHP/perimetro.shp')).toBeInTheDocument();
    expect(screen.getByText('modificado')).toBeInTheDocument();
  });

  it('exibe o preview do PDF com link seguro da API autenticada', () => {
    useAgente.setState({
      status: 'em_andamento',
      previews: [{ caminho: 'Mapas/v001/preview_1.pdf', pagina: 1 }],
      previewAtivo: { caminho: 'Mapas/v001/preview_1.pdf', pagina: 1 },
    });

    render(<PainelAgente projetoId="proj-1" />);

    const linkPdf = screen.getByRole('link', { name: /abrir pdf/i });
    expect(linkPdf).toHaveAttribute(
      'href',
      '/api/v1/projetos/proj-1/arquivos/Mapas/v001/preview_1.pdf',
    );
  });
});

describe('PainelAgente — Aprovação destrutiva explícita', () => {
  it('mostra caixa de alerta com ação, caminho e motivo quando houver aprovação pendente', () => {
    useAgente.setState({
      status: 'em_andamento',
      aprovacao: {
        acao: 'sobrescrever_arquivo',
        caminho: 'Mapas/v001/dinamica.pdf',
        motivo: 'Regeneração completa solicitada',
        token: 'tok-xyz',
        resolvida: false,
      },
    });

    render(<PainelAgente projetoId="proj-1" />);

    expect(screen.getByText(/Aprovação Necessária/i)).toBeInTheDocument();
    expect(screen.getByText('sobrescrever_arquivo')).toBeInTheDocument();
    expect(screen.getByText('Mapas/v001/dinamica.pdf')).toBeInTheDocument();
    expect(screen.getByText('Regeneração completa solicitada')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /aprovar ação/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /recusar/i })).toBeInTheDocument();
  });

  it('aciona decidirAprovacao ao clicar em aprovar ou recusar', async () => {
    const fnDecidir = vi.fn().mockResolvedValue(undefined);
    useAgente.setState({
      status: 'em_andamento',
      aprovacao: {
        acao: 'remover_camada',
        caminho: 'SHP/antiga.shp',
        motivo: 'Desatualizada',
        resolvida: false,
      },
      decidirAprovacao: fnDecidir,
    });

    render(<PainelAgente projetoId="proj-1" />);

    const btnAprovar = screen.getByRole('button', { name: /aprovar ação/i });
    fireEvent.click(btnAprovar);
    expect(fnDecidir).toHaveBeenCalledWith('proj-1', true);

    const btnRecusar = screen.getByRole('button', { name: /recusar/i });
    fireEvent.click(btnRecusar);
    expect(fnDecidir).toHaveBeenCalledWith('proj-1', false);
  });

  it('exibe bloqueio de segurança quando a aprovação remota for insegura ou não suportada', () => {
    useAgente.setState({
      status: 'em_andamento',
      aprovacao: {
        acao: 'apagar_tudo',
        caminho: 'todos',
        motivo: 'reset',
        resolvida: false,
      },
      bloqueioAprovacao: 'Aprovação remota segura não suportada pelo servidor neste momento.',
    });

    render(<PainelAgente projetoId="proj-1" />);

    expect(
      screen.getByText(/Aprovação remota segura não suportada pelo servidor neste momento/i),
    ).toBeInTheDocument();
  });
});

describe('PainelAgente — Botão Parar / cancelamento', () => {
  it('chama cancelar quando usuário clica em Parar', () => {
    const fnCancelar = vi.fn().mockResolvedValue(undefined);
    useAgente.setState({
      status: 'em_andamento',
      passos: [{ id: '1', titulo: 'Processando', status: 'em_andamento' }],
      cancelar: fnCancelar,
    });

    render(<PainelAgente projetoId="proj-1" />);

    const btnParar = screen.getByRole('button', { name: /parar agente/i });
    fireEvent.click(btnParar);

    expect(fnCancelar).toHaveBeenCalledWith('proj-1');
  });
});
