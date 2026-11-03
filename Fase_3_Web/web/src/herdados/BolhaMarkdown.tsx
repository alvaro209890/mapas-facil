/**
 * HERDADO de `Fase_1_Desktop/app/src/componentes/BolhaMarkdown.tsx` (W6-01).
 *
 * Copiado com o mínimo de mudança: só o caminho dos imports (os tipos vêm de
 * `./tipos.ts` em vez das stores do desktop) e este cabeçalho. A proveniência fica
 * registrada porque o desktop continua sendo a referência visual: mudança de estilo
 * aqui deve ser pensada também lá, ou assumida como divergência.
 */
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import estilos from "./BolhaMarkdown.module.css";

export interface PropsBolhaMarkdown {
  markdown: string;
  streaming?: boolean;
  cancelada?: boolean;
}

export function BolhaMarkdown({
  markdown,
  streaming = false,
  cancelada = false,
}: PropsBolhaMarkdown) {
  return (
    <article
      className={estilos.bolha}
      data-papel="assistente"
      data-streaming={streaming ? "sim" : undefined}
    >
      <span className={estilos.papel}>assistente</span>
      <div className={estilos.md}>
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            a: ({ children, ...props }) => (
              <a {...props} target="_blank" rel="noreferrer">
                {children}
              </a>
            ),
          }}
        >
          {markdown}
        </ReactMarkdown>
        {streaming && <span className={estilos.cursor} aria-hidden="true" />}
      </div>
      {cancelada && <p className={estilos.interrompida}>resposta interrompida por você</p>}
    </article>
  );
}
