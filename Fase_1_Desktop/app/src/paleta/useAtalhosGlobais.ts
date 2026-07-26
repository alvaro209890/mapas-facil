// Atalhos globais de F1-02 / F1-16. A paleta (`Ctrl+K`) e o Esc (fecha preferências
// / paleta antes de qualquer outra coisa) vivem aqui. Cancelar o **turno** do chat
// com Esc é responsabilidade do `PainelChat` (só ele sabe se há turno ativo) —
// este hook **não** chama `mapa.cancelar` (F1-02: Esc ≠ botão do job).

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
  novaConversa: () => void;
  focarBuscaChats: () => void;
  /** Ações cujo marco ainda não existe — mensagem honesta, sem no-op mudo. */
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
          return;
        }
        // Sem overlay: deixa o PainelChat (turno) ou outros ouvintes reagirem.
        // De propósito **não** cancela o job aqui.
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
        atual.novaConversa();
        return;
      }
      if (tecla === "f") {
        evento.preventDefault();
        atual.focarBuscaChats();
        return;
      }
    };

    window.addEventListener("keydown", ouvinte);
    return () => window.removeEventListener("keydown", ouvinte);
  }, []);
}
