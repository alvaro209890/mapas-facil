// Menus nativos e tray (F1-02 §layout — `topo-app` e menus do processo main).
//
// Regra que mantém isto honesto: o menu **não** implementa comportamento — ele
// despacha o mesmo `IdComando` que a paleta `Ctrl+K` já executa no renderer
// (`CANAL_COMANDO_MENU`). Menu e paleta não podem divergir; quem muda o
// comportamento mexe num lugar só, em `AppShell.executarComando`.
//
// Fora daqui, de propósito: auto-update (M10) e qualquer porta HTTP (AP-14).

import { app, BrowserWindow, Menu, nativeImage, Tray } from "electron";
import type { MenuItemConstructorOptions } from "electron";

import { CANAL_COMANDO_MENU } from "./ipc/canais.js";

/** Espelha `app/src/paleta/comandos.ts` — se um id sumir de lá, some daqui. */
export type IdComandoMenu =
  | "conectar-pasta"
  | "reindexar-pasta"
  | "verificar-ambiente"
  | "preferencias"
  | "alternar-tema"
  | "nova-conversa"
  | "buscar-chats";

export interface ProjetoRecenteMenu {
  indice: number;
  nome: string;
}

export interface OpcoesMenu {
  janela: BrowserWindow | null;
  recentes: ProjetoRecenteMenu[];
  /** Reabre um recente pelo **índice** — o caminho nunca sai do main (fronteira 1). */
  aoAbrirRecente: (indice: number) => void;
  aoReiniciarNucleo: () => void;
  /** Injetável para teste: por padrão manda pelo IPC para a janela. */
  aoComando?: (id: IdComandoMenu) => void;
}

function despachar(opcoes: OpcoesMenu, id: IdComandoMenu): void {
  if (opcoes.aoComando) {
    opcoes.aoComando(id);
    return;
  }
  const alvo = opcoes.janela;
  if (alvo !== null && !alvo.isDestroyed()) {
    alvo.webContents.send(CANAL_COMANDO_MENU, id);
  }
}

function submenuRecentes(opcoes: OpcoesMenu): MenuItemConstructorOptions[] {
  if (opcoes.recentes.length === 0) {
    return [{ label: "(nenhum projeto recente)", enabled: false }];
  }
  return opcoes.recentes.map((projeto) => ({
    label: projeto.nome,
    click: () => opcoes.aoAbrirRecente(projeto.indice),
  }));
}

/** Template do menu — puro, para o teste inspecionar sem abrir o Electron. */
export function montarTemplateMenu(opcoes: OpcoesMenu): MenuItemConstructorOptions[] {
  return [
    {
      label: "Arquivo",
      submenu: [
        {
          label: "Conectar pasta…",
          accelerator: "CmdOrCtrl+O",
          click: () => despachar(opcoes, "conectar-pasta"),
        },
        { label: "Projetos recentes", submenu: submenuRecentes(opcoes) },
        {
          label: "Reindexar pasta",
          accelerator: "CmdOrCtrl+R",
          click: () => despachar(opcoes, "reindexar-pasta"),
        },
        { type: "separator" },
        {
          label: "Nova conversa",
          accelerator: "CmdOrCtrl+N",
          click: () => despachar(opcoes, "nova-conversa"),
        },
        {
          label: "Buscar nas conversas",
          accelerator: "CmdOrCtrl+F",
          click: () => despachar(opcoes, "buscar-chats"),
        },
        { type: "separator" },
        { role: "quit", label: "Sair" },
      ],
    },
    {
      label: "Editar",
      submenu: [
        { role: "undo", label: "Desfazer" },
        { role: "redo", label: "Refazer" },
        { type: "separator" },
        { role: "cut", label: "Recortar" },
        { role: "copy", label: "Copiar" },
        { role: "paste", label: "Colar" },
        { role: "selectAll", label: "Selecionar tudo" },
      ],
    },
    {
      label: "Exibir",
      submenu: [
        {
          label: "Preferências",
          accelerator: "CmdOrCtrl+,",
          click: () => despachar(opcoes, "preferencias"),
        },
        { label: "Alternar tema", click: () => despachar(opcoes, "alternar-tema") },
        { type: "separator" },
        { role: "resetZoom", label: "Zoom padrão" },
        { role: "zoomIn", label: "Aumentar zoom" },
        { role: "zoomOut", label: "Diminuir zoom" },
        { type: "separator" },
        { role: "togglefullscreen", label: "Tela cheia" },
      ],
    },
    {
      label: "Ferramentas",
      submenu: [
        {
          label: "Diagnóstico do ambiente (doctor)",
          accelerator: "F1",
          click: () => despachar(opcoes, "verificar-ambiente"),
        },
        { label: "Reiniciar núcleo", click: () => opcoes.aoReiniciarNucleo() },
        { type: "separator" },
        { role: "toggleDevTools", label: "Ferramentas de desenvolvedor" },
      ],
    },
  ];
}

export function aplicarMenu(opcoes: OpcoesMenu): Menu {
  const menu = Menu.buildFromTemplate(montarTemplateMenu(opcoes));
  Menu.setApplicationMenu(menu);
  return menu;
}

/** Template do tray — mínimo e útil: mostrar, conectar, sair. */
export function montarTemplateTray(opcoes: OpcoesMenu): MenuItemConstructorOptions[] {
  return [
    {
      label: "Mostrar janela",
      click: () => {
        const alvo = opcoes.janela;
        if (alvo === null || alvo.isDestroyed()) return;
        if (alvo.isMinimized()) alvo.restore();
        alvo.show();
        alvo.focus();
      },
    },
    { label: "Conectar pasta…", click: () => despachar(opcoes, "conectar-pasta") },
    { type: "separator" },
    { role: "quit", label: "Sair" },
  ];
}

/**
 * Cria o tray. Devolve `null` quando o ambiente não suporta (headless, alguns
 * Linux sem StatusNotifier) — falhar aqui não pode derrubar o app inteiro.
 */
export function criarTray(opcoes: OpcoesMenu, caminhoIcone?: string): Tray | null {
  try {
    const imagem =
      caminhoIcone !== undefined
        ? nativeImage.createFromPath(caminhoIcone)
        : nativeImage.createEmpty();
    const tray = new Tray(imagem);
    tray.setToolTip(app.getName());
    atualizarTray(tray, opcoes);
    // Clique no ícone: mostra/esconde a janela. O menu de contexto cobre o resto.
    tray.on("click", () => {
      const alvo = opcoes.janela;
      if (alvo === null || alvo.isDestroyed()) return;
      if (alvo.isVisible()) alvo.hide();
      else {
        alvo.show();
        alvo.focus();
      }
    });
    return tray;
  } catch {
    return null;
  }
}

/** Reaplica o menu de contexto do tray (ex.: lista de recentes mudou). */
export function atualizarTray(tray: Tray, opcoes: OpcoesMenu): void {
  tray.setContextMenu(Menu.buildFromTemplate(montarTemplateTray(opcoes)));
}
