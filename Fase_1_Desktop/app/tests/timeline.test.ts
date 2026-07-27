import { describe, expect, it } from "vitest";

import { aplicarEventoTimeline, cancelarPendentesTimeline } from "../src/chat/timeline.js";

describe("aplicarEventoTimeline", () => {
  it("preserva a ordem tool → texto → tool → texto e agrupa só eventos consecutivos", () => {
    let blocos = aplicarEventoTimeline([], {
      tipo: "tool",
      dados: { trace_id: "t1", tool: "listar_arquivos", fase: "inicio" },
    });
    blocos = aplicarEventoTimeline(blocos, {
      tipo: "tool",
      dados: { trace_id: "t1", tool: "listar_arquivos", fase: "fim", ok: true, ms: 2 },
    });
    blocos = aplicarEventoTimeline(blocos, {
      tipo: "texto",
      dados: { texto: "Encontrei os arquivos. " },
    });
    blocos = aplicarEventoTimeline(blocos, {
      tipo: "texto",
      dados: { texto: "Vou inspecionar o ATP." },
    });
    blocos = aplicarEventoTimeline(blocos, {
      tipo: "tool",
      dados: { trace_id: "t2", tool: "inspecionar_shapefile", fase: "inicio" },
    });
    blocos = aplicarEventoTimeline(blocos, {
      tipo: "texto",
      dados: { texto: "A área é **3.823,9033 ha**." },
    });

    expect(blocos.map((bloco) => bloco.tipo)).toEqual(["tools", "texto", "tools", "texto"]);
    expect(blocos[0]).toMatchObject({ tipo: "tools", tools: [{ traceId: "t1", ms: 2 }] });
    expect(blocos[1]).toMatchObject({
      tipo: "texto",
      markdown: "Encontrei os arquivos. Vou inspecionar o ATP.",
    });
  });

  it("mantém raciocínio dedicado e cancela apenas tools pendentes", () => {
    let blocos = aplicarEventoTimeline([], {
      tipo: "raciocinio",
      dados: { texto: "Comparando " },
    });
    blocos = aplicarEventoTimeline(blocos, {
      tipo: "raciocinio",
      dados: { texto: "as camadas." },
    });
    blocos = aplicarEventoTimeline(blocos, {
      tipo: "tool",
      dados: { trace_id: "t1", tool: "comparar", fase: "inicio" },
    });

    expect(blocos).toHaveLength(2);
    expect(blocos[0]).toMatchObject({ tipo: "raciocinio", texto: "Comparando as camadas." });
    expect(cancelarPendentesTimeline(blocos)[1]).toMatchObject({
      tipo: "tools",
      tools: [{ cancelada: true }],
    });
  });
});
