/**
 * Testes unitários do gerenciador de camadas do MapLibre (W8-03).
 */

import { describe, expect, it } from 'vitest';
import type { MapaLike } from './Camera';
import { GerenciadorCamadas, type DadosCamada } from './Camadas';

interface CamadaAdicionada {
  layer: { id: string; [key: string]: unknown };
  beforeId?: string | undefined;
}

class MapaCamadasFalso implements MapaLike {
  sources: Record<string, unknown> = {};
  layers: CamadaAdicionada[] = [];
  imagens: Record<string, unknown> = {};

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
    this.layers.push({ layer: layer as { id: string; [key: string]: unknown }, beforeId });
  }

  getLayer(id: string): unknown {
    return this.layers.find((l) => l.layer.id === id)?.layer;
  }

  removeLayer(id: string): void {
    this.layers = this.layers.filter((l) => l.layer.id !== id);
  }

  addImage(id: string, image: unknown): void {
    this.imagens[id] = image;
  }

  hasImage(id: string): boolean {
    return id in this.imagens;
  }

  flyTo(): void {}
  fitBounds(): void {}
  jumpTo(): void {}
  getCanvas(): HTMLCanvasElement {
    return {} as HTMLCanvasElement;
  }
  remove(): void {}
}

const CAMADA_POLIGONO_SOLIDO: DadosCamada = {
  camada_id: 'avn',
  papel: 'avn',
  nome: 'Área de Vegetação Nativa',
  geometria: 'poligono',
  sequencia: 2,
  total: 5,
  ordem_desenho: 2000,
  estilo: {
    preenchimento: '#2e7d32',
    contorno: '#1b5e20',
    espessura_pt: 1.5,
    padrao: 'solido',
  },
  n_feicoes: 12,
};

const CAMADA_POLIGONO_VAZADO: DadosCamada = {
  camada_id: 'perimetro',
  papel: 'perimetro',
  nome: 'Perímetro do Imóvel',
  geometria: 'poligono',
  sequencia: 1,
  total: 5,
  ordem_desenho: 1000,
  estilo: {
    preenchimento: null,
    contorno: '#ffff00',
    espessura_pt: 2.0,
    padrao: 'vazado',
  },
  n_feicoes: 1,
};

const CAMADA_LINHA: DadosCamada = {
  camada_id: 'hidro_linha',
  papel: 'hidro_linha',
  nome: 'Rios e Córregos',
  geometria: 'linha',
  sequencia: 3,
  total: 5,
  ordem_desenho: 3000,
  estilo: {
    preenchimento: null,
    contorno: '#0288d1',
    espessura_pt: 1.2,
    padrao: 'solido',
  },
  n_feicoes: 8,
};

const CAMADA_PONTO: DadosCamada = {
  camada_id: 'nascente',
  papel: 'nascente',
  nome: 'Nascentes',
  geometria: 'ponto',
  sequencia: 4,
  total: 5,
  ordem_desenho: 4000,
  estilo: {
    preenchimento: '#00bcd4',
    contorno: '#006064',
    espessura_pt: 1.0,
    padrao: 'solido',
  },
  n_feicoes: 3,
};

const CAMADA_RASTER: DadosCamada = {
  camada_id: 'basemap',
  papel: 'basemap',
  nome: 'Imagem de Satélite Planet',
  geometria: 'raster',
  sequencia: 5,
  total: 5,
  ordem_desenho: 5000,
  caminho: '/api/v1/preview/j1/basemap.png',
  bbox_4326: [-52.5, -13.2, -52.1, -12.8],
  estilo: {
    preenchimento: null,
    contorno: '#ffffff',
    espessura_pt: 1.0,
    padrao: 'solido',
  },
  n_feicoes: 1,
};

