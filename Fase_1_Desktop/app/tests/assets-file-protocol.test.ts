// Regressão: todo asset resolvido em runtime tem de ser relativo.
//
// O renderer roda sob `file://` no app empacotado (`main.ts` usa `loadFile`), e
// por isso o `vite.config.ts` fixa `base: "./"`. Isso cobre o que o Vite
// reescreve — import estático, `<link>`, `<script>`. NÃO cobre URL montada em
// runtime: `/galeria/x.png` vira `file:///galeria/x.png`, a raiz do disco, e o
// preview quebra **só no build** (o dev server serve por http, onde `/` é a
// raiz do site e funciona). Foi assim que os 5 previews da galeria quebraram.

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { urlPreview } from "../src/estado/galeria.js";

const RAIZ = join(__dirname, "..");

describe("assets sob file:// (renderer empacotado)", () => {
  it("urlPreview devolve caminho relativo, nunca ancorado na raiz", () => {
    const url = urlPreview("shared/galeria/previews/dinamica_2026_retrato.png");
    expect(url).toBe("./galeria/dinamica_2026_retrato.png");
    expect(url.startsWith("/")).toBe(false);
  });

  it("aceita nome solto e caminho com barra invertida do Windows", () => {
    expect(urlPreview("uc_paisagem.png")).toBe("./galeria/uc_paisagem.png");
    expect(urlPreview("previews/tipologia_paisagem.png")).toBe(
      "./galeria/tipologia_paisagem.png",
    );
  });

  it("vite.config mantém base relativa — o resto do contrato depende disso", () => {
    const config = readFileSync(join(RAIZ, "vite.config.ts"), "utf8");
    expect(config).toMatch(/base:\s*"\.\/"/);
  });
});
