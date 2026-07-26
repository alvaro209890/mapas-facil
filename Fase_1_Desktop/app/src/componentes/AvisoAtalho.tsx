// Faixa temporária para atalho cujo marco ainda não existe (C10). Some sozinha.

import { useEffect } from "react";

import estilos from "./AvisoAtalho.module.css";

export interface PropsAvisoAtalho {
  mensagem: string | null;
  aoFechar: () => void;
}

export function AvisoAtalho({ mensagem, aoFechar }: PropsAvisoAtalho) {
  useEffect(() => {
    if (mensagem === null) return;
    const timer = window.setTimeout(aoFechar, 3200);
    return () => window.clearTimeout(timer);
  }, [mensagem, aoFechar]);

  if (mensagem === null) return null;
  return (
    <div className={estilos.aviso} role="status" aria-live="polite">
      {mensagem}
    </div>
  );
}
