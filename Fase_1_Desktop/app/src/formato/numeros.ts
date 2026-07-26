// Números da interface em pt-BR (F1-16 §Tipografia, AGENT_BRIEF §Convenções).
// Hectare **sempre** com 4 casas e separador de milhar: `3.823,9033`. Quem
// renderiza aplica `.mf-num` para cair na monoespaçada com `tabular-nums`.

const HECTARES = new Intl.NumberFormat("pt-BR", {
  minimumFractionDigits: 4,
  maximumFractionDigits: 4,
});

const INTEIRO = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });

const DECIMAL_1 = new Intl.NumberFormat("pt-BR", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

/** `3.823,9033` — sem a unidade, que é do componente. `null` vira travessão. */
export function formatarHectares(valor: number | null | undefined): string {
  if (typeof valor !== "number" || !Number.isFinite(valor)) return "—";
  return HECTARES.format(valor);
}

export function formatarInteiro(valor: number | null | undefined): string {
  if (typeof valor !== "number" || !Number.isFinite(valor)) return "—";
  return INTEIRO.format(valor);
}

export function formatarDecimal1(valor: number | null | undefined): string {
  if (typeof valor !== "number" || !Number.isFinite(valor)) return "—";
  return DECIMAL_1.format(valor);
}

/** "1 feição" / "12 feições" — plural certo importa numa tela cheia de números. */
export function contarFeicoes(quantas: number): string {
  return `${formatarInteiro(quantas)} ${quantas === 1 ? "feição" : "feições"}`;
}

/** Data ISO do núcleo/preferências em `dd/mm/aaaa`; entrada inválida vira travessão. */
export function formatarData(iso: string | undefined): string {
  if (typeof iso !== "string" || iso.length === 0) return "—";
  const data = new Date(iso);
  if (Number.isNaN(data.getTime())) return "—";
  return data.toLocaleDateString("pt-BR");
}
