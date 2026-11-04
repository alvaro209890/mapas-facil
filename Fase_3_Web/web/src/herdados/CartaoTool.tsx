/**
 * HERDADO de `Fase_1_Desktop/app/src/componentes/CartaoTool.tsx` (W6-01).
 *
 * Copiado com o mínimo de mudança: só o caminho dos imports (os tipos vêm de
 * `./tipos.ts` em vez das stores do desktop) e este cabeçalho. A proveniência fica
 * registrada porque o desktop continua sendo a referência visual: mudança de estilo
 * aqui deve ser pensada também lá, ou assumida como divergência.
 */
// A3 — `cartao-tool` (F1-16 §A3).
//
// Um cartão por `trace_id`: entra com `chat.tool` `fase:"inicio"` e fecha com
// `fase:"fim"`, mostrando duração e ✓/✕. Enquanto pendente o ícone gira; nada
// aqui é temporizado por conta própria — o estado vem do evento (AP-07).

import { Check, ChevronDown, CircleStop, Wrench, X } from "lucide-react";
import { useState } from "react";

import type { DadosChatTool } from "./tipos";
import { lerArgs, lerResultado, nomeAmigavel } from "./rotulosTool";
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

export function CartaoTool({ estado }: { estado: EstadoTool }) {
  const [expandido, setExpandido] = useState(false);
  const pendente = estado.fase === "inicio" && estado.cancelada !== true;
  const falhou = estado.fase === "fim" && estado.ok === false;
  const temDetalhes = Boolean(estado.argsResumo || estado.resultadoResumo);
  const detalhesId = `tool-detalhes-${estado.traceId.replace(/[^A-Za-z0-9_-]/g, "-")}`;
  const args = lerArgs(estado.argsResumo);
  const resultado = lerResultado(estado.resultadoResumo);
  const erro = falhou ? (resultado?.erro ?? "a ferramenta falhou") : null;

  return (
    <article
      className={estilos.cartao}
      data-tool={estado.tool}
      data-fase={estado.cancelada === true ? "cancelada" : estado.fase}
      data-ok={estado.ok === undefined ? undefined : String(estado.ok)}
    >
      <button
        type="button"
        className={estilos.resumo}
        onClick={() => temDetalhes && setExpandido((valor) => !valor)}
        aria-expanded={temDetalhes ? expandido : undefined}
        aria-controls={temDetalhes ? detalhesId : undefined}
        disabled={!temDetalhes}
        title={estado.tool}
      >
        <span className={estilos.icone} data-pendente={pendente ? "sim" : "nao"} aria-hidden="true">
          {estado.cancelada === true ? (
            <CircleStop size={13} />
          ) : falhou ? (
            <X size={13} />
          ) : estado.fase === "fim" ? (
            <Check size={13} />
          ) : (
            <Wrench size={13} />
          )}
        </span>
        <span className={estilos.corpo}>
          <span className={estilos.linha}>
            <span className={estilos.nome}>{nomeAmigavel(estado.tool)}</span>
            {args.etiquetas.slice(0, 3).map((etiqueta, indice) => (
              <span key={`${etiqueta.chave}-${indice}`} className={estilos.etiqueta}>
                {etiqueta.chave && <span className={estilos.etiquetaChave}>{etiqueta.chave}</span>}
                {etiqueta.valor}
              </span>
            ))}
            {args.etiquetas.length > 3 && (
              <span className={estilos.etiqueta}>+{args.etiquetas.length - 3}</span>
            )}
          </span>
          {args.motivo && <span className={estilos.motivo}>{args.motivo}</span>}
          {erro && <span className={estilos.erro}>{erro}</span>}
        </span>
        <span className={estilos.status}>
          {estado.cancelada === true
            ? "cancelada"
            : estado.fase === "inicio"
              ? "executando…"
              : estado.ms === undefined
                ? "pronto"
                : formatarDuracao(estado.ms)}
        </span>
        {temDetalhes && (
          <ChevronDown
            className={estilos.chevron}
            data-expandido={expandido ? "sim" : "nao"}
            size={14}
            aria-hidden="true"
          />
        )}
      </button>
      {expandido && temDetalhes && (
        <div id={detalhesId} className={estilos.detalhes}>
          <div>
            <span className={estilos.rotulo}>Ferramenta</span>
            <code className={estilos.codigoInline}>{estado.tool}</code>
          </div>
          {args.etiquetas.length > 0 && (
            <div>
              <span className={estilos.rotulo}>Argumentos</span>
              <dl className={estilos.argumentos}>
                {args.etiquetas.map((etiqueta, indice) => (
                  <div key={`${etiqueta.chave}-${indice}`}>
                    <dt>{etiqueta.chave || "valor"}</dt>
                    <dd>{etiqueta.valor}</dd>
                  </div>
                ))}
              </dl>
            </div>
          )}
          {resultado && (
            <div>
              <span className={estilos.rotulo}>
                Resultado{resultado.codigo ? ` · ${resultado.codigo}` : ""}
              </span>
              <pre className={estilos.codigo}>{resultado.formatado}</pre>
            </div>
          )}
        </div>
      )}
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
