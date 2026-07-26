// Ponte tipada main ↔ renderer. O renderer nunca ganha `fs`, `child_process`
// nem caminho absoluto: só métodos NDJSON e eventos (fronteira 1 de F1-01).
import { contextBridge, ipcRenderer } from "electron";

import {
  CANAL_CHAMAR,
  CANAL_ESTADO,
  CANAL_EVENTO,
  CANAL_PREFERENCIAS_GRAVAR,
  CANAL_PREFERENCIAS_LER,
  CANAL_REINICIAR,
} from "./ipc/canais.js";

export interface RespostaIpc {
  ok: boolean;
  resultado?: unknown;
  erro?: { codigo: string; mensagem: string; detalhes?: Record<string, unknown> };
}

const api = {
  chamar(metodo: string, params: Record<string, unknown> = {}): Promise<RespostaIpc> {
    return ipcRenderer.invoke(CANAL_CHAMAR, metodo, params) as Promise<RespostaIpc>;
  },
  reiniciarNucleo(): Promise<{ estado: string }> {
    return ipcRenderer.invoke(CANAL_REINICIAR) as Promise<{ estado: string }>;
  },
  aoEvento(ouvinte: (evento: unknown) => void): () => void {
    const alca = (_e: unknown, evento: unknown) => ouvinte(evento);
    ipcRenderer.on(CANAL_EVENTO, alca);
    return () => ipcRenderer.removeListener(CANAL_EVENTO, alca);
  },
  aoEstadoNucleo(ouvinte: (estado: unknown) => void): () => void {
    const alca = (_e: unknown, estado: unknown) => ouvinte(estado);
    ipcRenderer.on(CANAL_ESTADO, alca);
    return () => ipcRenderer.removeListener(CANAL_ESTADO, alca);
  },
  lerPreferencias(): Promise<Record<string, unknown>> {
    return ipcRenderer.invoke(CANAL_PREFERENCIAS_LER) as Promise<Record<string, unknown>>;
  },
  gravarPreferencias(parcial: Record<string, unknown>): Promise<Record<string, unknown>> {
    return ipcRenderer.invoke(CANAL_PREFERENCIAS_GRAVAR, parcial) as Promise<Record<string, unknown>>;
  },
};

export type ApiMapasFacil = typeof api;

contextBridge.exposeInMainWorld("mapasfacil", api);
