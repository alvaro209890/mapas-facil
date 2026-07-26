// Divisor de painel. Arrastável com o mouse e **operável pelo teclado** — a ordem
// de tabulação segue a ordem visual dos painéis (F1-16 §Acessibilidade).
//
// A largura só é persistida quando o arrasto termina (`aoSoltar`): gravar
// `config.json` a cada pixel escreveria no disco dezenas de vezes por segundo.

import { useCallback, useRef } from "react";

import type { PainelLateral } from "../estado/preferencias.js";
import { LIMITES_PAINEIS } from "../estado/preferencias.js";
import estilos from "./Divisor.module.css";

const PASSO_TECLADO = 16;

export interface PropsDivisor {
  painel: PainelLateral;
  largura: number;
  rotulo: string;
  /** `true` quando o painel fica à direita do divisor: arrastar para a esquerda o alarga. */
  invertido?: boolean;
  aoRedimensionar: (largura: number) => void;
  aoSoltar: () => void;
}

export function Divisor({
  painel,
  largura,
  rotulo,
  invertido = false,
  aoRedimensionar,
  aoSoltar,
}: PropsDivisor) {
  const arrasto = useRef<{ x: number; largura: number } | null>(null);
  const { min, max } = LIMITES_PAINEIS[painel];

  const aoMover = useCallback(
    (evento: React.PointerEvent<HTMLDivElement>) => {
      const inicio = arrasto.current;
      if (inicio === null) return;
      const delta = (evento.clientX - inicio.x) * (invertido ? -1 : 1);
      aoRedimensionar(inicio.largura + delta);
    },
    [aoRedimensionar, invertido],
  );

  const aoPressionar = useCallback(
    (evento: React.PointerEvent<HTMLDivElement>) => {
      arrasto.current = { x: evento.clientX, largura };
      evento.currentTarget.setPointerCapture(evento.pointerId);
    },
    [largura],
  );

  const aoLiberar = useCallback(
    (evento: React.PointerEvent<HTMLDivElement>) => {
      if (arrasto.current === null) return;
      arrasto.current = null;
      if (evento.currentTarget.hasPointerCapture(evento.pointerId)) {
        evento.currentTarget.releasePointerCapture(evento.pointerId);
      }
      aoSoltar();
    },
    [aoSoltar],
  );

  const aoTeclar = useCallback(
    (evento: React.KeyboardEvent<HTMLDivElement>) => {
      const sinal = invertido ? -1 : 1;
      if (evento.key === "ArrowLeft") aoRedimensionar(largura - PASSO_TECLADO * sinal);
      else if (evento.key === "ArrowRight") aoRedimensionar(largura + PASSO_TECLADO * sinal);
      else if (evento.key === "Home") aoRedimensionar(LIMITES_PAINEIS[painel].padrao);
      else return;
      evento.preventDefault();
      aoSoltar();
    },
    [aoRedimensionar, aoSoltar, invertido, largura, painel],
  );

  return (
    <div
      className={estilos.divisor}
      role="separator"
      tabIndex={0}
      aria-orientation="vertical"
      aria-label={`redimensionar ${rotulo}`}
      aria-valuemin={min}
      aria-valuemax={max}
      aria-valuenow={largura}
      data-painel={painel}
      onPointerDown={aoPressionar}
      onPointerMove={aoMover}
      onPointerUp={aoLiberar}
      onPointerCancel={aoLiberar}
      onKeyDown={aoTeclar}
    />
  );
}
