// O app empacotado precisa achar o sidecar. Errar o nome do executável faz o
// núcleo nunca subir e a tela ficar presa em "iniciando" — foi o que quebrou o
// instalador 0.5.0, que empacotou `nucleo.exe` e não `mapasfacil-nucleo.exe`.

import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import { afterEach, describe, expect, it } from "vitest";

import { localizarNucleo } from "../electron/nucleo/localizar.js";

const resourcesOriginal = process.resourcesPath;

function prepararResources(raiz: string, nomeExecutavel: string): void {
  const pasta = join(raiz, "nucleo");
  mkdirSync(pasta, { recursive: true });
  writeFileSync(join(pasta, nomeExecutavel), "");
  Object.defineProperty(process, "resourcesPath", { value: raiz, configurable: true });
}

afterEach(() => {
  Object.defineProperty(process, "resourcesPath", {
    value: resourcesOriginal,
    configurable: true,
  });
});

describe("localizarNucleo empacotado", () => {
  it("acha o sidecar publicado como nucleo.exe", (ctx) => {
    if (process.platform !== "win32") return ctx.skip();
    const raiz = join(process.env.TEMP ?? ".", `mf-teste-${Date.now()}-a`);
    prepararResources(raiz, "nucleo.exe");

    const { comando, args } = localizarNucleo("/qualquer", true);

    expect(comando).toBe(join(raiz, "nucleo", "nucleo.exe"));
    expect(args).toEqual(["stdio"]);
  });

  it("prefere mapasfacil-nucleo.exe quando os dois existem", (ctx) => {
    if (process.platform !== "win32") return ctx.skip();
    const raiz = join(process.env.TEMP ?? ".", `mf-teste-${Date.now()}-b`);
    prepararResources(raiz, "nucleo.exe");
    writeFileSync(join(raiz, "nucleo", "mapasfacil-nucleo.exe"), "");

    const { comando } = localizarNucleo("/qualquer", true);

    expect(comando).toBe(join(raiz, "nucleo", "mapasfacil-nucleo.exe"));
  });
});
