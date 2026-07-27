// Auto-update via electron-updater + GitHub Releases (F1-11 P2).
// Canal stable; feed = latest.yml na release. Sem assinatura Authenticode na
// v1 beta — dívida documentada (SmartScreen: "Executar mesmo assim").
import { app, dialog, BrowserWindow } from "electron";
import { autoUpdater } from "electron-updater";

let iniciado = false;

export function iniciarAtualizacao(janela: () => BrowserWindow | null): void {
  if (iniciado || !app.isPackaged) return;
  iniciado = true;

  autoUpdater.autoDownload = true;
  autoUpdater.autoInstallOnAppQuit = true;

  autoUpdater.on("error", (erro) => {
    process.stderr.write(`[atualizacao] ${erro.message}\n`);
  });

  autoUpdater.on("update-available", (info) => {
    process.stderr.write(`[atualizacao] disponível: ${info.version}\n`);
  });

  autoUpdater.on("update-downloaded", (info) => {
    const win = janela();
    const opcoes: Electron.MessageBoxOptions = {
      type: "info",
      buttons: ["Reiniciar agora", "Depois"],
      defaultId: 0,
      cancelId: 1,
      title: "Atualização pronta",
      message: `A versão ${info.version} do Mapas Fácil foi baixada.`,
      detail: "Reinicie para instalar. O núcleo e o app atualizam juntos.",
    };
    const mostrar = win ? dialog.showMessageBox(win, opcoes) : dialog.showMessageBox(opcoes);
    void mostrar.then((res) => {
      if (res.response === 0) autoUpdater.quitAndInstall(false, true);
    });
  });

  // Checa no boot e a cada 24 h (F1-11).
  void autoUpdater.checkForUpdates().catch((erro: unknown) => {
    process.stderr.write(`[atualizacao] check falhou: ${String(erro)}\n`);
  });
  setInterval(
    () => {
      void autoUpdater.checkForUpdates().catch(() => undefined);
    },
    24 * 60 * 60 * 1000,
  );
}
