// Tema da interface. Escuro é o default do produto (D15 / AP-08); claro é opção
// explícita do usuário, guardada em `config.json` (chave `tema`).
//
// `tokens.css` lê o tema de `:root[data-tema="claro"]`, então a única coisa que
// este módulo faz é escrever `document.documentElement.dataset.tema`.

export type Tema = "escuro" | "claro";

export const TEMA_PADRAO: Tema = "escuro";

export function ehTema(valor: unknown): valor is Tema {
  return valor === "escuro" || valor === "claro";
}

export function aplicarTema(tema: Tema): void {
  if (typeof document === "undefined") return;
  document.documentElement.dataset.tema = tema;
}
