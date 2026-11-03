/**
 * Tokens de movimento do palco do mapa (W8-08 / W-07 §Coreografia).
 *
 * Centraliza as durações e curvas de transição da câmera, acendimento de camadas
 * e montagem da folha. Segue o contrato do design system de `estilos/tokens.css`.
 *
 * Quando `prefers-reduced-motion: reduce` está ativo, as durações de voos e acendimentos
 * caem para zero e os voos viram saltos instantâneos (`jumpTo`), exceto crossfades
 * que duram no máximo 150 ms.
 */

export interface TokensMotion {
  voo_estado_ms: number;
  voo_municipio_ms: number;
  voo_imovel_ms: number;
  voo_enquadramento_ms: number;
  voo_folha_ms: number;
  voo_min_ms: number;
  voo_max_ms: number;
  camada_acende_ms: number;
  camada_intervalo_min_ms: number;
  raster_revela_ms: number;
  folha_recuo_ms: number;
  elemento_entra_ms: number;
  elemento_intervalo_min_ms: number;
  resultado_crossfade_ms: number;
}

/** Durações canônicas de animação do palco (em milissegundos). */
export const TOKENS_MOTION: TokensMotion = {
  voo_estado_ms: 1600,
  voo_municipio_ms: 1800,
  voo_imovel_ms: 2200,
  voo_enquadramento_ms: 900,
  voo_folha_ms: 1100,
  voo_min_ms: 500,
  voo_max_ms: 2400,
  camada_acende_ms: 520,
  camada_intervalo_min_ms: 180,
  raster_revela_ms: 700,
  folha_recuo_ms: 1100,
  elemento_entra_ms: 360,
  elemento_intervalo_min_ms: 120,
  resultado_crossfade_ms: 240,
};

/** Curvas de aceleração (easings) do design system do Mapas Fácil. */
export const EASINGS = {
  saida: 'cubic-bezier(0.2, 0.8, 0.2, 1)',
  ambos: 'cubic-bezier(0.4, 0, 0.2, 1)',
  entrada: 'cubic-bezier(0.4, 0, 1, 1)',
  /** Curva de voo do MapLibre para aproximação cinematográfica do imóvel. */
  vooCurva: 1.6,
} as const;

/** Teto de crossfade com movimento reduzido (W-07 §Fila item 5). */
export const CROSSFADE_REDUZIDO_MS = 150;

/**
 * Calcula a duração efetiva de um passo considerando a preferência por movimento reduzido.
 *
 * Para passos de câmera e entrada de elementos, o movimento reduzido anula o tempo (0 ms).
 * Apenas transições de opacidade / crossfades mantêm um valor sutil (≤ 150 ms).
 */
export function duracaoEfetiva(
  duracaoBaseMs: number,
  reduzirMovimento: boolean,
  ehCrossfade = false,
): number {
  if (!reduzirMovimento) return duracaoBaseMs;
  if (ehCrossfade) return Math.min(duracaoBaseMs, CROSSFADE_REDUZIDO_MS);
  return 0;
}
