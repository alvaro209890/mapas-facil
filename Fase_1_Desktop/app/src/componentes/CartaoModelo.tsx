// CartaoModelo — preview, chip de status e motivo (F1-15). Clique em
// `indisponivel` não dispara nada.

import { CircleAlert, CircleCheck, CircleHelp, TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";

import type { ModeloResumo, StatusModelo } from "../estado/galeria.js";
import { urlPreview } from "../estado/galeria.js";
import estilos from "./CartaoModelo.module.css";

const ROTULO: Record<StatusModelo, string> = {
  pronto: "pronto",
  parcial: "parcial",
  faltam_dados: "faltam dados",
  indisponivel: "indisponível",
};

const ICONE: Record<StatusModelo, ReactNode> = {
  pronto: <CircleCheck size={12} aria-hidden="true" />,
  parcial: <TriangleAlert size={12} aria-hidden="true" />,
  faltam_dados: <CircleAlert size={12} aria-hidden="true" />,
  indisponivel: <CircleHelp size={12} aria-hidden="true" />,
};

export interface PropsCartaoModelo {
  modelo: ModeloResumo;
  aoAbrir: (id: string) => void;
}

export function CartaoModelo({ modelo, aoAbrir }: PropsCartaoModelo) {
  const clicavel = modelo.status !== "indisponivel";
  return (
    <button
      type="button"
      id={`cartao-modelo-${modelo.id}`}
      className={estilos.cartao}
      data-status={modelo.status}
      disabled={!clicavel}
      title={clicavel ? modelo.nome : (modelo.motivo ?? "Modelo indisponível")}
      onClick={() => {
        if (!clicavel) return;
        aoAbrir(modelo.id);
      }}
    >
      <img
        className={estilos.preview}
        src={urlPreview(modelo.preview)}
        alt={`preview de ${modelo.nome}`}
        loading="lazy"
      />
      <span className={estilos.corpo}>
        <span className={estilos.nome}>{modelo.nome}</span>
        <span className={estilos.subtitulo}>{modelo.subtitulo}</span>
        <span className={estilos.linhaStatus}>
          <span className={estilos.chip} data-status={modelo.status}>
            {ICONE[modelo.status]}
            {ROTULO[modelo.status]}
          </span>
        </span>
        {modelo.motivo !== null && modelo.motivo.length > 0 && (
          <span className={estilos.motivo}>{modelo.motivo}</span>
        )}
      </span>
    </button>
  );
}
