// M7 — PainelChat: streaming, parar (chat.cancelar) e erros tipados do agente.

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { mensagemDeErro, PainelChat } from "../src/paineis/PainelChat.js";
import { desligarPonteFake, ligarPonteFake } from "./ponte-fake.js";

afterEach(() => {
  cleanup();
  desligarPonteFake();
});

const CONVERSA_VAZIA = { ok: true as const, resultado: { mensagens: [] } };

describe("mensagemDeErro", () => {
  it("põe o código na frente e diz o que fazer", () => {
    expect(mensagemDeErro({ codigo: "IA-030", mensagem: "Limite de 12 rodadas." })).toContain(
      "IA-030",
    );
    expect(mensagemDeErro({ codigo: "IA-040", mensagem: "grande demais" })).toContain("Ramifique");
    expect(mensagemDeErro({ codigo: "NU-001", mensagem: "faltou parâmetro" })).toBe(
      "NU-001: faltou parâmetro",
    );
  });
});

describe("PainelChat", () => {
  it("mostra o delta enquanto o turno roda e troca Enviar por Parar", async () => {
    let liberar: (() => void) | undefined;
    const ponte = ligarPonteFake({
      respostas: {
        "chat.abrir_conversa": CONVERSA_VAZIA,
        "chat.enviar": () => ({ ok: true, resultado: { texto: "pronto" } }),
        "chat.cancelar": { ok: true, resultado: { ok: true } },
      },
    });
    // segura a resposta de chat.enviar até o teste apertar Parar
    ponte.responder("chat.enviar", () => {
      const espera = new Promise<void>((resolve) => {
        liberar = resolve;
      });
      return espera.then(() => ({ ok: true, resultado: { texto: "" } })) as never;
    });

    render(<PainelChat conversationId="c1" semChaveIa={false} />);
    await userEvent.type(screen.getByRole("textbox"), "faz a Dinâmica");
    await userEvent.click(screen.getByRole("button", { name: "Enviar" }));

    ponte.emitir({ evento: "chat.delta", dados: { texto: "Estou montando…" } });
    await waitFor(() => expect(screen.getByText("Estou montando…")).toBeTruthy());

    const parar = await screen.findByRole("button", { name: "Parar" });
    await userEvent.click(parar);
    expect(ponte.chamadas.some((c) => c.metodo === "chat.cancelar")).toBe(true);
    liberar?.();
  });

  it("recarrega o transcript quando o turno falha, para não perder o parcial", async () => {
    const ponte = ligarPonteFake({
      respostas: {
        "chat.abrir_conversa": {
          ok: true,
          resultado: {
            mensagens: [
              { message_id: "m1", papel: "assistente", conteudo: "parcial", cancelada: true },
            ],
          },
        },
        "chat.enviar": {
          ok: false,
          erro: { codigo: "IA-030", mensagem: "Limite de 12 rodadas de tool neste turno." },
        },
      },
    });

    render(<PainelChat conversationId="c1" semChaveIa={false} />);
    await userEvent.type(screen.getByRole("textbox"), "loop");
    await userEvent.click(screen.getByRole("button", { name: "Enviar" }));

    await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("IA-030"));
    expect(screen.getByText("parcial")).toBeTruthy();
    expect(screen.getByText("resposta interrompida por você")).toBeTruthy();
    const recarregou = ponte.chamadas.filter((c) => c.metodo === "chat.abrir_conversa");
    expect(recarregou.length).toBeGreaterThan(1);
  });

  it("lista as tools chamadas no turno", async () => {
    const ponte = ligarPonteFake({
      respostas: {
        "chat.abrir_conversa": CONVERSA_VAZIA,
        "chat.enviar": { ok: true, resultado: { texto: "ok" } },
      },
    });
    render(<PainelChat conversationId="c1" semChaveIa={false} />);
    ponte.emitir({
      evento: "chat.tool",
      dados: { tool: "usar_modelo_da_galeria", fase: "inicio", trace_id: "t1" },
    });
    await waitFor(() =>
      expect(screen.getByText(/usar_modelo_da_galeria/)).toBeTruthy(),
    );
  });

  it("chat.pergunta mostra chips e clicar num deles envia como mensagem normal", async () => {
    const ponte = ligarPonteFake({
      respostas: {
        "chat.abrir_conversa": CONVERSA_VAZIA,
        "chat.enviar": { ok: true, resultado: { texto: "ok" } },
      },
    });
    render(<PainelChat conversationId="c1" semChaveIa={false} />);
    ponte.emitir({
      evento: "chat.pergunta",
      dados: {
        pergunta: "Qual desses arquivos é o perímetro (ATP)?",
        opcoes: [
          { id: "A", rotulo: "Fazenda_Harmonia.shp" },
          { id: "B", rotulo: "Area_do_PEF.shp" },
        ],
        permite_texto_livre: true,
      },
    });
    await waitFor(() =>
      expect(screen.getByText("Qual desses arquivos é o perímetro (ATP)?")).toBeTruthy(),
    );

    await userEvent.click(screen.getByRole("button", { name: "Fazenda_Harmonia.shp" }));

    await waitFor(() =>
      expect(
        ponte.chamadas.some(
          (c) =>
            c.metodo === "chat.enviar" &&
            (c.params as { mensagem?: string }).mensagem === "Fazenda_Harmonia.shp",
        ),
      ).toBe(true),
    );
    // novo turno começou: o cartão de pergunta some, não fica pendurado.
    expect(screen.queryByText("Qual desses arquivos é o perímetro (ATP)?")).toBeNull();
  });

  it("chat.pergunta aceita resposta pelo campo de texto livre", async () => {
    const ponte = ligarPonteFake({
      respostas: {
        "chat.abrir_conversa": CONVERSA_VAZIA,
        "chat.enviar": { ok: true, resultado: { texto: "ok" } },
      },
    });
    render(<PainelChat conversationId="c1" semChaveIa={false} />);
    ponte.emitir({
      evento: "chat.pergunta",
      dados: {
        pergunta: "Qual é o perímetro?",
        opcoes: [{ id: "A", rotulo: "Fazenda_Harmonia.shp" }],
        permite_texto_livre: true,
      },
    });
    await waitFor(() => expect(screen.getByText("Qual é o perímetro?")).toBeTruthy());

    await userEvent.type(
      screen.getByPlaceholderText("Ou digite sua resposta…"),
      "É o SIEGEF.shp, não está na lista",
    );
    await userEvent.click(screen.getByRole("button", { name: "Responder" }));

    await waitFor(() =>
      expect(
        ponte.chamadas.some(
          (c) =>
            c.metodo === "chat.enviar" &&
            (c.params as { mensagem?: string }).mensagem === "É o SIEGEF.shp, não está na lista",
        ),
      ).toBe(true),
    );
  });
});
