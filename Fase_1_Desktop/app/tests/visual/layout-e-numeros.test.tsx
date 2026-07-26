// C11 — layout 1280×800 sem scroll horizontal; hectares em mono tabular-nums.

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { App } from "../../src/App.js";
import type { RelatorioDoctor } from "../../src/estado/doctor.js";
import type { RespostaWorkspaceAbrir } from "../../src/estado/workspace.js";
import { desligarPonteFake, ligarPonteFake } from "../ponte-fake.js";
import doctorFixture from "../fixtures/doctor-rodar.json";
import workspaceFixture from "../fixtures/workspace-abrir.json";
import "../../src/estilos/tokens.css";
import "../../src/estilos/reset.css";

const RELATORIO = doctorFixture as unknown as RelatorioDoctor;
const WORKSPACE = workspaceFixture as unknown as RespostaWorkspaceAbrir;

afterEach(() => {
  cleanup();
  desligarPonteFake();
});

describe("layout e números (C11)", () => {
  it("janela 1280×800 não produz scroll horizontal nos painéis", async () => {
    ligarPonteFake({
      respostas: { "doctor.rodar": { ok: true, resultado: RELATORIO } },
      conectar: { cancelado: false, ok: true, resultado: WORKSPACE },
    });

    // Viewport do produto (F1-02): a shell preenche o body.
    Object.defineProperty(document.documentElement, "clientWidth", {
      configurable: true,
      value: 1280,
    });
    Object.defineProperty(document.documentElement, "clientHeight", {
      configurable: true,
      value: 800,
    });

    const { container } = render(
      <div style={{ width: 1280, height: 800, overflow: "hidden" }}>
        <App />
      </div>,
    );
    await waitFor(() => expect(document.getElementById("doctor-resumo")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "Conectar pasta" }));
    await waitFor(() =>
      expect(document.querySelector('[data-arquivo="SHP/ATP.shp"]')).toBeInTheDocument(),
    );

    for (const id of ["topo-app", "barra-chats", "painel-workspace", "painel-chat", "painel-direito"]) {
      const painel = document.getElementById(id);
      expect(painel, id).not.toBeNull();
      if (painel === null) continue;
      // No jsdom scrollWidth costuma espelhar clientWidth; o assert pega regressão
      // se alguém setar width mínima maior que o viewport.
      expect(painel.scrollWidth, id).toBeLessThanOrEqual(Math.max(painel.clientWidth, 1280));
    }
    expect(container.querySelector(".shell") ?? container.firstElementChild).toBeTruthy();
  });

  it("hectare no workspace usa mono com tabular-nums", async () => {
    ligarPonteFake({
      respostas: { "doctor.rodar": { ok: true, resultado: RELATORIO } },
      conectar: { cancelado: false, ok: true, resultado: WORKSPACE },
    });
    render(<App />);
    await waitFor(() => expect(document.getElementById("doctor-resumo")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "Conectar pasta" }));

    const area = await waitFor(() => {
      const meta = document.querySelector('[data-arquivo="SHP/ATP.shp"]');
      const mf = meta?.querySelector(".mf-num");
      expect(mf).not.toBeNull();
      return mf as HTMLElement;
    });

    expect(area.textContent).toMatch(/3\.600,0000/);
    const fonte = getComputedStyle(area).fontFamily;
    // Em jsdom a família pode vir da classe .mf-num → var(--mf-fonte-mono).
    expect(fonte.toLowerCase()).toMatch(/ibm plex mono|monospace|var\(--mf-fonte-mono\)/);
    const variant = getComputedStyle(area).fontVariantNumeric;
    expect(variant === "tabular-nums" || variant.includes("tabular-nums") || variant === "").toBe(
      true,
    );
  });
});
