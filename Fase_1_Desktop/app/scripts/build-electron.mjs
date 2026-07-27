// Compila os dois processos do Electron (main e preload) para CommonJS.
// esbuild em vez de mais um plugin de Vite: o main é um bundle pequeno e o
// contrato de saída (dist/electron/*.cjs) é o que o package.json aponta.
import { build } from "esbuild";

const comum = {
  bundle: true,
  platform: "node",
  target: "node20",
  format: "cjs",
  sourcemap: true,
  // electron-updater entra no bundle do main; `electron` fica externo.
  external: ["electron"],
  logLevel: "info",
};

await build({
  ...comum,
  entryPoints: ["electron/main.ts"],
  outfile: "dist/electron/main.cjs",
});

await build({
  ...comum,
  entryPoints: ["electron/preload.ts"],
  outfile: "dist/electron/preload.cjs",
});
