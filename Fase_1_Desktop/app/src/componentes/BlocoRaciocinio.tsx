import { Brain, ChevronDown } from "lucide-react";
import { useState } from "react";

import estilos from "./BlocoRaciocinio.module.css";

export interface PropsBlocoRaciocinio {
  id: string;
  texto: string;
  streaming?: boolean;
}

export function BlocoRaciocinio({ id, texto, streaming = false }: PropsBlocoRaciocinio) {
  const [expandido, setExpandido] = useState(false);
  if (texto === "") return null;

  const corpoId = `raciocinio-corpo-${id}`;
  return (
    <section
      id={`bloco-raciocinio-${id}`}
      className={estilos.bloco}
      data-bloco="raciocinio"
      data-streaming={streaming ? "sim" : "nao"}
    >
      <button
        type="button"
        className={estilos.cabecalho}
        onClick={() => setExpandido((valor) => !valor)}
        aria-expanded={expandido}
        aria-controls={corpoId}
      >
        <Brain size={14} aria-hidden="true" />
        <span>{streaming ? "Pensando…" : "Raciocínio"}</span>
        <ChevronDown
          className={estilos.chevron}
          data-expandido={expandido ? "sim" : "nao"}
          size={14}
          aria-hidden="true"
        />
      </button>
      {expandido && (
        <p id={corpoId} className={estilos.texto}>
          {texto}
        </p>
      )}
    </section>
  );
}
