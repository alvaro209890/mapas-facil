// F1-02: Esc cancela o turno do chat; o botão da barra cancela o job — nunca os dois.

import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { App } from "../src/App.js";
import { PainelChat } from "../src/paineis/PainelChat.js";
import { BarraProgressoJob } from "../src/componentes/BarraProgressoJob.js";
import type { RelatorioDoctor } from "../src/estado/doctor.js";
import { TEMA_PADRAO } from "../src/estado/tema.js";
import { desligarPonteFake, ligarPonteFake } from "./ponte-fake.js";
import doctorFixture from "./fixtures/doctor-rodar.json";

const RELATORIO = doctorFixture as unknown as RelatorioDoctor;
const CONVERSA_VAZIA = { ok: true as const, resultado: { mensagens: [] } };

afterEach(() => {
  cleanup();
  desligarPonteFake();
  document.documentElement.dataset.tema = TEMA_PADRAO;
});

describe("Esc cancela turno, não o job", () => {
  it("Esc durante o turno chama chat.cancelar e não mapa.cancelar", async () => {
    let liberar: (() => void) | undefined;
    const ponte = ligarPonteFake({
      respostas: {
        "chat.abrir_conversa": CONVERSA_VAZIA,
        "chat.cancelar": { ok: true, resultado: { ok: true } },
        "mapa.cancelar": { ok: true, resultado: { ok: true } },
      },
    });
    ponte.responder("chat.enviar", () => {
      const espera = new Promise<void>((resolve) => {
        liberar = resolve;
      });
      return espera.then(() => ({ ok: true, resultado: { texto: "" } })) as never;
    });

    render(<PainelChat conversationId="c1" semChaveIa={false} />);
    await userEvent.type(screen.getByRole("textbox"), "faz a Dinâmica");
    await userEvent.click(screen.getByRole("button", { name: "Enviar" }));
    await screen.findByRole("button", { name: "Parar" });

    await userEvent.keyboard("{Escape}");
    await waitFor(() =>
      expect(ponte.chamadas.some((c) => c.metodo === "chat.cancelar")).toBe(true),
    );
    expect(ponte.chamadas.some((c) => c.metodo === "mapa.cancelar")).toBe(false);
    liberar?.();
  });

  it("botão Cancelar geração chama mapa.cancelar e Esc sozinho não o faz", async () => {
    const ponte = ligarPonteFake({
      respostas: {
        "doctor.rodar": { ok: true, resultado: RELATORIO },
        "mapa.cancelar": { ok: true, resultado: { ok: true } },
      },
    });
    render(
      <BarraProgressoJob
        ativo
        onCancelar={() => {
          void ponte.api.chamar("mapa.cancelar", { job_id: "job-1" });
        }}
      />,
    );
    ponte.emitir({
      evento: "job.progresso",
      dados: { etapa: "validando_spec", pct: 3, job_id: "job-1" },
    });

    await userEvent.keyboard("{Escape}");
    expect(ponte.chamadas.some((c) => c.metodo === "mapa.cancelar")).toBe(false);

    await userEvent.click(screen.getByRole("button", { name: "Cancelar geração" }));
    expect(ponte.chamadas.some((c) => c.metodo === "mapa.cancelar")).toBe(true);
  });
});

describe("banner offline", () => {
  it("evento offline mostra o banner; online remove", async () => {
    ligarPonteFake({
      respostas: { "doctor.rodar": { ok: true, resultado: RELATORIO } },
    });
    render(<App />);
    await waitFor(() => expect(document.getElementById("doctor-resumo")).toBeInTheDocument());
    expect(screen.queryByTestId("banner-offline")).toBeNull();

    act(() => {
      window.dispatchEvent(new Event("offline"));
    });
    await waitFor(() => expect(screen.getByTestId("banner-offline")).toBeInTheDocument());
    expect(screen.getByText("Sem internet")).toBeInTheDocument();

    act(() => {
      window.dispatchEvent(new Event("online"));
    });
    await waitFor(() => expect(screen.queryByTestId("banner-offline")).toBeNull());
  });
});
