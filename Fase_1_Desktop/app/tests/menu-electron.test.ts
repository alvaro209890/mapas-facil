// Menus/tray nativos (F1-02) — o template é puro; o teste inspeciona sem abrir Electron.
//
// Regra: cada item acionável despacha um `IdComando` da paleta (ou recentes/
// reinício no main). Menu e Ctrl+K não podem divergir de comportamento.

import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("electron", () => ({
  app: { getName: () => "Mapas Fácil" },
  BrowserWindow: class {},
  Menu: {
    buildFromTemplate: (itens: unknown) => itens,
    setApplicationMenu: vi.fn(),
  },
  Tray: class {
    setToolTip() {
      return undefined;
    }
    setContextMenu() {
      return undefined;
    }
    on() {
      return undefined;
    }
    destroy() {
      return undefined;
    }
  },
  nativeImage: { createEmpty: () => ({}), createFromPath: () => ({}) },
}));

import {
  montarTemplateMenu,
  montarTemplateTray,
  type IdComandoMenu,
  type OpcoesMenu,
} from "../electron/menu.js";

afterEach(() => {
  vi.clearAllMocks();
});

function opcoesBase(parcial: Partial<OpcoesMenu> = {}): OpcoesMenu {
  return {
    janela: null,
    recentes: [],
    aoAbrirRecente: vi.fn(),
    aoReiniciarNucleo: vi.fn(),
    aoComando: vi.fn(),
    ...parcial,
  };
}

function rotulos(itens: Electron.MenuItemConstructorOptions[]): string[] {
  return itens.flatMap((item) => {
    const label = typeof item.label === "string" ? [item.label] : [];
    const filhos = Array.isArray(item.submenu) ? rotulos(item.submenu) : [];
    return [...label, ...filhos];
  });
}

function acharClique(
  itens: Electron.MenuItemConstructorOptions[],
  label: string,
): (() => void) | undefined {
  for (const item of itens) {
    if (item.label === label && typeof item.click === "function") {
      return () => item.click!(undefined as never, undefined, undefined as never);
    }
    if (Array.isArray(item.submenu)) {
      const achou = acharClique(item.submenu, label);
      if (achou) return achou;
    }
  }
  return undefined;
}

describe("montarTemplateMenu", () => {
  it("expõe os comandos da paleta com os atalhos de F1-02", () => {
    const template = montarTemplateMenu(opcoesBase());
    const textos = rotulos(template);
    expect(textos).toContain("Conectar pasta…");
    expect(textos).toContain("Nova conversa");
    expect(textos).toContain("Buscar nas conversas");
    expect(textos).toContain("Preferências");
    expect(textos).toContain("Diagnóstico do ambiente (doctor)");
    expect(textos).toContain("Reiniciar núcleo");
  });

  it("despacha IdComando da paleta — não implementa comportamento próprio", () => {
    const aoComando = vi.fn<(id: IdComandoMenu) => void>();
    const template = montarTemplateMenu(opcoesBase({ aoComando }));
    acharClique(template, "Conectar pasta…")?.();
    acharClique(template, "Nova conversa")?.();
    acharClique(template, "Preferências")?.();
    expect(aoComando.mock.calls.map((c) => c[0])).toEqual([
      "conectar-pasta",
      "nova-conversa",
      "preferencias",
    ]);
  });

  it("lista recentes por índice (caminho nunca sai do main)", () => {
    const aoAbrirRecente = vi.fn();
    const template = montarTemplateMenu(
      opcoesBase({
        recentes: [{ indice: 2, nome: "Harmonia" }],
        aoAbrirRecente,
      }),
    );
    acharClique(template, "Harmonia")?.();
    expect(aoAbrirRecente).toHaveBeenCalledWith(2);
  });

  it("reiniciar núcleo fica no main — não vira IdComando", () => {
    const aoReiniciarNucleo = vi.fn();
    const aoComando = vi.fn();
    const template = montarTemplateMenu(opcoesBase({ aoReiniciarNucleo, aoComando }));
    acharClique(template, "Reiniciar núcleo")?.();
    expect(aoReiniciarNucleo).toHaveBeenCalledTimes(1);
    expect(aoComando).not.toHaveBeenCalled();
  });
});

describe("montarTemplateTray", () => {
  it("é mínimo: mostrar, conectar, sair", () => {
    const aoComando = vi.fn();
    const template = montarTemplateTray(opcoesBase({ aoComando }));
    expect(rotulos(template)).toEqual(["Mostrar janela", "Conectar pasta…", "Sair"]);
    acharClique(template, "Conectar pasta…")?.();
    expect(aoComando).toHaveBeenCalledWith("conectar-pasta");
  });
});
