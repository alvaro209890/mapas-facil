// C2 — ponte NDJSON com o sidecar Python (F1-02, F1-01 §Protocolo).
//
// Regras que esta ponte respeita:
//   * transporte é stdio, nunca porta TCP (AP-14);
//   * uma mensagem JSON por linha, `stderr` é log;
//   * `evt` chega no meio de uma requisição e carrega o `id` dela;
//   * núcleo caído vira `UI-001` — com as requisições pendentes rejeitadas, não
//     penduradas — e o app oferece reiniciar.

import { spawn as spawnPadrao } from "node:child_process";
import type { ChildProcessWithoutNullStreams } from "node:child_process";
import { EventEmitter } from "node:events";

import type { Evento, MensagemNucleo, Requisicao } from "./protocolo.js";
import { PROTOCOLO_VERSAO } from "./protocolo.js";
import { novoUlid } from "./ulid.js";

export type EstadoPonte = "parado" | "iniciando" | "pronto" | "caido";

export interface OpcoesPonte {
  /** Executável do sidecar (python empacotado, ou `python` no dev). */
  comando: string;
  args?: string[];
  cwd?: string;
  env?: NodeJS.ProcessEnv;
  /** Reinícios automáticos antes de desistir e ficar em `caido`. */
  maxReinicios?: number;
  /** Espera entre reinícios, em ms. */
  esperaReinicioMs?: number;
  /** Injetável nos testes — assinatura de `child_process.spawn`. */
  spawn?: typeof spawnPadrao;
}

export class ErroPonte extends Error {
  readonly codigo: string;
  readonly detalhes?: Record<string, unknown>;

  constructor(codigo: string, mensagem: string, detalhes?: Record<string, unknown>) {
    super(mensagem);
    this.name = "ErroPonte";
    this.codigo = codigo;
    this.detalhes = detalhes;
  }
}

interface Pendente {
  resolver: (valor: unknown) => void;
  rejeitar: (erro: ErroPonte) => void;
  metodo: string;
}

/**
 * Eventos emitidos pela ponte:
 *   `evt`     — evento NDJSON do núcleo (`job.progresso`, …)
 *   `estado`  — mudança de `EstadoPonte`
 *   `log`     — linha de `stderr` do sidecar
 */
export class PonteNucleo extends EventEmitter {
  private readonly opcoes: Required<Pick<OpcoesPonte, "comando" | "maxReinicios" | "esperaReinicioMs">> &
    OpcoesPonte;
  private processo: ChildProcessWithoutNullStreams | null = null;
  private buffer = "";
  private pendentes = new Map<string, Pendente>();
  private _estado: EstadoPonte = "parado";
  private reinicios = 0;
  private encerrandoDeProposito = false;
  private temporizadorReinicio: NodeJS.Timeout | null = null;

  constructor(opcoes: OpcoesPonte) {
    super();
    this.opcoes = {
      maxReinicios: 3,
      esperaReinicioMs: 500,
      ...opcoes,
    };
  }

  get estado(): EstadoPonte {
    return this._estado;
  }

  get requisicoesPendentes(): number {
    return this.pendentes.size;
  }

  iniciar(): void {
    if (this.processo !== null) return;
    this.encerrandoDeProposito = false;
    this.trocarEstado("iniciando");

    const spawn = this.opcoes.spawn ?? spawnPadrao;
    let processo: ChildProcessWithoutNullStreams;
    try {
      processo = spawn(this.opcoes.comando, this.opcoes.args ?? [], {
        cwd: this.opcoes.cwd,
        env: this.opcoes.env,
        stdio: ["pipe", "pipe", "pipe"],
      });
    } catch (causa) {
      this.derrubar(
        new ErroPonte("UI-001", "O núcleo do Mapas Fácil não subiu.", {
          comando: this.opcoes.comando,
          causa: String(causa),
        }),
      );
      return;
    }

    this.processo = processo;
    processo.stdout.setEncoding("utf8");
    processo.stderr.setEncoding("utf8");
    // Todo ouvinte é amarrado a **este** processo: depois de `reiniciar()` o
    // `exit` do processo antigo ainda chega, e sem isso derrubaria o novo.
    processo.stdout.on("data", (pedaco: string) => {
      if (this.processo === processo) this.receber(pedaco);
    });
    processo.stderr.on("data", (pedaco: string) => this.emit("log", pedaco));
    processo.on("error", (causa) => {
      if (this.processo !== null && this.processo !== processo) return;
      this.derrubar(
        new ErroPonte("UI-001", "O núcleo do Mapas Fácil não subiu.", {
          comando: this.opcoes.comando,
          causa: String(causa),
        }),
      );
    });
    processo.on("exit", (codigo, sinal) => this.aoSair(processo, codigo, sinal));

    this.trocarEstado("pronto");
  }

