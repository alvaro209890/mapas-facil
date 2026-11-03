/**
 * Store do palco (W6-03 / W8-06 / W-07).
 *
 * Ela é a **casca fina** em volta de `palco/coreografia.ts`: guarda os eventos que o núcleo já
 * emitiu, deriva o estado do palco (foco, camadas, elementos, versão, modo) com as funções puras
 * e mantém a fila de animação. Não existe lógica de motion aqui — só o que precisa de `zustand`
 * (estado compartilhado) e de relógio (o instante de chegada de cada evento).
 *
 * Três regras que valem a leitura:
 *
 * 1. **Nada anda por timer.** A fila só tem evento real do núcleo; passo de animação sem evento é
 *    mentira (é a regra que a Fase 1 pagou caro para aprender). Quem executa os passos é o
 *    `Palco.tsx` (W8-01), com o relógio dele.
 * 2. **Nenhum evento é jogado fora do estado.** A compressão da coreografia só encurta tempo: se
 *    a fila estourar o limite, o palco perde animação, nunca o estado final (W-07 §Fila).
 * 3. **Um palco segue um job.** `definirProjeto()` e `definirJob()` são as duas portas de troca:
 *    trocar de projeto zera tudo; trocar de job dentro do projeto também. Enquanto um job está
 *    ativo, evento com outro `job_id` é **ignorado** — senão o palco de um mapa mostraria camada
 *    do mapa de outro.
 */

import { create } from 'zustand';

import type { Evento } from '../api/tipos';
import {
  coreografar,
  duracaoTotal,
  estadoFinal,
  type EventoCoreografia,
  type ModoPalco,
  type Passo,
} from '../palco/coreografia';

export type {
  Bbox4326,
  CamadaFinal as CamadaRenderizada,
  ElementoFinal as ElementoLayout,
  FocoFinal as Foco,
  NivelViewport,
  Passo,
  VersaoFinal,
} from '../palco/coreografia';

/** Os três eventos que o palco **possui** (dos outros ele só observa). */
export type TipoEventoPalco = 'viewport.foco' | 'camada.renderizada' | 'layout.elemento';

/** Item da fila de animação — um evento de palco esperando virar passo. */
export interface ItemFila {
  seq: number;
  tipo: TipoEventoPalco;
  dados: Record<string, unknown>;
  /** Relógio monotônico de chegada (ms desde o começo do job) — alimenta a compressão. */
  chegou_ms: number;
}

export interface ContextoEvento {
  /** Projeto dono do evento; se não casar com o da store, o evento é ignorado. */
  projetoId?: string | undefined;
}

/** Campos derivados — tudo o que o palco mostra sai daqui, nunca de um `set` solto. */
type Derivado = {
  foco: ReturnType<typeof estadoFinal>['foco'];
  camadas: ReturnType<typeof estadoFinal>['camadas'];
  elementos: ReturnType<typeof estadoFinal>['elementos'];
  modo: ModoPalco;
  versao: ReturnType<typeof estadoFinal>['versao'];
  resultado: boolean;
  erro: string | null;
  ultimoSeq: number;
};

export interface LojaPalco extends Derivado {
  // --- identidade: de quem é este palco
  projetoId: string | null;
  jobId: string | null;
  // --- fila de animação
  fila: ItemFila[];
  passoCorrente: Passo | null;
  eventos: EventoCoreografia[];
  /** Quantos eventos foram recusados pela guarda de projeto/job (observabilidade honesta). */
  descartados: number;
  /** `false` quando o usuário desliga a animação (acessibilidade / `prefers-reduced-motion`). */
  animar: boolean;
  reduzirMovimento: boolean;
  /** Início do relógio do job — base do `chegou_ms`. */
  inicio_ms: number | null;
  // --- ações
  aplicarEvento: (evento: Evento, contexto?: ContextoEvento) => boolean;
  definirProjeto: (projetoId: string | null) => void;
  definirJob: (jobId: string | null) => void;
  definirAnimar: (animar: boolean) => void;
  definirReduzirMovimento: (reduzir: boolean) => void;
  /** Coreografia da fila atual — o que o executor vai tocar. */
  planejar: () => Passo[];
  /** Tira o próximo passo da fila e o marca como corrente. */
  proximoPasso: () => Passo | null;
  concluirPasso: () => void;
  /** Mantida do W6: retira o primeiro evento da fila sem planejar. */
  consumir: () => ItemFila | null;
  limpar: () => void;
}

const LIMITE_FILA = 50;
const LIMITE_EVENTOS = 2000;

const TIPOS_DE_PALCO: readonly string[] = ['viewport.foco', 'camada.renderizada', 'layout.elemento'];

const VAZIO: Derivado = {
  foco: null,
  camadas: {},
  elementos: {},
  modo: 'ocioso',
  versao: null,
  resultado: false,
  erro: null,
  ultimoSeq: 0,
};

function derivar(eventos: readonly EventoCoreografia[]): Derivado {
  const estado = estadoFinal(eventos);
  return {
    foco: estado.foco,
    camadas: estado.camadas,
    elementos: estado.elementos,
    modo: estado.modo,
    versao: estado.versao,
    resultado: estado.resultado,
    erro: estado.erro,
    ultimoSeq: estado.ultimo_seq,
  };
}

function ehTipoDePalco(nome: string): nome is TipoEventoPalco {
  return TIPOS_DE_PALCO.includes(nome);
}

