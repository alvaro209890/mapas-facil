// A3 — `cartao-tool` (F1-16 §A3).
//
// Um cartão por `trace_id`: entra com `chat.tool` `fase:"inicio"` e fecha com
// `fase:"fim"`, mostrando duração e ✓/✕. Enquanto pendente o ícone gira; nada
// aqui é temporizado por conta própria — o estado vem do evento (AP-07).

import { Check, Wrench, X } from "lucide-react";

import type { DadosChatTool } from "../estado/eventos.js";
import estilos from "./CartaoTool.module.css";

export interface EstadoTool {
  traceId: string;
  tool: string;
  fase: "inicio" | "fim";
  argsResumo?: string;
  resultadoResumo?: string;
  ms?: number;
  ok?: boolean;
  /** Turno cancelado antes de a tool responder (F1-16 §A6). */
  cancelada?: boolean;
}

/** Reduz `chat.tool` a um cartão por `trace_id`. Pura: é o que o teste exercita. */
export function aplicarEventoTool(anterior: EstadoTool[], dados: DadosChatTool): EstadoTool[] {
  const existente = anterior.find((t) => t.traceId === dados.trace_id);
  const atualizado: EstadoTool = {
    traceId: dados.trace_id,
    tool: dados.tool,
    fase: dados.fase,
    ...(dados.args_resumo === undefined
      ? existente?.argsResumo === undefined
        ? {}
        : { argsResumo: existente.argsResumo }
      : { argsResumo: dados.args_resumo }),
    ...(dados.resultado_resumo === undefined ? {} : { resultadoResumo: dados.resultado_resumo }),
    ...(dados.ms === undefined ? {} : { ms: dados.ms }),
    ...(dados.ok === undefined ? {} : { ok: dados.ok }),
  };
  if (existente === undefined) return [...anterior, atualizado];
  return anterior.map((t) => (t.traceId === dados.trace_id ? { ...t, ...atualizado } : t));
}

/** Marca como cancelado o que ficou pendente quando o usuário parou o turno. */
export function cancelarPendentes(anterior: EstadoTool[]): EstadoTool[] {
  return anterior.map((t) => (t.fase === "inicio" ? { ...t, cancelada: true } : t));
}

/** `1,2 s` / `840 ms` em pt-BR — número de tool nunca aparece como `1.2s`. */
export function formatarDuracao(ms: number): string {
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} s`;
}

function limitar(texto: string, max = 80): string {
  const limpo = texto.replace(/\s+/g, " ").trim();
  return limpo.length <= max ? limpo : `${limpo.slice(0, max - 1)}…`;
}

export function CartaoTool({ estado }: { estado: EstadoTool }) {
  const pendente = estado.fase === "inicio" && estado.cancelada !== true;
  const falhou = estado.fase === "fim" && estado.ok === false;

  return (
    <article
      className={estilos.cartao}
      data-tool={estado.tool}
      data-fase={estado.cancelada === true ? "cancelada" : estado.fase}
      data-ok={estado.ok === undefined ? undefined : String(estado.ok)}
    >
      <span className={estilos.icone} data-pendente={pendente ? "sim" : "nao"} aria-hidden="true">
        {falhou ? <X size={13} /> : estado.fase === "fim" ? <Check size={13} /> : <Wrench size={13} />}
      </span>
      <span className={estilos.nome}>{estado.tool}</span>
      {estado.argsResumo !== undefined && estado.argsResumo !== "" && (
        <span className={estilos.args}>{limitar(estado.argsResumo)}</span>
      )}
      <span className={estilos.status}>
        {estado.cancelada === true
          ? "cancelada"
          : estado.fase === "inicio"
            ? "executando…"
            : estado.ms === undefined
              ? "pronto"
              : formatarDuracao(estado.ms)}
      </span>
    </article>
  );
}

export function ListaCartoesTool({ tools }: { tools: EstadoTool[] }) {
  if (tools.length === 0) return null;
  return (
    <div className={estilos.lista} aria-label="ferramentas do turno">
      {tools.map((tool) => (
        <CartaoTool key={tool.traceId} estado={tool} />
      ))}
    </div>
  );
}
