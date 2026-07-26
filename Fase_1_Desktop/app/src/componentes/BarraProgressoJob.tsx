// C6 — `barra-progresso-job` (F1-02 §painel-chat, F1-16 §A4).
//
// Consome **só** `job.progresso` (A9). Cancelar geração usa `mapa.cancelar` (A10).
// Regras que este componente obedece, e que o teste cobre:
//   * sem evento → "gerando…", sem barra e sem porcentagem (AP-07);
//   * `pct` vem do evento, nunca de timer ou interpolação;
//   * 10 segmentos nomeados em português, na ordem do contrato;
//   * `role="progressbar"` com `aria-valuenow` (F1-16 §Acessibilidade);
//   * cancelar o job é botão próprio — nunca o mesmo do `Esc` do turno (F1-02).

import { ETAPAS_JOB, rotuloDaEtapa } from "../estado/eventos.js";
import type { EstadoProgressoJob } from "../estado/progressoJob.js";
import { useProgressoJob } from "../estado/progressoJob.js";
import estilos from "./BarraProgressoJob.module.css";

export interface PropsBarraProgressoJob {
  /**
   * Um `mapa.gerar` foi despachado e ainda não respondeu. Enquanto nenhum evento
   * chegou, a barra existe mas mostra "gerando…" sem número.
   */
  ativo?: boolean;
  /** Cancelar **o job** (`mapa.cancelar`, R19). Sem handler, o botão não aparece. */
  onCancelar?: () => void;
}

type EstadoSegmento = "concluida" | "ativa" | "pendente";

function estadoDoSegmento(indice: number, progresso: EstadoProgressoJob): EstadoSegmento {
  if (indice < progresso.concluidas) return "concluida";
  if (indice === progresso.indice && progresso.concluidas <= indice) return "ativa";
  return "pendente";
}

export function BarraProgressoJob({ ativo = false, onCancelar }: PropsBarraProgressoJob) {
  const progresso = useProgressoJob();
  if (!ativo && progresso === null) return null;

  return (
    <div id="barra-progresso-job" className={estilos.barra}>
      {progresso === null ? (
        <p className={estilos.semEvento}>gerando…</p>
      ) : (
        <>
          <div
            className={estilos.trilha}
            role="progressbar"
            aria-label="progresso da geração do mapa"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={progresso.pct}
            aria-valuetext={`${progresso.pct}% · ${rotuloDaEtapa(progresso.etapa)}`}
          >
            {ETAPAS_JOB.map((etapa, indice) => (
              <span
                key={etapa.id}
                className={estilos.segmento}
                style={{ flexGrow: etapa.peso, flexBasis: 0 }}
                data-etapa={etapa.id}
                data-estado={estadoDoSegmento(indice, progresso)}
                title={etapa.rotulo}
              />
            ))}
          </div>
          <p className={estilos.linha}>
            <span>{rotuloDaEtapa(progresso.etapa)}</span>
            {progresso.item !== undefined && (
              <span className={`${estilos.item} mf-num`}>· {progresso.item}</span>
            )}
            <span className={`${estilos.pct} mf-num`}>{progresso.pct}%</span>
          </p>
        </>
      )}
      {onCancelar !== undefined && (
        <button type="button" className={estilos.cancelar} onClick={onCancelar}>
          Cancelar geração
        </button>
      )}
    </div>
  );
}
