// Compila o sidecar Python com PyInstaller antes do electron-builder.
// O instalador 0.5.0 foi montado fora da árvore e ficou irreproduzível; este
// script existe para que `pnpm dist` gere tudo a partir do repositório.
import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const AQUI = dirname(fileURLToPath(import.meta.url));
const NUCLEO = resolve(AQUI, "..", "..", "nucleo");

const python =
  process.platform === "win32"
    ? join(NUCLEO, ".venv", "Scripts", "python.exe")
    : join(NUCLEO, ".venv", "bin", "python3");

if (!existsSync(python)) {
  console.error(
    `venv do núcleo não encontrado em ${python}.\n` +
      "Rode: cd Fase_1_Desktop/nucleo && python -m venv .venv && " +
      '.venv/Scripts/pip install -e ".[empacotar]"',
  );
  process.exit(1);
}

console.log("→ PyInstaller: empacotando o sidecar…");
execFileSync(python, ["-m", "PyInstaller", "mapasfacil-nucleo.spec", "--noconfirm"], {
  cwd: NUCLEO,
  stdio: "inherit",
});

const executavel = join(
  NUCLEO,
  "dist",
  "mapasfacil-nucleo",
  process.platform === "win32" ? "mapasfacil-nucleo.exe" : "mapasfacil-nucleo",
);
if (!existsSync(executavel)) {
  console.error(`PyInstaller terminou mas ${executavel} não existe.`);
  process.exit(1);
}
console.log(`✓ sidecar pronto: ${executavel}`);
