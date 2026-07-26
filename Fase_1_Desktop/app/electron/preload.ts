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
  CANAL_WORKSPACE_ABRIR_RECENTE,
  CANAL_WORKSPACE_CONECTAR,
  CANAL_WORKSPACE_RECENTES,
} from "./ipc/canais.js";

export interface RespostaIpc {
  ok: boolean;
  resultado?: unknown;
  erro?: { codigo: string; mensagem: string; detalhes?: Record<string, unknown> };
}

/** Resposta de conectar pasta: `cancelado` é o usuário fechando o diálogo. */
export interface RespostaConectar extends Partial<RespostaIpc> {
  cancelado: boolean;
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
  /** Abre o diálogo nativo de pasta e manda o núcleo indexar o que o usuário escolheu. */
  conectarPasta(): Promise<RespostaConectar> {
    return ipcRenderer.invoke(CANAL_WORKSPACE_CONECTAR) as Promise<RespostaConectar>;
  },
  projetosRecentes(): Promise<{ indice: number; nome: string; abertoEm: string }[]> {
    return ipcRenderer.invoke(CANAL_WORKSPACE_RECENTES) as Promise<
      { indice: number; nome: string; abertoEm: string }[]
    >;
  },
  /** Reabre um recente **por índice** — o renderer nunca manda caminho de disco. */
  abrirProjetoRecente(indice: number): Promise<RespostaConectar> {
    return ipcRenderer.invoke(CANAL_WORKSPACE_ABRIR_RECENTE, indice) as Promise<RespostaConectar>;
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
