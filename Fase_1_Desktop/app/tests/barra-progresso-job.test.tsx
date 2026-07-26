// C6 — `barra-progresso-job` com eventos `job.progresso` injetados pela ponte.
//
// Os eventos entram pelo mesmo caminho do app (`window.mapasfacil.aoEvento`), não
// por prop: o que está sob teste é a UI reagindo a evento real do núcleo (AP-07).

import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { BarraProgressoJob } from "../src/componentes/BarraProgressoJob.js";
import type { DadosJobProgresso, EnvelopeEvento } from "../src/estado/eventos.js";
import { ETAPAS_JOB } from "../src/estado/eventos.js";
import { aplicarProgresso, jobConcluido } from "../src/estado/progressoJob.js";

type Emitir = (dados: DadosJobProgresso) => void;

/** Ponte de mentira: só o suficiente para entregar evento ao renderer. */
function ligarPonteFake(): Emitir {
  const ouvintes = new Set<(evento: EnvelopeEvento) => void>();
  window.mapasfacil = {
    chamar: () => Promise.resolve({ ok: true }),
    reiniciarNucleo: () => Promise.resolve({ estado: "pronto" }),
    aoEvento(ouvinte) {
      ouvintes.add(ouvinte);
      return () => {
        ouvintes.delete(ouvinte);
      };
    },
    aoEstadoNucleo: () => () => undefined,
    lerPreferencias: () => Promise.resolve({}),
    gravarPreferencias: (parcial) => Promise.resolve(parcial),
  };

  let sequencia = 0;
  return (dados) => {
    sequencia += 1;
    const evento: EnvelopeEvento = {
      v: 1,
      id: `01JTESTE${String(sequencia).padStart(4, "0")}`,
      tipo: "evt",
      evento: "job.progresso",
      dados: dados as unknown as Record<string, unknown>,
    };
    act(() => {
      for (const ouvinte of ouvintes) ouvinte(evento);
    });
  };
}

function barra(): HTMLElement {
  return screen.getByRole("progressbar");
}

function segmento(etapa: string): HTMLElement {
  const alvo = document.querySelector<HTMLElement>(`[data-etapa="${etapa}"]`);
  if (alvo === null) throw new Error(`segmento ausente: ${etapa}`);
  return alvo;
}

afterEach(() => {
  cleanup();
  delete window.mapasfacil;
});

