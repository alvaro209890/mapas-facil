// CartaoModelo — preview, chip de status e motivo (F1-15). Clique em
// `indisponivel` não dispara nada.
//
// O preview tem três estados visuais reais, nunca um ícone de imagem quebrada:
// esqueleto enquanto carrega, imagem quando chega, e um marcador tipografado
// quando o arquivo não existe.

import { CircleAlert, CircleCheck, CircleHelp, ImageOff, TriangleAlert } from "lucide-react";
import { useState, type ReactNode } from "react";

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
  /** A6 — cartão selecionado: `scale(1.02)` + borda de acento em `--mf-dur-1`. */
  selecionado?: boolean;
  /** Posição na grade — escalona a entrada para a lista não aparecer em bloco. */
  indice?: number;
}

type EstadoPreview = "carregando" | "pronto" | "falhou";

export function CartaoModelo({
  modelo,
  aoAbrir,
  selecionado = false,
  indice = 0,
}: PropsCartaoModelo) {
  const [preview, setPreview] = useState<EstadoPreview>("carregando");
  const clicavel = modelo.status !== "indisponivel";
  return (
    <button
      type="button"
      id={`cartao-modelo-${modelo.id}`}
      className={estilos.cartao}
      data-status={modelo.status}
      data-selecionado={selecionado ? "sim" : "nao"}
      aria-pressed={selecionado}
      disabled={!clicavel}
      title={clicavel ? modelo.nome : (modelo.motivo ?? "Modelo indisponível")}
      // Cascata de entrada: 40 ms por cartão, teto de 6 para a última linha não
      // ficar esperando meio segundo.
      style={{ animationDelay: `${Math.min(indice, 6) * 40}ms` }}
      onClick={() => {
        if (!clicavel) return;
        aoAbrir(modelo.id);
      }}
    >
      <span className={estilos.moldura} data-preview={preview}>
        {preview === "falhou" ? (
          <span className={estilos.semPreview}>
            <ImageOff size={20} aria-hidden="true" />
            <span className={estilos.semPreviewTexto}>sem preview</span>
          </span>
        ) : (
          <img
            className={estilos.preview}
            src={urlPreview(modelo.preview)}
            alt={`preview de ${modelo.nome}`}
            loading="lazy"
            onLoad={() => setPreview("pronto")}
            onError={() => setPreview("falhou")}
          />
        )}
        <span className={estilos.veu} aria-hidden="true" />
      </span>
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
