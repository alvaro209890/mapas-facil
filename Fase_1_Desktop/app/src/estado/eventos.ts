// Assinatura dos eventos NDJSON que o núcleo emite (F1-01 §Eventos).
//
// Estado real do núcleo nesta versão: **só `job.progresso` é emitido** (A9). Os
// demais estão aqui como contrato, sem consumidor — a UI não simula nenhum deles
// (AP-07: animação só existe amarrada a evento real).

export interface EnvelopeEvento<D = Record<string, unknown>> {
  v: number;
  id: string;
  tipo: "evt";
  evento: string;
  dados: D;
}

/** As 10 etapas de `mapa.gerar`, na ordem do contrato, com o rótulo da UI. */
export const ETAPAS_JOB = [
  { id: "validando_spec", rotulo: "validando a especificação" },
  { id: "resolvendo_camadas_locais", rotulo: "resolvendo camadas locais" },
  { id: "baixando_externas", rotulo: "baixando camadas externas" },
  { id: "calculando_quantitativos", rotulo: "calculando quantitativos" },
  { id: "gerando_tabela", rotulo: "gerando a tabela" },
  { id: "preparando_template", rotulo: "preparando o template" },
  { id: "aplicando_layout", rotulo: "aplicando o layout" },
  { id: "salvando_mxd", rotulo: "salvando o .mxd" },
  { id: "exportando_pdf", rotulo: "exportando o PDF" },
  { id: "validando_saida", rotulo: "validando a saída" },
] as const;

export type EtapaJob = (typeof ETAPAS_JOB)[number]["id"];

export function indiceDaEtapa(etapa: string): number {
  return ETAPAS_JOB.findIndex((e) => e.id === etapa);
}

export function rotuloDaEtapa(etapa: string): string {
  return ETAPAS_JOB.find((e) => e.id === etapa)?.rotulo ?? etapa;
}

/**
 * `job.progresso` — emitido **ao concluir** uma etapa: `etapa` é a que terminou e
 * `pct` é o acumulado do job. Nas etapas de camada vêm eventos intermediários com
 * `item` = `camadas[].id`. `pct` nunca anda para trás.
 */
export interface DadosJobProgresso {
  etapa: EtapaJob;
  pct: number;
  item?: string;
}

// ---------------------------------------------------------------- ainda não emitidos
export interface DadosJobLog {
  linha: string;
}
export interface DadosJobArtefatoParcial {
  tipo: "camada" | "tabela_png" | "preview_png" | "pdf";
  caminho: string;
  etapa: EtapaJob;
  camada_id?: string;
  ordem?: number;
  pct?: number;
}
export interface DadosWorkspaceMudou {
  mudancas: unknown[];
}
export interface DadosChatDelta {
  texto: string;
}
export interface DadosChatTool {
  trace_id: string;
  tool: string;
  fase: "inicio" | "fim";
  args_resumo?: string;
  resultado_resumo?: string;
  ms?: number;
  ok?: boolean;
}
export interface DadosMapspecAtualizado {
  id: string;
  versao: number;
  diff: unknown;
}
export interface DadosAviso {
  codigo: string;
  mensagem: string;
}

export type EventoNucleo =
  | (EnvelopeEvento<DadosJobProgresso> & { evento: "job.progresso" })
  | (EnvelopeEvento<DadosJobLog> & { evento: "job.log" })
  | (EnvelopeEvento<DadosJobArtefatoParcial> & { evento: "job.artefato_parcial" })
  | (EnvelopeEvento<DadosWorkspaceMudou> & { evento: "workspace.mudou" })
  | (EnvelopeEvento<DadosChatDelta> & { evento: "chat.delta" })
  | (EnvelopeEvento<DadosChatTool> & { evento: "chat.tool" })
  | (EnvelopeEvento<DadosMapspecAtualizado> & { evento: "mapspec.atualizado" })
  | (EnvelopeEvento<DadosAviso> & { evento: "aviso" });

export function ehJobProgresso(
  evento: EnvelopeEvento<Record<string, unknown>>,
): evento is EnvelopeEvento<DadosJobProgresso> & { evento: "job.progresso" } {
  if (evento.evento !== "job.progresso") return false;
  const { etapa, pct } = evento.dados;
  return typeof etapa === "string" && indiceDaEtapa(etapa) >= 0 && typeof pct === "number";
}
