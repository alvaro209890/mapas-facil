// C2 — testes da ponte NDJSON contra um sidecar de mentira em Node.
//
// O sidecar é um processo de verdade (`node -e`), não um mock: o que interessa
// aqui é justamente o framing por linha, o `stdout` chegando em pedaços e o
// processo morrendo no meio de uma requisição.

import { afterEach, describe, expect, it } from "vitest";

import { ErroPonte, PonteNucleo } from "../electron/nucleo/ponte.js";
import type { EstadoPonte } from "../electron/nucleo/ponte.js";
import type { Evento } from "../electron/nucleo/protocolo.js";

/** Responde toda requisição com `ok:true` e ecoa o método. */
const SIDECAR_ECO = `
let buffer = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (pedaco) => {
  buffer += pedaco;
  let quebra;
  while ((quebra = buffer.indexOf("\\n")) >= 0) {
    const linha = buffer.slice(0, quebra);
    buffer = buffer.slice(quebra + 1);
    if (!linha.trim()) continue;
    const req = JSON.parse(linha);
    process.stdout.write(
      JSON.stringify({ v: 1, id: req.id, tipo: "res", ok: true, resultado: { metodo: req.metodo } }) + "\\n",
    );
  }
});
`;

/** Emite um `job.progresso` antes da resposta, e manda a resposta em dois pedaços. */
const SIDECAR_EVENTO_E_RESPOSTA_PARTIDA = `
let buffer = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (pedaco) => {
  buffer += pedaco;
  const quebra = buffer.indexOf("\\n");
  if (quebra < 0) return;
  const req = JSON.parse(buffer.slice(0, quebra));
  buffer = "";
  process.stdout.write(
    JSON.stringify({ v: 1, id: req.id, tipo: "evt", evento: "job.progresso", dados: { etapa: "validando_spec", pct: 3 } }) + "\\n",
  );
  const resposta = JSON.stringify({ v: 1, id: req.id, tipo: "res", ok: true, resultado: { ok: 1 } }) + "\\n";
  process.stdout.write(resposta.slice(0, 12));
  setTimeout(() => process.stdout.write(resposta.slice(12)), 20);
});
`;

/** Devolve erro do núcleo, com código estável. */
const SIDECAR_ERRO = `
let buffer = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (pedaco) => {
  buffer += pedaco;
  const quebra = buffer.indexOf("\\n");
  if (quebra < 0) return;
  const req = JSON.parse(buffer.slice(0, quebra));
  buffer = "";
  process.stdout.write(
    JSON.stringify({ v: 1, id: req.id, tipo: "res", ok: false, erro: { codigo: "NU-010", mensagem: "fora do workspace" } }) + "\\n",
  );
});
`;

/** Morre assim que recebe qualquer coisa — é o núcleo caindo no meio do job. */
const SIDECAR_QUE_MORRE = `
process.stdin.on("data", () => process.exit(7));
`;

const pontes: PonteNucleo[] = [];

function abrir(script: string, opcoes: { maxReinicios?: number } = {}): PonteNucleo {
  const ponte = new PonteNucleo({
    comando: process.execPath,
    args: ["-e", script],
    esperaReinicioMs: 10,
    ...opcoes,
  });
  pontes.push(ponte);
  return ponte;
}

function esperarEstado(ponte: PonteNucleo, alvo: EstadoPonte, msLimite = 2000): Promise<void> {
  if (ponte.estado === alvo) return Promise.resolve();
  return new Promise((resolver, rejeitar) => {
    const relogio = setTimeout(() => {
      ponte.off("estado", ouvir);
      rejeitar(new Error(`a ponte não chegou em "${alvo}" (está em "${ponte.estado}")`));
    }, msLimite);
    function ouvir(estado: EstadoPonte) {
      if (estado !== alvo) return;
      clearTimeout(relogio);
      ponte.off("estado", ouvir);
      resolver();
    }
    ponte.on("estado", ouvir);
  });
}

afterEach(() => {
  for (const ponte of pontes.splice(0)) ponte.encerrar();
});

describe("PonteNucleo", () => {
  it("faz uma requisição NDJSON e resolve com o resultado do núcleo", async () => {
    const ponte = abrir(SIDECAR_ECO);
    ponte.iniciar();

    await expect(ponte.chamar("doctor.rodar")).resolves.toEqual({ metodo: "doctor.rodar" });
    expect(ponte.requisicoesPendentes).toBe(0);
  });

  it("entrega evento no meio da requisição e remonta resposta partida em dois pedaços", async () => {
    const ponte = abrir(SIDECAR_EVENTO_E_RESPOSTA_PARTIDA);
    const eventos: Evento[] = [];
    ponte.on("evt", (evento: Evento) => eventos.push(evento));
    ponte.iniciar();

    await expect(ponte.chamar("mapa.gerar")).resolves.toEqual({ ok: 1 });
    expect(eventos).toHaveLength(1);
    expect(eventos[0].evento).toBe("job.progresso");
    expect(eventos[0].dados).toEqual({ etapa: "validando_spec", pct: 3 });
  });

  it("propaga o código de erro do núcleo em vez de embrulhar tudo em UI-001", async () => {
    const ponte = abrir(SIDECAR_ERRO);
    ponte.iniciar();

    await expect(ponte.chamar("workspace.abrir")).rejects.toMatchObject({
      codigo: "NU-010",
      message: "fora do workspace",
    });
  });

  it("núcleo caído rejeita as pendentes com UI-001 e reinicia sozinho", async () => {
    const ponte = abrir(SIDECAR_QUE_MORRE, { maxReinicios: 1 });
    const estados: EstadoPonte[] = [];
    ponte.on("estado", (estado: EstadoPonte) => estados.push(estado));
    ponte.iniciar();

    const pendente = ponte.chamar("mapa.gerar");
    await expect(pendente).rejects.toBeInstanceOf(ErroPonte);
    await expect(pendente).rejects.toMatchObject({ codigo: "UI-001" });
    expect(ponte.requisicoesPendentes).toBe(0);

    await esperarEstado(ponte, "pronto");
    expect(estados).toEqual(["iniciando", "pronto", "iniciando", "pronto"]);
  });

  it("esgotados os reinícios, fica em caido e recusa novas chamadas com UI-001", async () => {
    const ponte = abrir(SIDECAR_QUE_MORRE, { maxReinicios: 0 });
    ponte.iniciar();

    await expect(ponte.chamar("mapa.gerar")).rejects.toMatchObject({ codigo: "UI-001" });
    await esperarEstado(ponte, "caido");

    await expect(ponte.chamar("doctor.rodar")).rejects.toMatchObject({
      codigo: "UI-001",
      detalhes: { metodo: "doctor.rodar" },
    });
  });

  it("comando inexistente vira UI-001 com o comando nos detalhes", async () => {
    const ponte = new PonteNucleo({
      comando: "/nao/existe/mapasfacil-nucleo",
      maxReinicios: 0,
      esperaReinicioMs: 10,
    });
    pontes.push(ponte);
    ponte.iniciar();

    await esperarEstado(ponte, "caido");
    await expect(ponte.chamar("doctor.rodar")).rejects.toMatchObject({ codigo: "UI-001" });
  });

  it("reiniciar() zera o contador e volta a responder", async () => {
    const ponte = abrir(SIDECAR_ECO);
    ponte.iniciar();
    await expect(ponte.chamar("doctor.rodar")).resolves.toBeTruthy();

    ponte.reiniciar();
    expect(ponte.estado).toBe("pronto");
    await expect(ponte.chamar("doctor.rodar")).resolves.toEqual({ metodo: "doctor.rodar" });
  });
});
