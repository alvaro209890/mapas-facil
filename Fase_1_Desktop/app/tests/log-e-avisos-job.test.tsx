// F1-01 §Eventos — `job.log` (colapsado) e `aviso` (visível) na barra do job.
//
// AP-07 nas duas metades: antes do evento a UI não desenha nada; depois do
// evento injetado pela ponte, aparece. Nenhum timer, nenhuma linha inventada.

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { BarraProgressoJob } from "../src/componentes/BarraProgressoJob.js";
import {
  LOG_INICIAL,
  MAX_LINHAS_MEMORIA,
  aplicarAviso,
  aplicarLog,
} from "../src/estado/logJob.js";
import { ehAviso, ehJobLog } from "../src/estado/eventos.js";
import { desligarPonteFake, ligarPonteFake } from "./ponte-fake.js";

afterEach(() => {
  cleanup();
  desligarPonteFake();
});

function emitirLog(ponte: ReturnType<typeof ligarPonteFake>, linha: string): void {
  ponte.emitir({ evento: "job.log", dados: { linha } });
}

function emitirAviso(
  ponte: ReturnType<typeof ligarPonteFake>,
  codigo: string,
  mensagem: string,
): void {
  ponte.emitir({ evento: "aviso", dados: { codigo, mensagem } });
}

// --------------------------------------------------------------------- estado puro

describe("estado de log e avisos (puro)", () => {
  it("acumula linhas de log na ordem", () => {
    let estado = aplicarLog(LOG_INICIAL, { linha: "primeira" });
    estado = aplicarLog(estado, { linha: "segunda" });
    expect(estado.linhas).toEqual(["primeira", "segunda"]);
    expect(LOG_INICIAL.linhas).toHaveLength(0); // inicial não é mutado
  });

  it("mantém só as últimas linhas quando passa do teto", () => {
    let estado = LOG_INICIAL;
    for (let i = 0; i < MAX_LINHAS_MEMORIA + 20; i += 1) {
      estado = aplicarLog(estado, { linha: `linha ${i}` });
    }
    expect(estado.linhas).toHaveLength(MAX_LINHAS_MEMORIA);
    expect(estado.linhas.at(-1)).toBe(`linha ${MAX_LINHAS_MEMORIA + 19}`);
  });

  it("agrupa aviso repetido em vez de empilhar igual", () => {
    let estado = aplicarAviso(LOG_INICIAL, { codigo: "NU-120", mensagem: "camada vazia" });
    estado = aplicarAviso(estado, { codigo: "NU-120", mensagem: "camada vazia" });
    expect(estado.avisos).toHaveLength(1);
    expect(estado.avisos[0].vezes).toBe(2);
  });

  it("avisos diferentes viram entradas diferentes", () => {
    let estado = aplicarAviso(LOG_INICIAL, { codigo: "NU-120", mensagem: "a" });
    estado = aplicarAviso(estado, { codigo: "NU-121", mensagem: "b" });
    expect(estado.avisos.map((a) => a.codigo)).toEqual(["NU-120", "NU-121"]);
  });
});

// --------------------------------------------------------------------- guards

describe("type guards", () => {
  const envelope = (evento: string, dados: Record<string, unknown>) => ({
    v: 1,
    id: "01J",
    tipo: "evt" as const,
    evento,
    dados,
  });

  it("ehJobLog exige linha não vazia", () => {
    expect(ehJobLog(envelope("job.log", { linha: "ok" }))).toBe(true);
    expect(ehJobLog(envelope("job.log", { linha: "" }))).toBe(false);
    expect(ehJobLog(envelope("job.log", {}))).toBe(false);
    expect(ehJobLog(envelope("aviso", { linha: "ok" }))).toBe(false);
  });

  it("ehAviso exige código e mensagem", () => {
    expect(ehAviso(envelope("aviso", { codigo: "NU-120", mensagem: "x" }))).toBe(true);
    expect(ehAviso(envelope("aviso", { codigo: "NU-120" }))).toBe(false);
    expect(ehAviso(envelope("aviso", { codigo: "", mensagem: "x" }))).toBe(false);
  });
});

