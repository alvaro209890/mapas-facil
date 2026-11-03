/**
 * Gerenciador de camadas vetoriais e raster no MapLibre (W8-03 / W-07 §Camadas).
 *
 * Responsabilidades:
 * - Adicionar e remover fontes (sources) e camadas (layers) por `camada_id`;
 * - Traduzir o `estilo` do evento canônico (`preenchimento`, `contorno`, `espessura_pt`, `padrao`)
 *   para as propriedades de pintura (paint) do MapLibre GL;
 * - Respeitar a ordem de pintura = ordem dos passos recebidos;
 * - Suporte a raster recortado (basemap) por imagem georreferenciada em `bbox_4326`;
 * - Não usa estado global e aceita `MapaLike` injetado para testes no jsdom.
 */

import type { Bbox4326 } from './coreografia';
import type { MapaLike } from './Camera';

export type TipoGeometria = 'poligono' | 'linha' | 'ponto' | 'raster';
export type PadraoPreenchimento = 'solido' | 'hachura' | 'vazado';

export interface EstiloCamada {
  preenchimento: string | null;
  contorno: string;
  espessura_pt: number;
  padrao: PadraoPreenchimento;
}

export interface DadosCamada {
  camada_id: string;
  papel: string;
  nome: string;
  geometria: TipoGeometria;
  sequencia: number;
  total: number;
  ordem_desenho: number;
  caminho?: string | null | undefined;
  bbox_4326?: Bbox4326 | null | undefined;
  estilo: EstiloCamada;
  n_feicoes?: number | undefined;
  area_ha?: number | null | undefined;
  etapa?: string | null | undefined;
}

interface RegistroCamada {
  camadaId: string;
  sourceId: string;
  layerIds: string[];
  geometria: TipoGeometria;
  ordemDesenho: number;
}

// Conversão tipográfica padrão: 1 pt = 96/72 px = 1.333 px
const FATOR_PT_PARA_PX = 96 / 72;

/**
 * Converte bbox_4326 [oeste, sul, leste, norte] para coordenadas de imagem do MapLibre:
 * [top-left, top-right, bottom-right, bottom-left].
 */
function converterCoordenadasRaster(
  bbox: Bbox4326,
): [[number, number], [number, number], [number, number], [number, number]] {
  const [oeste, sul, leste, norte] = bbox;
  return [
    [oeste, norte], // topo-esquerda
    [leste, norte], // topo-direita
    [leste, sul], // base-direita
    [oeste, sul], // base-esquerda
  ];
}

/**
 * Cria um canvas com padrão de hachura a 45° na cor especificada.
 * Retorna ImageData se o ambiente suportar canvas 2D, ou null se não disponível.
 */
function criarImagemHachura(corLinha: string): ImageData | null {
  if (typeof document === 'undefined') return null;
  try {
    const tamanho = 16;
    const canvas = document.createElement('canvas');
    canvas.width = tamanho;
    canvas.height = tamanho;
    const ctx = canvas.getContext('2d');
    if (!ctx) return null;

    ctx.clearRect(0, 0, tamanho, tamanho);
    ctx.strokeStyle = corLinha;
    ctx.lineWidth = 2;

    // Linhas diagonais a 45 graus com repetição contínua
    ctx.beginPath();
    ctx.moveTo(0, tamanho);
    ctx.lineTo(tamanho, 0);

    ctx.moveTo(-tamanho / 2, tamanho / 2);
    ctx.lineTo(tamanho / 2, -tamanho / 2);

    ctx.moveTo(tamanho / 2, (3 * tamanho) / 2);
    ctx.lineTo((3 * tamanho) / 2, tamanho / 2);
    ctx.stroke();

    return ctx.getImageData(0, 0, tamanho, tamanho);
  } catch {
    return null;
  }
}

export class GerenciadorCamadas {
  private readonly mapa: MapaLike;
  private readonly registros = new Map<string, RegistroCamada>();
  private readonly padroesRegistrados = new Set<string>();

  constructor(mapa: MapaLike) {
    this.mapa = mapa;
  }

