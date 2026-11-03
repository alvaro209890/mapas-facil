/**
 * Hook para detecção da preferência do usuário por movimento reduzido (W8-08).
 *
 * Consulta `(prefers-reduced-motion: reduce)` via `window.matchMedia`.
 * Seguro em ambientes SSR e testes unitários com jsdom.
 */

import { useEffect, useState } from 'react';

export const MEDIA_QUERY_MOVIMENTO_REDUZIDO = '(prefers-reduced-motion: reduce)';

function checarPreferencia(): boolean {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return false;
  }
  return window.matchMedia(MEDIA_QUERY_MOVIMENTO_REDUZIDO).matches;
}

export function useReducedMotion(): boolean {
  const [reduzido, setReduzido] = useState<boolean>(checarPreferencia);

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
      return;
    }

    const mql = window.matchMedia(MEDIA_QUERY_MOVIMENTO_REDUZIDO);
    const tratarMudanca = (evento: MediaQueryListEvent) => {
      setReduzido(evento.matches);
    };

    setReduzido(mql.matches);

    if (typeof mql.addEventListener === 'function') {
      mql.addEventListener('change', tratarMudanca);
      return () => mql.removeEventListener('change', tratarMudanca);
    } else if (typeof mql.addListener === 'function') {
      // Compatibilidade com navegadores legados
      mql.addListener(tratarMudanca);
      return () => mql.removeListener(tratarMudanca);
    }
  }, []);

  return reduzido;
}
