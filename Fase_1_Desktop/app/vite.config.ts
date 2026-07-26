import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// O renderer roda dentro do Electron (file://), então base relativa.
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
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    include: ["tests/**/*.test.{ts,tsx}"],
    css: true,
  },
});
