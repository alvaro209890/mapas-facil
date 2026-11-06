import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";

import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

/**
 * O MapLibre 6 procura o worker em `assets/maplibre-gl-worker.mjs`, relativo ao bundle.
 * O Vite não copia esse arquivo (ele não é importado como módulo), então o navegador pedia
 * `/assets/maplibre-gl-worker.mjs?v=6.16.0` e recebia 404 em produção. Copiar no fim do
 * build resolve sem mudar o bundle.
 */
function copiarWorkerMapLibre() {
  return {
    name: "copiar-worker-maplibre",
    apply: "build" as const,
    closeBundle() {
      const origem = resolve("node_modules/maplibre-gl/dist/maplibre-gl-worker.mjs");
      const destino = resolve("dist/assets/maplibre-gl-worker.mjs");
      mkdirSync(dirname(destino), { recursive: true });
      copyFileSync(origem, destino);
    },
  };
}

// O SPA é servido pelo próprio backend (FastAPI) em produção: `base: "/"` e build em `dist/`.
// Em desenvolvimento o proxy manda `/api` para o servidor local (127.0.0.1:3130).
export default defineConfig({
  plugins: [react(), copiarWorkerMapLibre()],
  base: "/",
  server: {
    port: 5273,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:3130",
        changeOrigin: false,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/teste/setup.ts"],
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
    css: false,
  },
});
