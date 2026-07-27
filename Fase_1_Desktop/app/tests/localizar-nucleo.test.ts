// Testes do localizarNucleo (dev vs empacotado) — M10.
import { describe, expect, it } from "vitest";
import { join } from "node:path";

import { localizarNucleo } from "../electron/nucleo/localizar.js";

describe("localizarNucleo", () => {
  it("em desenvolvimento aponta para -m mapasfacil_nucleo", () => {
    const cmd = localizarNucleo(join("/fake/app"), false);
    expect(cmd.args).toEqual(["-m", "mapasfacil_nucleo", "stdio"]);
    expect(cmd.cwd).toMatch(/nucleo$/);
  });

  it("empacotado usa resources/nucleo/nucleo(.exe)", () => {
    const original = process.resourcesPath;
    Object.defineProperty(process, "resourcesPath", {
      value: "C:\\Program Files\\Mapas Facil\\resources",
      configurable: true,
    });
    try {
      const cmd = localizarNucleo("/ignored", true);
      expect(cmd.comando.replace(/\\/g, "/")).toMatch(/resources\/nucleo\/nucleo/);
      expect(cmd.args).toEqual(["stdio"]);
      expect(cmd.cwd.replace(/\\/g, "/")).toMatch(/resources\/nucleo$/);
    } finally {
      Object.defineProperty(process, "resourcesPath", {
        value: original,
        configurable: true,
      });
    }
  });
});
