// Assinatura dos eventos NDJSON que o núcleo emite (F1-01 §Eventos).
//
// Emitidos hoje: `job.progresso`, `job.artefato_parcial`, `chat.delta`, `chat.tool`,
// `workspace.mudou` (A12). Os demais estão no contrato sem emissor — a UI não
// simula nenhum deles (AP-07).

export interface EnvelopeEvento<D = Record<string, unknown>> {
  v: number;
  id: string;
  tipo: "evt";
  evento: string;
  dados: D;
}

/**
 * As 10 etapas de `mapa.gerar`, na ordem do contrato, com o rótulo da UI.
 *
 * `peso` é a fatia de `pct` que cada etapa vale e **espelha**
 * `nucleo/mapasfacil_nucleo/progresso.py` — os dois têm de somar 100 e mudar juntos.
 */
export const ETAPAS_JOB = [
  { id: "validando_spec", rotulo: "validando a especificação", peso: 3 },
  { id: "resolvendo_camadas_locais", rotulo: "resolvendo camadas locais", peso: 7 },
  { id: "baixando_externas", rotulo: "baixando camadas externas", peso: 20 },
  { id: "calculando_quantitativos", rotulo: "calculando quantitativos", peso: 10 },
  { id: "gerando_tabela", rotulo: "gerando a tabela", peso: 5 },
  { id: "preparando_template", rotulo: "preparando o template", peso: 10 },
  { id: "aplicando_layout", rotulo: "aplicando o layout", peso: 15 },
  { id: "salvando_mxd", rotulo: "salvando o .mxd", peso: 5 },
  { id: "exportando_pdf", rotulo: "exportando o PDF", peso: 15 },
  { id: "validando_saida", rotulo: "validando a saída", peso: 10 },
] as const;

export type EtapaJob = (typeof ETAPAS_JOB)[number]["id"];

export function indiceDaEtapa(etapa: string): number {
  return ETAPAS_JOB.findIndex((e) => e.id === etapa);
}

export function rotuloDaEtapa(etapa: string): string {
  return ETAPAS_JOB.find((e) => e.id === etapa)?.rotulo ?? etapa;
}

/** `pct` acumulado quando a etapa termina: 3, 10, 30, 40, 45, 55, 70, 75, 90, 100. */
export function pctAoConcluir(etapa: string): number {
  const indice = indiceDaEtapa(etapa);
  if (indice < 0) return 0;
  return ETAPAS_JOB.slice(0, indice + 1).reduce((soma, e) => soma + e.peso, 0);
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
  /** A10 — id do job para `mapa.cancelar`. */
  job_id?: string;
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
  mudancas: MudancaWorkspace[];
  /** Índice completo após o reindex — a UI troca o estado sem segunda chamada. */
  workspace: Record<string, unknown>;
}

export type AcaoMudancaWorkspace = "adicionado" | "removido" | "modificado";

export type TipoMudancaWorkspace = "shapefile" | "pdf" | "zip" | "outro";

