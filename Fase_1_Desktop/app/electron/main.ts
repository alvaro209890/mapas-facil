// Processo main do Electron: janela, ponte com o núcleo, IPC tipado e o diálogo
// nativo de pasta (C7). Menus, tray, conta local (M5) e auto-update são de marcos
// posteriores (F1-02, F1-14, F1-11).
import { app, BrowserWindow, dialog, ipcMain, nativeTheme } from "electron";
import { join } from "node:path";

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
import { localizarNucleo } from "./nucleo/localizar.js";
import { ErroPonte, PonteNucleo } from "./nucleo/ponte.js";
import type { EstadoPonte } from "./nucleo/ponte.js";
import type { Evento } from "./nucleo/protocolo.js";
import { ArquivoPreferencias } from "./preferencias.js";
import { lerRecentes, registrar, visiveis } from "./projetos.js";

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
  const env = {
    ...process.env,
    // D13: chats.sqlite sob userData/chats (mesmo root do config.json)
    MAPASFACIL_DADOS: app.getPath("userData"),
  };
  const nova = new PonteNucleo({ comando, args, cwd, env });

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

  // O renderer monta depois de a ponte já ter mudado de estado; sem este empurrão
  // ele ficaria esperando para sempre um evento que já passou.
  destino.webContents.on("did-finish-load", () => {
    if (!destino.isDestroyed()) {
      destino.webContents.send(CANAL_ESTADO, { estado: nova.estado, erro: null });
    }
  });

  nova.iniciar();
  return nova;
}

interface RespostaIpc {
  ok: boolean;
  resultado?: unknown;
  erro?: { codigo: string; mensagem: string; detalhes?: Record<string, unknown> };
}

async function chamarNucleo(metodo: string, params: Record<string, unknown>): Promise<RespostaIpc> {
  if (ponte === null) {
    return { ok: false, erro: { codigo: "UI-001", mensagem: "O núcleo não está rodando." } };
  }
  try {
    const resultado = await ponte.chamar(metodo, params);
    return { ok: true, resultado };
  } catch (causa) {
    const erro =
      causa instanceof ErroPonte
        ? { codigo: causa.codigo, mensagem: causa.message, detalhes: causa.detalhes }
        : { codigo: "UI-001", mensagem: String(causa) };
    return { ok: false, erro };
  }
}

/** Abre a pasta no núcleo e, dando certo, registra o projeto recente. */
async function abrirWorkspace(caminho: string): Promise<RespostaIpc> {
  const resposta = await chamarNucleo("workspace.abrir", { caminho });
  if (resposta.ok && preferencias !== null) registrar(preferencias, caminho);
  return resposta;
}

function registrarIpc(): void {
  ipcMain.handle(CANAL_CHAMAR, (_evento, metodo: string, params: Record<string, unknown>) =>
    chamarNucleo(metodo, params ?? {}),
  );

  // C7 — diálogo nativo de pasta. Só o main abre o diálogo e só ele vê o caminho
  // absoluto; o renderer recebe o índice do núcleo, não um handle de disco.
  ipcMain.handle(CANAL_WORKSPACE_CONECTAR, async () => {
    const opcoes: Electron.OpenDialogOptions = {
      title: "Conectar pasta do projeto",
      buttonLabel: "Conectar",
      properties: ["openDirectory", "createDirectory"],
    };
    const escolha =
      janela === null
        ? await dialog.showOpenDialog(opcoes)
        : await dialog.showOpenDialog(janela, opcoes);
    if (escolha.canceled || escolha.filePaths.length === 0) return { cancelado: true };
    return { cancelado: false, ...(await abrirWorkspace(escolha.filePaths[0])) };
  });

  ipcMain.handle(CANAL_WORKSPACE_RECENTES, () =>
    preferencias === null ? [] : visiveis(lerRecentes(preferencias)),
  );

  ipcMain.handle(CANAL_WORKSPACE_ABRIR_RECENTE, async (_evento, indice: number) => {
    const recentes = preferencias === null ? [] : lerRecentes(preferencias);
    const projeto = recentes[indice];
    if (projeto === undefined) {
      return {
        cancelado: false,
        ok: false,
        erro: { codigo: "UI-020", mensagem: "Esse projeto recente não está mais na lista." },
      };
    }
    return { cancelado: false, ...(await abrirWorkspace(projeto.caminho)) };
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
