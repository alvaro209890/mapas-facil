// C8 — `doctor-resumo` com a resposta real de `doctor.rodar`.
//
// Fixture gerada por `tests/fixtures/gerar-fixture-workspace.py`. O ponto do teste
// é que a UI não inventa check: o que o núcleo reporta como `nao_testado` aparece
// como não testado, e chave ausente é aviso — não erro, porque o app continua.

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { DoctorResumo } from "../src/componentes/DoctorResumo.js";
import type { RelatorioDoctor } from "../src/estado/doctor.js";
import { checksDoRelatorio, tomGeral } from "../src/estado/doctor.js";
import { desligarPonteFake, ligarPonteFake } from "./ponte-fake.js";
import fixture from "./fixtures/doctor-rodar.json";

const RELATORIO = fixture as unknown as RelatorioDoctor;

function check(id: string): HTMLElement {
  const alvo = document.querySelector<HTMLElement>(`p[data-check="${id}"]`);
  if (alvo === null) throw new Error(`check ausente: ${id}`);
  return alvo;
}

afterEach(() => {
  cleanup();
  desligarPonteFake();
});

describe("DoctorResumo", () => {
  it("mostra o diagnóstico que o núcleo devolveu, com estado em texto e não só em cor", async () => {
    ligarPonteFake({ respostas: { "doctor.rodar": { ok: true, resultado: RELATORIO } } });
    render(<DoctorResumo />);

    await waitFor(() => expect(check("nucleo")).toBeInTheDocument());

    expect(check("nucleo")).toHaveTextContent("v0.4.0");
    expect(check("nucleo")).toHaveTextContent("ok");
    expect(check("motor")).toHaveTextContent("nativo");
    expect(check("motor")).toHaveTextContent("atenção");
    expect(check("ogr2ogr")).toHaveTextContent("disponível");
  });

  it("chave ausente é aviso, com a saída explicada — o app não para por isso", async () => {
    ligarPonteFake({ respostas: { "doctor.rodar": { ok: true, resultado: RELATORIO } } });
    render(<DoctorResumo />);

    await waitFor(() => expect(check("chave-deepseek")).toBeInTheDocument());
    expect(check("chave-deepseek")).toHaveTextContent("ausente");
    expect(check("chave-deepseek")).toHaveTextContent("atenção");
    expect(check("chave-deepseek")).toHaveTextContent("galeria e geração funcionam");
    expect(check("chave-sema")).toHaveTextContent("configurada");
  });

  it("rede não testada aparece como não testada, nunca como ok", async () => {
    ligarPonteFake({ respostas: { "doctor.rodar": { ok: true, resultado: RELATORIO } } });
    render(<DoctorResumo />);

    await waitFor(() => expect(check("rede-sema")).toBeInTheDocument());
    expect(check("rede-sema")).toHaveTextContent("não testado");
    expect(check("rede-sema").querySelector("[data-tom]")).toHaveAttribute(
      "data-tom",
      "desconhecido",
    );
  });

  it("núcleo fora do ar mostra o código, sem inventar checks verdes", async () => {
    ligarPonteFake({
      respostas: {
        "doctor.rodar": {
          ok: false,
          erro: { codigo: "UI-001", mensagem: "O núcleo não está rodando." },
        },
      },
    });
    render(<DoctorResumo />);

    await waitFor(() => expect(screen.getByText("UI-001")).toBeInTheDocument());
    expect(screen.getByText(/diagnóstico indisponível/)).toBeInTheDocument();
    expect(document.querySelector("p[data-check]")).toBeNull();
  });

  it("núcleo que volta ao ar redispara o diagnóstico sozinho", async () => {
    const ponte = ligarPonteFake({
      respostas: {
        "doctor.rodar": {
          ok: false,
          erro: { codigo: "UI-001", mensagem: "O núcleo não está rodando." },
        },
      },
    });
    render(<DoctorResumo />);
    await waitFor(() => expect(screen.getByText("UI-001")).toBeInTheDocument());

    ponte.responder("doctor.rodar", { ok: true, resultado: RELATORIO });
    ponte.emitirEstado({ estado: "pronto", erro: null });

    await waitFor(() => expect(check("nucleo")).toBeInTheDocument());
  });

  it("verificar de novo chama doctor.rodar outra vez", async () => {
    const ponte = ligarPonteFake({
      respostas: { "doctor.rodar": { ok: true, resultado: RELATORIO } },
    });
    render(<DoctorResumo />);
    await waitFor(() => expect(check("nucleo")).toBeInTheDocument());

    const antes = ponte.chamadas.filter((c) => c.metodo === "doctor.rodar").length;
    await userEvent.click(screen.getByRole("button", { name: "Verificar de novo" }));

    await waitFor(() =>
      expect(ponte.chamadas.filter((c) => c.metodo === "doctor.rodar").length).toBe(antes + 1),
    );
  });
});

describe("checksDoRelatorio", () => {
  it("não cria check para campo que o núcleo não mandou", () => {
    const semEspaco: RelatorioDoctor = { ...RELATORIO, espaco_livre_gb: null };
    const ids = checksDoRelatorio(semEspaco).map((c) => c.id);

    expect(ids).not.toContain("espaco");
    expect(ids).toContain("templates");
    expect(checksDoRelatorio(RELATORIO).map((c) => c.id)).toContain("espaco");
  });

  it("o tom geral é o pior dos checks", () => {
    expect(tomGeral(checksDoRelatorio(RELATORIO))).toBe("aviso");

    const tudoOk: RelatorioDoctor = {
      ...RELATORIO,
      pronto_para_mxd: true,
      arcmap: { encontrado: true, versao: "10.8" },
      chaves: { deepseek: true, sema: true, planet: true },
      templates: RELATORIO.templates.map((t) => ({ ...t, sha256_ok: true })),
      rede: {},
    };
    expect(tomGeral(checksDoRelatorio(tudoOk))).toBe("ok");

    const semOgr: RelatorioDoctor = { ...tudoOk, gdal: { ogr2ogr: null, versao: null } };
    expect(tomGeral(checksDoRelatorio(semOgr))).toBe("erro");
  });
});
