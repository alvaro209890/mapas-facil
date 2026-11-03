import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// O SPA é servido pelo próprio backend (FastAPI) em produção: `base: "/"` e build em `dist/`.
// Em desenvolvimento o proxy manda `/api` para o servidor local (127.0.0.1:3130).
export default defineConfig({
  plugins: [react()],
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