  /** Uma requisição NDJSON. Rejeita com `ErroPonte` (código do núcleo ou `UI-001`). */
  chamar<T = unknown>(
    metodo: string,
    params: Record<string, unknown> = {},
    opcoes: { timeoutMs?: number } = {},
  ): Promise<T> {
    if (this.processo === null || this._estado === "caido") {
      return Promise.reject(
        new ErroPonte("UI-001", "O núcleo não está rodando. Reinicie para continuar.", { metodo }),
      );
    }

    const id = novoUlid();
    const requisicao: Requisicao = {
      v: PROTOCOLO_VERSAO,
      id,
      tipo: "req",
      metodo,
      params,
    };

    return new Promise<T>((resolver, rejeitar) => {
      let temporizador: NodeJS.Timeout | null = null;
      const limpar = () => {
        if (temporizador !== null) clearTimeout(temporizador);
        this.pendentes.delete(id);
      };

      this.pendentes.set(id, {
        metodo,
        resolver: (valor) => {
          limpar();
          resolver(valor as T);
        },
        rejeitar: (erro) => {
          limpar();
          rejeitar(erro);
        },
      });

      if (opcoes.timeoutMs !== undefined) {
        temporizador = setTimeout(() => {
          this.pendentes.get(id)?.rejeitar(
            new ErroPonte("UI-001", `O núcleo não respondeu a ${metodo}.`, {
              metodo,
              timeoutMs: opcoes.timeoutMs,
            }),
          );
        }, opcoes.timeoutMs);
      }

      this.processo?.stdin.write(`${JSON.stringify(requisicao)}\n`, (erro) => {
        if (erro) {
          this.pendentes.get(id)?.rejeitar(
            new ErroPonte("UI-001", "Não consegui falar com o núcleo.", {
              metodo,
              causa: String(erro),
            }),
          );
        }
      });
    });
  }

  /** Reinício manual — é o botão do banner `UI-001`. */
  reiniciar(): void {
    this.reinicios = 0;
    if (this.processo !== null) {
      this.encerrandoDeProposito = true;
      this.processo.kill();
      this.processo = null;
    }
    this.buffer = "";
    this.iniciar();
  }

  encerrar(): void {
    this.encerrandoDeProposito = true;
    if (this.temporizadorReinicio !== null) {
      clearTimeout(this.temporizadorReinicio);
      this.temporizadorReinicio = null;
    }
    this.processo?.stdin.end();
    this.processo?.kill();
    this.processo = null;
    this.trocarEstado("parado");
  }

  // ------------------------------------------------------------------ interno

  private receber(pedaco: string): void {
    this.buffer += pedaco;
    let quebra = this.buffer.indexOf("\n");
    while (quebra >= 0) {
      const linha = this.buffer.slice(0, quebra).trim();
      this.buffer = this.buffer.slice(quebra + 1);
      if (linha.length > 0) this.despachar(linha);
      quebra = this.buffer.indexOf("\n");
    }
  }

  private despachar(linha: string): void {
    let mensagem: MensagemNucleo;
    try {
      mensagem = JSON.parse(linha) as MensagemNucleo;
    } catch {
      this.emit("log", `[ponte] linha NDJSON inválida: ${linha}\n`);
      return;
    }

    if (mensagem.tipo === "evt") {
      this.emit("evt", mensagem as Evento);
      return;
    }

    const pendente = this.pendentes.get(mensagem.id);
    if (pendente === undefined) {
      this.emit("log", `[ponte] resposta sem requisição correspondente: ${mensagem.id}\n`);
      return;
    }
    if (mensagem.ok) {
      pendente.resolver(mensagem.resultado);
    } else {
      pendente.rejeitar(new ErroPonte(mensagem.erro.codigo, mensagem.erro.mensagem, mensagem.erro.detalhes));
    }
  }

  private aoSair(
    processo: ChildProcessWithoutNullStreams,
    codigo: number | null,
    sinal: NodeJS.Signals | null,
  ): void {
    // Saída de um processo já substituído (reinício manual): não é queda do atual.
    if (this.processo !== null && this.processo !== processo) return;
    this.processo = null;
    this.buffer = "";
    if (this.encerrandoDeProposito) {
      this.trocarEstado("parado");
      return;
    }
    // `error` já derrubou a ponte; o `exit` que vem atrás não reinicia de novo.
    if (this._estado === "caido") return;

    const erro = new ErroPonte("UI-001", "O núcleo do Mapas Fácil parou de responder.", {
      codigoSaida: codigo,
      sinal,
    });

    if (this.reinicios < this.opcoes.maxReinicios) {
      this.reinicios += 1;
      this.rejeitarPendentes(erro);
      this.trocarEstado("iniciando");
      this.temporizadorReinicio = setTimeout(() => {
        this.temporizadorReinicio = null;
        this.iniciar();
      }, this.opcoes.esperaReinicioMs);
      return;
    }

    this.derrubar(erro);
  }

  private derrubar(erro: ErroPonte): void {
    this.processo = null;
    this.rejeitarPendentes(erro);
    this.trocarEstado("caido", erro);
  }

  private rejeitarPendentes(erro: ErroPonte): void {
    const pendentes = [...this.pendentes.values()];
    this.pendentes.clear();
    for (const pendente of pendentes) pendente.rejeitar(erro);
  }

  private trocarEstado(estado: EstadoPonte, erro?: ErroPonte): void {
    if (this._estado === estado && erro === undefined) return;
    this._estado = estado;
    this.emit("estado", estado, erro);
  }
}
