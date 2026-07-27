// Auto-update (F1-11 P2). Feed: GitHub Releases — o `latest.yml` que o
// electron-builder publica junto do instalador.
//
// O usuário decide: nada é baixado sozinho (`autoDownload = false`) e nada é
// instalado sem clique. O app só avisa que existe versão nova.
//
// Só funciona empacotado: em dev o electron-updater não tem `app-update.yml`,
// então `iniciarAtualizador` sai cedo em vez de estourar.

import type { BrowserWindow } from "electron";
import { autoUpdater } from "electron-updater";

import { CANAL_ATUALIZACAO } from "./ipc/canais.js";

export type EstadoAtualizacao =
  | { fase: "ocioso" }
  | { fase: "verificando" }
  | { fase: "disponivel"; versao: string; notas?: string }
  | { fase: "baixando"; pct: number }
  | { fase: "pronta"; versao: string }
  | { fase: "erro"; mensagem: string };

let estado: EstadoAtualizacao = { fase: "ocioso" };
let destino: BrowserWindow | null = null;

/** 4 h: o app fica aberto o dia todo; checar a cada boot só não basta. */
const INTERVALO_MS = 4 * 60 * 60 * 1000;

export function estadoAtualizacao(): EstadoAtualizacao {
  return estado;
}

function publicar(proximo: EstadoAtualizacao): void {
  estado = proximo;
  if (destino !== null && !destino.isDestroyed()) {
    destino.webContents.send(CANAL_ATUALIZACAO, estado);
  }
}

export function iniciarAtualizador(janela: BrowserWindow, empacotado: boolean): void {
  destino = janela;
  if (!empacotado) return;

  autoUpdater.autoDownload = false;
  autoUpdater.autoInstallOnAppQuit = false;

  autoUpdater.on("checking-for-update", () => publicar({ fase: "verificando" }));
  autoUpdater.on("update-not-available", () => publicar({ fase: "ocioso" }));
  autoUpdater.on("update-available", (info) =>
    publicar({
      fase: "disponivel",
      versao: info.version,
      notas: typeof info.releaseNotes === "string" ? info.releaseNotes : undefined,
    }),
  );
  autoUpdater.on("download-progress", (p) =>
    publicar({ fase: "baixando", pct: Math.round(p.percent) }),
  );
  autoUpdater.on("update-downloaded", (info) =>
    publicar({ fase: "pronta", versao: info.version }),
  );
  // Falha de update nunca derruba o app nem vira modal: é um aviso na barra.
  autoUpdater.on("error", (erro) =>
    publicar({ fase: "erro", mensagem: erro?.message ?? String(erro) }),
  );

  void verificar();
  setInterval(() => void verificar(), INTERVALO_MS);
}

export async function verificar(): Promise<void> {
  try {
    await autoUpdater.checkForUpdates();
  } catch (erro) {
    publicar({ fase: "erro", mensagem: erro instanceof Error ? erro.message : String(erro) });
  }
}

export async function baixar(): Promise<void> {
  try {
    await autoUpdater.downloadUpdate();
  } catch (erro) {
    publicar({ fase: "erro", mensagem: erro instanceof Error ? erro.message : String(erro) });
  }
}

/** Fecha o app e roda o instalador. Só chame depois de `fase: "pronta"`. */
export function instalarEReiniciar(): void {
  autoUpdater.quitAndInstall(false, true);
}
