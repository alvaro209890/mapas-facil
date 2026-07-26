// C10 — paleta de comandos e atalhos globais.

import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { App } from "../src/App.js";
import type { RelatorioDoctor } from "../src/estado/doctor.js";
import type { RespostaWorkspaceAbrir } from "../src/estado/workspace.js";
import { TEMA_PADRAO } from "../src/estado/tema.js";
import { desligarPonteFake, ligarPonteFake } from "./ponte-fake.js";
import doctorFixture from "./fixtures/doctor-rodar.json";
import workspaceFixture from "./fixtures/workspace-abrir.json";

const RELATORIO = doctorFixture as unknown as RelatorioDoctor;
const WORKSPACE = workspaceFixture as unknown as RespostaWorkspaceAbrir;

afterEach(() => {
  cleanup();
  desligarPonteFake();
  document.documentElement.dataset.tema = TEMA_PADRAO;
});

async function montarApp() {
  ligarPonteFake({
    respostas: { "doctor.rodar": { ok: true, resultado: RELATORIO } },
    conectar: { cancelado: false, ok: true, resultado: WORKSPACE },
  });
  render(<App />);
  await waitFor(() => expect(document.getElementById("doctor-resumo")).toBeInTheDocument());
}

describe("PaletaComandos e atalhos (C10)", () => {
  it("Ctrl+K abre a paleta e Esc fecha", async () => {
    await montarApp();
    expect(document.getElementById("paleta-comandos")).toBeNull();

    await userEvent.keyboard("{Control>}k{/Control}");
    const paleta = await screen.findByRole("dialog", { name: "Paleta de comandos" });
    expect(paleta).toBeInTheDocument();

    await userEvent.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Paleta de comandos" })).toBeNull());
  });

  it("filtra comandos e Enter executa conectar pasta", async () => {
    const ponte = ligarPonteFake({
      respostas: { "doctor.rodar": { ok: true, resultado: RELATORIO } },
      conectar: { cancelado: false, ok: true, resultado: WORKSPACE },
    });
    render(<App />);
    await waitFor(() => expect(document.getElementById("doctor-resumo")).toBeInTheDocument());

    await userEvent.keyboard("{Control>}k{/Control}");
    const busca = screen.getByPlaceholderText("Filtrar comandos…");
    await userEvent.type(busca, "conectar");

    const opcao = screen.getByRole("option", { name: /Conectar pasta/i });
    expect(opcao).toHaveAttribute("data-disponivel", "true");
    await userEvent.keyboard("{Enter}");

    await waitFor(() => expect(ponte.conexoes).toBe(1));
    await waitFor(() =>
      expect(document.querySelector('[data-arquivo="SHP/ATP.shp"]')).toBeInTheDocument(),
    );
  });

  it("comando de nova conversa está disponível (M6)", async () => {
    await montarApp();
    await userEvent.keyboard("{Control>}k{/Control}");
    const opcao = screen.getByRole("option", { name: /Nova conversa/i });
    expect(opcao).toHaveAttribute("data-disponivel", "true");
    expect(opcao).not.toBeDisabled();
  });

  it("Ctrl+O dispara conectar pasta sem abrir a paleta", async () => {
    const ponte = ligarPonteFake({
      respostas: { "doctor.rodar": { ok: true, resultado: RELATORIO } },
      conectar: { cancelado: false, ok: true, resultado: WORKSPACE },
    });
    render(<App />);
    await waitFor(() => expect(document.getElementById("doctor-resumo")).toBeInTheDocument());

    await userEvent.keyboard("{Control>}o{/Control}");
    await waitFor(() => expect(ponte.conexoes).toBe(1));
  });

  it("Ctrl+N cria conversa via chat.criar_conversa", async () => {
    const ponte = ligarPonteFake({
      respostas: { "doctor.rodar": { ok: true, resultado: RELATORIO } },
      conectar: { cancelado: false, ok: true, resultado: WORKSPACE },
    });
    render(<App />);
    await waitFor(() => expect(document.getElementById("doctor-resumo")).toBeInTheDocument());

    await userEvent.keyboard("{Control>}n{/Control}");
    await waitFor(() =>
      expect(ponte.chamadas.some((c) => c.metodo === "chat.criar_conversa")).toBe(true),
    );
    expect(await screen.findByText("Conversa sem título")).toBeInTheDocument();
  });

  it("F1 roda o doctor de novo", async () => {
    const ponte = ligarPonteFake({
      respostas: { "doctor.rodar": { ok: true, resultado: RELATORIO } },
    });
    render(<App />);
    await waitFor(() => expect(document.getElementById("doctor-resumo")).toBeInTheDocument());
    const antes = ponte.chamadas.filter((c) => c.metodo === "doctor.rodar").length;

    await userEvent.keyboard("{F1}");
    await waitFor(() =>
      expect(ponte.chamadas.filter((c) => c.metodo === "doctor.rodar").length).toBeGreaterThan(antes),
    );
  });

  it("Ctrl+, abre preferências e permite tema claro", async () => {
    const ponte = ligarPonteFake({
      respostas: { "doctor.rodar": { ok: true, resultado: RELATORIO } },
    });
    render(<App />);
    await waitFor(() => expect(document.getElementById("doctor-resumo")).toBeInTheDocument());

    await userEvent.keyboard("{Control>},{/Control}");
    const dialogo = await screen.findByRole("dialog", { name: "Preferências" });
    expect(dialogo).toBeInTheDocument();

    await userEvent.click(within(dialogo).getByRole("radio", { name: "Claro" }));
    expect(document.documentElement.dataset.tema).toBe("claro");
    expect(ponte.gravacoes.some((g) => g.tema === "claro")).toBe(true);
  });

  it("botão Ctrl+K no topo abre a mesma paleta", async () => {
    await montarApp();
    await userEvent.click(screen.getByRole("button", { name: "abrir paleta de comandos" }));
    expect(await screen.findByRole("dialog", { name: "Paleta de comandos" })).toBeInTheDocument();
  });
});
