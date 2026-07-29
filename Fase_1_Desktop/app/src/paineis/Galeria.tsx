// painel-galeria — grade de modelos (F1-15 D8).

import { CartaoModelo } from "../componentes/CartaoModelo.js";
import type { ModeloResumo } from "../estado/galeria.js";
import estilos from "./Galeria.module.css";

export interface PropsGaleria {
  modelos: ModeloResumo[];
  situacao: "idle" | "carregando" | "pronta" | "erro";
  erro: { codigo: string; mensagem: string } | null;
  aoAbrir: (id: string) => void;
  ocupado?: boolean;
  /** Modelo cuja montagem alimenta o `painel-preview` (A6). */
  selecionado?: string | null;
}

export function Galeria({
  modelos,
  situacao,
  erro,
  aoAbrir,
  selecionado = null,
  ocupado = false,
}: PropsGaleria) {
  return (
    <div id="painel-galeria" className={estilos.raiz}>
      <div className={estilos.cabecalho}>
        <span className={estilos.titulo}>Galeria de modelos</span>
        <span className={estilos.meta}>{modelos.length} modelos</span>
      </div>
      {situacao === "carregando" && (
        // Esqueleto na forma da grade real: a lista não "salta" quando chega.
        <div className={estilos.grade} aria-hidden="true">
          {Array.from({ length: 4 }, (_, i) => (
            <div
              key={i}
              className={estilos.esqueleto}
              style={{ animationDelay: `${i * 90}ms` }}
            />
          ))}
        </div>
      )}
      {situacao === "carregando" && (
        <p className={estilos.estado} role="status">
          carregando catálogo…
        </p>
      )}
      {erro !== null && (
        <p className={estilos.estado} role="alert">
          <span className="mf-num">{erro.codigo}</span> · {erro.mensagem}
        </p>
      )}
      {situacao === "pronta" && (
        <div className={estilos.grade}>
          {modelos.map((modelo, i) => (
            <CartaoModelo
              key={modelo.id}
              modelo={modelo}
              aoAbrir={aoAbrir}
              selecionado={modelo.id === selecionado}
              indice={i}
              ocupado={ocupado}
            />
          ))}
        </div>
      )}
    </div>
  );
}
