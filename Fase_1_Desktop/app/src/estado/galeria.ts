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
  tipo_execucao: "mapspec" | "analise_de_area";
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
  executandoSerie: boolean;
  resultadoSerie: Record<string, unknown> | null;
}

const INICIAL: EstadoGaleria = {
  situacao: "idle",
  modelos: [],
  detalhe: null,
  mapspecMontado: null,
  avisosMontagem: [],
  erro: null,
  executandoSerie: false,
  resultadoSerie: null,
};

export function useGaleria(): EstadoGaleria & {
  listar: () => Promise<void>;
  detalhar: (modeloId: string) => Promise<void>;
  montar: (modeloId: string, sobrescritas?: Record<string, unknown>) => Promise<boolean>;
  executarSerie: () => Promise<boolean>;
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
    const resposta = await ponte.chamar("galeria.listar", { saidas_pedidas: ["pdf"] });
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
    const resposta = await ponte.chamar("galeria.detalhar", {
      modelo_id: modeloId,
      saidas_pedidas: ["pdf"],
    });
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
      sobrescritas: sobrescritas ?? { saidas: ["pdf"] },
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

  const executarSerie = useCallback(async () => {
    const ponte = api();
    if (ponte === undefined) return false;
    setEstado((a) => ({ ...a, executandoSerie: true, resultadoSerie: null, erro: null }));
    try {
      const resposta = await ponte.chamar("analise.executar", {});
      if (!resposta.ok || typeof resposta.resultado !== "object" || resposta.resultado === null) {
        setEstado((a) => ({
          ...a,
          erro: resposta.erro ?? { codigo: "NU-240", mensagem: "A série não pôde ser gerada." },
        }));
        return false;
      }
      setEstado((a) => ({
        ...a,
        resultadoSerie: resposta.resultado as Record<string, unknown>,
        erro: null,
      }));
      return true;
    } finally {
      setEstado((a) => ({ ...a, executandoSerie: false }));
    }
  }, []);

  const limparDetalhe = useCallback(() => {
    setEstado((a) => ({ ...a, detalhe: null, mapspecMontado: null, avisosMontagem: [] }));
  }, []);

  return { ...estado, listar, detalhar, montar, executarSerie, limparDetalhe };
}

/** Caminho servido pelo Vite a partir de `app/public/galeria/`.
 *
 * **Relativo, nunca `/galeria/…`**: o renderer roda sob `file://` no app
 * empacotado (`vite.config.ts` usa `base: "./"` pelo mesmo motivo), e um
 * caminho absoluto resolveria para a raiz do disco — preview quebrado em
 * produção e verde no dev server. */
export function urlPreview(preview: string): string {
  const nome = preview.split("/").pop() ?? preview;
  return `./galeria/${nome}`;
}
