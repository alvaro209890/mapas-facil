// F6 / F1-17 — busca no histórico (`Ctrl+F` → `chat.buscar`).
//
// Enter abre a conversa **na mensagem encontrada** (o `seq` vai com o clique). O
// trecho vem destacado do FTS5 com `[` `]`; aqui esses marcadores viram <mark>,
// sem `innerHTML` — o conteúdo é texto do usuário e não pode virar HTML.

import { useEffect, useRef } from "react";
import { Search, X } from "lucide-react";

import type { ResultadoBusca } from "../estado/conversas.js";
import estilos from "./BuscaChats.module.css";

export interface PropsBuscaChats
 {
  termo: string;
  resultados: ResultadoBusca[] | null;
  /** Foca o campo quando o contador muda (é o que `Ctrl+F` incrementa). */
  foco: number;
  aoDigitar: (termo: string) => void;
  aoLimpar: () => void;
  aoEscolher: (conversationId: string, seq: number) => void;
}

/** `[termo]` do `snippet()` do FTS5 → pedaços marcados, sem interpretar HTML. */
export function partirDestaque(trecho: string): { texto: string; marcado: boolean }[] {
  const partes: { texto: string; marcado: boolean }[] = [];
  let resto = trecho;
  while (resto.length > 0) {
    const abre = resto.indexOf("[");
    const fecha = abre === -1 ? -1 : resto.indexOf("]", abre + 1);
    if (abre === -1 || fecha === -1) {
      partes.push({ texto: resto, marcado: false });
      break;
    }
    if (abre > 0) partes.push({ texto: resto.slice(0, abre), marcado: false });
    partes.push({ texto: resto.slice(abre + 1, fecha), marcado: true });
    resto = resto.slice(fecha + 1);
  }
  return partes.filter((parte) => parte.texto.length > 0);
}

export function BuscaChats({
  termo,
  resultados,
  foco,
  aoDigitar,
  aoLimpar,
  aoEscolher,
}: PropsBuscaChats) {
  const campo = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (foco > 0) campo.current?.focus();
  }, [foco]);

  return (
    <div className={estilos.raiz}>
      <div className={estilos.campo}>
        <Search size={14} aria-hidden="true" />
        <input
          ref={campo}
          type="search"
          value={termo}
          placeholder="Buscar nas conversas (Ctrl+F)"
          aria-label="buscar nas conversas"
          onChange={(evento) => aoDigitar(evento.target.value)}
          onKeyDown={(evento) => {
            if (evento.key === "Escape") aoLimpar();
            if (evento.key === "Enter" && resultados !== null && resultados.length > 0) {
              const primeiro = resultados[0]!;
              aoEscolher(primeiro.conversation_id, primeiro.seq);
            }
          }}
        />
        {termo.length > 0 && (
          <button type="button" onClick={aoLimpar} aria-label="limpar busca">
            <X size={13} aria-hidden="true" />
          </button>
        )}
      </div>

      {resultados !== null && (
        <div className={estilos.resultados}>
          <p className={estilos.contagem} role="status">
            {resultados.length === 0
              ? "Nenhuma mensagem com esse texto no histórico local."
              : `${resultados.length} ${resultados.length === 1 ? "mensagem" : "mensagens"}`}
          </p>
          <ul className={estilos.lista}>
            {resultados.map((resultado) => (
              <li key={resultado.message_id}>
                <button
                  type="button"
                  onClick={() => aoEscolher(resultado.conversation_id, resultado.seq)}
                >
                  <span className={estilos.tituloResultado}>{resultado.title}</span>
                  <span className={estilos.trecho}>
                    {partirDestaque(resultado.trecho_destacado).map((parte, indice) =>
                      parte.marcado ? (
                        <mark key={indice}>{parte.texto}</mark>
                      ) : (
                        <span key={indice}>{parte.texto}</span>
                      ),
                    )}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
