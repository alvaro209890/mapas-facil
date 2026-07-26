// R14 — menu de contexto da `barra-chats`: renomear · arquivar/desarquivar ·
// ramificar · apagar. Os quatro batem em método NDJSON real do núcleo (M6).

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppShell } from "../src/layout/AppShell.js";
import { BarraChats } from "../src/paineis/BarraChats.js";
import type { ConversaResumo } from "../src/estado/conversas.js";
import { desligarPonteFake, ligarPonteFake } from "./ponte-fake.js";

const CONVERSA: ConversaResumo = {
  conversation_id: "01CONV",
  title: "Dinâmica 2026",
  updated_at: new Date().toISOString(),
  workspace_nome: "Harmonia",
  arquivada: false,
  mensagens_total: 7,
  ultimo_trecho: "gerei o mapa",
};

afterEach(() => {
  cleanup();
  desligarPonteFake();
  vi.restoreAllMocks();
});

function renderBarra(over: Partial<React.ComponentProps<typeof BarraChats>> = {}) {
  const handlers = {
    aoCriar: vi.fn(),
    aoBuscar: vi.fn(),
    aoSelecionar: vi.fn(),
    aoAlternarFiltro: vi.fn(),
    aoApagar: vi.fn(),
    aoRenomear: vi.fn(),
    aoArquivar: vi.fn(),
    aoRamificar: vi.fn(),
    aoAlternarArquivadas: vi.fn(),
  };
  render(
    <BarraChats
      situacao="pronta"
      conversas={[CONVERSA]}
      busca=""
      resultadosBusca={[]}
      filtrarPastaAtual={false}
      conversaAtiva={null}
      workspaceNome="Harmonia"
      erro={null}
      mostrarArquivadas={false}
      {...handlers}
      {...over}
    />,
  );
  return handlers;
}

async function abrirMenu() {
  const usuario = userEvent.setup();
  await usuario.click(screen.getByRole("button", { name: /Ações de Dinâmica 2026/ }));
  await screen.findByTestId("menu-chat");
  return usuario;
}

describe("BarraChats — menu de contexto (R14)", () => {
  it("o menu só abre quando pedido", async () => {
    renderBarra();
    expect(screen.queryByTestId("menu-chat")).toBeNull();
    await abrirMenu();
    expect(screen.getByTestId("menu-chat")).toBeInTheDocument();
  });

  it("mostra as quatro ações", async () => {
    renderBarra();
    await abrirMenu();
    const itens = screen.getAllByRole("menuitem").map((b) => b.textContent);
    expect(itens).toEqual(["Renomear", "Arquivar", "Ramificar daqui", "Apagar"]);
  });

  it("renomear troca o item por um campo e confirma com Enter", async () => {
    const handlers = renderBarra();
    const usuario = await abrirMenu();

    await usuario.click(screen.getByRole("menuitem", { name: /Renomear/ }));
    const campo = await screen.findByLabelText("Novo título da conversa");
    await usuario.clear(campo);
    await usuario.type(campo, "Tipologia 2026{Enter}");

    expect(handlers.aoRenomear).toHaveBeenCalledWith("01CONV", "Tipologia 2026");
  });

  it("renomear com Esc cancela sem chamar o núcleo", async () => {
    const handlers = renderBarra();
    const usuario = await abrirMenu();

    await usuario.click(screen.getByRole("menuitem", { name: /Renomear/ }));
    const campo = await screen.findByLabelText("Novo título da conversa");
    await usuario.type(campo, "nao vale{Escape}");

    expect(handlers.aoRenomear).not.toHaveBeenCalled();
    await waitFor(() => expect(screen.getByText("Dinâmica 2026")).toBeInTheDocument());
  });

  it("arquivar manda `arquivada: true`", async () => {
    const handlers = renderBarra();
    const usuario = await abrirMenu();
    await usuario.click(screen.getByRole("menuitem", { name: /Arquivar/ }));
    expect(handlers.aoArquivar).toHaveBeenCalledWith("01CONV", true);
  });

  it("conversa já arquivada oferece desarquivar, mandando `false`", async () => {
    const handlers = renderBarra({ conversas: [{ ...CONVERSA, arquivada: true }] });
    const usuario = await abrirMenu();
    await usuario.click(screen.getByRole("menuitem", { name: /Desarquivar/ }));
    expect(handlers.aoArquivar).toHaveBeenCalledWith("01CONV", false);
  });

  it("ramificar entrega a conversa inteira (o store deriva o seq)", async () => {
    const handlers = renderBarra();
    const usuario = await abrirMenu();
    await usuario.click(screen.getByRole("menuitem", { name: /Ramificar daqui/ }));
    expect(handlers.aoRamificar).toHaveBeenCalledWith(CONVERSA);
  });

  it("apagar confirma antes — recusar não apaga", async () => {
    const handlers = renderBarra();
    const confirmar = vi.spyOn(window, "confirm").mockReturnValue(false);
    const usuario = await abrirMenu();

    await usuario.click(screen.getByRole("menuitem", { name: /Apagar/ }));
    expect(confirmar).toHaveBeenCalled();
    expect(handlers.aoApagar).not.toHaveBeenCalled();
  });

  it("apagar confirmado chama o núcleo", async () => {
    const handlers = renderBarra();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const usuario = await abrirMenu();
    await usuario.click(screen.getByRole("menuitem", { name: /Apagar/ }));
    expect(handlers.aoApagar).toHaveBeenCalledWith("01CONV");
  });

  it("Esc fecha o menu sem executar ação", async () => {
    renderBarra();
    const usuario = await abrirMenu();
    await usuario.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByTestId("menu-chat")).toBeNull());
  });

  it("o botão de arquivadas só aparece quando há handler", () => {
    renderBarra({ aoAlternarArquivadas: undefined });
    expect(screen.queryByRole("button", { name: /Arquivadas/ })).toBeNull();
  });
});

