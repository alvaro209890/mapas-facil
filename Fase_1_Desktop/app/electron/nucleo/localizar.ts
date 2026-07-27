// Onde está o sidecar Python. Em produção ele vem empacotado (PyInstaller onedir,
// F1-11); em desenvolvimento roda o pacote do repositório, com o venv do núcleo
// se ele existir.
import { existsSync } from "node:fs";
import { join, resolve } from "node:path";

export interface ComandoNucleo {
  comando: string;
  args: string[];
  cwd: string;
}

export function localizarNucleo(raizApp: string, empacotado: boolean): ComandoNucleo {
  if (empacotado) {
    // resources/nucleo/nucleo.exe (+ shared/ e, no staging, arcpy_job.py)
    const pasta = join(process.resourcesPath, "nucleo");
    const executavel = process.platform === "win32" ? "nucleo.exe" : "nucleo";
    return { comando: join(pasta, executavel), args: ["stdio"], cwd: pasta };
  }

  const pastaNucleo = resolve(raizApp, "..", "nucleo");
  const candidatos =
    process.platform === "win32"
      ? [join(pastaNucleo, ".venv", "Scripts", "python.exe")]
      : [join(pastaNucleo, ".venv", "bin", "python3"), join(pastaNucleo, ".venv", "bin", "python")];
  const python = candidatos.find((caminho) => existsSync(caminho)) ?? "python3";

  return { comando: python, args: ["-m", "mapasfacil_nucleo", "stdio"], cwd: pastaNucleo };
}

/** Caminho do `arcpy_job.py` na instalação (F1-11: ao lado do .exe do app). */
export function localizarArcpyJob(empacotado: boolean): string | null {
  if (!empacotado) return null;
  const candidato = join(process.resourcesPath, "..", "arcpy_job.py");
  return existsSync(candidato) ? candidato : null;
}
