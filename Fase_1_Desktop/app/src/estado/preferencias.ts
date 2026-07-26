// Preferências de interface (`config.json`, IPC de `electron/preferencias.ts`).
// Só largura/colapso de painel e tema moram aqui — segredo nenhum (F1-01).
//
// Fora do Electron (vitest, `vite dev` no navegador) a API não existe: o estado
// vive só em memória e nada é gravado. Nunca inventamos um valor "salvo".

import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "./ponte.js";

export type PainelLateral = "barraChats" | "workspace" | "painelDireito";

export interface LimitePainel {
  min: number;
  max: number;
  padrao: number;
}

/** Larguras em px. O `painel-chat` não entra: ele é o que sobra e nunca some (F1-02). */
export const LIMITES_PAINEIS: Record<PainelLateral, LimitePainel> = {
  barraChats: { min: 180, max: 360, padrao: 240 },
  workspace: { min: 220, max: 480, padrao: 300 },
  painelDireito: { min: 280, max: 640, padrao: 380 },
};

export interface EstadoPaineis {
  larguras: Record<PainelLateral, number>;
  colapsados: Record<PainelLateral, boolean>;
}

export const CHAVE_PAINEIS = "paineis";

export const PAINEIS_PADRAO: EstadoPaineis = {
  larguras: {
    barraChats: LIMITES_PAINEIS.barraChats.padrao,
    workspace: LIMITES_PAINEIS.workspace.padrao,
    painelDireito: LIMITES_PAINEIS.painelDireito.padrao,
  },
  colapsados: { barraChats: false, workspace: false, painelDireito: false },
};

export function limitar(painel: PainelLateral, largura: number): number {
  const { min, max } = LIMITES_PAINEIS[painel];
  if (!Number.isFinite(largura)) return LIMITES_PAINEIS[painel].padrao;
  return Math.round(Math.min(max, Math.max(min, largura)));
}

/** Lê o que veio do `config.json` sem confiar nele: arquivo editado à mão não quebra o layout. */
export function paineisDePreferencias(brutas: Record<string, unknown>): EstadoPaineis {
  const guardado = brutas[CHAVE_PAINEIS];
  if (typeof guardado !== "object" || guardado === null) return PAINEIS_PADRAO;

  const { larguras, colapsados } = guardado as Partial<EstadoPaineis>;
  const saida: EstadoPaineis = {
    larguras: { ...PAINEIS_PADRAO.larguras },
    colapsados: { ...PAINEIS_PADRAO.colapsados },
  };

  for (const painel of Object.keys(LIMITES_PAINEIS) as PainelLateral[]) {
    const largura = larguras?.[painel];
    if (typeof largura === "number") saida.larguras[painel] = limitar(painel, largura);
    const colapsado = colapsados?.[painel];
    if (typeof colapsado === "boolean") saida.colapsados[painel] = colapsado;
  }
  return saida;
}

function persistir(estado: EstadoPaineis): void {
  void api()?.gravarPreferencias({ [CHAVE_PAINEIS]: estado });
}

/**
 * Estado dos painéis com persistência. Grava no `config.json` só quando o usuário
 * solta o divisor (`gravar`), não a cada pixel arrastado.
 */
export function usePaineis(): {
  paineis: EstadoPaineis;
  definirLargura: (painel: PainelLateral, largura: number) => void;
  alternarColapso: (painel: PainelLateral) => void;
  gravar: () => void;
} {
  const [paineis, setPaineis] = useState<EstadoPaineis>(PAINEIS_PADRAO);
  const atual = useRef<EstadoPaineis>(PAINEIS_PADRAO);
  atual.current = paineis;

  useEffect(() => {
    let vivo = true;
    void api()
      ?.lerPreferencias()
      .then((brutas) => {
        if (vivo) setPaineis(paineisDePreferencias(brutas));
      });
    return () => {
      vivo = false;
    };
  }, []);

  const gravar = useCallback(() => {
    persistir(atual.current);
  }, []);

  const definirLargura = useCallback((painel: PainelLateral, largura: number) => {
    const anterior = atual.current;
    const proximo: EstadoPaineis = {
      ...anterior,
      larguras: { ...anterior.larguras, [painel]: limitar(painel, largura) },
    };
    atual.current = proximo;
    setPaineis(proximo);
  }, []);

  const alternarColapso = useCallback((painel: PainelLateral) => {
    const anterior = atual.current;
    const proximo: EstadoPaineis = {
      ...anterior,
      colapsados: { ...anterior.colapsados, [painel]: !anterior.colapsados[painel] },
    };
    atual.current = proximo;
    setPaineis(proximo);
    // O colapso é um clique, não um arrasto: persiste na hora.
    persistir(proximo);
  }, []);

  return { paineis, definirLargura, alternarColapso, gravar };
}
