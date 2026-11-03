/**
 * Wrapper de câmera sobre MapLibre GL (W8-02 / W-07 §Coreografia).
 *
 * Encapsula movimentação da câmera (`flyTo`, `fitBounds`, `jumpTo`), captura de
 * snapshots da tela para transição para o modo folha e ciclo de vida do mapa.
 *
 * Totalmente desacoplado de estado global e com suporte a injeção de `MapaLike`
 * para execução em testes sob jsdom (onde WebGL não existe).
 */

import {
  Map as MapLibreMap,
  type CameraOptions,
  type FitBoundsOptions,
  type FlyToOptions,
  type JumpToOptions,
  type LngLatBoundsLike,
} from 'maplibre-gl';
import type { Bbox4326, NivelViewport } from './coreografia';
import { EASINGS, TOKENS_MOTION } from './tokens';

export type { CameraOptions, FitBoundsOptions, FlyToOptions, JumpToOptions, LngLatBoundsLike };

export type OpcoesFlyTo = FlyToOptions;
export type OpcoesFitBounds = FitBoundsOptions;
export type OpcoesJumpTo = JumpToOptions;

/** Interface mínima de um mapa compatível com MapLibre para testes e injeção. */
export interface MapaLike {
  flyTo(opcoes: FlyToOptions): unknown;
  fitBounds(bounds: LngLatBoundsLike, opcoes?: FitBoundsOptions): unknown;
  jumpTo(opcoes: JumpToOptions): unknown;
  getCanvas(): HTMLCanvasElement;
  remove(): void;
  addSource?(id: string, source: unknown): unknown;
  getSource?(id: string): unknown;
  removeSource?(id: string): unknown;
  addLayer?(layer: unknown, beforeId?: string): unknown;
  getLayer?(id: string): unknown;
  removeLayer?(id: string): unknown;
  setPaintProperty?(layerId: string, name: string, value: unknown): unknown;
  addImage?(id: string, image: unknown): unknown;
  hasImage?(id: string): boolean;
}

export interface OpcoesFocoCamera {
  nivel?: NivelViewport | undefined;
  duracao_ms?: number | undefined;
  reduzirMovimento?: boolean | undefined;
  paddingPixels?: number | undefined;
}

export interface OpcoesCamera {
  container?: HTMLElement | undefined;
  mapaInjetado?: MapaLike | undefined;
}

/**
 * Cria uma instância padrão do MapLibre GL com estilo escuro mínimo.
 */
function instanciarMapLibrePadrao(container: HTMLElement): MapaLike {
  return new MapLibreMap({
    container,
    style: {
      version: 8,
      sources: {},
      layers: [
        {
          id: 'fundo-palco',
          type: 'background',
          paint: {
            'background-color': '#0b0e11', // token --mf-bg
          },
        },
      ],
    },
    center: [-55.0, -13.0], // Centro aproximado de Mato Grosso
    zoom: 5,
    attributionControl: false,
  });
}

export class Camera {
  private readonly mapa: MapaLike;
  private destruida = false;

  constructor(opcoes: OpcoesCamera) {
    if (opcoes.mapaInjetado) {
      this.mapa = opcoes.mapaInjetado;
    } else if (opcoes.container) {
      this.mapa = instanciarMapLibrePadrao(opcoes.container);
    } else {
      throw new Error('Camera requer "container" ou "mapaInjetado".');
    }
  }

  obterMapa(): MapaLike {
    return this.mapa;
  }

  estaDestruida(): boolean {
    return this.destruida;
  }

  /**
   * Converte bbox [oeste, sul, leste, norte] para formato de bounds do MapLibre.
   */
  private static converterBounds(bbox: Bbox4326): [[number, number], [number, number]] {
    return [
      [bbox[0], bbox[1]],
      [bbox[2], bbox[3]],
    ];
  }

  /**
   * Ajusta a câmera ao bbox especificado segundo o nível de detalhe e regras de motion.
   */
  focarBbox(bbox: Bbox4326, opcoes: OpcoesFocoCamera = {}): void {
    if (this.destruida) return;

    const nivel = opcoes.nivel;
    const reduzir = opcoes.reduzirMovimento === true;
    const bounds = Camera.converterBounds(bbox);

    // Padding padrão proporcional ao nível (W-07 §Coreografia)
    let padding = opcoes.paddingPixels ?? 40;
    let duracao = opcoes.duracao_ms;

    if (duracao === undefined) {
      switch (nivel) {
        case 'estado':
          duracao = TOKENS_MOTION.voo_estado_ms;
          padding = opcoes.paddingPixels ?? 32;
          break;
        case 'municipio':
          duracao = TOKENS_MOTION.voo_municipio_ms;
          padding = opcoes.paddingPixels ?? 48;
          break;
        case 'imovel':
          duracao = TOKENS_MOTION.voo_imovel_ms;
          padding = opcoes.paddingPixels ?? 80;
          break;
        case 'enquadramento':
          duracao = TOKENS_MOTION.voo_enquadramento_ms;
          padding = opcoes.paddingPixels ?? 20;
          break;
        case 'folha':
          duracao = TOKENS_MOTION.voo_folha_ms;
          padding = opcoes.paddingPixels ?? 10;
          break;
        default:
          duracao = TOKENS_MOTION.voo_enquadramento_ms;
      }
    }

    if (reduzir || duracao === 0) {
      // Movimento reduzido: salto instantâneo sem animação
      this.mapa.fitBounds(bounds, {
        padding,
        duration: 0,
        linear: true,
      });
      return;
    }

    // Voo cinematográfico para o imóvel usa curva acentuada
    const ehImovel = nivel === 'imovel';
    const fitOpcoes: OpcoesFitBounds = {
      padding,
      duration: duracao,
      essential: true,
    };
    if (ehImovel) {
      fitOpcoes.curve = EASINGS.vooCurva;
    }
    this.mapa.fitBounds(bounds, fitOpcoes);
  }

  flyTo(opcoes: OpcoesFlyTo): void {
    if (this.destruida) return;
    this.mapa.flyTo(opcoes);
  }

  fitBounds(bbox: Bbox4326, opcoes?: OpcoesFitBounds): void {
    if (this.destruida) return;
    this.mapa.fitBounds(Camera.converterBounds(bbox), opcoes);
  }

  jumpTo(opcoes: OpcoesJumpTo): void {
    if (this.destruida) return;
    this.mapa.jumpTo(opcoes);
  }

  /**
   * Captura a imagem atual do canvas do mapa para transição mapa → folha.
   * Retorna `null` se o canvas não suportar captura ou se falhar.
   */
  tirarSnapshot(): string | null {
    if (this.destruida) return null;
    try {
      const canvas = this.mapa.getCanvas();
      if (!canvas || typeof canvas.toDataURL !== 'function') return null;
      return canvas.toDataURL('image/png');
    } catch {
      return null;
    }
  }

  destruir(): void {
    if (this.destruida) return;
    this.destruida = true;
    try {
      this.mapa.remove();
    } catch {
      // Ignora erro no teardown
    }
  }
}
