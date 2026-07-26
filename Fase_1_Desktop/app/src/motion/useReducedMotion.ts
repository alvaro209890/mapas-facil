// `prefers-reduced-motion` para o que é animado em JS. O CSS já se vira sozinho
// pela media query de `tokens.css`; isto é para decidir em código (por exemplo,
// não animar a entrada de itens de lista).
//
// No Windows a preferência vem de "Mostrar animações" (Facilidade de Acesso) e o
// Chromium do Electron a reflete na media query — não precisamos de IPC.

import { useEffect, useState } from "react";

export const CONSULTA_MOVIMENTO_REDUZIDO = "(prefers-reduced-motion: reduce)";

function consultar(): MediaQueryList | null {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return null;
  return window.matchMedia(CONSULTA_MOVIMENTO_REDUZIDO);
}

export function useReducedMotion(): boolean {
  const [reduzido, setReduzido] = useState<boolean>(() => consultar()?.matches ?? false);

  useEffect(() => {
    const consulta = consultar();
    if (consulta === null) return;
    const aoMudar = (evento: MediaQueryListEvent) => setReduzido(evento.matches);
    setReduzido(consulta.matches);
    consulta.addEventListener("change", aoMudar);
    return () => consulta.removeEventListener("change", aoMudar);
  }, []);

  return reduzido;
}