// --------------------------------------------------------------------- componente

describe("BarraProgressoJob — log e avisos", () => {
  it("sem evento nenhum não há log nem aviso (AP-07)", () => {
    ligarPonteFake();
    render(<BarraProgressoJob ativo />);
    expect(screen.queryByTestId("log-job")).toBeNull();
    expect(screen.queryByTestId("avisos-job")).toBeNull();
  });

  it("job.log aparece colapsado, com a contagem no resumo", async () => {
    const ponte = ligarPonteFake();
    render(<BarraProgressoJob ativo />);

    emitirLog(ponte, "job iniciado · template=dinamica_retrato");
    emitirLog(ponte, "camadas locais materializadas em SHP/: 4");

    const detalhe = await screen.findByTestId("log-job");
    expect(detalhe.tagName).toBe("DETAILS");
    expect((detalhe as HTMLDetailsElement).open).toBe(false); // colapsado (F1-02)
    expect(screen.getByText("(2)")).toBeInTheDocument();
  });

  it("abrir o detalhe revela as linhas na ordem em que chegaram", async () => {
    const ponte = ligarPonteFake();
    render(<BarraProgressoJob ativo />);
    const usuario = userEvent.setup();

    emitirLog(ponte, "primeira linha");
    emitirLog(ponte, "segunda linha");
    await screen.findByTestId("log-job");

    await usuario.click(screen.getByText(/log técnico/));
    const itens = screen.getByTestId("log-job").querySelectorAll("li");
    expect([...itens].map((li) => li.textContent)).toEqual(["primeira linha", "segunda linha"]);
  });

  it("aviso aparece visível, com código, sem precisar de clique", async () => {
    const ponte = ligarPonteFake();
    render(<BarraProgressoJob ativo />);

    emitirAviso(ponte, "NU-120", "Camada 'auas' sem feições após o recorte.");

    await waitFor(() => expect(screen.getByTestId("avisos-job")).toBeInTheDocument());
    expect(screen.getByText("NU-120")).toBeInTheDocument();
    expect(screen.getByText(/sem feições após o recorte/)).toBeInTheDocument();
  });

  it("aviso repetido mostra contador em vez de duplicar a linha", async () => {
    const ponte = ligarPonteFake();
    render(<BarraProgressoJob ativo />);

    emitirAviso(ponte, "NU-121", "ogr2ogr indisponível");
    emitirAviso(ponte, "NU-121", "ogr2ogr indisponível");
    emitirAviso(ponte, "NU-121", "ogr2ogr indisponível");

    await waitFor(() => expect(screen.getByText("×3")).toBeInTheDocument());
    expect(screen.getByTestId("avisos-job").querySelectorAll("li")).toHaveLength(1);
  });

  it("evento malformado é ignorado — a UI não inventa entrada", async () => {
    const ponte = ligarPonteFake();
    render(<BarraProgressoJob ativo />);

    ponte.emitir({ evento: "job.log", dados: { linha: "" } });
    ponte.emitir({ evento: "aviso", dados: { codigo: "NU-120" } });

    await new Promise((r) => setTimeout(r, 10));
    expect(screen.queryByTestId("log-job")).toBeNull();
    expect(screen.queryByTestId("avisos-job")).toBeNull();
  });

  it("log e aviso sobrevivem mesmo sem job ativo (o job já respondeu)", async () => {
    const ponte = ligarPonteFake();
    render(<BarraProgressoJob />);
    emitirAviso(ponte, "NU-123", "PNG da tabela com dpi efetivo 300");
    await waitFor(() => expect(screen.getByTestId("avisos-job")).toBeInTheDocument());
  });
});
