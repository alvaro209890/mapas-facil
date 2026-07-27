// Processo main do Electron: janela, ponte com o núcleo, IPC tipado, diálogo
// nativo de pasta (C7), menus e tray (F1-02). Auto-update fica para M10.
import { app, BrowserWindow, dialog, ipcMain, nativeTheme, type Tray } from "electron";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
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
import { aplicarMenu, atualizarTray, criarTray, type OpcoesMenu } from "./menu.js";
import { localizarNucleo } from "./nucleo/localizar.js";
import { ErroPonte, PonteNucleo } from "./nucleo/ponte.js";
import type { EstadoPonte } from "./nucleo/ponte.js";
import type { Evento } from "./nucleo/protocolo.js";
import { ArquivoPreferencias } from "./preferencias.js";
import { lerRecentes, registrar, visiveis } from "./projetos.js";

const URL_DEV = process.env.VITE_DEV_SERVER_URL;
const NOME_SISTEMA = "MapasFacil";

let janela: BrowserWindow | null = null;
let ponte: PonteNucleo | null = null;
let preferencias: ArquivoPreferencias | null = null;
let tray: Tray | null = null;

/** Documentos/Documents do usuário (Acer Linux: Documentos). */
function pastaDocumentos(): string {
  const home = homedir();
  for (const nome of ["Documentos", "Documents"] as const) {
    const candidata = join(home, nome);
    if (existsSync(candidata)) return candidata;
  }
  const docs = join(home, "Documents");
  mkdirSync(docs, { recursive: true });
  return docs;
}

/** ``Documentos/database/MapasFacil`` — contas + pastas por usuário. */
function raizDatabase(): string {
  if (process.env.MAPASFACIL_DATABASE_ROOT?.trim()) {
    return process.env.MAPASFACIL_DATABASE_ROOT.trim();
  }
  const raiz = join(pastaDocumentos(), "database", NOME_SISTEMA);
  mkdirSync(join(raiz, "contas"), { recursive: true });
  return raiz;
}

/**
 * Espelha secrets.local.json → provisao.local.json (sem logar o valor).
 * Assim o núcleo encontra a chave do projeto após o login.
 */
function espelharProvisao(raiz: string, appPath: string, packaged: boolean): string | undefined {
  const destino = join(raiz, "provisao.local.json");
  const candidatos: string[] = [];
  if (process.env.MAPASFACIL_PROVISAO_PATH?.trim()) {
    candidatos.push(process.env.MAPASFACIL_PROVISAO_PATH.trim());
  }
  if (packaged) {
    candidatos.push(join(process.resourcesPath, "provisao.local.json"));
  }
  // Dev: monorepo/secrets.local.json (appPath ≈ Fase_1_Desktop/app)
  candidatos.push(join(appPath, "..", "..", "secrets.local.json"));
  candidatos.push(join(appPath, "..", "..", "..", "secrets.local.json"));

  for (const origem of candidatos) {
    if (!existsSync(origem)) continue;
    try {
      const bruto = JSON.parse(readFileSync(origem, "utf8")) as Record<string, unknown>;
      const deepseek =
        typeof bruto.deepseek_api_key === "string" ? bruto.deepseek_api_key.trim() : "";
      if (!deepseek) continue;
      const payload: Record<string, string> = { deepseek_api_key: deepseek };
      for (const k of ["sema_authkey", "planet_api_key"] as const) {
        const v = bruto[k];
        if (typeof v === "string" && v.trim()) payload[k] = v.trim();
      }
      writeFileSync(destino, `${JSON.stringify(payload, null, 2)}\n`, { mode: 0o600 });
      return destino;
    } catch {
      // tenta o próximo candidato
    }
  }
  return existsSync(destino) ? destino : undefined;
}

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
    // Menu nativo fica visível — é o mesmo catálogo da paleta Ctrl+K.
    autoHideMenuBar: false,
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
  const raiz = raizDatabase();
  const provisao = espelharProvisao(raiz, app.getAppPath(), app.isPackaged);

  const env: NodeJS.ProcessEnv = {
    ...process.env,
    MAPASFACIL_DADOS: raiz,
    MAPASFACIL_DATABASE_ROOT: raiz,
  };
  if (provisao) {
    env.MAPASFACIL_PROVISAO_PATH = provisao;
  }

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

/** Abre a pasta no núcleo e, dando certo, registra o projeto recente + atualiza o menu. */
async function abrirWorkspace(caminho: string): Promise<RespostaIpc> {
  const resposta = await chamarNucleo("workspace.abrir", { caminho });
  if (resposta.ok && preferencias !== null) {
    registrar(preferencias, caminho);
    atualizarChrome();
  }
  return resposta;
}

/**
 * Após login/criar conta: abre o workspace padrão do usuário
 * (Documentos/database/MapasFacil/<user>/workspace).
 */
async function talvezAbrirWorkspacePadrao(resultado: unknown): Promise<void> {
  if (!resultado || typeof resultado !== "object") return;
  const dados = (resultado as { dados?: { workspace_padrao?: string } }).dados;
  const caminho = dados?.workspace_padrao?.trim();
  if (!caminho) return;
  mkdirSync(caminho, { recursive: true });
  await abrirWorkspace(caminho);
}

/** Opções frescas a cada aplicação — recentes e `janela` não podem ficar stale. */
function montarOpcoesMenu(): OpcoesMenu {
  return {
    janela,
    recentes:
      preferencias === null
        ? []
        : visiveis(lerRecentes(preferencias)).map((p) => ({ indice: p.indice, nome: p.nome })),
    aoAbrirRecente: (indice) => {
      const recentes = preferencias === null ? [] : lerRecentes(preferencias);
      const projeto = recentes[indice];
      if (projeto === undefined) return;
      void abrirWorkspace(projeto.caminho);
    },
    aoReiniciarNucleo: () => {
      ponte?.reiniciar();
    },
  };
}

function atualizarChrome(): void {
  const opcoes = montarOpcoesMenu();
  aplicarMenu(opcoes);
  if (tray !== null) atualizarTray(tray, opcoes);
}

function registrarIpc(): void {
  ipcMain.handle(CANAL_CHAMAR, async (_evento, metodo: string, params: Record<string, unknown>) => {
    const resposta = await chamarNucleo(metodo, params ?? {});
    if (
      resposta.ok &&
      (metodo === "conta.criar" || metodo === "conta.entrar" || metodo === "conta.estado")
    ) {
      void talvezAbrirWorkspacePadrao(resposta.resultado);
    }
    return resposta;
  });

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
  const raiz = raizDatabase();
  preferencias = new ArquivoPreferencias(raiz);
  registrarIpc();
  janela = criarJanela();
  ponte = ligarPonte(janela);
  atualizarChrome();
  tray = criarTray(montarOpcoesMenu());

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      janela = criarJanela();
      ponte = ligarPonte(janela);
      atualizarChrome();
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
  if (tray !== null) {
    tray.destroy();
    tray = null;
  }
});
