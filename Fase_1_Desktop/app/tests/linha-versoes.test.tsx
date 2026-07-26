// H6/A6 — `linha-versoes` com `mapspec.atualizado` injetado pela ponte fake.
//
// Os eventos entram pelo mesmo caminho do app (`window.mapasfacil.aoEvento`), não
// por prop: o que está sob teste é a UI reagindo a evento real do núcleo (AP-07).
// Sem evento nenhum, o componente não existe — nada de "v1" inventado.

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { LinhaVersoes } from "../src/componentes/LinhaVersoes.js";
import type { DadosMapspecAtualizado } from "../src/estado/eventos.js";
import {
  VERSOES_INICIAL,
  aplicarMapspecAtualizado,
  irParaVersao,
  navegarVersao,
  useMapspecVersoes,
} from "../src/estado/mapspecVersoes.js";
import { desligarPonteFake, ligarPonteFake } from "./ponte-fake.js";

function diffFake(resumo: string[]): DadosMapspecAtualizado["diff"] {
  return {
    operacoes: resumo.map((_linha, i) => ({ op: "alterar" as const, caminho: `campo${i}` })),
    total: resumo.length,
    resumo,
  };
}

afterEach(() => {
  cleanup();
  desligarPonteFake();
});

// --------------------------------------------------------------------- estado puro

describe("aplicarMapspecAtualizado / navegarVersao / irParaVersao (puras)", () => {
  it("acrescenta ao histórico e passa a exibir a versão nova", () => {
    let estado = aplicarMapspecAtualizado(VERSOES_INICIAL, {
      id: "v1",
      versao: 1,
      diff: diffFake(["título: nenhum → Fazenda Harmonia"]),
    });
    expect(estado.versoes).toHaveLength(1);
    expect(estado.indiceExibido).toBe(0);

    estado = aplicarMapspecAtualizado(estado, {
      id: "v2",
      versao: 2,
      diff: diffFake(["elemento “tabela”: ligado → desligado"]),
    });
    expect(estado.versoes).toHaveLength(2);
    expect(estado.indiceExibido).toBe(1); // segue a mais recente
  });

  it("reemissão do mesmo id não duplica a linha do tempo", () => {
    const dados: DadosMapspecAtualizado = { id: "v1", versao: 1, diff: diffFake([]) };
    let estado = aplicarMapspecAtualizado(VERSOES_INICIAL, dados);
    estado = aplicarMapspecAtualizado(estado, dados);
    expect(estado.versoes).toHaveLength(1);
  });

  it("navegarVersao não sai da faixa [0, tamanho-1]", () => {
    let estado = aplicarMapspecAtualizado(VERSOES_INICIAL, { id: "v1", versao: 1, diff: diffFake([]) });
    estado = aplicarMapspecAtualizado(estado, { id: "v2", versao: 2, diff: diffFake([]) });

    const antes = navegarVersao(estado, -1);
    expect(antes.indiceExibido).toBe(0);
    const aindaAntes = navegarVersao(antes, -1);
    expect(aindaAntes.indiceExibido).toBe(0); // não passa de zero
    expect(aindaAntes).toBe(antes); // não recria estado sem mudança

    const depois = navegarVersao(aindaAntes, 1);
    expect(depois.indiceExibido).toBe(1);
    const aindaDepois = navegarVersao(depois, 1);
    expect(aindaDepois.indiceExibido).toBe(1); // não passa do fim
  });

  it("navegarVersao em histórico vazio não quebra", () => {
    expect(navegarVersao(VERSOES_INICIAL, 1)).toBe(VERSOES_INICIAL);
  });

  it("irParaVersao pula direto para o índice pedido", () => {
    let estado = aplicarMapspecAtualizado(VERSOES_INICIAL, { id: "v1", versao: 1, diff: diffFake([]) });
    estado = aplicarMapspecAtualizado(estado, { id: "v2", versao: 2, diff: diffFake([]) });
    estado = aplicarMapspecAtualizado(estado, { id: "v3", versao: 3, diff: diffFake([]) });
    expect(estado.indiceExibido).toBe(2);

    const paraV1 = irParaVersao(estado, 0);
    expect(paraV1.indiceExibido).toBe(0);
    expect(irParaVersao(paraV1, 99)).toBe(paraV1); // índice fora da faixa é no-op
    expect(irParaVersao(paraV1, -1)).toBe(paraV1);
  });

  it("estado inicial não é mutado", () => {
    aplicarMapspecAtualizado(VERSOES_INICIAL, { id: "v1", versao: 1, diff: diffFake([]) });
    expect(VERSOES_INICIAL.versoes).toHaveLength(0);
    expect(VERSOES_INICIAL.indiceExibido).toBe(-1);
  });
});

// --------------------------------------------------------------------- componente + evento

function emitirMapspecAtualizado(
  ponte: ReturnType<typeof ligarPonteFake>,
  dados: DadosMapspecAtualizado,
): void {
  ponte.emitir({
    evento: "mapspec.atualizado",
    dados: dados as unknown as Record<string, unknown>,
  });
}

/** Componente ligado à ponte, do jeito que o AppShell monta de verdade. */
function LinhaVersoesLigada() {
  const versoes = useMapspecVersoes();
  return (
    <LinhaVersoes
      versoes={versoes.estado.versoes}
      indiceExibido={versoes.estado.indiceExibido}
      aoNavegar={versoes.navegar}
      aoIrPara={versoes.irPara}
    />
  );
}

