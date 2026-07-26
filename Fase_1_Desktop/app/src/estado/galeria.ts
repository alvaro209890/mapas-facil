// Estado da galeria no renderer — consome galeria.listar / detalhar / montar_mapspec.

import { useCallback, useEffect, useState } from "react";

import { api } from "./ponte.js";

export type StatusModelo = "pronto" | "parcial" | "faltam_dados" | "indisponivel";

export interface ModeloResumo {
  id: string;
  nome: string;
  subtitulo: string;
  tags: string[];
  orientacao: string;
  preview: string;
  status: StatusModelo;
  motivo: string | null;
  requisitos_faltando: string[];
}

export interface ModeloDetalhe extends ModeloResumo {
  descricao: string;
  template: string;
  saidas_padrao: string[];
  requisitos_camadas: {
    papel: string;
    obrigatorio: boolean;
    nome_no_mxd: string;
    estilo: string;
    ordem: number;
  }[];
  elementos_layout_padrao: Record<string, boolean>;
  mapeamento_sugerido: Record<string, string>;
}

export interface EstadoGaleria {
  situacao: "idle" | "carregando" | "pronta" | "erro";
  modelos: ModeloResumo[];
  detalhe: ModeloDetalhe | null;
  mapspecMontado: Record<string, unknown> | null;
  avisosMontagem: string[];
  erro: { codigo: string; mensagem: string } | null;
}

const INICIAL: EstadoGaleria = {
  situacao: "idle",
  modelos: [],
  detalhe: null,
  mapspecMontado: null,
  avisosMontagem: [],
  erro: null,
};

export function useGaleria(): EstadoGaleria & {
  listar: () => Promise<void>;
  detalhar: (modeloId: string) => Promise<void>;
  montar: (modeloId: string, sobrescritas?: Record<string, unknown>) => Promise<boolean>;
  limparDetalhe: () => void;
} {
  const [estado, setEstado] = useState<EstadoGaleria>(INICIAL);

  const listar = useCallback(async () => {
    const ponte = api();
    if (ponte === undefined) {
      setEstado((a) => ({
        ...a,
        situacao: "erro",
        erro: { codigo: "UI-001", mensagem: "Núcleo indisponível." },
      }));
      return;
    }
    setEstado((a) => ({ ...a, situacao: "carregando", erro: null }));
    const resposta = await ponte.chamar("galeria.listar", {});
    if (!resposta.ok || typeof resposta.resultado !== "object" || resposta.resultado === null) {
      setEstado((a) => ({
        ...a,
        situacao: "erro",
        erro: resposta.erro ?? { codigo: "UI-001", mensagem: "Falha ao listar a galeria." },
      }));
      return;
    }
    const bruto = resposta.resultado as { modelos?: ModeloResumo[] };
    setEstado((a) => ({
      ...a,
      situacao: "pronta",
      modelos: bruto.modelos ?? [],
      erro: null,
    }));
  }, []);

  useEffect(() => {
    void listar();
  }, [listar]);

  const detalhar = useCallback(async (modeloId: string) => {
    const ponte = api();
    if (ponte === undefined) return;
    const resposta = await ponte.chamar("galeria.detalhar", { modelo_id: modeloId });
    if (!resposta.ok || typeof resposta.resultado !== "object" || resposta.resultado === null) {
      setEstado((a) => ({
        ...a,
        erro: resposta.erro ?? { codigo: "NU-230", mensagem: "Não foi possível detalhar o modelo." },
      }));
      return;
    }
    setEstado((a) => ({
      ...a,
      detalhe: resposta.resultado as ModeloDetalhe,
      mapspecMontado: null,
      avisosMontagem: [],
      erro: null,
    }));
  }, []);

  const montar = useCallback(async (modeloId: string, sobrescritas?: Record<string, unknown>) => {
    const ponte = api();
    if (ponte === undefined) return false;
    const resposta = await ponte.chamar("galeria.montar_mapspec", {
      modelo_id: modeloId,
      sobrescritas: sobrescritas ?? {},
    });
    if (!resposta.ok || typeof resposta.resultado !== "object" || resposta.resultado === null) {
      setEstado((a) => ({
        ...a,
        erro: resposta.erro ?? { codigo: "NU-233", mensagem: "Montagem recusada." },
        mapspecMontado: null,
      }));
      return false;
    }
    const bruto = resposta.resultado as {
      mapspec?: Record<string, unknown>;
      avisos?: string[];
    };
    setEstado((a) => ({
      ...a,
      mapspecMontado: bruto.mapspec ?? null,
      avisosMontagem: bruto.avisos ?? [],
      erro: null,
    }));
    return true;
  }, []);

  const limparDetalhe = useCallback(() => {
    setEstado((a) => ({ ...a, detalhe: null, mapspecMontado: null, avisosMontagem: [] }));
  }, []);

  return { ...estado, listar, detalhar, montar, limparDetalhe };
}

/** Caminho servido pelo Vite a partir de `app/public/galeria/`. */
export function urlPreview(preview: string): string {
  const nome = preview.split("/").pop() ?? preview;
  return `/galeria/${nome}`;
}
