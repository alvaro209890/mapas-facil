// config.json em %APPDATA%\MapasFacil\ (F1-01 §Estado e armazenamento local).
// Só preferências de interface: larguras de painel, tema, projetos recentes.
// Segredo nenhum mora aqui — token e chave vão para o Credential Manager (M5).
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";

export type Preferencias = Record<string, unknown>;

export class ArquivoPreferencias {
  private readonly caminho: string;
  private cache: Preferencias | null = null;

  constructor(pastaUsuario: string) {
    this.caminho = join(pastaUsuario, "config.json");
  }

  ler(): Preferencias {
    if (this.cache !== null) return this.cache;
    try {
      const bruto = readFileSync(this.caminho, "utf8");
      const dados = JSON.parse(bruto) as unknown;
      this.cache = typeof dados === "object" && dados !== null ? (dados as Preferencias) : {};
    } catch {
      this.cache = {};
    }
    return this.cache;
  }

  gravar(parcial: Preferencias): Preferencias {
    const atual = this.ler();
    this.cache = { ...atual, ...parcial };
    mkdirSync(dirname(this.caminho), { recursive: true });
    writeFileSync(this.caminho, `${JSON.stringify(this.cache, null, 2)}\n`, "utf8");
    return this.cache;
  }
}
