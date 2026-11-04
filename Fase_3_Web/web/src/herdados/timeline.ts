/**
 * HERDADO de `Fase_1_Desktop/app/src/componentes/(chat/timeline.ts)` (W6-01).
 *
 * Copiado com o mínimo de mudança: só o caminho dos imports (os tipos vêm de
 * `./tipos.ts` em vez das stores do desktop) e este cabeçalho. A proveniência fica
 * registrada porque o desktop continua sendo a referência visual: mudança de estilo
 * aqui deve ser pensada também lá, ou assumida como divergência.
 */
import { aplicarEventoTool, cancelarPendentes, type EstadoTool } from "./CartaoTool";
import type {
  DadosChatPergunta,
  DadosChatRaciocinio,
  DadosChatTool,
} from "./tipos";

export type BlocoTurno =
  | { tipo: "usuario"; id: string; texto: string }
  | { tipo: "texto"; id: string; markdown: string; streaming?: boolean }
  | { tipo: "tools"; id: string; tools: EstadoTool[] }
  | { tipo: "raciocinio"; id: string; texto: string; streaming?: boolean }
  | { tipo: "pergunta"; id: string; dados: DadosChatPergunta; respondida?: boolean };

export type EventoTimeline =
  | { tipo: "usuario"; dados: { texto: string } }
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
  if (evento.tipo === "usuario") {
    // DIVERGÊNCIA da web: a fala do usuário vira bolha própria na timeline e encerra o
    // streaming do que veio antes (a próxima resposta abre bolha nova).
    if (evento.dados.texto.trim() === "") return anterior;
    return [
      // A fala do usuário responde a qualquer pergunta aberta antes dela.
      ...encerrarStreaming(anterior).map((bloco) =>
        bloco.tipo === "pergunta" && bloco.respondida !== true
          ? { ...bloco, respondida: true }
          : bloco,
      ),
      {
        tipo: "usuario",
        id: idDoProximoBloco(anterior, "usuario"),
        texto: evento.dados.texto,
      },
    ];
  }

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

/** Fecha bolhas e raciocínios que ainda estavam "digitando" (fim de turno). */
export function encerrarStreaming(anterior: BlocoTurno[]): BlocoTurno[] {
  return anterior.map((bloco) =>
    (bloco.tipo === "texto" || bloco.tipo === "raciocinio") && bloco.streaming === true
      ? { ...bloco, streaming: false }
      : bloco,
  );
}

export function cancelarPendentesTimeline(anterior: BlocoTurno[]): BlocoTurno[] {
  return anterior.map((bloco) =>
    bloco.tipo === "tools" ? { ...bloco, tools: cancelarPendentes(bloco.tools) } : bloco,
  );
}