describe("BarraProgressoJob", () => {
  it("sem job e sem evento não renderiza nada", () => {
    ligarPonteFake();
    const { container } = render(<BarraProgressoJob />);
    expect(container).toBeEmptyDOMElement();
  });

  it("job despachado sem evento mostra 'gerando…' sem barra e sem porcentagem (AP-07)", () => {
    ligarPonteFake();
    render(<BarraProgressoJob ativo />);

    expect(screen.getByText("gerando…")).toBeInTheDocument();
    expect(screen.queryByRole("progressbar")).toBeNull();
    expect(screen.queryByText(/%/)).toBeNull();
  });

  it("primeiro job.progresso liga a barra com aria-valuenow e a etapa em português", () => {
    const emitir = ligarPonteFake();
    render(<BarraProgressoJob ativo />);

    emitir({ etapa: "validando_spec", pct: 3 });

    expect(barra()).toHaveAttribute("aria-valuenow", "3");
    expect(barra()).toHaveAttribute("aria-valuemax", "100");
    expect(screen.getByText("validando a especificação")).toBeInTheDocument();
    expect(screen.getByText("3%")).toBeInTheDocument();
    expect(segmento("validando_spec")).toHaveAttribute("data-estado", "concluida");
    expect(segmento("baixando_externas")).toHaveAttribute("data-estado", "pendente");
  });

  it("mostra as 10 etapas do contrato, na ordem, com os rótulos pt-BR", () => {
    const emitir = ligarPonteFake();
    render(<BarraProgressoJob ativo />);
    emitir({ etapa: "validando_spec", pct: 3 });

    const segmentos = [...barra().querySelectorAll<HTMLElement>("[data-etapa]")];
    expect(segmentos).toHaveLength(10);
    expect(segmentos.map((s) => s.dataset.etapa)).toEqual(ETAPAS_JOB.map((e) => e.id));
    expect(segmentos.map((s) => s.getAttribute("title"))).toEqual(ETAPAS_JOB.map((e) => e.rotulo));
  });

  it("evento com item mostra a camada e deixa a etapa em andamento", () => {
    const emitir = ligarPonteFake();
    render(<BarraProgressoJob ativo />);

    emitir({ etapa: "resolvendo_camadas_locais", pct: 10 });
    emitir({ etapa: "baixando_externas", pct: 20, item: "lim_municipios_mt" });

    expect(barra()).toHaveAttribute("aria-valuenow", "20");
    expect(screen.getByText("baixando camadas externas")).toBeInTheDocument();
    expect(screen.getByText("· lim_municipios_mt")).toBeInTheDocument();
    expect(segmento("resolvendo_camadas_locais")).toHaveAttribute("data-estado", "concluida");
    expect(segmento("baixando_externas")).toHaveAttribute("data-estado", "ativa");
  });

  it("pct é monotônico: evento atrasado não faz a barra andar para trás", () => {
    const emitir = ligarPonteFake();
    render(<BarraProgressoJob ativo />);

    emitir({ etapa: "baixando_externas", pct: 30 });
    expect(barra()).toHaveAttribute("aria-valuenow", "30");

    emitir({ etapa: "resolvendo_camadas_locais", pct: 10 });
    expect(barra()).toHaveAttribute("aria-valuenow", "30");
    expect(segmento("baixando_externas")).toHaveAttribute("data-estado", "concluida");
  });

  it("no fim das 10 etapas chega a 100% com todos os segmentos concluídos", () => {
    const emitir = ligarPonteFake();
    render(<BarraProgressoJob ativo />);

    let acumulado = 0;
    for (const etapa of ETAPAS_JOB) {
      acumulado += etapa.peso;
      emitir({ etapa: etapa.id, pct: acumulado });
    }

    expect(barra()).toHaveAttribute("aria-valuenow", "100");
    for (const etapa of ETAPAS_JOB) {
      expect(segmento(etapa.id)).toHaveAttribute("data-estado", "concluida");
    }
  });

  it("cancelar o job é botão próprio, e só existe quando há handler", () => {
    const emitir = ligarPonteFake();
    const { rerender } = render(<BarraProgressoJob ativo />);
    emitir({ etapa: "validando_spec", pct: 3 });
    expect(screen.queryByRole("button", { name: "Cancelar geração" })).toBeNull();

    rerender(<BarraProgressoJob ativo onCancelar={() => undefined} />);
    expect(screen.getByRole("button", { name: "Cancelar geração" })).toBeInTheDocument();
  });
});

describe("aplicarProgresso", () => {
  it("nunca deixa pct andar para trás nem passar de 100", () => {
    const um = aplicarProgresso(null, { etapa: "aplicando_layout", pct: 70 });
    const dois = aplicarProgresso(um, { etapa: "aplicando_layout", pct: 12 });
    const tres = aplicarProgresso(dois, { etapa: "validando_saida", pct: 140 });

    expect(um.pct).toBe(70);
    expect(dois.pct).toBe(70);
    expect(tres.pct).toBe(100);
    expect(jobConcluido(tres)).toBe(true);
    expect(jobConcluido(um)).toBe(false);
  });

  it("etapa fora do contrato não corrompe o estado", () => {
    const bom = aplicarProgresso(null, { etapa: "validando_spec", pct: 3 });
    const invasor = aplicarProgresso(bom, {
      etapa: "etapa_que_nao_existe" as never,
      pct: 99,
    });
    expect(invasor).toBe(bom);
  });
});
