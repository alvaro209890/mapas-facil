// C6 — estado da `barra-progresso-job`, alimentado **só** por `job.progresso`.
//
// AP-07 / F1-16 §A4: nada aqui interpola `pct` por timer nem inventa etapa. Sem
// evento, o estado é `null` e a UI mostra "gerando…" sem porcentagem. `pct` é
// monotônico — evento fora de ordem não faz a barra andar para trás.

import { useEffect, useState } from "react";

import type { DadosJobProgresso, DadosProgressoSerie, EnvelopeEvento } from "./eventos.js";
import { ETAPAS_JOB, ehJobProgresso, indiceDaEtapa, pctAoConcluir } from "./eventos.js";
import { assinarEventos } from "./ponte.js";

export interface EstadoProgressoJob {
  /** Etapa do último evento aceito. */
  etapa: DadosJobProgresso["etapa"];
  /** Índice da etapa, 0–9. */
  indice: number;
  /** Acumulado do job, 0–100, monotônico. */
  pct: number;
  /** `camadas[].id` que acabou de ficar pronto, quando a etapa reporta item. */
  item?: string;
  /** Quantas das 10 etapas já fecharam. */
  concluidas: number;
  /** A10 — para `mapa.cancelar`. */
  jobId?: string;
  /** Passo estruturado atual da série de 20 mapas. */
  serie?: DadosProgressoSerie;
  /** Últimos passos reais, para a timeline compacta do job. */
  historicoSerie: DadosProgressoSerie[];
}

/**
 * Aplica um `job.progresso` ao estado anterior. Pura: é o que o teste exercita.
 *
 * O evento é emitido **ao concluir** a etapa, com `pct` acumulado; nas etapas de
 * camada vêm eventos intermediários com `item` e `pct` dentro da faixa da etapa,
 * que ainda não a fecham.
 */
export function aplicarProgresso(
  anterior: EstadoProgressoJob | null,
  dados: DadosJobProgresso,
): EstadoProgressoJob {
  const indice = indiceDaEtapa(dados.etapa);
  if (indice < 0) return anterior ?? criarInicial();

  const pct = Math.min(100, Math.max(anterior?.pct ?? 0, Math.max(0, Math.round(dados.pct))));
  const fechou = pct >= pctAoConcluir(dados.etapa);
  const concluidas = Math.max(anterior?.concluidas ?? 0, fechou ? indice + 1 : indice);

  const historicoSerie =
    dados.serie === undefined
      ? (anterior?.historicoSerie ?? [])
      : acrescentarPasso(anterior?.historicoSerie ?? [], dados.serie);

  // Evento atrasado comum não reescreve a etapa. Na série, cada mapa reinicia
  // as dez etapas; o percentual global continua monotônico e é a autoridade.
  if (dados.serie === undefined && anterior !== null && indice < anterior.indice) {
    return { ...anterior, pct, concluidas };
  }

  return {
    etapa: dados.etapa,
    indice,
    pct,
    ...(dados.item === undefined ? {} : { item: dados.item }),
    concluidas,
    historicoSerie,
    ...(dados.serie === undefined ? {} : { serie: dados.serie }),
    ...(dados.job_id !== undefined
      ? { jobId: dados.job_id }
      : anterior?.jobId !== undefined
        ? { jobId: anterior.jobId }
        : {}),
  };
}

function criarInicial(): EstadoProgressoJob {
  return { etapa: ETAPAS_JOB[0].id, indice: 0, pct: 0, concluidas: 0, historicoSerie: [] };
}

function acrescentarPasso(
  anterior: DadosProgressoSerie[],
  passo: DadosProgressoSerie,
): DadosProgressoSerie[] {
  const ultimo = anterior.at(-1);
  if (
    ultimo?.fase === passo.fase &&
    ultimo.mensagem === passo.mensagem &&
    ultimo.indice === passo.indice
  ) {
    return anterior;
  }
  return [...anterior, passo].slice(-8);
}

/** Verdadeiro quando o job chegou ao fim das 10 etapas. */
export function jobConcluido(estado: EstadoProgressoJob | null): boolean {
  return estado !== null && estado.concluidas >= ETAPAS_JOB.length && estado.pct >= 100;
}

/**
 * Assina `job.progresso` na ponte e devolve o estado acumulado. Fora do Electron
 * a assinatura é no-op e o estado fica `null` — nenhum progresso é simulado.
 */
export function useProgressoJob(): EstadoProgressoJob | null {
  const [estado, setEstado] = useState<EstadoProgressoJob | null>(null);

  useEffect(() => {
    return assinarEventos((evento: EnvelopeEvento) => {
      if (!ehJobProgresso(evento)) return;
      setEstado((anterior) => aplicarProgresso(anterior, evento.dados));
    });
  }, []);

  return estado;
}
