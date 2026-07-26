// H7 — M8: cada animação provada com **evento injetado** pela ponte fake.
//
// A regra que estes testes protegem é AP-07: nenhuma animação existe sem evento
// do núcleo. Por isso todo caso tem duas metades — antes do evento (nada) e
// depois do evento (o estado visual muda).

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { BarraProgressoJob } from "../../src/componentes/BarraProgressoJob.js";
import {
  aplicarEventoTool,
  cancelarPendentes,
  formatarDuracao,
} from "../../src/componentes/CartaoTool.js";
import { LinhaVersoes } from "../../src/componentes/LinhaVersoes.js";
import { ARTEFATOS_INICIAL, aplicarArtefato } from "../../src/estado/artefatos.js";
import { ehJobArtefatoParcial } from "../../src/estado/eventos.js";
import { useMapspecVersoes } from "../../src/estado/mapspecVersoes.js";
import { PainelChat } from "../../src/paineis/PainelChat.js";
import { Preview } from "../../src/paineis/Preview.js";
import { desligarPonteFake, ligarPonteFake } from "../ponte-fake.js";

afterEach(() => {
  cleanup();
  desligarPonteFake();
});

const MAPSPEC = {
  titulo: "Dinâmica 2026",
  camadas: [
    { id: "perimetro", legenda: "Fazenda Harmonia", ordem: 10 },
    { id: "auas", legenda: "Desmate após 2008", ordem: 20 },
    { id: "avn", legenda: "Vegetação nativa", ordem: 30 },
  ],
  elementos_layout: { tabela: true, minimapa: true },
};

const PNG_1x1 =
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==";

// --------------------------------------------------------------------- A2 streaming

describe("A2 — streaming de tokens (chat.delta)", () => {
  it("sem evento não há cursor; com evento o texto cresce e o cursor aparece", async () => {
    const ponte = ligarPonteFake({
      respostas: {
        "chat.abrir_conversa": { ok: true, resultado: { mensagens: [] } },
        "chat.enviar": { ok: true, resultado: { texto: "pronto" } },
      },
    });
    const { container } = render(<PainelChat conversationId="c1" semChaveIa={false} />);

    expect(container.querySelector('[data-streaming="sim"]')).toBeNull();

    ponte.emitir({ evento: "chat.delta", dados: { texto: "Vou usar o modelo " } });
    ponte.emitir({ evento: "chat.delta", dados: { texto: "da galeria." } });

    await waitFor(() =>
      expect(screen.getByText(/Vou usar o modelo da galeria\./)).toBeTruthy(),
    );
    expect(container.querySelector('[data-streaming="sim"]')).not.toBeNull();
  });
});

// -------------------------------------------------------------------------- A1 + A3

describe("A1/A3 — pensando e cartão de tool (chat.tool)", () => {
  it("pensando aparece no turno despachado e some quando a tool chega", async () => {
    let liberar: (() => void) | undefined;
    const ponte = ligarPonteFake({
      respostas: {
        "chat.abrir_conversa": { ok: true, resultado: { mensagens: [] } },
      },
    });
    ponte.responder("chat.enviar", () => {
      const espera = new Promise<void>((resolve) => {
        liberar = resolve;
      });
      return espera.then(() => ({ ok: true, resultado: { texto: "" } })) as never;
    });

    render(<PainelChat conversationId="c1" semChaveIa={false} />);
    expect(screen.queryByText("pensando")).toBeNull();

    await userEvent.type(screen.getByRole("textbox"), "faz a Dinâmica");
    await userEvent.click(screen.getByRole("button", { name: "Enviar" }));
    await waitFor(() => expect(screen.getByText("pensando")).toBeTruthy());

    ponte.emitir({
      evento: "chat.tool",
      dados: { trace_id: "t1", tool: "usar_modelo_da_galeria", fase: "inicio", args_resumo: "{}" },
    });
    await waitFor(() => expect(screen.queryByText("pensando")).toBeNull());
    expect(screen.getByText("usar_modelo_da_galeria")).toBeTruthy();
    expect(screen.getByText("executando…")).toBeTruthy();

    ponte.emitir({
      evento: "chat.tool",
      dados: { trace_id: "t1", tool: "usar_modelo_da_galeria", fase: "fim", ok: true, ms: 1240 },
    });
    await waitFor(() => expect(screen.getByText("1,2 s")).toBeTruthy());
    liberar?.();
  });

  it("um cartão por trace_id, com fase e falha refletidas", () => {
    let tools = aplicarEventoTool([], {
      trace_id: "t1",
      tool: "validar_mapspec",
      fase: "inicio",
      args_resumo: "{}",
    });
    tools = aplicarEventoTool(tools, {
      trace_id: "t2",
      tool: "gerar_mapa",
      fase: "inicio",
    });
    tools = aplicarEventoTool(tools, {
      trace_id: "t1",
      tool: "validar_mapspec",
      fase: "fim",
      ok: false,
      ms: 320,
    });
    expect(tools).toHaveLength(2);
    expect(tools[0]).toMatchObject({ fase: "fim", ok: false, ms: 320 });
    expect(tools[0].argsResumo).toBe("{}"); // não se perde no evento de fim
    expect(cancelarPendentes(tools)[1].cancelada).toBe(true);
    expect(cancelarPendentes(tools)[0].cancelada).toBeUndefined();
    expect(formatarDuracao(840)).toBe("840 ms");
  });
});

