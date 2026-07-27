// C11 — tema default, fundo e tipografia embarcada (F1-16 DoD visual).

import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { cleanup, render, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { App } from "../../src/App.js";
import type { RelatorioDoctor } from "../../src/estado/doctor.js";
import { TEMA_PADRAO, aplicarTema } from "../../src/estado/tema.js";
import { desligarPonteFake, ligarPonteFake } from "../ponte-fake.js";
import doctorFixture from "../fixtures/doctor-rodar.json";
import "../../src/estilos/tokens.css";
import "../../src/estilos/reset.css";

const DIR = dirname(fileURLToPath(import.meta.url));
const RELATORIO = doctorFixture as unknown as RelatorioDoctor;

function listarArquivos(raiz: string): string[] {
  const out: string[] = [];
  for (const nome of readdirSync(raiz)) {
    const caminho = join(raiz, nome);
    if (statSync(caminho).isDirectory()) out.push(...listarArquivos(caminho));
    else out.push(caminho);
  }
  return out;
}

afterEach(() => {
  cleanup();
  desligarPonteFake();
  aplicarTema(TEMA_PADRAO);
});

describe("tema e tipografia (C11)", () => {
  it("app sem config abre com data-tema=escuro e --mf-bg do tema escuro", async () => {
    ligarPonteFake({
      respostas: { "doctor.rodar": { ok: true, resultado: RELATORIO } },
      preferencias: {},
    });
    render(<App />);
    await waitFor(() => expect(document.getElementById("doctor-resumo")).toBeInTheDocument());

    expect(document.documentElement.dataset.tema).toBe("escuro");
    // jsdom resolve custom properties em :root; rgb() no body é instável sem layout real.
    const mfBg = getComputedStyle(document.documentElement).getPropertyValue("--mf-bg").trim();
    expect(mfBg.toLowerCase()).toBe("#0b0e11");
  });

  it("tokens.css só cita Inter/Roboto/Arial/Helvetica/system-ui depois da família embarcada", () => {
    const css = readFileSync(resolve(DIR, "../../src/estilos/tokens.css"), "utf8");
    expect(css).toMatch(/--mf-fonte-display:\s*"Space Grotesk"/);
    expect(css).toMatch(/--mf-fonte-ui:\s*"IBM Plex Sans"/);
    expect(css).toMatch(/--mf-fonte-mono:\s*"IBM Plex Mono"/);
    // Fallbacks genéricos só aparecem depois do nome embarcado na mesma declaração.
    for (const linha of css.split("\n")) {
      const lower = linha.toLowerCase();
      if (!/(inter|roboto|arial|helvetica|system-ui)/.test(lower)) continue;
      expect(linha).toMatch(/Space Grotesk|IBM Plex/);
    }
  });

  it("nenhuma fonte vem de CDN no src/", () => {
    const raiz = resolve(DIR, "../../src");
    const re = /https:\/\/fonts\.|cdn\./i;
    const ofensores: string[] = [];
    for (const arquivo of listarArquivos(raiz)) {
      const texto = readFileSync(arquivo, "utf8");
      if (re.test(texto)) ofensores.push(arquivo);
    }
    expect(ofensores).toEqual([]);
  });
});