  /**
   * Adiciona uma camada ao mapa a partir do contrato canônico de `camada.renderizada`.
   *
   * @param dados Metadados e estilo da camada vindo do núcleo
   * @param geojsonConteudo Dado GeoJSON opcional (objeto ou FeatureCollection)
   */
  adicionarCamada(dados: DadosCamada, geojsonConteudo?: unknown): void {
    const { camada_id, geometria, estilo, bbox_4326, caminho, ordem_desenho } = dados;

    // Se já existia camada com este ID, remove antes para evitar colisão de ID
    if (this.registros.has(camada_id)) {
      this.removerCamada(camada_id);
    }

    const sourceId = `mf-src-${camada_id}`;
    const prefixoLyr = `mf-lyr-${camada_id}`;
    const layerIdsCriados: string[] = [];

    if (geometria === 'raster') {
      if (!bbox_4326) {
        throw new Error(`Camada raster "${camada_id}" requer bbox_4326.`);
      }
      const urlRaster = caminho ?? '';
      const coordinates = converterCoordenadasRaster(bbox_4326);

      if (this.mapa.addSource) {
        this.mapa.addSource(sourceId, {
          type: 'image',
          url: urlRaster,
          coordinates,
        });
      }

      const layerIdRaster = `${prefixoLyr}-raster`;
      layerIdsCriados.push(layerIdRaster);

      // O basemap raster deve ficar abaixo das camadas vetoriais existentes
      const primeiraCamadaVetorial = this.encontrarPrimeiraCamadaVetorial();

      if (this.mapa.addLayer) {
        this.mapa.addLayer(
          {
            id: layerIdRaster,
            type: 'raster',
            source: sourceId,
            paint: {
              'raster-opacity': 1.0,
            },
          },
          primeiraCamadaVetorial,
        );
      }
    } else {
      // Vetor (polígono, linha, ponto)
      const data =
        geojsonConteudo ?? {
          type: 'FeatureCollection',
          features: [],
        };

      if (this.mapa.addSource) {
        this.mapa.addSource(sourceId, {
          type: 'geojson',
          data,
        });
      }

      const espessuraPx = Math.max(1, (estilo.espessura_pt || 1.0) * FATOR_PT_PARA_PX);
      const corContorno = estilo.contorno || '#FFFF00';
      const corPreenchimento = estilo.preenchimento || '#35c79a';

      if (geometria === 'poligono') {
        if (estilo.padrao === 'hachura') {
          const nomePadrao = `hachura-${corContorno.replace('#', '')}`;
          this.garantirPadraoHachura(nomePadrao, corContorno);

          const layerIdFill = `${prefixoLyr}-fill`;
          layerIdsCriados.push(layerIdFill);
          if (this.mapa.addLayer) {
            this.mapa.addLayer({
              id: layerIdFill,
              type: 'fill',
              source: sourceId,
              paint: {
                'fill-pattern': this.padroesRegistrados.has(nomePadrao) ? nomePadrao : undefined,
                'fill-color': corPreenchimento,
                'fill-opacity': 0.4,
              },
            });
          }
        } else if (estilo.padrao === 'solido') {
          const layerIdFill = `${prefixoLyr}-fill`;
          layerIdsCriados.push(layerIdFill);
          if (this.mapa.addLayer) {
            this.mapa.addLayer({
              id: layerIdFill,
              type: 'fill',
              source: sourceId,
              paint: {
                'fill-color': corPreenchimento,
                'fill-opacity': 0.6,
              },
            });
          }
        }

        // Toda camada de polígono (exceto vazada pura sem linha) tem contorno
        const layerIdLinha = `${prefixoLyr}-linha`;
        layerIdsCriados.push(layerIdLinha);
        if (this.mapa.addLayer) {
          this.mapa.addLayer({
            id: layerIdLinha,
            type: 'line',
            source: sourceId,
            paint: {
              'line-color': corContorno,
              'line-width': espessuraPx,
            },
          });
        }
      } else if (geometria === 'linha') {
        const layerIdLinha = `${prefixoLyr}-linha`;
        layerIdsCriados.push(layerIdLinha);
        if (this.mapa.addLayer) {
          this.mapa.addLayer({
            id: layerIdLinha,
            type: 'line',
            source: sourceId,
            paint: {
              'line-color': corContorno,
              'line-width': espessuraPx,
            },
          });
        }
      } else if (geometria === 'ponto') {
        const layerIdPonto = `${prefixoLyr}-ponto`;
        layerIdsCriados.push(layerIdPonto);
        if (this.mapa.addLayer) {
          this.mapa.addLayer({
            id: layerIdPonto,
            type: 'circle',
            source: sourceId,
            paint: {
              'circle-color': corPreenchimento,
              'circle-radius': 5,
              'circle-stroke-color': corContorno,
              'circle-stroke-width': espessuraPx,
            },
          });
        }
      }
    }

    this.registros.set(camada_id, {
      camadaId: camada_id,
      sourceId,
      layerIds: layerIdsCriados,
      geometria,
      ordemDesenho: ordem_desenho,
    });
  }

  /**
   * Encontra o id do primeiro layer de camada vetorial para inserção do raster abaixo.
   */
  private encontrarPrimeiraCamadaVetorial(): string | undefined {
    for (const reg of this.registros.values()) {
      if (reg.geometria !== 'raster' && reg.layerIds.length > 0) {
        return reg.layerIds[0];
      }
    }
    return undefined;
  }

  /**
   * Registra a imagem de hachura no mapa caso disponível.
   */
  private garantirPadraoHachura(nome: string, cor: string): void {
    if (this.padroesRegistrados.has(nome)) return;
    if (!this.mapa.addImage || !this.mapa.hasImage) return;

    if (!this.mapa.hasImage(nome)) {
      const img = criarImagemHachura(cor);
      if (img) {
        this.mapa.addImage(nome, img);
        this.padroesRegistrados.add(nome);
      }
    } else {
      this.padroesRegistrados.add(nome);
    }
  }

  /**
   * Remove uma camada e suas fontes associadas do mapa.
   */
  removerCamada(camadaId: string): void {
    const reg = this.registros.get(camadaId);
    if (!reg) return;

    for (const lyrId of reg.layerIds) {
      try {
        if (this.mapa.removeLayer) {
          this.mapa.removeLayer(lyrId);
        }
      } catch {
        // Silencioso se o layer já foi removido
      }
    }

    try {
      if (this.mapa.removeSource) {
        this.mapa.removeSource(reg.sourceId);
      }
    } catch {
      // Silencioso se a fonte já foi removida
    }

    this.registros.delete(camadaId);
  }

  /**
   * Remove todas as camadas e fontes gerenciadas.
   */
  limpar(): void {
    const ids = Array.from(this.registros.keys());
    for (const id of ids) {
      this.removerCamada(id);
    }
  }

  /**
   * Retorna os identificadores das camadas ativas, na ordem em que foram adicionadas.
   */
  obterCamadas(): string[] {
    return Array.from(this.registros.keys());
  }

  /**
   * Retorna os dados de registro de uma camada específica.
   */
  obterRegistro(camadaId: string): RegistroCamada | undefined {
    return this.registros.get(camadaId);
  }
}