// ------------------------------------------------------------------------ A4 progresso

describe("A4 — barra de progresso (job.progresso)", () => {
  it("sem evento não mostra porcentagem; com evento os segmentos fecham", async () => {
    const ponte = ligarPonteFake();
    const { container } = render(<BarraProgressoJob ativo />);
    expect(screen.getByText("gerando…")).toBeTruthy();
    expect(container.querySelector('[role="progressbar"]')).toBeNull();

    ponte.emitir({ evento: "job.progresso", dados: { etapa: "validando_spec", pct: 3 } });
    await waitFor(() =>
      expect(container.querySelector('[role="progressbar"]')?.getAttribute("aria-valuenow")).toBe(
        "3",
      ),
    );

    ponte.emitir({
      evento: "job.progresso",
      dados: { etapa: "resolvendo_camadas_locais", pct: 10, item: "avn" },
    });
    await waitFor(() => expect(screen.getByText("· avn")).toBeTruthy());
    const concluidos = container.querySelectorAll('[data-estado="concluida"]');
    expect(concluidos.length).toBe(2);
  });
});

// -------------------------------------------------------- A5 fase 1 e 2 (preview)

describe("A5 — preview de construção", () => {
  it("fase 1: a linha da camada acende com o item de job.progresso", async () => {
    const ponte = ligarPonteFake();
    const { container } = render(<Preview mapspec={MAPSPEC} />);

    const linhaAvn = () => container.querySelector('[data-camada="avn"]');
    expect(linhaAvn()?.getAttribute("data-estado")).toBe("pendente");

    ponte.emitir({
      evento: "job.progresso",
      dados: { etapa: "resolvendo_camadas_locais", pct: 7, item: "avn" },
    });
    await waitFor(() => expect(linhaAvn()?.getAttribute("data-estado")).toBe("pronta"));
    // as outras continuam apagadas: nada acende por simpatia
    expect(container.querySelector('[data-camada="auas"]')?.getAttribute("data-estado")).toBe(
      "pendente",
    );
  });

  it("fase 1: moldura da tabela acende na etapa em que ela nasce", async () => {
    const ponte = ligarPonteFake();
    const { container } = render(<Preview mapspec={MAPSPEC} />);
    const tabela = () => container.querySelector('[data-elemento="tabela"]');
    expect(tabela()?.getAttribute("data-estado")).toBe("pendente");

    ponte.emitir({ evento: "job.progresso", dados: { etapa: "gerando_tabela", pct: 45 } });
    await waitFor(() => expect(tabela()?.getAttribute("data-estado")).toBe("pronta"));
  });

  it("fase 2: preview_png vira imagem lida pelo núcleo, com crossfade", async () => {
    const ponte = ligarPonteFake({
      respostas: {
        "artefato.ler": (params) => ({
          ok: true,
          resultado: {
            caminho: String(params["caminho"]),
            mime: "image/png",
            tamanho: 68,
            base64: PNG_1x1,
          },
        }),
      },
    });
    const { container } = render(<Preview mapspec={MAPSPEC} />);
    expect(container.querySelector("img")).toBeNull();

    ponte.emitir({
      evento: "job.artefato_parcial",
      dados: {
        tipo: "preview_png",
        caminho: "Mapas/.preview/parcial_01.png",
        etapa: "aplicando_layout",
        pct: 70,
      },
    });

    await waitFor(() => expect(container.querySelector("img")).not.toBeNull());
    const imagem = container.querySelector('img[data-camada="atual"]');
    expect(imagem?.getAttribute("src")).toContain("data:image/png;base64,");
    expect(imagem?.className).toContain("entrando"); // crossfade --mf-dur-3
    // o renderer leu pelo núcleo, não do disco
    expect(ponte.chamadas.some((c) => c.metodo === "artefato.ler")).toBe(true);

    ponte.emitir({
      evento: "job.artefato_parcial",
      dados: { tipo: "pdf", caminho: "Mapas/Dinamica.pdf", etapa: "exportando_pdf", pct: 90 },
    });
    await waitFor(() => expect(screen.getByText(/PDF pronto/)).toBeTruthy());
  });

  it("artefato com caminho absoluto ou de fuga é descartado pela UI", () => {
    const envelope = (caminho: string) => ({
      v: 1,
      id: "01J",
      tipo: "evt" as const,
      evento: "job.artefato_parcial",
      dados: { tipo: "preview_png", caminho, etapa: "aplicando_layout" },
    });
    expect(ehJobArtefatoParcial(envelope("Mapas/.preview/p.png"))).toBe(true);
    expect(ehJobArtefatoParcial(envelope("C:\\Users\\alvaro\\p.png"))).toBe(false);
    expect(ehJobArtefatoParcial(envelope("/home/alvaro/p.png"))).toBe(false);
    expect(ehJobArtefatoParcial(envelope("../fora/p.png"))).toBe(false);
  });

  it("estado dos artefatos acumula sem inventar nada", () => {
    let estado = aplicarArtefato(ARTEFATOS_INICIAL, {
      tipo: "camada",
      caminho: "SHP/AVN.shp",
      etapa: "resolvendo_camadas_locais",
      camada_id: "avn",
      ordem: 30,
    });
    estado = aplicarArtefato(estado, {
      tipo: "camada",
      caminho: "SHP/AVN.shp",
      etapa: "resolvendo_camadas_locais",
      camada_id: "avn",
    });
    expect(estado.camadas).toHaveLength(1); // reemissão não duplica
    expect(estado.total).toBe(2);
    expect(estado.previewPng).toBeNull();
    expect(ARTEFATOS_INICIAL.camadas).toHaveLength(0); // estado inicial não é mutado
  });
});