describe('GerenciadorCamadas (W8-03)', () => {
  it('adiciona camada de polígono sólido com fill e contorno line', () => {
    const mapa = new MapaCamadasFalso();
    const gerenciador = new GerenciadorCamadas(mapa);

    gerenciador.adicionarCamada(CAMADA_POLIGONO_SOLIDO);

    // Source GeoJSON
    expect(mapa.sources['mf-src-avn']).toBeDefined();

    // 2 Layers: fill + linha
    const layerFill = mapa.layers.find((l) => l.layer.id === 'mf-lyr-avn-fill')?.layer;
    expect(layerFill).toBeDefined();
    expect(layerFill?.type).toBe('fill');
    expect((layerFill?.paint as Record<string, unknown>)?.['fill-color']).toBe('#2e7d32');

    const layerLinha = mapa.layers.find((l) => l.layer.id === 'mf-lyr-avn-linha')?.layer;
    expect(layerLinha).toBeDefined();
    expect(layerLinha?.type).toBe('line');
    expect((layerLinha?.paint as Record<string, unknown>)?.['line-color']).toBe('#1b5e20');
  });

  it('adiciona camada de polígono vazado apenas com contorno line', () => {
    const mapa = new MapaCamadasFalso();
    const gerenciador = new GerenciadorCamadas(mapa);

    gerenciador.adicionarCamada(CAMADA_POLIGONO_VAZADO);

    const layerFill = mapa.layers.find((l) => l.layer.id === 'mf-lyr-perimetro-fill');
    expect(layerFill).toBeUndefined();

    const layerLinha = mapa.layers.find((l) => l.layer.id === 'mf-lyr-perimetro-linha')?.layer;
    expect(layerLinha).toBeDefined();
    expect((layerLinha?.paint as Record<string, unknown>)?.['line-color']).toBe('#ffff00');
  });

  it('adiciona camada de linha com pintura de linha', () => {
    const mapa = new MapaCamadasFalso();
    const gerenciador = new GerenciadorCamadas(mapa);

    gerenciador.adicionarCamada(CAMADA_LINHA);

    const layer = mapa.layers.find((l) => l.layer.id === 'mf-lyr-hidro_linha-linha')?.layer;
    expect(layer?.type).toBe('line');
    expect((layer?.paint as Record<string, unknown>)?.['line-color']).toBe('#0288d1');
  });

  it('adiciona camada de ponto com tipo circle', () => {
    const mapa = new MapaCamadasFalso();
    const gerenciador = new GerenciadorCamadas(mapa);

    gerenciador.adicionarCamada(CAMADA_PONTO);

    const layer = mapa.layers.find((l) => l.layer.id === 'mf-lyr-nascente-ponto')?.layer;
    expect(layer?.type).toBe('circle');
    expect((layer?.paint as Record<string, unknown>)?.['circle-color']).toBe('#00bcd4');
  });

  it('adiciona camada raster com coordenadas convertidas e insere abaixo de camadas vetoriais', () => {
    const mapa = new MapaCamadasFalso();
    const gerenciador = new GerenciadorCamadas(mapa);

    // Primeiro adiciona uma camada vetorial
    gerenciador.adicionarCamada(CAMADA_POLIGONO_VAZADO);

    // Depois adiciona o raster
    gerenciador.adicionarCamada(CAMADA_RASTER);

    const sourceRaster = mapa.sources['mf-src-basemap'] as Record<string, unknown>;
    expect(sourceRaster.type).toBe('image');
    expect(sourceRaster.url).toBe('/api/v1/preview/j1/basemap.png');
    // Coordenadas: top-left, top-right, bottom-right, bottom-left
    expect(sourceRaster.coordinates).toEqual([
      [-52.5, -12.8],
      [-52.1, -12.8],
      [-52.1, -13.2],
      [-52.5, -13.2],
    ]);

    // O raster deve ser inserido antes do primeiro layer vetorial
    const rasterAdicionado = mapa.layers.find((l) => l.layer.id === 'mf-lyr-basemap-raster');
    expect(rasterAdicionado).toBeDefined();
    expect(rasterAdicionado?.beforeId).toBe('mf-lyr-perimetro-linha');
  });

  it('mantém a ordem de pintura igual à ordem de inserção dos passos', () => {
    const mapa = new MapaCamadasFalso();
    const gerenciador = new GerenciadorCamadas(mapa);

    gerenciador.adicionarCamada(CAMADA_POLIGONO_VAZADO);
    gerenciador.adicionarCamada(CAMADA_POLIGONO_SOLIDO);
    gerenciador.adicionarCamada(CAMADA_LINHA);

    expect(gerenciador.obterCamadas()).toEqual(['perimetro', 'avn', 'hidro_linha']);
  });

  it('removerCamada limpa sources e layers daquela camada específica', () => {
    const mapa = new MapaCamadasFalso();
    const gerenciador = new GerenciadorCamadas(mapa);

    gerenciador.adicionarCamada(CAMADA_POLIGONO_SOLIDO);
    gerenciador.adicionarCamada(CAMADA_LINHA);

    gerenciador.removerCamada('avn');

    expect(mapa.sources['mf-src-avn']).toBeUndefined();
    expect(mapa.layers.some((l) => l.layer.id.includes('avn'))).toBe(false);

    // Linha permanece intacta
    expect(mapa.sources['mf-src-hidro_linha']).toBeDefined();
    expect(gerenciador.obterCamadas()).toEqual(['hidro_linha']);
  });

  it('limpar() remove todas as fontes e camadas gerenciadas', () => {
    const mapa = new MapaCamadasFalso();
    const gerenciador = new GerenciadorCamadas(mapa);

    gerenciador.adicionarCamada(CAMADA_POLIGONO_VAZADO);
    gerenciador.adicionarCamada(CAMADA_POLIGONO_SOLIDO);

    gerenciador.limpar();

    expect(Object.keys(mapa.sources)).toHaveLength(0);
    expect(mapa.layers).toHaveLength(0);
    expect(gerenciador.obterCamadas()).toHaveLength(0);
  });
});
