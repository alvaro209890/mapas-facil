// M8 — estado do `painel-preview`, alimentado **só** por `job.artefato_parcial`.
//
// AP-07 / F1-16 §A5: a Fase 2 (imagem real) só existe quando o evento chega. Sem
// evento, o estado é o inicial e o preview fica na Fase 1 (esqueleto de camadas
// aceso por `job.progresso`) — nada de imagem inventada nem de placeholder que
// finge rasterização.

import { useCallback, useEffect, useState } from "react";

import type {
  DadosJobArtefatoParcial,
  DadosProgressoSerie,
  EnvelopeEvento,
} from "./eventos.js";
import { ehJobArtefatoParcial } from "./eventos.js";
import { api, assinarEventos } from "./ponte.js";

export interface CamadaMaterializada {
  camadaId: string;
  caminho: string;
  ordem?: number;
}

export interface EstadoArtefatos {
  /** `camadas[].id` → shapefile materializado, na ordem em que o núcleo anunciou. */
  camadas: CamadaMaterializada[];
  /** Última rasterização intermediária do mapa (Fase 2). */
  previewPng: string | null;
  /** PNG da tabela de quantitativos. */
  tabelaPng: string | null;
  /** PDF final; presença marca o estado final do preview. */
  pdf: string | null;
  /** Quantos artefatos chegaram — o teste usa para provar que nada foi simulado. */
  total: number;
  /** Contexto da série a que pertence o último artefato. */
  serie: DadosProgressoSerie | null;
}

export const ARTEFATOS_INICIAL: EstadoArtefatos = {
  camadas: [],
  previewPng: null,
  tabelaPng: null,
  pdf: null,
  total: 0,
  serie: null,
};

/** Aplica um `job.artefato_parcial` ao estado anterior. Pura: é o que o teste exercita. */
export function aplicarArtefato(
  anterior: EstadoArtefatos,
  dados: DadosJobArtefatoParcial,
): EstadoArtefatos {
  const base = {
    ...anterior,
    total: anterior.total + 1,
    serie: dados.serie ?? anterior.serie,
  };
  switch (dados.tipo) {
    case "camada": {
      const camadaId = dados.camada_id ?? dados.caminho;
      const outras = base.camadas.filter((c) => c.camadaId !== camadaId);
      return {
        ...base,
        camadas: [
          ...outras,
          {
            camadaId,
            caminho: dados.caminho,
            ...(dados.ordem === undefined ? {} : { ordem: dados.ordem }),
          },
        ],
      };
    }
    case "preview_png":
      return { ...base, previewPng: dados.caminho };
    case "tabela_png":
      return { ...base, tabelaPng: dados.caminho };
    case "pdf":
      return { ...base, pdf: dados.caminho };
    default:
      return anterior;
  }
}

/** Assina `job.artefato_parcial` na ponte. Fora do Electron, no-op silencioso. */
export function useArtefatosJob(): EstadoArtefatos {
  const [estado, setEstado] = useState<EstadoArtefatos>(ARTEFATOS_INICIAL);

  useEffect(() => {
    return assinarEventos((evento: EnvelopeEvento) => {
      if (!ehJobArtefatoParcial(evento)) return;
      setEstado((anterior) => aplicarArtefato(anterior, evento.dados));
    });
  }, []);

  return estado;
}

export interface ImagemArtefato {
  /** `data:` URL pronta para `<img src>`; `null` enquanto não carregou. */
  src: string | null;
  erro: string | null;
}

/**
 * Lê um artefato de imagem **pelo núcleo** (`artefato.ler`), nunca do disco pelo
 * renderer — fronteira 1 de F1-01. Devolve `data:` URL para o `<img>`.
 */
export function useImagemArtefato(caminho: string | null): ImagemArtefato {
  const [imagem, setImagem] = useState<ImagemArtefato>({ src: null, erro: null });

  const carregar = useCallback(async (alvo: string) => {
    const ponte = api();
    if (ponte === undefined) return;
    const resposta = await ponte.chamar("artefato.ler", { caminho: alvo });
    if (!resposta.ok || typeof resposta.resultado !== "object" || resposta.resultado === null) {
      setImagem({ src: null, erro: resposta.erro?.mensagem ?? "falha ao ler o artefato" });
      return;
    }
    const { mime, base64 } = resposta.resultado as { mime?: string; base64?: string };
    if (typeof mime !== "string" || typeof base64 !== "string") {
      setImagem({ src: null, erro: "artefato sem conteúdo" });
      return;
    }
    setImagem({ src: `data:${mime};base64,${base64}`, erro: null });
  }, []);

  useEffect(() => {
    if (caminho === null) {
      setImagem({ src: null, erro: null });
      return;
    }
    let vivo = true;
    void carregar(caminho).catch(() => {
      if (vivo) setImagem({ src: null, erro: "falha ao ler o artefato" });
    });
    return () => {
      vivo = false;
    };
  }, [carregar, caminho]);

  return imagem;
}
