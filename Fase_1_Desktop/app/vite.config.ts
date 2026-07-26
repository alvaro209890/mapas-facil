import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// O renderer roda dentro do Electron (file://), então base relativa.
// A configuração dos testes vive em `vitest.config.ts`: o `defineConfig` do
// Vitest 2 carrega os tipos do Vite 5 e brigaria com o Vite 6 usado no build.
export default defineConfig({
  base: "./",
  plugins: [react()],
  build: {
    outDir: "dist/renderer",
    emptyOutDir: true,
    sourcemap: true,
  },
  server: {
    port: 5273,
    strictPort: true,
  },
});
