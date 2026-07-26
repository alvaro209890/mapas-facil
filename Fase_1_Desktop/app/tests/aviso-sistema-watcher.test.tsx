// F1-02 §Watcher — arquivo que aparece/some vira aviso do **sistema** no chat.
//
// Não é mensagem do agente: não custa turno, não vai ao LLM, não entra no
// transcript. Sem `workspace.mudou`, nenhum aviso existe (AP-07).

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import {
  MAX_AVISOS_SISTEMA,
  aplicarMudancas,
  avisoDaMudanca,
  idLocalDoCaminho,
} from "../src/estado/avisosSistema.js";
import type { MudancaWorkspace } from "../src/estado/eventos.js";
import { PainelChat } from "../src/paineis/PainelChat.js";
import { desligarPonteFake, ligarPonteFake } from "./ponte-fake.js";

afterEach(() => {
  cleanup();
  desligarPonteFake();
});

const MAPSPEC_COM_AUAS = {
  camadas: [{ fonte: "local.ATP" }, { fonte: "local.AUAS" }, { fonte: "catalogo.embargos_siga" }],
};

function mudanca(over: Partial<MudancaWorkspace> = {}): MudancaWorkspace {
  return {
    acao: "adicionado",
    caminho: "SHP/AUAS_corrigido.shp",
    tipo: "shapefile",
    resumo: "apareceu AUAS_corrigido.shp (AUAS) · 8 feições · 491,26 ha",
    ...over,
  };
}

function emitirMudanca(
  ponte: ReturnType<typeof ligarPonteFake>,
  mudancas: MudancaWorkspace[],
): void {
  ponte.emitir({
    evento: "workspace.mudou",
    dados: { mudancas, workspace: { raiz: "/projeto" } } as unknown as Record<string, unknown>,
  });
}

// --------------------------------------------------------------------- puro

describe("avisoDaMudanca (puro)", () => {
  it("arquivo novo vira info com o resumo do núcleo", () => {
    const aviso = avisoDaMudanca(mudanca(), MAPSPEC_COM_AUAS, "evt1");
    expect(aviso).not.toBeNull();
    expect(aviso!.nivel).toBe("info");
    expect(aviso!.texto).toContain("apareceu AUAS_corrigido.shp");
  });

  it("arquivo removido que o MapSpec ativo usa vira ALERTA e explica a consequência", () => {
    const aviso = avisoDaMudanca(
      mudanca({ acao: "removido", caminho: "SHP/AUAS.shp", resumo: "sumiu AUAS.shp" }),
      MAPSPEC_COM_AUAS,
      "evt1",
    );
    expect(aviso!.nivel).toBe("alerta");
    expect(aviso!.texto).toContain("o mapa atual usa esta camada");
  });

  it("arquivo removido que o MapSpec NÃO usa fica em info", () => {
    const aviso = avisoDaMudanca(
      mudanca({ acao: "removido", caminho: "SHP/OUTRO.shp", resumo: "sumiu OUTRO.shp" }),
      MAPSPEC_COM_AUAS,
      "evt1",
    );
    expect(aviso!.nivel).toBe("info");
  });

  it("sem MapSpec ativo, remoção não vira alerta (não há mapa para quebrar)", () => {
    const aviso = avisoDaMudanca(
      mudanca({ acao: "removido", caminho: "SHP/AUAS.shp", resumo: "sumiu AUAS.shp" }),
      null,
      "evt1",
    );
    expect(aviso!.nivel).toBe("info");
  });

  it("camada de catálogo não conta como arquivo do disco", () => {
    const aviso = avisoDaMudanca(
      mudanca({ acao: "removido", caminho: "SHP/embargos_siga.shp" }),
      { camadas: [{ fonte: "catalogo.embargos_siga" }] },
      "evt1",
    );
    expect(aviso!.nivel).toBe("info");
  });

  it("`modificado` não vira aviso — arquivo reescrito por outro programa é ruído", () => {
    expect(avisoDaMudanca(mudanca({ acao: "modificado" }), MAPSPEC_COM_AUAS, "evt1")).toBeNull();
  });

  it("idLocalDoCaminho tira pasta e extensão", () => {
    expect(idLocalDoCaminho("SHP/AUAS.shp")).toBe("auas");
    expect(idLocalDoCaminho("AUAS.shp")).toBe("auas");
  });

  it("aplicarMudancas mantém só os últimos avisos", () => {
    let avisos = aplicarMudancas([], [], null, "e");
    for (let i = 0; i < MAX_AVISOS_SISTEMA + 5; i += 1) {
      avisos = aplicarMudancas(avisos, [mudanca({ caminho: `SHP/a${i}.shp` })], null, `e${i}`);
    }
    expect(avisos).toHaveLength(MAX_AVISOS_SISTEMA);
  });

  it("lista de mudanças vazia não recria o estado", () => {
    const antes = aplicarMudancas([], [mudanca()], null, "e1");
    expect(aplicarMudancas(antes, [], null, "e2")).toBe(antes);
  });
});