// ------------------------------------------------------- integração NDJSON

describe("BarraChats no AppShell — os quatro métodos NDJSON", () => {
  beforeEach(() => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
  });

  it("cada ação do menu vira a chamada NDJSON correspondente", async () => {
    const ponte = ligarPonteFake({
      respostas: {
        "chat.listar_conversas": { ok: true, resultado: { conversas: [CONVERSA], tem_mais: false } },
        "chat.renomear": { ok: true, resultado: { ok: true } },
        "chat.arquivar": { ok: true, resultado: { ok: true } },
        "chat.ramificar": { ok: true, resultado: { conversation_id: "01NOVA" } },
        "chat.apagar": { ok: true, resultado: { ok: true } },
      },
    });
    render(<AppShell nucleo={{ estado: "pronto", erro: null }} />);
    await screen.findByText("Dinâmica 2026");
    const usuario = userEvent.setup();

    // arquivar
    await usuario.click(screen.getByRole("button", { name: /Ações de Dinâmica 2026/ }));
    await usuario.click(await screen.findByRole("menuitem", { name: /Arquivar/ }));
    await waitFor(() =>
      expect(ponte.chamadas.find((c) => c.metodo === "chat.arquivar")?.params).toEqual({
        conversation_id: "01CONV",
        arquivada: true,
      }),
    );

    // ramificar — o seq sai de `mensagens_total`
    await usuario.click(screen.getByRole("button", { name: /Ações de Dinâmica 2026/ }));
    await usuario.click(await screen.findByRole("menuitem", { name: /Ramificar daqui/ }));
    await waitFor(() =>
      expect(ponte.chamadas.find((c) => c.metodo === "chat.ramificar")?.params).toEqual({
        conversation_id: "01CONV",
        a_partir_do_seq: 7,
      }),
    );

    // apagar
    await usuario.click(screen.getByRole("button", { name: /Ações de Dinâmica 2026/ }));
    await usuario.click(await screen.findByRole("menuitem", { name: /Apagar/ }));
    await waitFor(() =>
      expect(ponte.chamadas.find((c) => c.metodo === "chat.apagar")?.params).toEqual({
        conversation_id: "01CONV",
      }),
    );
  });

  it("mostrar arquivadas relista pedindo `incluir_arquivadas`", async () => {
    const ponte = ligarPonteFake({
      respostas: {
        "chat.listar_conversas": { ok: true, resultado: { conversas: [CONVERSA], tem_mais: false } },
      },
    });
    render(<AppShell nucleo={{ estado: "pronto", erro: null }} />);
    await screen.findByText("Dinâmica 2026");

    await userEvent.setup().click(screen.getByRole("button", { name: /Arquivadas/ }));
    await waitFor(() =>
      expect(
        ponte.chamadas.some(
          (c) => c.metodo === "chat.listar_conversas" && c.params.incluir_arquivadas === true,
        ),
      ).toBe(true),
    );
  });
});
