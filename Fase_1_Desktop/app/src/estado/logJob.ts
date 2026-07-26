// Estado de `job.log` e `aviso` — os dois últimos eventos do vocabulário F1-01.
//
// AP-07: sem evento, as duas listas ficam vazias e a UI não desenha nem o
// detalhe de log nem o banner de avisos. Nada aqui inventa linha, nem repete
// aviso que o núcleo não mandou.

import { useEffect, useState } from "react";

import type { DadosAviso, DadosJobLog, EnvelopeEvento } from "./eventos.js";
import { ehAviso, ehJobLog } from "./eventos.js";
import { assinarEventos } from "./ponte.js";

/** Espelha `MAX_LINHAS_LOG` do núcleo — o renderer não guarda mais que o emissor manda. */
export const MAX_LINHAS_MEMORIA = 500;

export interface AvisoJob {
  codigo: string;
  mensagem: string;
  /** Quantas vezes o mesmo (código + mensagem) chegou — evita lista repetida. */
  vezes: number;
}

export interface EstadoLogJob {
  linhas: string[];
  avisos: AvisoJob[];
}

export const LOG_INICIAL: EstadoLogJob = { linhas: [], avisos: [] };

/** Aplica `job.log`. Pura: é o que o teste exercita. */
export function aplicarLog(anterior: EstadoLogJob, dados: DadosJobLog): EstadoLogJob {
  const linhas = [...anterior.linhas, dados.linha];
  return {
    ...anterior,
    linhas: linhas.length > MAX_LINHAS_MEMORIA ? linhas.slice(-MAX_LINHAS_MEMORIA) : linhas,
  };
}

/** Aplica `aviso`, agrupando repetição em `vezes` em vez de empilhar igual. */
export function aplicarAviso(anterior: EstadoLogJob, dados: DadosAviso): EstadoLogJob {
  const indice = anterior.avisos.findIndex(
    (a) => a.codigo === dados.codigo && a.mensagem === dados.mensagem,
  );
  if (indice >= 0) {
    const avisos = [...anterior.avisos];
    avisos[indice] = { ...avisos[indice], vezes: avisos[indice].vezes + 1 };
    return { ...anterior, avisos };
  }
  return {
    ...anterior,
    avisos: [...anterior.avisos, { codigo: dados.codigo, mensagem: dados.mensagem, vezes: 1 }],
  };
}

/** Assina `job.log` + `aviso` na ponte. Fora do Electron, no-op silencioso. */
export function useLogJob(): EstadoLogJob & { limpar: () => void } {
  const [estado, setEstado] = useState<EstadoLogJob>(LOG_INICIAL);

  useEffect(() => {
    return assinarEventos((evento: EnvelopeEvento) => {
      if (ehJobLog(evento)) {
        setEstado((anterior) => aplicarLog(anterior, evento.dados));
        return;
      }
      if (ehAviso(evento)) {
        setEstado((anterior) => aplicarAviso(anterior, evento.dados));
      }
    });
  }, []);

  return { ...estado, limpar: () => setEstado(LOG_INICIAL) };
}
