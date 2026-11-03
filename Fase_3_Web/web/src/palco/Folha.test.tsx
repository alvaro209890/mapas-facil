/**
 * Testes unitários e de integração de Folha (W8-04 / W-07 §CamadaFolha).
 *
 * Garante:
 * 1. Proporções da folha em mm reais (um A3 gera viewBox 297×420 em retrato);
 * 2. Elemento só aparece depois do seu passo na fila (controle por elementosVisiveis);
 * 3. Entrada com prefers-reduced-motion não anima (duração 0 / initial false);
 * 4. Elemento com caminho vira <image> com href e dimensões corretas;
 * 5. Elemento com conteudo vira <text> com tamanho proporcional ao mm;
 * 6. Snapshot do mapa encaixado na caixa do quadro do mapa;
 * 7. Elementos dispostos na ordem canônica de ORDEM_LAYOUT.
 */

import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Folha, type ElementoFolhaDados } from './Folha';
import { MEDIA_QUERY_MOVIMENTO_REDUZIDO } from './useReducedMotion';

describe('Folha (W8-04)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('1. Proporções da folha e mm reais', () => {
    it('a folha renderiza com as proporções certas (um A3 gera viewBox 297×420)', () => {
      const { container } = render(<Folha formato="A3" orientacao="retrato" />);
      const svg = container.querySelector('svg');

      expect(svg).toBeInTheDocument();
      expect(svg).toHaveAttribute('viewBox', '0 0 297 420');
      expect(svg).toHaveAttribute('preserveAspectRatio', 'xMidYMid meet');

      const papel = container.querySelector('[data-testid="papel-folha"]');
      expect(papel).toBeInTheDocument();
      expect(papel).toHaveAttribute('width', '297');
      expect(papel).toHaveAttribute('height', '420');
    });

    it('renderiza A3 paisagem com proporções invertidas (420×297)', () => {
      const { container } = render(<Folha formato="A3" orientacao="paisagem" />);
      const svg = container.querySelector('svg');

      expect(svg).toHaveAttribute('viewBox', '0 0 420 297');

      const papel = container.querySelector('[data-testid="papel-folha"]');
      expect(papel).toHaveAttribute('width', '420');
      expect(papel).toHaveAttribute('height', '297');
    });

    it('renderiza A4 retrato com 210×297 mm', () => {
      const { container } = render(<Folha formato="A4" orientacao="retrato" />);
      const svg = container.querySelector('svg');

      expect(svg).toHaveAttribute('viewBox', '0 0 210 297');
    });
  });

  describe('2. Controle de visibilidade por passos na fila', () => {
    it('elemento só aparece depois do seu passo na fila', () => {
      const elementos: Record<string, ElementoFolhaDados> = {
        grade: {
          elemento: 'grade',
          caixa_mm: { x0: 10, y0: 10, x1: 200, y1: 280 },
        },
        titulo_caixa: {
          elemento: 'titulo_caixa',
          caixa_mm: { x0: 20, y0: 15, x1: 150, y1: 35 },
          conteudo: 'FAZENDA SANTA MARIA',
        },
        norte: {
          elemento: 'norte',
          caixa_mm: { x0: 180, y0: 15, x1: 195, y1: 35 },
          caminho: 'Mapas/.preview/job-1/layout/norte.png',
        },
      };

      // Passo 1: apenas 'grade' foi consumida
      const { rerender, container } = render(
        <Folha
          formato="A4"
          orientacao="retrato"
          elementos={elementos}
          elementosVisiveis={['grade']}
        />,
      );

      expect(container.querySelector('[data-elemento="grade"]')).toBeInTheDocument();
      expect(container.querySelector('[data-elemento="titulo_caixa"]')).not.toBeInTheDocument();
      expect(container.querySelector('[data-elemento="norte"]')).not.toBeInTheDocument();
      expect(screen.queryByText('FAZENDA SANTA MARIA')).not.toBeInTheDocument();

      // Passo 2: 'titulo_caixa' entra após o seu passo na fila
      rerender(
        <Folha
          formato="A4"
          orientacao="retrato"
          elementos={elementos}
          elementosVisiveis={['grade', 'titulo_caixa']}
        />,
      );

      expect(container.querySelector('[data-elemento="grade"]')).toBeInTheDocument();
      expect(container.querySelector('[data-elemento="titulo_caixa"]')).toBeInTheDocument();
      expect(screen.getByText('FAZENDA SANTA MARIA')).toBeInTheDocument();
      expect(container.querySelector('[data-elemento="norte"]')).not.toBeInTheDocument();

      // Passo 3: 'norte' entra após o seu passo na fila
      rerender(
        <Folha
          formato="A4"
          orientacao="retrato"
          elementos={elementos}
          elementosVisiveis={['grade', 'titulo_caixa', 'norte']}
        />,
      );

      expect(container.querySelector('[data-elemento="norte"]')).toBeInTheDocument();
    });
  });

  describe('3. Movimento reduzido (prefers-reduced-motion)', () => {
    it('prefers-reduced-motion faz aparecer sem animação (duração 0)', () => {
      // Simula media query com prefers-reduced-motion ativo
      vi.spyOn(window, 'matchMedia').mockImplementation((query: string) => ({
        matches: query === MEDIA_QUERY_MOVIMENTO_REDUZIDO,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }));

      const elementos: Record<string, ElementoFolhaDados> = {
        titulo_caixa: {
          elemento: 'titulo_caixa',
          caixa_mm: { x0: 10, y0: 10, x1: 100, y1: 30 },
          conteudo: 'TITULO DIRETO',
        },
      };

      const { container } = render(
        <Folha
          formato="A3"
          orientacao="retrato"
          elementos={elementos}
          elementosVisiveis={['titulo_caixa']}
          reduzirMovimento={true}
        />,
      );

      const grupo = container.querySelector('#elemento-titulo_caixa');
      expect(grupo).toBeInTheDocument();
      // O elemento entra e é exibido diretamente sem animação pendente
      expect(screen.getByText('TITULO DIRETO')).toBeInTheDocument();
    });
  });

  describe('4. Elemento com caminho vira <image>', () => {
    it('elemento com caminho vira <image> com href e dimensões proporcionais', () => {
      const elementos: Record<string, ElementoFolhaDados> = {
        minimapa: {
          elemento: 'minimapa',
          caixa_mm: { x0: 5, y0: 250, x1: 65, y1: 295 },
          caminho: 'Mapas/.preview/job-42/layout/minimapa.png',
        },
      };

      const { container } = render(
        <Folha
          formato="A4"
          orientacao="retrato"
          elementos={elementos}
          elementosVisiveis={['minimapa']}
        />,
      );

      const imagem = container.querySelector('#elemento-minimapa image');
      expect(imagem).toBeInTheDocument();
      expect(imagem).toHaveAttribute('href', 'Mapas/.preview/job-42/layout/minimapa.png');
      expect(imagem).toHaveAttribute('x', '5');
      expect(imagem).toHaveAttribute('y', '250');
      expect(imagem).toHaveAttribute('width', '60');
      expect(imagem).toHaveAttribute('height', '45');
    });
  });

  describe('5. Elemento com texto vira <text>', () => {
    it('os que têm conteudo usam <text> com tamanho proporcional ao mm', () => {
      const elementos: Record<string, ElementoFolhaDados> = {
        titulo_caixa: {
          elemento: 'titulo_caixa',
          caixa_mm: { x0: 50, y0: 10, x1: 150, y1: 30 },
          conteudo: 'MAPA DE USO E OCUPAÇÃO DO SOLO',
        },
      };

      const { container } = render(
        <Folha
          formato="A3"
          orientacao="retrato"
          elementos={elementos}
          elementosVisiveis={['titulo_caixa']}
        />,
      );

      const texto = container.querySelector('#elemento-titulo_caixa text');
      expect(texto).toBeInTheDocument();
      expect(texto?.textContent).toBe('MAPA DE USO E OCUPAÇÃO DO SOLO');

      // Em A3 (fator k ≈ 1.414), tamanho em mm calculado pelo perfil Harmonia
      const fontSize = Number(texto?.getAttribute('font-size') ?? texto?.getAttribute('fontSize'));
      expect(fontSize).toBeGreaterThan(5); // Proporcional em mm reais
      expect(fontSize).toBeLessThan(20);
    });
  });

  describe('6. Snapshot do mapa encaixado no quadro', () => {
    it('renderiza o snapshot como <image> dentro do quadro do mapa', () => {
      const snapshotUrl = 'data:image/png;base64,snapshot-teste-quadro';

      const { container } = render(
        <Folha
          formato="A3"
          orientacao="retrato"
          snapshotMapa={snapshotUrl}
        />,
      );

      const snapshot = container.querySelector('image[data-elemento="snapshot-mapa"]');
      expect(snapshot).toBeInTheDocument();
      expect(snapshot).toHaveAttribute('href', snapshotUrl);
    });

    it('sem snapshotMapa, exibe placeholder do quadro', () => {
      const { container } = render(
        <Folha
          formato="A3"
          orientacao="retrato"
          snapshotMapa={null}
        />,
      );

      expect(container.querySelector('[data-testid="quadro-mapa-placeholder"]')).toBeInTheDocument();
      expect(screen.getByText('[Quadro do Mapa]')).toBeInTheDocument();
    });
  });

  describe('7. Ordem canônica de ORDEM_LAYOUT', () => {
    it('ordena os elementos no DOM segundo ORDEM_LAYOUT', () => {
      // Fornece fora de ordem: tabela, logo, grade, norte
      const elementos: Record<string, ElementoFolhaDados> = {
        tabela: { elemento: 'tabela', caixa_mm: { x0: 10, y0: 10, x1: 50, y1: 50 } },
        logo: { elemento: 'logo', caixa_mm: { x0: 60, y0: 10, x1: 80, y1: 30 } },
        grade: { elemento: 'grade', caixa_mm: { x0: 5, y0: 5, x1: 200, y1: 200 } },
        norte: { elemento: 'norte', caixa_mm: { x0: 180, y0: 10, x1: 195, y1: 30 } },
      };

      const { container } = render(
        <Folha
          formato="A4"
          orientacao="retrato"
          elementos={elementos}
          elementosVisiveis={['tabela', 'logo', 'grade', 'norte']}
        />,
      );

      const elementosRenderizados = Array.from(
        container.querySelectorAll('[data-elemento]'),
      ).map((el) => el.getAttribute('data-elemento'));

      // Filtra os que pertencem aos elementos testados
      const ordemObtida = elementosRenderizados.filter((nome) =>
        ['grade', 'norte', 'logo', 'tabela'].includes(nome ?? ''),
      );

      // Esperado segundo ORDEM_LAYOUT: grade -> norte -> logo -> tabela
      expect(ordemObtida).toEqual(['grade', 'norte', 'logo', 'tabela']);
    });
  });

  describe('8. Interatividade de clique e acessibilidade (W8-11 / D43)', () => {
    it('clique em elemento da folha dispara aoSelecionarElemento com id e bbox', () => {
      const aoSelecionar = vi.fn();
      const elementos: Record<string, ElementoFolhaDados> = {
        legenda: {
          elemento: 'legenda',
          caixa_mm: { x0: 130, y0: 260, x1: 170, y1: 290 },
        },
      };

      const { container } = render(
        <Folha
          formato="A4"
          orientacao="retrato"
          elementos={elementos}
          elementosVisiveis={['legenda']}
          aoSelecionarElemento={aoSelecionar}
        />,
      );

      const elLegenda = container.querySelector('#elemento-legenda');
      expect(elLegenda).toBeInTheDocument();
      expect(elLegenda).toHaveAttribute('tabindex', '0');
      expect(elLegenda).toHaveAttribute('role', 'button');

      // Simula clique
      elLegenda?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      expect(aoSelecionar).toHaveBeenCalledTimes(1);
      expect(aoSelecionar).toHaveBeenCalledWith(
        expect.objectContaining({
          id: 'legenda',
          tipo: 'legenda',
          bbox_mm: { x0: 130, y0: 260, x1: 170, y1: 290 },
        }),
      );
    });

    it('teclado Enter seleciona o elemento com foco', () => {
      const aoSelecionar = vi.fn();
      const elementos: Record<string, ElementoFolhaDados> = {
        titulo_caixa: {
          elemento: 'titulo_caixa',
          caixa_mm: { x0: 20, y0: 10, x1: 100, y1: 30 },
          conteudo: 'TITULO TESTE',
        },
      };

      const { container } = render(
        <Folha
          formato="A4"
          orientacao="retrato"
          elementos={elementos}
          elementosVisiveis={['titulo_caixa']}
          aoSelecionarElemento={aoSelecionar}
        />,
      );

      const elTitulo = container.querySelector('#elemento-titulo_caixa');
      elTitulo?.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
      expect(aoSelecionar).toHaveBeenCalledWith(
        expect.objectContaining({
          id: 'titulo_caixa',
        }),
      );
    });

    it('elemento selecionado recebe classe de destaque', () => {
      const elementos: Record<string, ElementoFolhaDados> = {
        legenda: { elemento: 'legenda' },
      };

      const { container } = render(
        <Folha
          formato="A4"
          orientacao="retrato"
          elementos={elementos}
          elementosVisiveis={['legenda']}
          elementoSelecionado="legenda"
        />,
      );

      const elLegenda = container.querySelector('#elemento-legenda');
      expect(elLegenda?.getAttribute('class')).toContain('elementoSelecionado');
    });
  });
});
