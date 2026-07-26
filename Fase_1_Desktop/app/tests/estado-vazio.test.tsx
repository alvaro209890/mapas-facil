// C9 — estados vazios e de erro (F1-02 §Estados vazios, carregamento e erro).
//
// A regra que estes testes protegem: erro mostra **o que aconteceu, por quê e o
// que fazer**, com código copiável — nunca só o código, nunca só "deu erro".

import { cleanup, render, screen } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ErroDoNucleo,
  EstadoVazio,
  NucleoCaido,
  PastaSemShapefile,
  SemArcMap,
  SemChaveDeepSeek,
  SemPastaConectada,
} from "../src/componentes/EstadoVazio.js";

afterEach(cleanup);

describe("EstadoVazio", () => {
  it("erro vira alerta, com código, motivo e o que fazer", () => {
    render(
      <EstadoVazio
        tom="erro"
        codigo="AG-020"
        titulo="O ArcMap não respondeu"
        descricao="O arcpy travou ao abrir o template."
        saidas={["Feche o ArcMap e tente de novo", "Ou gere sem ArcMap"]}
      />,
    );

    const alerta = screen.getByRole("alert");
    expect(alerta).toHaveTextContent("AG-020");
    expect(alerta).toHaveTextContent("O ArcMap não respondeu");
    expect(alerta).toHaveTextContent("O arcpy travou ao abrir o template.");
    expect(screen.getByText("Feche o ArcMap e tente de novo")).toBeInTheDocument();
    expect(screen.getByText("Ou gere sem ArcMap")).toBeInTheDocument();
  });

  it("estado sem erro não é anunciado como alerta", () => {
    render(<EstadoVazio titulo="Sem mapa gerado" descricao="Gere pela galeria." />);
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("ações chamam o handler certo", async () => {
    const primeira = vi.fn();
    const segunda = vi.fn();
    render(
      <EstadoVazio
        titulo="Nenhuma pasta conectada"
        descricao="Conecte para começar."
        acoes={[
          { rotulo: "Conectar pasta", aoAcionar: primeira, primaria: true },
          { rotulo: "Abrir recente", aoAcionar: segunda },
        ]}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Conectar pasta" }));
    expect(primeira).toHaveBeenCalledTimes(1);
    expect(segunda).not.toHaveBeenCalled();
  });
});

describe("casos da tabela de F1-02", () => {
  it("nenhuma pasta conectada oferece conectar", async () => {
    const conectar = vi.fn();
    render(<SemPastaConectada aoConectar={conectar} />);

    await userEvent.click(screen.getByRole("button", { name: "Conectar pasta" }));
    expect(conectar).toHaveBeenCalledTimes(1);
  });

  it("pasta sem shapefile explica o que o app procura e oferece o zip do SIMCAR", () => {
    render(<PastaSemShapefile aoConectarOutra={() => undefined} />);

    expect(screen.getByText("A pasta não tem shapefile")).toBeInTheDocument();
    expect(screen.getByText(/\.zip do SIMCAR na pasta e clicar em reindexar/)).toBeInTheDocument();
  });

  it("núcleo caído mostra UI-001 e o botão de reiniciar", async () => {
    const reiniciar = vi.fn();
    render(<NucleoCaido aoReiniciar={reiniciar} />);

    expect(screen.getByRole("alert")).toHaveTextContent("UI-001");
    await userEvent.click(screen.getByRole("button", { name: "Reiniciar o núcleo" }));
    expect(reiniciar).toHaveBeenCalledTimes(1);
  });

  it("erro fora da allowlist aponta a saída específica do NU-010", () => {
    render(<ErroDoNucleo codigo="NU-010" mensagem="Caminho fora da allowlist." />);

    expect(screen.getByRole("alert")).toHaveTextContent("NU-010");
    expect(screen.getByText(/só lê o que você conectou/)).toBeInTheDocument();
  });

  it("sem chave da DeepSeek é informativo: o app continua funcionando", () => {
    render(<SemChaveDeepSeek />);

    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByText("IA-001")).toBeInTheDocument();
    expect(screen.getByText(/o app continua inteiro/)).toBeInTheDocument();
  });

  it("sem ArcMap diz por qual motor o mapa vai sair", () => {
    render(<SemArcMap motor="nativo" />);

    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByText("Sem ArcMap neste computador")).toBeInTheDocument();
    expect(screen.getByText("nativo")).toBeInTheDocument();
  });
});
