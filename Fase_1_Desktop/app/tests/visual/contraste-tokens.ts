// Utilitário WCAG relativo luminance / contraste — para asserts de tokens em C11
// quando o axe no jsdom não consegue calcular color-contrast de verdade.

function canal(valor: number): number {
  const c = valor / 255;
  return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}

export function luminanciaRelativa(hex: string): number {
  const limpo = hex.replace("#", "").trim();
  const completo =
    limpo.length === 3
      ? limpo
          .split("")
          .map((c) => c + c)
          .join("")
      : limpo;
  const n = Number.parseInt(completo, 16);
  const r = (n >> 16) & 255;
  const g = (n >> 8) & 255;
  const b = n & 255;
  return 0.2126 * canal(r) + 0.7152 * canal(g) + 0.0722 * canal(b);
}

/** Razão de contraste WCAG entre dois hex (#rrggbb). */
export function razaoContraste(frente: string, fundo: string): number {
  const l1 = luminanciaRelativa(frente);
  const l2 = luminanciaRelativa(fundo);
  const claro = Math.max(l1, l2);
  const escuro = Math.min(l1, l2);
  return (claro + 0.05) / (escuro + 0.05);
}