function texto(valor: unknown): string {
  return typeof valor === 'string' ? valor.trim() : '';
}

function enfileirar(fila: ItemFila[], item: ItemFila, animar: boolean): ItemFila[] {
  if (!animar) return fila;
  return [...fila, item].slice(-LIMITE_FILA);
}

export const usePalco = create<LojaPalco>((set, get) => ({
  projetoId: null,
  jobId: null,
  ...VAZIO,
  fila: [],
  passoCorrente: null,
  eventos: [],
  descartados: 0,
  animar: true,
  reduzirMovimento: false,
  inicio_ms: null,

  /**
   * Devolve `true` quando o evento é **do palco** — o despachante então para, porque ele já foi
   * tratado aqui.
   *
   * `versao.criada` e `nucleo.res` são **observados**: o palco usa os dois para escolher o modo
   * (`resultado`) e para guardar o erro, mas devolve `false` porque a guarda não pode roubá-los do
   * chat nem da linha de versões.
   */
  aplicarEvento: (evento, contexto) => {
    const nome = evento.evento;
    const dados = (evento.dados ?? {}) as Record<string, unknown>;
    const ehPalco = ehTipoDePalco(nome);
    const observado = nome === 'versao.criada' || nome === 'nucleo.res';
    if (!ehPalco && !observado) return false;

    // --- guarda 1: o evento tem de ser do projeto que a store está mostrando.
    const projetoDaStore = get().projetoId;
    if (
      projetoDaStore !== null &&
      contexto?.projetoId !== undefined &&
      contexto.projetoId !== projetoDaStore
    ) {
      set({ descartados: get().descartados + 1 });
      return true;
    }
    const projetoDoEvento = texto(dados.projeto_id);
    if (projetoDaStore !== null && projetoDoEvento && projetoDoEvento !== projetoDaStore) {
      set({ descartados: get().descartados + 1 });
      return true;
    }

    // --- guarda 2: um palco segue um job. Evento de outro job não contamina o estado.
    const jobDoEvento = texto(dados.job_id) || texto(evento.job_id);
    let jobId = get().jobId;
    if (jobDoEvento) {
      if (jobId !== null && jobId !== jobDoEvento) {
        set({ descartados: get().descartados + 1 });
        return true;
      }
      jobId = jobDoEvento;
    }

    // --- aplica: o estado é sempre derivado da lista COMPLETA de eventos (nada se perde).
    const agora = Date.now();
    const inicio = get().inicio_ms ?? agora;
    const eventos = [...get().eventos, { seq: evento.seq, evento: nome, dados }];
    if (eventos.length > LIMITE_EVENTOS) {
      eventos.splice(0, eventos.length - LIMITE_EVENTOS);
    }

    const fila = ehPalco
      ? enfileirar(
          get().fila,
          { seq: evento.seq, tipo: nome, dados, chegou_ms: agora - inicio },
          get().animar,
        )
      : get().fila;

    set({
      eventos,
      fila,
      jobId,
      inicio_ms: inicio,
      ...derivar(eventos),
    });
    return ehPalco;
  },

  /** Troca de projeto: zera o palco inteiro (evento de outro projeto não pode aparecer aqui). */
  definirProjeto: (projetoId) => {
    if (get().projetoId === projetoId) return;
    set({
      ...VAZIO,
      projetoId,
      jobId: null,
      fila: [],
      passoCorrente: null,
      eventos: [],
      inicio_ms: null,
    });
  },

  /** Troca de job dentro do mesmo projeto: zera a fila e o estado, e passa a aceitar o job novo. */
  definirJob: (jobId) => {
    if (get().jobId === jobId) return;
    set({ ...VAZIO, jobId, fila: [], passoCorrente: null, eventos: [], inicio_ms: null });
  },

  definirAnimar: (animar) => set({ animar, fila: animar ? get().fila : [] }),

  definirReduzirMovimento: (reduzirMovimento) => set({ reduzirMovimento }),

  planejar: () => {
    const { fila, animar, reduzirMovimento } = get();
    const eventos: EventoCoreografia[] = fila.map((item) => ({
      seq: item.seq,
      evento: item.tipo,
      dados: item.dados,
      chegou_ms: item.chegou_ms,
    }));
    return coreografar(eventos, { reduzir_movimento: reduzirMovimento || !animar });
  },

  proximoPasso: () => {
    const passos = get().planejar();
    const primeiro = passos[0] ?? null;
    if (!primeiro) {
      set({ passoCorrente: null });
      return null;
    }
    set((atual) => ({
      passoCorrente: primeiro,
      fila: atual.fila.filter((item) => `${item.tipo}:${item.seq}` !== primeiro.id),
    }));
    return primeiro;
  },

  concluirPasso: () => set({ passoCorrente: null }),

  consumir: () => {
    const [primeiro, ...resto] = get().fila;
    if (!primeiro) return null;
    set({ fila: resto });
    return primeiro;
  },

  limpar: () =>
    set({
      ...VAZIO,
      jobId: null,
      fila: [],
      passoCorrente: null,
      eventos: [],
      inicio_ms: null,
    }),
}));

/** Duração total planejada para a fila atual (o executor usa para saber se ainda há animação). */
export function duracaoDaFila(passos: readonly Passo[]): number {
  return duracaoTotal(passos);
}
