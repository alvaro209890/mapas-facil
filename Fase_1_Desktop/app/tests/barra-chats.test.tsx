// M6 — barra de chats: lista, criar, busca e agrupamento.

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "../src/App.js";
import { agruparPorData, type ConversaResumo } from "../src/estado/conversas.js";
import type { RelatorioDoctor } from "../src/estado/doctor.js";
import { BarraChats } from "../src/paineis/BarraChats.js";
import { desligarPonteFake, ligarPonteFake } from "./ponte-fake.js";
import doctorFixture from "./fixtures/doctor-rodar.json";

const RELATORIO = doctorFixture as unknown as RelatorioDoctor;

afterEach(() => {
  cleanup();
  desligarPonteFake();
});

describe("agruparPorData", () => {
  it("separa hoje / ontem / 7 dias / antes", () => {
    const agora = new Date("2026-07-26T15:00:00.000Z");
    const base: Omit<ConversaResumo, "conversation_id" | "updated_at" | "title"> = {
      workspace_nome: null,
      arquivada: false,
      mensagens_total: 1,
      ultimo_trecho: "",
    };
    const itens: ConversaResumo[] = [
      { ...base, conversation_id: "1", title: "hoje", updated_at: "2026-07-26T12:00:00.000Z" },
      { ...base, conversation_id: "2", title: "ontem", updated_at: "2026-07-25T12:00:00.000Z" },
      { ...base, conversation_id: "3", title: "semana", updated_at: "2026-07-22T12:00:00.000Z" },
      { ...base, conversation_id: "4", title: "velha", updated_at: "2026-06-01T12:00:00.000Z" },
    ];
    const grupos = agruparPorData(itens, agora);
    expect(grupos.map((g) => g.rotulo)).toEqual(["Hoje", "Ontem", "7 dias", "Antes"]);
  });
});

describe("BarraChats", () => {
  it("mostra vazio honesto e cria conversa pelo botão Novo", async () => {
    const aoCriar = vi.fn();
    render(
      <BarraChats
        situacao="pronta"
        conversas={[]}
        busca=""
        resultadosBusca={[]}
        filtrarPastaAtual={false}
        conversaAtiva={null}
        workspaceNome={null}
        erro={null}
        aoCriar={aoCriar}
        aoBuscar={() => undefined}
        aoSelecionar={() => undefined}
        aoAlternarFiltro={() => undefined}
        aoApagar={() => undefined}
      />,
    );
    expect(screen.getByText("Nenhuma conversa ainda")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Nova conversa" }));
    expect(aoCriar).toHaveBeenCalledTimes(1);
  });

  it("no AppShell, listar e criar passam pelo NDJSON", async () => {
    const ponte = ligarPonteFake({
      respostas: { "doctor.rodar": { ok: true, resultado: RELATORIO } },
    });
    render(<App />);
    await waitFor(() => expect(document.getElementById("busca-chats")).toBeInTheDocument());
    expect(ponte.chamadas.some((c) => c.metodo === "chat.listar_conversas")).toBe(true);

    await userEvent.click(screen.getByRole("button", { name: "Nova conversa" }));
    await waitFor(() =>
      expect(ponte.chamadas.some((c) => c.metodo === "chat.criar_conversa")).toBe(true),
    );
  });
});
