/**
 * Testes de integração do Palco do Mapa (W8-01, W8-07, W8-08, W8-09).
 */

import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Versao } from '../api/tipos';
import { usePalco } from '../estado/palco';
import { useProjetoAtivo } from '../estado/projetoAtivo';
import { Camera, type MapaLike, type OpcoesFitBounds, type OpcoesFlyTo, type OpcoesJumpTo } from './Camera';
import { Palco, urlDoArquivo } from './Palco';

class MapaFalso implements MapaLike {
  sources: Record<string, unknown> = {};
  layers: Array<{ layer: Record<string, unknown>; beforeId?: string | undefined }> = [];
  chamadasFitBounds: Array<{ bounds: unknown; opcoes?: OpcoesFitBounds | undefined }> = [];
  canvas: HTMLCanvasElement;

  constructor() {
    this.canvas = {
      toDataURL: vi.fn(() => 'data:image/png;base64,snapshot-teste'),
    } as unknown as HTMLCanvasElement;
  }

  addSource(id: string, source: unknown): void {
    this.sources[id] = source;
  }

  getSource(id: string): unknown {
    return this.sources[id];
  }

  removeSource(id: string): void {
    delete this.sources[id];
  }

  addLayer(layer: unknown, beforeId?: string): void {
    this.layers.push({ layer: layer as Record<string, unknown>, beforeId });
  }

  getLayer(id: string): unknown {
    return this.layers.find((l) => l.layer.id === id)?.layer;
  }

  removeLayer(id: string): void {
    this.layers = this.layers.filter((l) => l.layer.id !== id);
  }

  flyTo(_opcoes: OpcoesFlyTo): void {}

  fitBounds(bounds: unknown, opcoes?: OpcoesFitBounds | undefined): void {
    this.chamadasFitBounds.push({ bounds, opcoes });
  }

  jumpTo(_opcoes: OpcoesJumpTo): void {}

  getCanvas(): HTMLCanvasElement {
    return this.canvas;
  }

  remove(): void {}
}

const VERSAO_TESTE: Versao = {
  numero: 1,
  pasta: 'Mapas/v001',
  conforme: true,
  miniatura: null,
  artefatos: { pdf: 'Mapas/v001/mapa.pdf' },
  validacao: {},
  criada_em: '2026-11-03T12:00:00Z',
};

