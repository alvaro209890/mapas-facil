import { describe, expect, it } from "vitest";

import { ErroVersaoNucleo } from "../electron/nucleo/conferirVersao.js";
import { VERSAO_APP, VERSAO_NUCLEO_ESPERADA } from "../electron/nucleo/versao.js";

describe("versão do produto", () => {
  it("expõe semver do app e do núcleo esperado", () => {
    expect(VERSAO_APP).toMatch(/^\d+\.\d+\.\d+/);
    expect(VERSAO_NUCLEO_ESPERADA).toMatch(/^\d+\.\d+\.\d+/);
  });

  it("UI-010 descreve reinstalar", () => {
    const erro = new ErroVersaoNucleo("0.0.1", "0.4.0");
    expect(erro.codigo).toBe("UI-010");
    expect(erro.message).toMatch(/Reinstale/);
  });
});