// --------------------------------------------------------------------- A6 troca de versão

function LinhaVersoesLigada() {
  const versoes = useMapspecVersoes();
  return (
    <LinhaVersoes
      versoes={versoes.estado.versoes}
      indiceExibido={versoes.estado.indiceExibido}
      aoNavegar={versoes.navegar}
      aoIrPara={versoes.irPara}
    />
  );
}

describe("A6 — troca de versão (mapspec.atualizado)", () => {
  it("sem evento não há navegador de versões; mapspec.atualizado liga v1 com o diff", async () => {
    const ponte = ligarPonteFake();
    const { container } = render(<LinhaVersoesLigada />);
    expect(container).toBeEmptyDOMElement();

    ponte.emitir({
      evento: "mapspec.atualizado",
      dados: {
        id: "01MAPSPECV1",
        versao: 1,
        diff: {
          operacoes: [{ op: "adicionar", caminho: "titulo", depois: "Fazenda Harmonia" }],
          resumo: ["título: adicionado (Fazenda Harmonia)"],
        },
      } as unknown as Record<string, unknown>,
    });

    await waitFor(() => expect(screen.getByText("v1")).toBeInTheDocument());
    expect(screen.getByText(/título: adicionado/)).toBeInTheDocument();
  });

  it("segundo evento (edição) acrescenta v2 e o diff muda para o da edição", async () => {
    const ponte = ligarPonteFake();
    render(<LinhaVersoesLigada />);

    ponte.emitir({
      evento: "mapspec.atualizado",
      dados: {
        id: "01V1",
        versao: 1,
        diff: { operacoes: [], resumo: ["título: adicionado (Fazenda Harmonia)"] },
      } as unknown as Record<string, unknown>,
    });
    await waitFor(() => expect(screen.getByText("v1")).toBeInTheDocument());

    ponte.emitir({
      evento: "mapspec.atualizado",
      dados: {
        id: "01V2",
        versao: 2,
        diff: { operacoes: [], resumo: ["elemento “tabela”: ligado → desligado"] },
      } as unknown as Record<string, unknown>,
    });

    await waitFor(() => expect(screen.getByText("v2")).toBeInTheDocument());
    expect(screen.getByText(/tabela.*ligado → desligado/)).toBeInTheDocument();
  });
});
