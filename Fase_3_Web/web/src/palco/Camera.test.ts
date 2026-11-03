/**
 * Testes unitários do wrapper de câmera do MapLibre (W8-02).
 */

import { describe, expect, it, vi } from 'vitest';
import { Camera, type MapaLike, type OpcoesFitBounds, type OpcoesFlyTo, type OpcoesJumpTo } from './Camera';
import type { Bbox4326 } from './coreografia';

class MapaFalso implements MapaLike {
  chamadasFlyTo: OpcoesFlyTo[] = [];
  chamadasFitBounds: Array<{ bounds: unknown; opcoes?: OpcoesFitBounds | undefined }> = [];
  chamadasJumpTo: OpcoesJumpTo[] = [];
  removido = false;
  canvasFalso: HTMLCanvasElement;

  constructor() {
    this.canvasFalso = {
      toDataURL: vi.fn(() => 'data:image/png;base64,falso'),
    } as unknown as HTMLCanvasElement;
  }

  flyTo(opcoes: OpcoesFlyTo): void {
    this.chamadasFlyTo.push(opcoes);
  }

  fitBounds(bounds: unknown, opcoes?: OpcoesFitBounds | undefined): void {
    this.chamadasFitBounds.push({ bounds, opcoes });
  }

  jumpTo(opcoes: OpcoesJumpTo): void {
    this.chamadasJumpTo.push(opcoes);
  }

  getCanvas(): HTMLCanvasElement {
    return this.canvasFalso;
  }

  remove(): void {
    this.removido = true;
  }
}

const BBOX_TESTE: Bbox4326 = [-52.5, -13.2, -52.1, -12.8];

describe('Camera (W8-02)', () => {
  it('instancia com mapa injetado sem necessidade de WebGL real', () => {
    const mapa = new MapaFalso();
    const camera = new Camera({ mapaInjetado: mapa });
    expect(camera.obterMapa()).toBe(mapa);
    expect(camera.estaDestruida()).toBe(false);
  });

  it('lança erro se criada sem container nem mapaInjetado', () => {
    expect(() => new Camera({})).toThrow('requer "container" ou "mapaInjetado"');
  });

  describe('focarBbox', () => {
    it('executa voo cinematográfico para nível "imovel" com curva 1.6', () => {
      const mapa = new MapaFalso();
      const camera = new Camera({ mapaInjetado: mapa });

      camera.focarBbox(BBOX_TESTE, { nivel: 'imovel' });

      expect(mapa.chamadasFitBounds).toHaveLength(1);
      const chamada = mapa.chamadasFitBounds[0]!;
      expect(chamada.bounds).toEqual([
        [-52.5, -13.2],
        [-52.1, -12.8],
      ]);
      expect(chamada.opcoes?.duration).toBe(2200);
      expect(chamada.opcoes?.curve).toBe(1.6);
      expect(chamada.opcoes?.padding).toBe(80);
      expect(chamada.opcoes?.essential).toBe(true);
    });

    it('ajusta câmera para nível "estado" com duração canônica de 1600ms', () => {
      const mapa = new MapaFalso();
      const camera = new Camera({ mapaInjetado: mapa });

      camera.focarBbox(BBOX_TESTE, { nivel: 'estado' });

      expect(mapa.chamadasFitBounds).toHaveLength(1);
      const chamada = mapa.chamadasFitBounds[0]!;
      expect(chamada.opcoes?.duration).toBe(1600);
      expect(chamada.opcoes?.padding).toBe(32);
    });

    it('com movimento reduzido, zera a duração e não usa curva (salto)', () => {
      const mapa = new MapaFalso();
      const camera = new Camera({ mapaInjetado: mapa });

      camera.focarBbox(BBOX_TESTE, { nivel: 'imovel', reduzirMovimento: true });

      expect(mapa.chamadasFitBounds).toHaveLength(1);
      const chamada = mapa.chamadasFitBounds[0]!;
      expect(chamada.opcoes?.duration).toBe(0);
      expect(chamada.opcoes?.linear).toBe(true);
      expect(chamada.opcoes?.curve).toBeUndefined();
    });

    it('respeita duração customizada injetada', () => {
      const mapa = new MapaFalso();
      const camera = new Camera({ mapaInjetado: mapa });

      camera.focarBbox(BBOX_TESTE, { duracao_ms: 500, paddingPixels: 15 });

      expect(mapa.chamadasFitBounds).toHaveLength(1);
      const chamada = mapa.chamadasFitBounds[0]!;
      expect(chamada.opcoes?.duration).toBe(500);
      expect(chamada.opcoes?.padding).toBe(15);
    });
  });

  describe('tirarSnapshot', () => {
    it('captura dataURL do canvas', () => {
      const mapa = new MapaFalso();
      const camera = new Camera({ mapaInjetado: mapa });

      const snap = camera.tirarSnapshot();
      expect(snap).toBe('data:image/png;base64,falso');
    });

    it('retorna null se o canvas falhar', () => {
      const mapa = new MapaFalso();
      mapa.canvasFalso = {
        toDataURL: vi.fn(() => {
          throw new Error('Falha no canvas');
        }),
      } as unknown as HTMLCanvasElement;
      const camera = new Camera({ mapaInjetado: mapa });

      expect(camera.tirarSnapshot()).toBeNull();
    });
  });

  describe('destruir', () => {
    it('remove o mapa e ignora comandos subsequentes', () => {
      const mapa = new MapaFalso();
      const camera = new Camera({ mapaInjetado: mapa });

      camera.destruir();
      expect(mapa.removido).toBe(true);
      expect(camera.estaDestruida()).toBe(true);

      // Não deve chamar nada no mapa após destruído
      camera.focarBbox(BBOX_TESTE);
      expect(mapa.chamadasFitBounds).toHaveLength(0);
      expect(camera.tirarSnapshot()).toBeNull();
    });
  });
});