beforeEach(() => {
  usePalco.getState().limpar();
  useProjetoAtivo.getState().limpar();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('Palco (W8-01, W8-07, W8-08, W8-09)', () => {
  describe('Montagem dos 4 modos (W8-01)', () => {
    it('1. Modo Ocioso: exibe repouso com versão aberta e perímetro da indexação (W8-09)', () => {
      useProjetoAtivo.setState({
        projeto: {
          id: 'p1',
          nome: 'Boa Vista',
          estado: 'pronto',
          folha: { formato: 'A3', orientacao: 'paisagem' },
          imovel: { nome: 'Fazenda Boa Vista', municipio: 'Querência', uf: 'MT' },
          versao_atual: 1,
          miniatura: null,
          atualizado_em: '2026-11-03T12:00:00Z',
        },
      });

      render(<Palco versao={VERSAO_TESTE} suporteWebGL={false} />);

      expect(screen.getByLabelText('Visão Geral do Projeto')).toBeInTheDocument();
      expect(screen.getByText('Versão 1')).toBeInTheDocument();
      expect(
        screen.getByText(/Perímetro do imóvel: Fazenda Boa Vista \(Querência\/MT\)/),
      ).toBeInTheDocument();
      expect(
        screen.getByText(/Sem job ativo, ele permanece em repouso/),
      ).toBeInTheDocument();
    });

    it('2. Modo Mapa: exibe legendinha, rótulo de foco e container do mapa', () => {
      const mapa = new MapaFalso();
      const camera = new Camera({ mapaInjetado: mapa });

      // Simula evento de foco que leva ao modo mapa
      usePalco.getState().aplicarEvento({
        seq: 1,
        ts: '2026-11-03T12:00:00Z',
        origem: 'nucleo',
        evento: 'viewport.foco',
        dados: {
          nivel: 'municipio',
          rotulo: 'Querência/MT',
          bbox_4326: [-52.5, -13.2, -52.1, -12.8],
          origem: 'ibge',
        },
      });

      render(<Palco cameraInjetada={camera} suporteWebGL={true} />);

      expect(screen.getByLabelText('Informações da Câmera')).toBeInTheDocument();
      expect(screen.getByText('Querência/MT')).toBeInTheDocument();
    });

    it('3. Modo Folha: exibe área de montagem da folha com SVG em mm reais (W8-04)', () => {
      // Evento de folha leva ao modo folha
      usePalco.getState().aplicarEvento({
        seq: 1,
        ts: '2026-11-03T12:00:00Z',
        origem: 'nucleo',
        evento: 'viewport.foco',
        dados: {
          nivel: 'folha',
          rotulo: 'Folha A3',
          bbox_4326: [-52.5, -13.2, -52.1, -12.8],
          origem: 'perfil_pagina',
        },
      });

      render(<Palco suporteWebGL={false} />);

      expect(screen.getByLabelText('Montagem da Folha')).toBeInTheDocument();
      expect(screen.getByTestId('palco-folha')).toBeInTheDocument();
      expect(screen.getByTestId('papel-folha')).toBeInTheDocument();
    });

    it('3.1 Modo Folha: elemento entra após consumo do passo na fila', async () => {
      usePalco.getState().definirReduzirMovimento(true);

      usePalco.getState().aplicarEvento({
        seq: 1,
        ts: '2026-11-03T12:00:00Z',
        origem: 'nucleo',
        evento: 'viewport.foco',
        dados: {
          nivel: 'folha',
          rotulo: 'Folha A3',
          bbox_4326: [-52.5, -13.2, -52.1, -12.8],
          origem: 'perfil_pagina',
        },
      });

      usePalco.getState().aplicarEvento({
        seq: 2,
        ts: '2026-11-03T12:00:01Z',
        origem: 'nucleo',
        evento: 'layout.elemento',
        dados: {
          elemento: 'titulo_caixa',
          sequencia: 1,
          total: 1,
          folha: { formato: 'A3', orientacao: 'retrato', largura_mm: 297, altura_mm: 420 },
          caixa_mm: { x0: 20, y0: 10, x1: 200, y1: 30 },
          conteudo: 'MAPA INTEGRAÇÃO',
        },
      });

      render(<Palco suporteWebGL={false} />);

      await vi.waitFor(() => {
        expect(screen.getByText('MAPA INTEGRAÇÃO')).toBeInTheDocument();
      });
    });

    it('4. Modo Resultado: exibe selo conforme e resultado da versão', () => {
      // Evento de versão criada leva ao modo resultado
      usePalco.getState().aplicarEvento({
        seq: 1,
        ts: '2026-11-03T12:00:00Z',
        origem: 'servidor',
        evento: 'versao.criada',
        dados: {
          versao: {
            numero: 1,
            conforme: true,
          },
        },
      });

      render(<Palco versao={VERSAO_TESTE} suporteWebGL={false} />);

      expect(screen.getByLabelText('Resultado da Versão')).toBeInTheDocument();
      expect(screen.getByText('✓ Conforme com as normas')).toBeInTheDocument();
    });

    it('5. Projeto reaberto com versão pronta mostra o mapa, não a folha vazia (teste_22)', () => {
      useProjetoAtivo.setState({
        projeto: {
          id: 'p 22',
          nome: 'teste_22',
          estado: 'pronto',
          folha: { formato: 'A4', orientacao: 'retrato' },
          imovel: { nome: null },
          versao_atual: 1,
          miniatura: null,
          atualizado_em: '2026-11-04T13:00:00Z',
        },
      });
      // O replay de um job terminado traz só os elementos da folha (sem `versao.criada`).
      usePalco.getState().aplicarEvento({
        seq: 1,
        ts: '2026-11-04T13:00:00Z',
        origem: 'nucleo',
        evento: 'layout.elemento',
        dados: { elemento: 'titulo_caixa', caixa_mm: { x0: 0, y0: 0, x1: 10, y1: 10 } },
      });
      const versao: Versao = {
        ...VERSAO_TESTE,
        miniatura: 'Mapas/v001/miniatura.jpg',
        artefatos: { pdf: 'Mapas/v001/Dinamica.pdf' },
      };

      render(<Palco versao={versao} suporteWebGL={false} />);

      expect(screen.getByLabelText('Resultado da Versão')).toBeInTheDocument();
      const imagem = screen.getByAltText('Miniatura da versão 1') as HTMLImageElement;
      expect(imagem.getAttribute('src')).toBe('/api/v1/projetos/p%2022/arquivos/Mapas/v001/miniatura.jpg');
      expect(screen.getByTitle('Abrir o PDF desta versão').getAttribute('href')).toBe(
        '/api/v1/projetos/p%2022/arquivos/Mapas/v001/Dinamica.pdf',
      );
    });
  });

  describe('urlDoArquivo', () => {
    it('caminho do projeto vira rota da API; URL pronta passa como veio', () => {
      expect(urlDoArquivo('p1', 'Mapas/v002/miniatura.jpg')).toBe(
        '/api/v1/projetos/p1/arquivos/Mapas/v002/miniatura.jpg',
      );
      expect(urlDoArquivo('p1', 'data:image/png;base64,AAAA')).toBe('data:image/png;base64,AAAA');
      expect(urlDoArquivo('p1', '/api/v1/x.png')).toBe('/api/v1/x.png');
      expect(urlDoArquivo(undefined, 'Mapas/v001/a.png')).toBeNull();
      expect(urlDoArquivo('p1', null)).toBeNull();
    });
  });

  describe('Fallback sem WebGL (W8-07 / WB-001)', () => {
    it('detecta ausência de WebGL, exibe WB-001 e cai no modo folha com camadas listadas', () => {
      // Dispara foco de mapa e camada renderizada
      usePalco.getState().aplicarEvento({
        seq: 1,
        ts: '2026-11-03T12:00:00Z',
        origem: 'nucleo',
        evento: 'viewport.foco',
        dados: {
          nivel: 'imovel',
          rotulo: 'Fazenda Bela Vista',
          bbox_4326: [-52.5, -13.2, -52.1, -12.8],
          origem: 'geometria_local',
        },
      });

      usePalco.getState().aplicarEvento({
        seq: 2,
        ts: '2026-11-03T12:00:01Z',
        origem: 'nucleo',
        evento: 'camada.renderizada',
        dados: {
          camada_id: 'avn',
          papel: 'avn',
          nome: 'Vegetação Nativa',
          geometria: 'poligono',
          sequencia: 1,
          total: 1,
          ordem_desenho: 2000,
          estilo: { preenchimento: '#2e7d32', contorno: '#1b5e20', espessura_pt: 1, padrao: 'solido' },
        },
      });

      render(<Palco suporteWebGL={false} />);

      // Banner com código canônico WB-001
      expect(screen.getByText('WB-001')).toBeInTheDocument();
      expect(
        screen.getByText('Aceleração gráfica WebGL indisponível (WB-001): modo folha ativado.'),
      ).toBeInTheDocument();

      // Cai em modo folha (não mapa)
      expect(screen.getByLabelText('Montagem da Folha')).toBeInTheDocument();

      // Camadas acendem na legendinha como chips de texto
      expect(screen.getByText('Vegetação Nativa')).toBeInTheDocument();
    });
  });

  describe('Redução de movimento (W8-08)', () => {
    it('com reduzirMovimento ativo, passa duracao_ms zero para a câmera', async () => {
      const mapa = new MapaFalso();
      const camera = new Camera({ mapaInjetado: mapa });
      const spyFocar = vi.spyOn(camera, 'focarBbox');

      usePalco.getState().definirReduzirMovimento(true);

      usePalco.getState().aplicarEvento({
        seq: 1,
        ts: '2026-11-03T12:00:00Z',
        origem: 'nucleo',
        evento: 'viewport.foco',
        dados: {
          nivel: 'imovel',
          rotulo: 'Fazenda Imóvel',
          bbox_4326: [-52.5, -13.2, -52.1, -12.8],
          origem: 'geometria_local',
        },
      });

      render(<Palco cameraInjetada={camera} suporteWebGL={true} />);

      await vi.waitFor(() => {
        expect(spyFocar).toHaveBeenCalledWith(
          [-52.5, -13.2, -52.1, -12.8],
          expect.objectContaining({
            duracao_ms: 0,
            reduzirMovimento: true,
          }),
        );
      });
    });
  });

  describe('Aplicação de camada por camada_id no mapa falso (W8-03)', () => {
    it('adiciona source e layer correspondente no mapa ao processar passo de camada', async () => {
      const mapa = new MapaFalso();
      const camera = new Camera({ mapaInjetado: mapa });

      usePalco.getState().definirReduzirMovimento(true);

      usePalco.getState().aplicarEvento({
        seq: 1,
        ts: '2026-11-03T12:00:00Z',
        origem: 'nucleo',
        evento: 'camada.renderizada',
        dados: {
          camada_id: 'avn',
          papel: 'avn',
          nome: 'Vegetação Nativa',
          geometria: 'poligono',
          sequencia: 1,
          total: 1,
          ordem_desenho: 2000,
          estilo: { preenchimento: '#2e7d32', contorno: '#1b5e20', espessura_pt: 1.5, padrao: 'solido' },
        },
      });

      render(<Palco cameraInjetada={camera} suporteWebGL={true} />);

      await vi.waitFor(() => {
        expect(mapa.sources['mf-src-avn']).toBeDefined();
        expect(mapa.layers.some((l) => l.layer.id === 'mf-lyr-avn-fill')).toBe(true);
        expect(mapa.layers.some((l) => l.layer.id === 'mf-lyr-avn-linha')).toBe(true);
      });
    });
  });

  describe('Sem eventos, o palco não anima (W8-01 / W8-09)', () => {
    it('não agenda ticks nem executa passos quando a fila está vazia', () => {
      const spyRaf = vi.spyOn(window, 'requestAnimationFrame');

      render(<Palco suporteWebGL={false} />);

      // Como não há eventos na fila nem passo corrente, requestAnimationFrame NÃO é chamado pelo palco
      expect(spyRaf).not.toHaveBeenCalled();
      expect(usePalco.getState().passoCorrente).toBeNull();
      expect(usePalco.getState().fila).toHaveLength(0);
    });
  });
});