describe("LinhaVersoes — componente", () => {
  it("sem evento nenhum, não renderiza nada (AP-07)", () => {
    ligarPonteFake();
    const { container } = render(<LinhaVersoesLigada />);
    expect(container).toBeEmptyDOMElement();
  });

  it("primeiro mapspec.atualizado mostra v1 e o diff em português", async () => {
    const ponte = ligarPonteFake();
    render(<LinhaVersoesLigada />);

    emitirMapspecAtualizado(ponte, {
      id: "01MAPSPECV1",
      versao: 1,
      diff: diffFake(["título: nenhum → Fazenda Harmonia", "camadas: adicionado (1 item(ns))"]),
    });

    await waitFor(() => expect(screen.getByText("v1")).toBeInTheDocument());
    expect(screen.getByText(/título: nenhum → Fazenda Harmonia/)).toBeInTheDocument();
    expect(screen.getByText(/camadas: adicionado/)).toBeInTheDocument();
  });

  it("segundo evento acrescenta v2 e passa a exibi-la; ◀ volta para v1", async () => {
    const ponte = ligarPonteFake();
    render(<LinhaVersoesLigada />);
    const usuario = userEvent.setup();

    emitirMapspecAtualizado(ponte, {
      id: "01V1",
      versao: 1,
      diff: diffFake(["título: nenhum → Fazenda Harmonia"]),
    });
    await waitFor(() => expect(screen.getByText("v1")).toBeInTheDocument());

    emitirMapspecAtualizado(ponte, {
      id: "01V2",
      versao: 2,
      diff: diffFake(["elemento “tabela”: ligado → desligado"]),
    });
    await waitFor(() => expect(screen.getByText("v2")).toBeInTheDocument());
    // segue a mais recente sozinho, sem clique
    expect(screen.getByText(/tabela.*ligado → desligado/)).toBeInTheDocument();
    expect(screen.queryByText(/Fazenda Harmonia/)).not.toBeInTheDocument();

    await usuario.click(screen.getByRole("button", { name: "versão anterior" }));
    await waitFor(() => expect(screen.getByText(/Fazenda Harmonia/)).toBeInTheDocument());
    expect(screen.queryByText(/tabela.*ligado → desligado/)).not.toBeInTheDocument();

    // marcador v1 está com data-ativo, v2 não
    expect(screen.getByRole("button", { name: "v1" })).toHaveAttribute("data-ativo", "true");
    expect(screen.getByRole("button", { name: "v2" })).toHaveAttribute("data-ativo", "false");
  });

  it("◀ na v1 fica desabilitada; ▶ na última também", async () => {
    const ponte = ligarPonteFake();
    render(<LinhaVersoesLigada />);
    emitirMapspecAtualizado(ponte, { id: "01V1", versao: 1, diff: diffFake([]) });
    await waitFor(() => expect(screen.getByText("v1")).toBeInTheDocument());

    expect(screen.getByRole("button", { name: "versão anterior" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "próxima versão" })).toBeDisabled();
  });

  it("clicar num marcador (vN) vai direto para aquela versão", async () => {
    const ponte = ligarPonteFake();
    render(<LinhaVersoesLigada />);
    const usuario = userEvent.setup();

    emitirMapspecAtualizado(ponte, { id: "01V1", versao: 1, diff: diffFake(["a"]) });
    await waitFor(() => expect(screen.getByText("v1")).toBeInTheDocument());
    emitirMapspecAtualizado(ponte, { id: "01V2", versao: 2, diff: diffFake(["b"]) });
    await waitFor(() => expect(screen.getByText("v2")).toBeInTheDocument());
    emitirMapspecAtualizado(ponte, { id: "01V3", versao: 3, diff: diffFake(["c"]) });
    await waitFor(() => expect(screen.getByText("v3")).toBeInTheDocument());

    await usuario.click(screen.getByRole("button", { name: "v1" }));
    await waitFor(() => expect(screen.getByText("a")).toBeInTheDocument());
    expect(screen.queryByText("c")).not.toBeInTheDocument();
  });

  it("versão sem alteração de conteúdo mostra o texto honesto, não uma lista vazia", async () => {
    const ponte = ligarPonteFake();
    render(<LinhaVersoesLigada />);
    emitirMapspecAtualizado(ponte, { id: "01V1", versao: 1, diff: diffFake([]) });
    await waitFor(() => expect(screen.getByText("v1")).toBeInTheDocument());
    expect(screen.getByText("sem alterações de conteúdo nesta versão")).toBeInTheDocument();
  });

  it("card de diff troca de key a cada versão exibida — CSS reinicia o crossfade/flash", async () => {
    const ponte = ligarPonteFake();
    render(<LinhaVersoesLigada />);
    emitirMapspecAtualizado(ponte, { id: "01V1", versao: 1, diff: diffFake(["a"]) });
    await waitFor(() => expect(screen.getByTestId("mapspec-diff")).toBeInTheDocument());

    emitirMapspecAtualizado(ponte, { id: "01V2", versao: 2, diff: diffFake(["b"]) });
    await waitFor(() => expect(screen.getByText("b")).toBeInTheDocument());
    // troca real de elemento no DOM (key nova) — é isso que reinicia a animação CSS
    expect(screen.queryByText("a")).not.toBeInTheDocument();
  });

  it("evento malformado (sem operacoes/resumo) é ignorado, não quebra a UI", async () => {
    const ponte = ligarPonteFake();
    render(<LinhaVersoesLigada />);
    ponte.emitir({ evento: "mapspec.atualizado", dados: { id: "x", versao: 1 } });
    await new Promise((r) => setTimeout(r, 10));
    expect(screen.queryByText("v1")).not.toBeInTheDocument();
  });
});
