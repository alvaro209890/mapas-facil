// Espelho TypeScript do protocolo NDJSON do núcleo (F1-01 §Protocolo Electron ↔ núcleo).
// Uma mensagem JSON por linha, sem framing extra; `stderr` é log.

export const PROTOCOLO_VERSAO = 1;

export interface ErroProtocolo {
  codigo: string;
  mensagem: string;
  detalhes?: Record<string, unknown>;
}

export interface Requisicao {
  v: number;
  id: string;
  tipo: "req";
  metodo: string;
  params: Record<string, unknown>;
}

export interface RespostaOk {
  v: number;
  id: string;
  tipo: "res";
  ok: true;
  resultado: unknown;
}

export interface RespostaErro {
  v: number;
  id: string;
  tipo: "res";
  ok: false;
  erro: ErroProtocolo;
}

export interface Evento {
  v: number;
  id: string;
  tipo: "evt";
  evento: string;
  dados: Record<string, unknown>;
}

export type Resposta = RespostaOk | RespostaErro;
export type MensagemNucleo = Resposta | Evento;

export function ehEvento(mensagem: MensagemNucleo): mensagem is Evento {
  return mensagem.tipo === "evt";
}

export function ehResposta(mensagem: MensagemNucleo): mensagem is Resposta {
  return mensagem.tipo === "res";
}
