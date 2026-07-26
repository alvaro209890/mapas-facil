// D8 — galeria na UI: grade, cartão indisponível sem clique, detalhe + montar.

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { App } from "../src/App.js";
import type { RelatorioDoctor } from "../src/estado/doctor.js";
import { desligarPonteFake, ligarPonteFake } from "./ponte-fake.js";
import doctorFixture from "./fixtures/doctor-rodar.json";

const RELATORIO = doctorFixture as unknown as RelatorioDoctor;

const MODELOS = {
  galeria_version: 1,
  modelos: [
    {
      id: "dinamica_2026_retrato",
      nome: "Dinâmica de uso do solo",
      subtitulo: "Série Dinâmica · A4 retrato",
      tags: ["dinamica"],
      orientacao: "retrato",
      preview: "previews/dinamica_2026_retrato.png",
      status: "parcial",
      motivo: "template parcial (offsets pendentes)",
      requisitos_faltando: [],
    },
    {
      id: "uc_paisagem",
      nome: "Unidades de Conservação",
      subtitulo: "A4 paisagem",
      tags: ["uc"],
      orientacao: "paisagem",
      preview: "previews/uc_paisagem.png",
      status: "indisponivel",
      motivo: "template ainda não preparado no ArcMap",
      requisitos_faltando: [],
    },
  ],
};

const DETALHE = {
  ...MODELOS.modelos[0],
  descricao: "Perímetro e quantitativos.",
  template: "dinamica_retrato",
  saidas_padrao: ["pdf"],
  requisitos_camadas: [
    {
      papel: "ATP",
      obrigatorio: true,
      nome_no_mxd: "{imovel.nome}",
      estilo: "perimetro_imovel",
      ordem: 10,
    },
  ],
  elementos_layout_padrao: { tabela: true },
  mapeamento_sugerido: { ATP: "local.ATP" },
};

afterEach(() => {
  cleanup();
  desligarPonteFake();
});

describe("Galeria (D8)", () => {
  it("lista cartões e não dispara detalhar em indisponivel", async () => {
    const ponte = ligarPonteFake({
      respostas: {
        "doctor.rodar": { ok: true, resultado: RELATORIO },
        "galeria.listar": { ok: true, resultado: MODELOS },
      },
    });
    render(<App />);

    await waitFor(() => expect(screen.getByText("Dinâmica de uso do solo")).toBeInTheDocument());
    expect(screen.getByText("Unidades de Conservação")).toBeInTheDocument();

    const indisponivel = document.getElementById("cartao-modelo-uc_paisagem");
    expect(indisponivel).toBeDisabled();
    await userEvent.click(indisponivel!);
    expect(ponte.chamadas.map((c) => c.metodo)).not.toContain("galeria.detalhar");
  });

  it("abre detalhe e monta MapSpec", async () => {
    const ponte = ligarPonteFake({
      respostas: {
        "doctor.rodar": { ok: true, resultado: RELATORIO },
        "galeria.listar": { ok: true, resultado: MODELOS },
        "galeria.detalhar": { ok: true, resultado: DETALHE },
        "galeria.montar_mapspec": {
          ok: true,
          resultado: {
            mapspec: { id: "01TESTE", template: "dinamica_retrato", titulo: "Dinâmica" },
            avisos: [],
          },
        },
      },
    });
    render(<App />);
    await waitFor(() => expect(screen.getByText("Dinâmica de uso do solo")).toBeInTheDocument());

    await userEvent.click(document.getElementById("cartao-modelo-dinamica_2026_retrato")!);
    await waitFor(() => expect(screen.getByText("Montar MapSpec")).toBeInTheDocument());
    expect(ponte.chamadas.map((c) => c.metodo)).toContain("galeria.detalhar");

    await userEvent.click(screen.getByRole("button", { name: "Montar MapSpec" }));
    await waitFor(() => expect(document.getElementById("painel-mapspec")).toBeInTheDocument());
    expect(document.getElementById("painel-mapspec")).toHaveTextContent('"template": "dinamica_retrato"');
  });
});
