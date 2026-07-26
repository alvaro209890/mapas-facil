// Acesso do renderer ao núcleo, sempre pelo preload (`window.mapasfacil`).
// Fora do Electron (vitest, `vite dev` no navegador) a API não existe: as funções
// viram no-op explícito, nunca um mock que finge que o núcleo respondeu.

import type { EnvelopeEvento } from "./eventos.js";

export interface RespostaNucleo {
  ok: boolean;
  resultado?: unknown;
  erro?: { codigo: string; mensagem: string; detalhes?: Record<string, unknown> };
}

export interface EstadoNucleo {
  estado: "parado" | "iniciando" | "pronto" | "caido";
  erro: { codigo: string; mensagem: string } | null;
}

/** Conectar pasta: `cancelado` é o usuário fechando o diálogo nativo, não erro. */
export interface RespostaConectar extends Partial<RespostaNucleo> {
  cancelado: boolean;
}

export interface ProjetoRecente {
  indice: number;
  nome: string;
  abertoEm: string;
}

export interface ApiMapasFacil {
  chamar(metodo: string, params?: Record<string, unknown>): Promise<RespostaNucleo>;
  reiniciarNucleo(): Promise<{ estado: string }>;
  aoEvento(ouvinte: (evento: EnvelopeEvento) => void): () => void;
  aoEstadoNucleo(ouvinte: (estado: EstadoNucleo) => void): () => void;
  /** Menu/tray do main → id de comando da paleta (`conectar-pasta`, …). */
  aoComandoMenu?(ouvinte: (id: string) => void): () => void;
  conectarPasta(): Promise<RespostaConectar>;
  projetosRecentes(): Promise<ProjetoRecente[]>;
  abrirProjetoRecente(indice: number): Promise<RespostaConectar>;
  lerPreferencias(): Promise<Record<string, unknown>>;
  gravarPreferencias(parcial: Record<string, unknown>): Promise<Record<string, unknown>>;
}

declare global {
  interface Window {
    mapasfacil?: ApiMapasFacil;
  }
}

export function api(): ApiMapasFacil | undefined {
  return typeof window === "undefined" ? undefined : window.mapasfacil;
}

export function assinarEventos(ouvinte: (evento: EnvelopeEvento) => void): () => void {
  return api()?.aoEvento(ouvinte) ?? (() => undefined);
}

export function assinarEstadoNucleo(ouvinte: (estado: EstadoNucleo) => void): () => void {
  return api()?.aoEstadoNucleo(ouvinte) ?? (() => undefined);
}
