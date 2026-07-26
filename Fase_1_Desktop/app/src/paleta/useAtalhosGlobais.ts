// Atalhos globais de F1-02 / F1-16. A paleta (`Ctrl+K`) e o Esc (fecha a paleta
// antes de qualquer outra coisa) vivem aqui; ações cujo marco ainda não existe
// disparam o callback `aoIndisponivel` com uma mensagem honesta — sem no-op mudo.

import { useEffect, useRef } from "react";

export interface AcoesAtalho {
  abrirPaleta: () => void;
  fecharPaleta: () => void;
  paletaAberta: boolean;
  preferenciasAbertas: boolean;
  fecharPreferencias: () => void;
  conectarPasta: () => void;
  verificarAmbiente: () => void;
  abrirPreferencias: () => void;
  /** Ctrl+N / Ctrl+F / Ctrl+Enter enquanto M6/M7 não existem. */
  aoIndisponivel: (mensagem: string) => void;
}

function ehModificador(evento: KeyboardEvent): boolean {
  return evento.ctrlKey || evento.metaKey;
}

export function useAtalhosGlobais(acoes: AcoesAtalho): void {
  const ref = useRef(acoes);
  ref.current = acoes;

  useEffect(() => {
    const ouvinte = (evento: KeyboardEvent) => {
      const atual = ref.current;

      if (evento.key === "Escape") {
        if (atual.preferenciasAbertas) {
          evento.preventDefault();
          atual.fecharPreferencias();
          return;
        }
        if (atual.paletaAberta) {
          evento.preventDefault();
          atual.fecharPaleta();
        }
        // Cancelar turno (Esc com chat ativo) é M7 — sem turno aberto, nada a fazer.
        return;
      }

      if (!ehModificador(evento) && evento.key === "F1") {
        evento.preventDefault();
        atual.verificarAmbiente();
        return;
      }

      if (!ehModificador(evento)) return;

      const tecla = evento.key.toLowerCase();

      if (tecla === "k") {
        evento.preventDefault();
        if (atual.paletaAberta) atual.fecharPaleta();
        else atual.abrirPaleta();
        return;
      }
      if (tecla === "o") {
        evento.preventDefault();
        atual.conectarPasta();
        return;
      }
      if (tecla === ",") {
        evento.preventDefault();
        atual.abrirPreferencias();
        return;
      }
      if (tecla === "n") {
        evento.preventDefault();
        atual.aoIndisponivel("Nova conversa chega com a persistência de chats (M6).");
        return;
      }
      if (tecla === "f") {
        evento.preventDefault();
        atual.aoIndisponivel("Busca no histórico chega com a persistência de chats (M6).");
        return;
      }
      if (tecla === "enter") {
        const alvo = evento.target as HTMLElement | null;
        const digitando =
          alvo !== null &&
          (alvo.tagName === "TEXTAREA" || alvo.isContentEditable);
        if (!digitando) {
          evento.preventDefault();
          atual.aoIndisponivel("Enviar mensagem depende do agente (M7).");
        }
      }
    };

    window.addEventListener("keydown", ouvinte);
    return () => window.removeEventListener("keydown", ouvinte);
  }, []);
}
