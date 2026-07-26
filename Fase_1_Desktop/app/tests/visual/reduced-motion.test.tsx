// C11 — prefers-reduced-motion ≤ 80 ms (F1-16 DoD).
//
// jsdom não reaplica @media sozinho a partir de matchMedia; o teste (1) confere
// o CSS-fonte, (2) aplica a mesma regra do tokens.css e (3) varre getComputedStyle.

import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { cleanup, render, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { App } from "../../src/App.js";
import { BarraProgressoJob } from "../../src/componentes/BarraProgressoJob.js";
import type { RelatorioDoctor } from "../../src/estado/doctor.js";
import { DURACAO_MOVIMENTO_REDUZIDO, duracao } from "../../src/motion/tokens.js";
import { desligarPonteFake, ligarPonteFake } from "../ponte-fake.js";
import doctorFixture from "../fixtures/doctor-rodar.json";
import "../../src/estilos/tokens.css";
import "../../src/estilos/reset.css";

const DIR = dirname(fileURLToPath(import.meta.url));
const RELATORIO = doctorFixture as unknown as RelatorioDoctor;

const ESTILO_REDUZIDO = `
@media (prefers-reduced-motion: reduce) {
  :root {
    --mf-dur-1: 0ms;
    --mf-dur-2: 0ms;
    --mf-dur-3: 0ms;
    --mf-dur-4: 0ms;
  }
  *, *::before, *::after {
    animation-duration: 80ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 80ms !important;
    transition-property: opacity, color, background-color, border-color !important;
    scroll-behavior: auto !important;
  }
}
`;

function mockMatchMedia(reduzir: boolean): void {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    configurable: true,
    value: (consulta: string) => ({
      matches: reduzir && consulta.includes("prefers-reduced-motion"),
      media: consulta,
      onchange: null,
      addListener: () => undefined,
      removeListener: () => undefined,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      dispatchEvent: () => false,
    }),
  });
}

function parseMs(valor: string): number {
  if (!valor || valor === "none" || valor === "normal") return 0;
  // getComputedStyle pode devolver "0.08s" ou "80ms" ou lista "80ms, 80ms".
  const partes = valor.split(",").map((p) => p.trim());
  let max = 0;
  for (const parte of partes) {
    if (parte.endsWith("ms")) max = Math.max(max, Number.parseFloat(parte));
    else if (parte.endsWith("s")) max = Math.max(max, Number.parseFloat(parte) * 1000);
  }
  return Number.isFinite(max) ? max : 0;
}

function maxDuracaoNaArvore(raiz: ParentNode): number {
  let max = 0;
  const visitados = [raiz, ...Array.from(raiz.querySelectorAll("*"))];
  for (const no of visitados) {
    if (!(no instanceof Element)) continue;
    // jsdom não implementa getComputedStyle(elt, pseudo); só elementos reais.
    const estilo = getComputedStyle(no);
    max = Math.max(max, parseMs(estilo.animationDuration), parseMs(estilo.transitionDuration));
  }
  return max;
}

afterEach(() => {
  cleanup();
  desligarPonteFake();
  document.getElementById("mf-teste-reduced")?.remove();
  mockMatchMedia(false);
});

describe("reduced-motion (C11)", () => {
  it("tokens.css declara o teto de 80 ms em prefers-reduced-motion", () => {
    const css = readFileSync(resolve(DIR, "../../src/estilos/tokens.css"), "utf8");
    expect(css).toMatch(/prefers-reduced-motion:\s*reduce/);
    expect(css).toMatch(/animation-duration:\s*80ms\s*!important/);
    expect(css).toMatch(/transition-duration:\s*80ms\s*!important/);
  });

  it("motion/tokens.ts nunca passa de 80 ms com movimento reduzido", () => {
    expect(DURACAO_MOVIMENTO_REDUZIDO).toBe(80);
    expect(duracao("d1", true)).toBeLessThanOrEqual(80);
    expect(duracao("d4", true)).toBeLessThanOrEqual(80);
  });

  it("árvore renderizada com reduced-motion não excede 80 ms", async () => {
    mockMatchMedia(true);
    const estilo = document.createElement("style");
    estilo.id = "mf-teste-reduced";
    estilo.textContent = ESTILO_REDUZIDO;
    document.head.appendChild(estilo);

    const ponte = ligarPonteFake({
      respostas: { "doctor.rodar": { ok: true, resultado: RELATORIO } },
    });
    const { container } = render(
      <div>
        <App />
        <BarraProgressoJob ativo />
      </div>,
    );
    await waitFor(() => expect(document.getElementById("doctor-resumo")).toBeInTheDocument());
    ponte.emitir({
      evento: "job.progresso",
      dados: { etapa: "resolvendo_camadas_locais", pct: 10, item: "avn" } as unknown as Record<
        string,
        unknown
      >,
    });
    await waitFor(() => expect(container.querySelector('[role="progressbar"]')).not.toBeNull());

    const max = maxDuracaoNaArvore(container);
    expect(max).toBeLessThanOrEqual(DURACAO_MOVIMENTO_REDUZIDO);
  });
});
