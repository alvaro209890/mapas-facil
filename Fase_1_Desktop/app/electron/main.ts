// Processo main do Electron: janela, ponte com o núcleo e IPC tipado.
// Escopo desta rodada: C1/C2 do bloco C. Menus, tray, diálogo de pasta, OAuth e
// auto-update são de marcos posteriores (F1-02, F1-14, F1-11).
import { app, BrowserWindow, ipcMain, nativeTheme } from "electron";
import { join } from "node:path";

import {
  CANAL_CHAMAR,
  CANAL_ESTADO,
  CANAL_EVENTO,
  CANAL_PREFERENCIAS_GRAVAR,
  CANAL_PREFERENCIAS_LER,
  CANAL_REINICIAR,
} from "./ipc/canais.js";
import { localizarNucleo } from "./nucleo/localizar.js";
import { ErroPonte, PonteNucleo } from "./nucleo/ponte.js";
import type { EstadoPonte } from "./nucleo/ponte.js";
import type { Evento } from "./nucleo/protocolo.js";
import { ArquivoPreferencias } from "./preferencias.js";

const URL_DEV = process.env.VITE_DEV_SERVER_URL;

let janela: BrowserWindow | null = null;
let ponte: PonteNucleo | null = null;
let preferencias: ArquivoPreferencias | null = null;

function criarJanela(): BrowserWindow {
  // D15/AP-08: escuro é o default do produto, não o do sistema.
  nativeTheme.themeSource = "dark";

  const nova = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1280,
    minHeight: 800,
    backgroundColor: "#0B0E11",
    show: false,
    autoHideMenuBar: true,
    webPreferences: {
      preload: join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  nova.once("ready-to-show", () => nova.show());

  if (URL_DEV) {
    void nova.loadURL(URL_DEV);
  } else {
    void nova.loadFile(join(__dirname, "..", "renderer", "index.html"));
  }
  return nova;
}

function ligarPonte(destino: BrowserWindow): PonteNucleo {
  const { comando, args, cwd } = localizarNucleo(app.getAppPath(), app.isPackaged);
  const nova = new PonteNucleo({ comando, args, cwd });

  nova.on("evt", (evento: Evento) => {
    if (!destino.isDestroyed()) destino.webContents.send(CANAL_EVENTO, evento);
  });
  nova.on("estado", (estado: EstadoPonte, erro?: ErroPonte) => {
    if (!destino.isDestroyed()) {
      destino.webContents.send(CANAL_ESTADO, {
        estado,
        erro: erro ? { codigo: erro.codigo, mensagem: erro.message } : null,
      });
    }
  });
  nova.on("log", (linha: string) => process.stderr.write(linha));

  nova.iniciar();
  return nova;
}

function registrarIpc(): void {
  ipcMain.handle(CANAL_CHAMAR, async (_evento, metodo: string, params: Record<string, unknown>) => {
    if (ponte === null) {
      return { ok: false, erro: { codigo: "UI-001", mensagem: "O núcleo não está rodando." } };
    }
    try {
      const resultado = await ponte.chamar(metodo, params ?? {});
      return { ok: true, resultado };
    } catch (causa) {
      const erro =
        causa instanceof ErroPonte
          ? { codigo: causa.codigo, mensagem: causa.message, detalhes: causa.detalhes }
          : { codigo: "UI-001", mensagem: String(causa) };
      return { ok: false, erro };
    }
  });

  ipcMain.handle(CANAL_REINICIAR, () => {
    ponte?.reiniciar();
    return { estado: ponte?.estado ?? "parado" };
  });

  ipcMain.handle(CANAL_PREFERENCIAS_LER, () => preferencias?.ler() ?? {});
  ipcMain.handle(CANAL_PREFERENCIAS_GRAVAR, (_evento, parcial: Record<string, unknown>) =>
    preferencias?.gravar(parcial ?? {}) ?? {},
  );
}

void app.whenReady().then(() => {
  preferencias = new ArquivoPreferencias(app.getPath("userData"));
  registrarIpc();
  janela = criarJanela();
  ponte = ligarPonte(janela);

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      janela = criarJanela();
      ponte = ligarPonte(janela);
    }
  });
});

app.on("window-all-closed", () => {
  ponte?.encerrar();
  ponte = null;
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", () => {
  ponte?.encerrar();
  ponte = null;
});