// --------------------------------------------------------------------- componente

function renderChat(mapspec: typeof MAPSPEC_COM_AUAS | null = MAPSPEC_COM_AUAS) {
  return render(
    <PainelChat conversationId="01TESTCONV" semChaveIa={false} mapspecAtivo={mapspec} />,
  );
}

describe("PainelChat — avisos do sistema", () => {
  it("sem workspace.mudou não há aviso nenhum (AP-07)", () => {
    ligarPonteFake();
    renderChat();
    expect(screen.queryByTestId("aviso-sistema")).toBeNull();
  });

  it("arquivo novo aparece como aviso de sistema, não como bolha de mensagem", async () => {
    const ponte = ligarPonteFake();
    const { container } = renderChat();

    emitirMudanca(ponte, [mudanca()]);

    const aviso = await screen.findByTestId("aviso-sistema");
    expect(aviso).toHaveAttribute("data-nivel", "info");
    expect(aviso.textContent).toContain("apareceu AUAS_corrigido.shp");
    // não virou fala de ninguém
    expect(container.querySelector('[data-papel="assistente"]')).toBeNull();
    expect(container.querySelector('[data-papel="usuario"]')).toBeNull();
  });

  it("remoção de camada em uso vira alerta com role=alert", async () => {
    const ponte = ligarPonteFake();
    renderChat();

    emitirMudanca(ponte, [
      mudanca({ acao: "removido", caminho: "SHP/AUAS.shp", resumo: "sumiu AUAS.shp" }),
    ]);

    const aviso = await screen.findByTestId("aviso-sistema");
    expect(aviso).toHaveAttribute("data-nivel", "alerta");
    expect(aviso).toHaveAttribute("role", "alert");
  });

  it("o usuário consegue dispensar o aviso", async () => {
    const ponte = ligarPonteFake();
    renderChat();
    const usuario = userEvent.setup();

    emitirMudanca(ponte, [mudanca()]);
    await screen.findByTestId("aviso-sistema");

    await usuario.click(screen.getByRole("button", { name: /dispensar aviso/ }));
    await waitFor(() => expect(screen.queryByTestId("aviso-sistema")).toBeNull());
  });

  it("várias mudanças no mesmo evento viram vários avisos", async () => {
    const ponte = ligarPonteFake();
    renderChat();

    emitirMudanca(ponte, [
      mudanca({ caminho: "SHP/a.shp", resumo: "apareceu a.shp" }),
      mudanca({ caminho: "SHP/b.shp", resumo: "apareceu b.shp" }),
    ]);

    await waitFor(() => expect(screen.getAllByTestId("aviso-sistema")).toHaveLength(2));
  });

  it("evento malformado é descartado pelo guard", async () => {
    const ponte = ligarPonteFake();
    renderChat();
    ponte.emitir({ evento: "workspace.mudou", dados: { mudancas: "nao e lista" } });
    await new Promise((r) => setTimeout(r, 10));
    expect(screen.queryByTestId("aviso-sistema")).toBeNull();
  });
});
