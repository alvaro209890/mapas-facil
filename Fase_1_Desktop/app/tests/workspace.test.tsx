// C7 — `painel-workspace` com a resposta **real** de `workspace.abrir`.
//
// A fixture não foi escrita à mão: `tests/fixtures/gerar-fixture-workspace.py`
// monta uma pasta com shapefiles de verdade e grava o que o núcleo devolveu. Se o
// contrato do núcleo mudar, este teste quebra — que é exatamente o que se quer.

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { Workspace } from "../src/paineis/Workspace.js";
import type { EstadoWorkspace, RespostaWorkspaceAbrir } from "../src/estado/workspace.js";
import { nomeDoProjeto, useWorkspace } from "../src/estado/workspace.js";
import { desligarPonteFake, ligarPonteFake } from "./ponte-fake.js";
import fixture from "./fixtures/workspace-abrir.json";

const RESPOSTA = fixture as unknown as RespostaWorkspaceAbrir;

const VAZIO: EstadoWorkspace = {
  situacao: "vazio",
  indice: null,
  recibo: null,
  doctor: null,
  erro: null,
  recentes: [],
  destaques: [],
};

const ABERTO: EstadoWorkspace = {
  situacao: "aberto",
  indice: RESPOSTA.workspace,
  recibo: RESPOSTA.recibo,
  doctor: RESPOSTA.doctor,
  erro: null,
  recentes: [],
  destaques: [],
};

function renderizar(estado: EstadoWorkspace, acoes: Partial<Record<string, () => void>> = {}) {
  return render(
    <Workspace
      estado={estado}
      aoConectar={acoes.aoConectar ?? (() => undefined)}
      aoAbrirRecente={acoes.aoAbrirRecente ?? (() => undefined)}
      aoReindexar={acoes.aoReindexar ?? (() => undefined)}
    />,
  );
}

/** Componente mínimo que exercita o hook pelo mesmo caminho do app. */
function Sonda() {
  const estado = useWorkspace();
  return (
    <Workspace
      estado={estado}
      aoConectar={() => void estado.conectar()}
      aoAbrirRecente={(indice) => void estado.abrirRecente(indice)}
      aoReindexar={() => void estado.reindexar()}
    />
  );
}

function itemDoArquivo(caminho: string): HTMLElement {
  const alvo = document.querySelector<HTMLElement>(`[data-arquivo="${caminho}"]`);
  if (alvo === null) throw new Error(`arquivo ausente na árvore: ${caminho}`);
  return alvo;
}

afterEach(() => {
  cleanup();
  desligarPonteFake();
});

