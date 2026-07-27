#!/usr/bin/env node
/**
 * Copia o onedir do núcleo para `resources-staging/nucleo` (entrada do electron-builder).
 * Pré-requisito: `python packaging/empacotar.py` no diretório do núcleo.
 */
import { cpSync, existsSync, mkdirSync, rmSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const aqui = dirname(fileURLToPath(import.meta.url));
const appDir = resolve(aqui, "..");
const nucleoDist = resolve(appDir, "..", "nucleo", "dist", "nucleo");
const staging = join(appDir, "resources-staging", "nucleo");

if (!existsSync(nucleoDist)) {
  console.error(
    `Núcleo empacotado ausente em ${nucleoDist}.\n` +
      `Rode antes: python ../nucleo/packaging/empacotar.py`,
  );
  process.exit(1);
}

const exeWin = join(nucleoDist, "nucleo.exe");
const exeUnix = join(nucleoDist, "nucleo");
if (!existsSync(exeWin) && !existsSync(exeUnix)) {
  console.error(`Executável nucleo.* não encontrado em ${nucleoDist}`);
  process.exit(1);
}
if (!existsSync(join(nucleoDist, "shared", "templates", "MANIFEST.json"))) {
  console.error("shared/templates ausente no onedir — empacotar.py incompleto.");
  process.exit(1);
}
if (!existsSync(join(nucleoDist, "arcpy_job.py"))) {
  console.error("arcpy_job.py ausente no onedir.");
  process.exit(1);
}

rmSync(join(appDir, "resources-staging"), { recursive: true, force: true });
mkdirSync(dirname(staging), { recursive: true });
cpSync(nucleoDist, staging, { recursive: true });
console.log(`OK: ${staging}`);