export interface MudancaWorkspace {
  acao: AcaoMudancaWorkspace;
  caminho: string;
  tipo: TipoMudancaWorkspace;
  papel?: string;
  resumo?: string;
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
/** Uma operação do diff estrutural — mesma forma de `mapspec/diff.py::diff`. */
export interface OperacaoDiffMapspec {
  op: "adicionar" | "remover" | "alterar";
  caminho: string;
  antes?: unknown;
  depois?: unknown;
  nota?: string;
}

/** `diff` de `mapspec.atualizado`: operações estruturadas + resumo em português. */
export interface DiffMapspec {
  operacoes: OperacaoDiffMapspec[];
  total?: number;
  id_antes?: string | null;
  id_depois?: string | null;
  versao_antes?: number | null;
  versao_depois?: number | null;
  /** Linhas prontas para exibir — `agente/edicao.py::descrever_diff`. */
  resumo: string[];
}

export interface DadosMapspecAtualizado {
  id: string;
  versao: number;
  diff: DiffMapspec;
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

/** `job.artefato_parcial` estreitado (M8 / F1-16 §A5 fase 2). */
export type EventoJobArtefatoParcial = EnvelopeEvento<
  Record<string, unknown> & DadosJobArtefatoParcial
> & { evento: "job.artefato_parcial" };

export const TIPOS_ARTEFATO = ["camada", "tabela_png", "preview_png", "pdf"] as const;

export function ehJobArtefatoParcial(
  evento: EnvelopeEvento<Record<string, unknown>>,
): evento is EventoJobArtefatoParcial {
  if (evento.evento !== "job.artefato_parcial") return false;
  const { tipo, caminho, etapa } = evento.dados;
  if (typeof tipo !== "string" || !TIPOS_ARTEFATO.includes(tipo as never)) return false;
  if (typeof caminho !== "string" || caminho === "") return false;
  // Caminho absoluto ou de fuga é bug do núcleo — a UI descarta em vez de exibir.
  if (caminho.startsWith("/") || /^[A-Za-z]:/.test(caminho) || caminho.includes("..")) return false;
  return typeof etapa === "string" && indiceDaEtapa(etapa) >= 0;
}

/** `job.progresso` já estreitado, mantendo o envelope genérico que a ponte entrega. */
export type EventoJobProgresso = EnvelopeEvento<Record<string, unknown> & DadosJobProgresso> & {
  evento: "job.progresso";
};

export function ehJobProgresso(
  evento: EnvelopeEvento<Record<string, unknown>>,
): evento is EventoJobProgresso {
  if (evento.evento !== "job.progresso") return false;
  const { etapa, pct } = evento.dados;
  return typeof etapa === "string" && indiceDaEtapa(etapa) >= 0 && typeof pct === "number";
}

/** `workspace.mudou` estreitado (A12). */
export type EventoWorkspaceMudou = EnvelopeEvento<Record<string, unknown> & DadosWorkspaceMudou> & {
  evento: "workspace.mudou";
};

const ACOES_MUDANCA = ["adicionado", "removido", "modificado"] as const;
const TIPOS_MUDANCA = ["shapefile", "pdf", "zip", "outro"] as const;

export function ehWorkspaceMudou(
  evento: EnvelopeEvento<Record<string, unknown>>,
): evento is EventoWorkspaceMudou {
  if (evento.evento !== "workspace.mudou") return false;
  const { mudancas, workspace } = evento.dados;
  if (!Array.isArray(mudancas) || typeof workspace !== "object" || workspace === null) {
    return false;
  }
  return mudancas.every((item) => {
    if (typeof item !== "object" || item === null) return false;
    const m = item as Partial<MudancaWorkspace>;
    if (typeof m.caminho !== "string" || m.caminho === "") return false;
    if (typeof m.acao !== "string" || !ACOES_MUDANCA.includes(m.acao as never)) return false;
    if (typeof m.tipo !== "string" || !TIPOS_MUDANCA.includes(m.tipo as never)) return false;
    return true;
  });
}

/** `mapspec.atualizado` estreitado (H6/A6 — troca de versão). */
export type EventoMapspecAtualizado = EnvelopeEvento<
  Record<string, unknown> & DadosMapspecAtualizado
> & { evento: "mapspec.atualizado" };

const OPS_DIFF = ["adicionar", "remover", "alterar"] as const;

export function ehMapspecAtualizado(
  evento: EnvelopeEvento<Record<string, unknown>>,
): evento is EventoMapspecAtualizado {
  if (evento.evento !== "mapspec.atualizado") return false;
  const { id, versao, diff } = evento.dados;
  if (typeof id !== "string" || id === "") return false;
  if (typeof versao !== "number") return false;
  if (typeof diff !== "object" || diff === null) return false;
  const { operacoes, resumo } = diff as Partial<DiffMapspec>;
  if (!Array.isArray(operacoes) || !Array.isArray(resumo)) return false;
  return operacoes.every((op) => {
    if (typeof op !== "object" || op === null) return false;
    const o = op as Partial<OperacaoDiffMapspec>;
    return typeof o.caminho === "string" && typeof o.op === "string" && OPS_DIFF.includes(o.op as never);
  });
}
