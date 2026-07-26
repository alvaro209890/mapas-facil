// H6 — estado da `linha-versoes`, alimentado **só** por `mapspec.atualizado`.
//
// AP-07 / F1-16 §A6: sem o evento, não existe versão nenhuma para navegar — o
// componente nem aparece. Nada aqui infere versão por contagem de mensagens ou
// por timer; cada versão do histórico é exatamente um `mapspec.atualizado` que
// chegou pela ponte.

import { useEffect, useState } from "react";

import type { DadosMapspecAtualizado, EnvelopeEvento } from "./eventos.js";
import { ehMapspecAtualizado } from "./eventos.js";
import { assinarEventos } from "./ponte.js";

export interface VersaoMapspec {
  id: string;
  versao: number;
  diff: DadosMapspecAtualizado["diff"];
  /** Ordem de chegada — chave estável para animação (crossfade/flash). */
  chave: string;
}

export interface EstadoVersoes {
  /** Histórico na ordem em que os eventos chegaram. */
  versoes: VersaoMapspec[];
  /** Índice em `versoes` sendo exibido; -1 quando não há nenhuma ainda. */
  indiceExibido: number;
}

export const VERSOES_INICIAL: EstadoVersoes = { versoes: [], indiceExibido: -1 };

/**
 * Aplica um `mapspec.atualizado` ao estado anterior — acrescenta ao histórico e
 * passa a exibir a versão que acabou de chegar (a UI segue o que o agente está
 * fazendo agora; o usuário pode voltar com `navegarVersao`). Pura: é o que o
 * teste exercita.
 */
export function aplicarMapspecAtualizado(
  anterior: EstadoVersoes,
  dados: DadosMapspecAtualizado,
): EstadoVersoes {
  // Reemissão do mesmo id (ex.: replay) não duplica a linha do tempo.
  if (anterior.versoes.some((v) => v.id === dados.id)) return anterior;
  const versoes = [
    ...anterior.versoes,
    { id: dados.id, versao: dados.versao, diff: dados.diff, chave: dados.id },
  ];
  return { versoes, indiceExibido: versoes.length - 1 };
}

/** Move a versão exibida por `direcao` (-1 anterior, +1 próxima), sem sair da faixa. */
export function navegarVersao(estado: EstadoVersoes, direcao: -1 | 1): EstadoVersoes {
  if (estado.versoes.length === 0) return estado;
  const indice = Math.min(Math.max(estado.indiceExibido + direcao, 0), estado.versoes.length - 1);
  if (indice === estado.indiceExibido) return estado;
  return { ...estado, indiceExibido: indice };
}

/** Pula direto para um índice do histórico (clique num marcador `vN`). */
export function irParaVersao(estado: EstadoVersoes, indice: number): EstadoVersoes {
  if (indice < 0 || indice >= estado.versoes.length || indice === estado.indiceExibido) {
    return estado;
  }
  return { ...estado, indiceExibido: indice };
}

/** Assina `mapspec.atualizado` na ponte e devolve o histórico + navegação. */
export function useMapspecVersoes(): {
  estado: EstadoVersoes;
  navegar: (direcao: -1 | 1) => void;
  irPara: (indice: number) => void;
} {
  const [estado, setEstado] = useState<EstadoVersoes>(VERSOES_INICIAL);

  useEffect(() => {
    return assinarEventos((evento: EnvelopeEvento) => {
      if (!ehMapspecAtualizado(evento)) return;
      setEstado((anterior) => aplicarMapspecAtualizado(anterior, evento.dados));
    });
  }, []);

  return {
    estado,
    navegar: (direcao) => setEstado((anterior) => navegarVersao(anterior, direcao)),
    irPara: (indice) => setEstado((anterior) => irParaVersao(anterior, indice)),
  };
}
