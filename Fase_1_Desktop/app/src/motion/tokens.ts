// Espelho em TS dos tokens de movimento de `estilos/tokens.css` (F1-16 §Movimento).
// Existe para animação controlada em JS; o CSS continua sendo a fonte da verdade —
// se um valor mudar lá, muda aqui no mesmo commit.
//
// Nada aqui gera progresso: duração de animação nunca vira barra de porcentagem
// (AP-07). Quem mostra progresso é `job.progresso`.

export const DURACAO = {
  /** hover, foco */
  d1: 120,
  /** entrada de item, colapso */
  d2: 180,
  /** troca de painel, crossfade de preview */
  d3: 260,
  /** transição de tela (login → app) */
  d4: 420,
} as const;

export const EASING = {
  saida: "cubic-bezier(0.2, 0.8, 0.2, 1)",
  ambos: "cubic-bezier(0.4, 0, 0.2, 1)",
  entrada: "cubic-bezier(0.4, 0, 1, 1)",
} as const;

/** Teto de duração com `prefers-reduced-motion: reduce` (F1-16 §Movimento). */
export const DURACAO_MOVIMENTO_REDUZIDO = 80;

export type ChaveDuracao = keyof typeof DURACAO;

/** Duração efetiva em ms, já respeitando a preferência do sistema. */
export function duracao(chave: ChaveDuracao, movimentoReduzido: boolean): number {
  return movimentoReduzido ? Math.min(DURACAO[chave], DURACAO_MOVIMENTO_REDUZIDO) : DURACAO[chave];
}

/** Máximo de itens que entram animados numa lista (F1-16 §A6). */
export const MAX_ITENS_ANIMADOS = 12;
