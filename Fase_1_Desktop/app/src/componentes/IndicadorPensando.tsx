// A1 — `bloco-raciocinio` (F1-16 §A1).
//
// Liga quando o turno foi despachado; desliga no primeiro `chat.delta` de texto.
// Não é spinner infinito: quem decide se ele aparece é o `PainelChat`, com base
// em estado real do turno (AP-07). Com `prefers-reduced-motion`, os pontos ficam
// parados e sobra o rótulo — a media query de `tokens.css` já corta a animação,
// e aqui a marcação continua a mesma.

import estilos from "./IndicadorPensando.module.css";

export interface PropsIndicadorPensando {
  /** Rótulo ao lado dos pontos; padrão "pensando". */
  rotulo?: string;
}

export function IndicadorPensando({ rotulo = "pensando" }: PropsIndicadorPensando) {
  return (
    <p id="bloco-raciocinio" className={estilos.raiz} role="status" aria-live="polite">
      <span className={estilos.pontos} aria-hidden="true">
        <span className={estilos.ponto} />
        <span className={estilos.ponto} />
        <span className={estilos.ponto} />
      </span>
      <span className={estilos.rotulo}>{rotulo}</span>
    </p>
  );
}
