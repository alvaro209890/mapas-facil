// Configuração dos testes do app. Sem o plugin do React de propósito: o JSX é
// transformado pelo esbuild do Vite com o `jsx: "react-jsx"` do tsconfig, e o Fast
// Refresh não serve para nada em teste.
//
// `css: true` porque os componentes usam CSS Modules — sem isso `estilos.barra`
// viria `undefined` e o teste passaria por engano.
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    include: ["tests/**/*.test.{ts,tsx}"],
    css: true,
  },
});
