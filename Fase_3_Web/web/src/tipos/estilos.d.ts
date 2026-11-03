/**
 * Módulos CSS (CSS Modules) — o Vite resolve em runtime, o `tsc` precisa da declaração.
 * Sem isto, todo componente herdado do desktop que importa `*.module.css` quebra o
 * `typecheck` com TS2307.
 */
declare module '*.module.css' {
  const classes: Record<string, string>;
  export default classes;
}

declare module '*.css';
