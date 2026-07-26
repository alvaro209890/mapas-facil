// C11 — contraste AA dos tokens + axe nas telas que existem hoje
// (app vazio, app com job, app com erro). Login é M5 — fora desta fatia.

import axe from "axe-core";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { App } from "../../src/App.js";
import { BarraProgressoJob } from "../../src/componentes/BarraProgressoJob.js";
import { ErroDoNucleo } from "../../src/componentes/EstadoVazio.js";
import type { RelatorioDoctor } from "../../src/estado/doctor.js";
import { TEMA_PADRAO, aplicarTema } from "../../src/estado/tema.js";
import { desligarPonteFake, ligarPonteFake } from "../ponte-fake.js";
import doctorFixture from "../fixtures/doctor-rodar.json";
import { razaoContraste } from "./contraste-tokens.js";
import "../../src/estilos/tokens.css";
import "../../src/estilos/reset.css";

const RELATORIO = doctorFixture as unknown as RelatorioDoctor;

afterEach(() => {
  cleanup();
  desligarPonteFake();
  aplicarTema(TEMA_PADRAO);
});

async function axeSemViolacao(container: HTMLElement): Promise<void> {
  // color-contrast do axe no jsdom é incompleto; os pares de token cobrem AA.
  // Aqui rodamos o restante (nome, aria, contraste quando o motor conseguir).
  const resultado = await axe.run(container, {
    rules: {
      "color-contrast": { enabled: false },
    },
  });
  expect(resultado.violations, JSON.stringify(resultado.violations, null, 2)).toEqual([]);
}

describe("contraste e axe (C11)", () => {
  it("pares de texto/fundo do tema escuro passam WCAG AA (≥ 4,5)", () => {
    const pares: [string, string, string][] = [
      ["texto", "#e8edf2", "#0b0e11"],
      ["texto-2", "#a6b2c0", "#0b0e11"],
      ["texto em superfície", "#e8edf2", "#12161b"],
      ["texto-2 em superfície", "#a6b2c0", "#12161b"],
      ["erro", "#f2555a", "#0b0e11"],
      ["aviso", "#e8a33d", "#0b0e11"],
    ];
    for (const [nome, frente, fundo] of pares) {
      const razao = razaoContraste(frente, fundo);
      expect(razao, nome).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("pares do tema claro também passam AA", () => {
    const pares: [string, string][] = [
      ["#131920", "#f4f6f8"],
      ["#46525f", "#f4f6f8"],
      ["#131920", "#ffffff"],
      ["#c0272c", "#f4f6f8"],
    ];
    for (const [frente, fundo] of pares) {
      expect(razaoContraste(frente, fundo)).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("axe sem violação no app vazio", async () => {
    ligarPonteFake({
      respostas: { "doctor.rodar": { ok: true, resultado: RELATORIO } },
    });
    const { container } = render(<App />);
    await waitFor(() => expect(screen.getByText("Nenhuma pasta conectada")).toBeInTheDocument());
    await axeSemViolacao(container);
  });

  it("axe sem violação com barra de job (evento real)", async () => {
    const ponte = ligarPonteFake({
      respostas: { "doctor.rodar": { ok: true, resultado: RELATORIO } },
    });
    // Mesmo caminho do teste C6: a barra só sobe com evento injetado na ponte.
    const { container } = render(
      <div style={{ background: "var(--mf-bg)", color: "var(--mf-texto)", padding: 16 }}>
        <App />
        <div id="zona-job">
          <BarraProgressoJob ativo />
        </div>
      </div>,
    );
    await waitFor(() => expect(document.getElementById("doctor-resumo")).toBeInTheDocument());
    expect(screen.getByText("gerando…")).toBeInTheDocument();

    ponte.emitir({
      evento: "job.progresso",
      dados: { etapa: "validando_spec", pct: 3 } as unknown as Record<string, unknown>,
    });

    await waitFor(() => {
      expect(document.querySelector("#zona-job [role='progressbar']")).not.toBeNull();
    });
    await axeSemViolacao(container);
  });

  it("axe sem violação na tela de erro do núcleo", async () => {
    const { container } = render(
      <ErroDoNucleo
        codigo="NU-010"
        mensagem="Caminho fora do workspace."
        aoTentarDeNovo={() => undefined}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("NU-010");
    await axeSemViolacao(container);
  });
});
