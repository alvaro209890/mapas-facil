// Fumaça do shell inteiro: os quatro painéis, o workspace de verdade no lugar do
// placeholder e os informativos que só aparecem se o doctor sustentar.
//
// É o teste que pega fiação quebrada — cada componente passa sozinho e a tela
// mesmo assim monta errado.

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { App } from "../src/App.js";
import type { RelatorioDoctor } from "../src/estado/doctor.js";
import type { RespostaWorkspaceAbrir } from "../src/estado/workspace.js";
import { desligarPonteFake, ligarPonteFake } from "./ponte-fake.js";
import doctorFixture from "./fixtures/doctor-rodar.json";
import workspaceFixture from "./fixtures/workspace-abrir.json";

const RELATORIO = doctorFixture as unknown as RelatorioDoctor;
const WORKSPACE = workspaceFixture as unknown as RespostaWorkspaceAbrir;

function painel(id: string): HTMLElement {
  const alvo = document.getElementById(id);
  if (alvo === null) throw new Error(`painel ausente: ${id}`);
  return alvo;
}

afterEach(() => {
  cleanup();
  desligarPonteFake();
});

describe("AppShell", () => {
  it("monta os quatro painéis com os IDs de F1-16", async () => {
    ligarPonteFake({ respostas: { "doctor.rodar": { ok: true, resultado: RELATORIO } } });
    render(<App />);

    await waitFor(() => expect(painel("doctor-resumo")).toBeInTheDocument());
    for (const id of ["topo-app", "barra-chats", "painel-workspace", "painel-chat", "painel-direito"]) {
      expect(painel(id)).toBeInTheDocument();
    }
    expect(screen.getByText("Nenhuma pasta conectada")).toBeInTheDocument();
  });

  it("conectar pasta preenche a árvore e o breadcrumb do topo", async () => {
    ligarPonteFake({
      respostas: { "doctor.rodar": { ok: true, resultado: RELATORIO } },
      conectar: { cancelado: false, ok: true, resultado: WORKSPACE },
    });
    render(<App />);

    await userEvent.click(screen.getByRole("button", { name: "Conectar pasta" }));

    await waitFor(() =>
      expect(document.querySelector('[data-arquivo="SHP/ATP.shp"]')).toBeInTheDocument(),
    );
    expect(painel("topo-app")).toHaveTextContent("Analise_de_area-Harmonia");
    expect(painel("painel-workspace")).toHaveTextContent("3.600,0000 ha");
  });

  it("informativo de chave e de ArcMap só aparece com relatório do doctor", async () => {
    ligarPonteFake({ respostas: { "doctor.rodar": { ok: true, resultado: RELATORIO } } });
    render(<App />);

    await waitFor(() => expect(screen.getByText("Sem chave da DeepSeek")).toBeInTheDocument());
    expect(screen.getByText("Sem ArcMap neste computador")).toBeInTheDocument();
  });

  it("sem diagnóstico, nenhum informativo é inventado", async () => {
    ligarPonteFake({
      respostas: {
        "doctor.rodar": { ok: false, erro: { codigo: "UI-001", mensagem: "núcleo parado" } },
      },
    });
    render(<App />);

    await waitFor(() => expect(screen.getByText(/diagnóstico indisponível/)).toBeInTheDocument());
    expect(screen.queryByText("Sem chave da DeepSeek")).toBeNull();
    expect(screen.queryByText("Sem ArcMap neste computador")).toBeNull();
  });

  it("núcleo caído mostra o banner UI-001 com o botão de reiniciar", async () => {
    const ponte = ligarPonteFake({
      respostas: { "doctor.rodar": { ok: true, resultado: RELATORIO } },
    });
    render(<App />);
    await waitFor(() => expect(painel("doctor-resumo")).toBeInTheDocument());

    ponte.emitirEstado({
      estado: "caido",
      erro: { codigo: "UI-001", mensagem: "O núcleo do Mapas Fácil parou de responder." },
    });

    const banner = await screen.findByRole("button", { name: "Reiniciar o núcleo" });
    expect(banner.closest('[role="alert"]')).toHaveTextContent("UI-001");
  });
});
