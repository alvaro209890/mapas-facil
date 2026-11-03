/**
 * Store do palco (W6-03 / W-07).
 *
 * Guarda o estado que a coreografia do mapa consome — foco do viewport, camadas
 * renderizadas e elementos de layout — e uma fila de eventos de motion. A fila só recebe
 * evento real do núcleo: nada é enfileirado por timer, porque animação sem evento é
 * mentira (é a mesma regra que a Fase 1 pagou caro para aprender).
 *
 * O desenho do palco em si entra no W8; aqui só o estado.
 */

import { create } from 'zustand';

import type { Evento } from '../api/tipos';

export interface Foco {
  x: number;
  y: number;
  escala: number;
  motivo: string;
}

export interface CamadaRenderizada {
  nome: string;
  estado: 'renderizando' | 'ok' | 'falhou';
}

export interface ElementoLayout {
  nome: string;
  visivel: boolean;
}

export interface ItemFila {
  seq: number;
  tipo: 'viewport.foco' | 'camada.renderizada' | 'layout.elemento';
  dados: Record<string, unknown>;
}

interface LojaPalco {
  foco: Foco | null;
  camadas: Record<string, CamadaRenderizada>;
  elementos: Record<string, ElementoLayout>;
  fila: ItemFila[];
  /** `false` quando o usuário desliga a animação (acessibilidade / `prefers-reduced-motion`). */
  animar: boolean;
  aplicarEvento: (evento: Evento) => boolean;
  consumir: () => ItemFila | null;
  definirAnimar: (animar: boolean) => void;
  limpar: () => void;
}

const LIMITE_FILA = 50;

export const usePalco = create<LojaPalco>((set, get) => ({
  foco: null,
  camadas: {},
  elementos: {},
  fila: [],
  animar: true,

  /** Devolve `true` se o evento era do palco (o despachante usa isso para decidir). */
  aplicarEvento: (evento) => {
    switch (evento.evento) {
      case 'viewport.foco': {
        const d = evento.dados as { x?: unknown; y?: unknown; escala?: unknown; motivo?: unknown };
        const foco: Foco = {
          x: Number(d.x ?? 0),
          y: Number(d.y ?? 0),
          escala: Number(d.escala ?? 1),
          motivo: String(d.motivo ?? ''),
        };
        set((atual) => ({ foco, fila: enfileirar(atual.fila, evento, 'viewport.foco') }));
        return true;
      }
      case 'camada.renderizada': {
        const d = evento.dados as { nome?: unknown; estado?: unknown };
        const nome = String(d.nome ?? '');
        if (!nome) return true;
        const estado = d.estado === 'falhou' || d.estado === 'renderizando' ? d.estado : 'ok';
        set((atual) => ({
          camadas: { ...atual.camadas, [nome]: { nome, estado } },
          fila: enfileirar(atual.fila, evento, 'camada.renderizada'),
        }));
        return true;
      }
      case 'layout.elemento': {
        const d = evento.dados as { nome?: unknown; visivel?: unknown };
        const nome = String(d.nome ?? '');
        if (!nome) return true;
        set((atual) => ({
          elementos: {
            ...atual.elementos,
            [nome]: { nome, visivel: d.visivel !== false },
          },
          fila: enfileirar(atual.fila, evento, 'layout.elemento'),
        }));
        return true;
      }
      default:
        return false;
    }
  },

  consumir: () => {
    const [primeiro, ...resto] = get().fila;
    if (!primeiro) return null;
    set({ fila: resto });
    return primeiro;
  },

  definirAnimar: (animar) => set({ animar, fila: animar ? get().fila : [] }),

  limpar: () => set({ foco: null, camadas: {}, elementos: {}, fila: [] }),
}));

function enfileirar(
  fila: ItemFila[],
  evento: Evento,
  tipo: ItemFila['tipo'],
): ItemFila[] {
  if (!usePalco.getState().animar) return fila;
  return [...fila, { seq: evento.seq, tipo, dados: evento.dados }].slice(-LIMITE_FILA);
}