describe("painel-workspace", () => {
  it("sem pasta conectada explica o que fazer e oferece o botão", () => {
    ligarPonteFake();
    renderizar(VAZIO);

    expect(screen.getByText("Nenhuma pasta conectada")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Conectar pasta" })).toBeInTheDocument();
  });

  it("lista as camadas da fixture com feições, CRS e área em pt-BR com 4 casas", () => {
    ligarPonteFake();
    renderizar(ABERTO);

    const atp = itemDoArquivo("SHP/ATP.shp");
    expect(atp).toHaveTextContent("ATP.shp");
    expect(atp).toHaveTextContent("1 feição");
    expect(atp).toHaveTextContent("EPSG:31982");
    expect(atp).toHaveTextContent("3.600,0000 ha");

    expect(itemDoArquivo("SHP/AVN.shp")).toHaveTextContent("144,0000 ha");
    expect(itemDoArquivo("SHP/AUAS.shp")).toHaveTextContent("49,0000 ha");
    expect(screen.getByText(nomeDoProjeto(RESPOSTA.workspace) as string)).toBeInTheDocument();
  });

  it("shapefile com problema ganha alerta com o motivo no title", () => {
    ligarPonteFake();
    renderizar(ABERTO);

    const consolidada = itemDoArquivo("SHP/AREA_CONSOLIDADA.shp");
    expect(consolidada).toHaveAttribute("data-alerta", "true");
    const alerta = consolidada.querySelector<HTMLElement>('[role="img"]');
    expect(alerta?.getAttribute("title")).toContain("NU-020");
    expect(alerta?.getAttribute("title")).toContain(".prj");

    // O CRS foi estimado pelas coordenadas: a UI diz isso, não finge certeza.
    expect(consolidada).toHaveTextContent("(estimado)");
    expect(itemDoArquivo("SHP/ATP.shp")).toHaveAttribute("data-alerta", "false");
  });

  it("lista os PDFs indexados sem marcar como recibo o que não é", () => {
    ligarPonteFake();
    renderizar(ABERTO);

    expect(itemDoArquivo("Mapas/Dinamica_referencia.pdf")).toHaveTextContent(
      "Dinamica_referencia.pdf",
    );
    expect(screen.queryByText("recibo do CAR")).toBeNull();
  });

  it("pasta sem shapefile explica o que o app espera encontrar", () => {
    ligarPonteFake();
    renderizar({
      ...ABERTO,
      indice: { ...RESPOSTA.workspace, shapefiles: [], pdfs: [] },
    });

    expect(screen.getByText("A pasta não tem shapefile")).toBeInTheDocument();
    expect(screen.getByText(/zip do SIMCAR/i)).toBeInTheDocument();
  });

  it("erro do núcleo aparece com código e caminho de saída", () => {
    ligarPonteFake();
    renderizar({
      ...VAZIO,
      situacao: "erro",
      erro: { codigo: "NU-010", mensagem: "Caminho fora da allowlist do workspace." },
    });

    expect(screen.getByRole("alert")).toHaveTextContent("NU-010");
    expect(screen.getByText("Caminho fora da allowlist do workspace.")).toBeInTheDocument();
    expect(screen.getByText(/só lê o que você conectou/)).toBeInTheDocument();
  });
});

describe("useWorkspace", () => {
  it("conectar pasta passa pelo diálogo do main e mostra o índice que voltou", async () => {
    const ponte = ligarPonteFake({
      conectar: { cancelado: false, ok: true, resultado: RESPOSTA },
      recentes: [{ indice: 0, nome: "Analise_de_area-Harmonia", abertoEm: "2026-07-26T12:00:00Z" }],
    });
    render(<Sonda />);

    await userEvent.click(screen.getByRole("button", { name: "Conectar pasta" }));

    await waitFor(() => expect(itemDoArquivo("SHP/ATP.shp")).toBeInTheDocument());
    expect(ponte.conexoes).toBe(1);
    // O renderer não manda caminho nenhum: quem abriu o diálogo foi o main.
    expect(ponte.chamadas.filter((c) => c.metodo === "workspace.abrir")).toHaveLength(0);
  });

  it("cancelar o diálogo não vira erro nem apaga o que estava aberto", async () => {
    ligarPonteFake({ conectar: { cancelado: true } });
    render(<Sonda />);

    await userEvent.click(screen.getByRole("button", { name: "Conectar pasta" }));

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Conectar pasta" })).toBeInTheDocument(),
    );
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("projeto recente é reaberto por índice, nunca por caminho", async () => {
    const ponte = ligarPonteFake({
      recentes: [{ indice: 0, nome: "Harmonia", abertoEm: "2026-07-20T09:30:00Z" }],
      abrirRecente: { cancelado: false, ok: true, resultado: RESPOSTA },
    });
    render(<Sonda />);

    const botao = await screen.findByRole("button", { name: /Harmonia/ });
    expect(botao).toHaveTextContent("20/07/2026");
    await userEvent.click(botao);

    await waitFor(() => expect(itemDoArquivo("SHP/ATP.shp")).toBeInTheDocument());
    expect(ponte.recentesAbertos).toEqual([0]);
  });

  it("reindexar chama workspace.reindexar e atualiza a árvore", async () => {
    const semAuas = {
      workspace: {
        ...RESPOSTA.workspace,
        shapefiles: RESPOSTA.workspace.shapefiles.filter(
          (shp) => shp.caminho !== "SHP/AUAS.shp",
        ),
      },
    };
    const ponte = ligarPonteFake({
      conectar: { cancelado: false, ok: true, resultado: RESPOSTA },
      respostas: { "workspace.reindexar": { ok: true, resultado: semAuas } },
    });
    render(<Sonda />);

    await userEvent.click(screen.getByRole("button", { name: "Conectar pasta" }));
    await waitFor(() => expect(itemDoArquivo("SHP/AUAS.shp")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: "reindexar a pasta" }));

    await waitFor(() =>
      expect(document.querySelector('[data-arquivo="SHP/AUAS.shp"]')).toBeNull(),
    );
    expect(ponte.chamadas.map((c) => c.metodo)).toContain("workspace.reindexar");
    expect(itemDoArquivo("SHP/ATP.shp")).toBeInTheDocument();
  });

  it("erro na abertura mostra o código do núcleo, não uma mensagem genérica", async () => {
    ligarPonteFake({
      conectar: {
        cancelado: false,
        ok: false,
        erro: { codigo: "NU-001", mensagem: "Essa pasta não existe mais." },
      },
    });
    render(<Sonda />);

    await userEvent.click(screen.getByRole("button", { name: "Conectar pasta" }));

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("NU-001"));
    expect(screen.getByText("Essa pasta não existe mais.")).toBeInTheDocument();
  });

  it("workspace.mudou atualiza a árvore e marca o arquivo novo (A12)", async () => {
    const ponte = ligarPonteFake({
      conectar: { cancelado: false, ok: true, resultado: RESPOSTA },
    });
    render(<Sonda />);

    await userEvent.click(screen.getByRole("button", { name: "Conectar pasta" }));
    await waitFor(() => expect(itemDoArquivo("SHP/ATP.shp")).toBeInTheDocument());

    const novo = {
      ...RESPOSTA.workspace.shapefiles[0],
      caminho: "SHP/NOVO.shp",
      id_local: "NOVO",
      papel: "NOVO",
    };
    const indiceNovo = {
      ...RESPOSTA.workspace,
      shapefiles: [...RESPOSTA.workspace.shapefiles, novo],
    };

    ponte.emitir({
      evento: "workspace.mudou",
      dados: {
        mudancas: [
          {
            acao: "adicionado",
            caminho: "SHP/NOVO.shp",
            tipo: "shapefile",
            papel: "NOVO",
            resumo: "apareceu NOVO.shp",
          },
        ],
        workspace: indiceNovo,
      },
    });

    await waitFor(() => expect(itemDoArquivo("SHP/NOVO.shp")).toBeInTheDocument());
    expect(itemDoArquivo("SHP/NOVO.shp")).toHaveAttribute("data-destaque", "true");
  });
});
