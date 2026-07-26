// Menu nativo → renderer: o mesmo `executarComando` da paleta (F1-02).

import { cleanup, render, waitFor } from "@testing-library/react";
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

describe("comando do menu nativo (IPC)", () => {
  it("conectar-pasta pelo menu abre o diálogo como a paleta", async () => {
    const ponte = ligarPonteFake({
      respostas: { "doctor.rodar": { ok: true, resultado: RELATORIO } },
      conectar: { cancelado: false, ok: true, resultado: WORKSPACE },
    });
    render(<App />);
    await waitFor(() => expect(document.getElementById("doctor-resumo")).toBeInTheDocument());

    ponte.emitirComandoMenu("conectar-pasta");
    await waitFor(() => expect(ponte.conexoes).toBe(1));
    await waitFor(() =>
      expect(document.querySelector('[data-arquivo="SHP/ATP.shp"]')).toBeInTheDocument(),
    );
  });

  it("id desconhecido é ignorado — não inventa comando", async () => {
    const ponte = ligarPonteFake({
      respostas: { "doctor.rodar": { ok: true, resultado: RELATORIO } },
    });
    render(<App />);
    await waitFor(() => expect(document.getElementById("doctor-resumo")).toBeInTheDocument());
    ponte.emitirComandoMenu("comando-que-nao-existe");
    expect(ponte.conexoes).toBe(0);
  });
});
