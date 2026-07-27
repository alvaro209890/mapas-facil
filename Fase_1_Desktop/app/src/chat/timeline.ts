import { aplicarEventoTool, cancelarPendentes, type EstadoTool } from "../componentes/CartaoTool.js";
import type {
  DadosChatPergunta,
  DadosChatRaciocinio,
  DadosChatTool,
} from "../estado/eventos.js";

export type BlocoTurno =
  | { tipo: "texto"; id: string; markdown: string; streaming?: boolean }
  | { tipo: "tools"; id: string; tools: EstadoTool[] }
  | { tipo: "raciocinio"; id: string; texto: string; streaming?: boolean }
  | { tipo: "pergunta"; id: string; dados: DadosChatPergunta };

export type EventoTimeline =
  | { tipo: "texto"; dados: { texto: string } }
  | { tipo: "tool"; dados: DadosChatTool }
  | { tipo: "raciocinio"; dados: DadosChatRaciocinio }
  | { tipo: "pergunta"; dados: DadosChatPergunta };

function idDoProximoBloco(blocos: BlocoTurno[], tipo: BlocoTurno["tipo"]): string {
  return `${tipo}-${blocos.length + 1}`;
}

/**
 * Reduz eventos do turno para blocos na ordem em que chegaram.
 *
 * Deltas consecutivos compartilham uma bolha e tools consecutivas compartilham
 * um grupo. Qualquer texto ou raciocínio no meio encerra o agrupamento anterior.
 */
export function aplicarEventoTimeline(
  anterior: BlocoTurno[],
  evento: EventoTimeline,
): BlocoTurno[] {
  if (evento.tipo === "texto") {
    if (evento.dados.texto === "") return anterior;
    const ultimo = anterior.at(-1);
    if (ultimo?.tipo === "texto" && ultimo.streaming === true) {
      return anterior.map((bloco, indice) =>
        indice === anterior.length - 1
          ? { ...ultimo, markdown: ultimo.markdown + evento.dados.texto }
          : bloco,
      );
    }
    return [
      ...anterior,
      {
        tipo: "texto",
        id: idDoProximoBloco(anterior, "texto"),
        markdown: evento.dados.texto,
        streaming: true,
      },
    ];
  }

  if (evento.tipo === "raciocinio") {
    if (evento.dados.texto === "") return anterior;
    const ultimo = anterior.at(-1);
    if (ultimo?.tipo === "raciocinio" && ultimo.streaming === true) {
      return anterior.map((bloco, indice) =>
        indice === anterior.length - 1
          ? { ...ultimo, texto: ultimo.texto + evento.dados.texto }
          : bloco,
      );
    }
    return [
      ...anterior,
      {
        tipo: "raciocinio",
        id: idDoProximoBloco(anterior, "raciocinio"),
        texto: evento.dados.texto,
        streaming: true,
      },
    ];
  }

  if (evento.tipo === "pergunta") {
    const ultimo = anterior.at(-1);
    if (ultimo?.tipo === "pergunta") {
      return anterior.map((bloco, indice) =>
        indice === anterior.length - 1 ? { ...ultimo, dados: evento.dados } : bloco,
      );
    }
    return [
      ...anterior,
      {
        tipo: "pergunta",
        id: idDoProximoBloco(anterior, "pergunta"),
        dados: evento.dados,
      },
    ];
  }

  const indiceExistente = anterior.findIndex(
    (bloco) =>
      bloco.tipo === "tools" &&
      bloco.tools.some((tool) => tool.traceId === evento.dados.trace_id),
  );
  if (indiceExistente >= 0) {
    return anterior.map((bloco, indice) =>
      indice === indiceExistente && bloco.tipo === "tools"
        ? { ...bloco, tools: aplicarEventoTool(bloco.tools, evento.dados) }
        : bloco,
    );
  }

  const ultimo = anterior.at(-1);
  if (ultimo?.tipo === "tools") {
    return anterior.map((bloco, indice) =>
      indice === anterior.length - 1
        ? { ...ultimo, tools: aplicarEventoTool(ultimo.tools, evento.dados) }
        : bloco,
    );
  }
  return [
    ...anterior,
    {
      tipo: "tools",
      id: idDoProximoBloco(anterior, "tools"),
      tools: aplicarEventoTool([], evento.dados),
    },
  ];
}

export function cancelarPendentesTimeline(anterior: BlocoTurno[]): BlocoTurno[] {
  return anterior.map((bloco) =>
    bloco.tipo === "tools" ? { ...bloco, tools: cancelarPendentes(bloco.tools) } : bloco,
  );
}
