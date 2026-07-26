// Ponte de mentira para os testes de UI: implementa `window.mapasfacil` inteira,
// registra o que foi chamado e deixa o teste escolher a resposta de cada método
// NDJSON. Nenhum componente ganha caminho especial "de teste" — eles falam com a
// mesma API que o preload expõe no app de verdade.

import { act } from "@testing-library/react";

import type { EnvelopeEvento } from "../src/estado/eventos.js";
import type {
  ApiMapasFacil,
  EstadoNucleo,
  ProjetoRecente,
  RespostaConectar,
  RespostaNucleo,
} from "../src/estado/ponte.js";

export type Responder = RespostaNucleo | ((params: Record<string, unknown>) => RespostaNucleo);

export interface OpcoesPonteFake {
  /** Resposta por método NDJSON (`workspace.reindexar`, `doctor.rodar`, …). */
  respostas?: Record<string, Responder>;
  /** O que o diálogo nativo devolve em `conectarPasta()`. */
  conectar?: RespostaConectar;
  /** O que `abrirProjetoRecente(i)` devolve; sem isto, repete `conectar`. */
  abrirRecente?: RespostaConectar;
  recentes?: ProjetoRecente[];
  preferencias?: Record<string, unknown>;
}

export interface PonteFake {
  api: ApiMapasFacil;
  chamadas: { metodo: string; params: Record<string, unknown> }[];
  conexoes: number;
  recentesAbertos: number[];
  gravacoes: Record<string, unknown>[];
  /** Emite um evento NDJSON para todos os assinantes, dentro de `act`. */
  emitir: (evento: Omit<EnvelopeEvento, "v" | "id" | "tipo">) => void;
  /** Empurra um estado de núcleo (é o que o main manda em `did-finish-load`). */
  emitirEstado: (estado: EstadoNucleo) => void;
  /** Troca a resposta de um método depois da montagem. */
  responder: (metodo: string, resposta: Responder) => void;
}

const CANCELADO: RespostaConectar = { cancelado: true };

export function ligarPonteFake(opcoes: OpcoesPonteFake = {}): PonteFake {
  const respostas = new Map<string, Responder>(Object.entries(opcoes.respostas ?? {}));
  const ouvintesEvento = new Set<(evento: EnvelopeEvento) => void>();
  const ouvintesEstado = new Set<(estado: EstadoNucleo) => void>();
  const fake: PonteFake = {
    api: undefined as unknown as ApiMapasFacil,
    chamadas: [],
    conexoes: 0,
    recentesAbertos: [],
    gravacoes: [],
    emitir: () => undefined,
    emitirEstado: () => undefined,
    responder: (metodo, resposta) => respostas.set(metodo, resposta),
  };

  let sequencia = 0;

  const api: ApiMapasFacil = {
    chamar(metodo, params = {}) {
      fake.chamadas.push({ metodo, params });
      const resposta = respostas.get(metodo);
      if (resposta === undefined) {
        // Galeria vazia por padrão: testes antigos do shell não precisam mockar M4.
        if (metodo === "galeria.listar") {
          return Promise.resolve({ ok: true, resultado: { galeria_version: 1, modelos: [] } });
        }
        if (metodo === "chat.listar_conversas") {
          return Promise.resolve({ ok: true, resultado: { conversas: [], tem_mais: false } });
        }
        if (metodo === "chat.criar_conversa") {
          sequencia += 1;
          return Promise.resolve({
            ok: true,
            resultado: {
              conversation_id: `01TEST${String(sequencia).padStart(20, "0")}`,
              title: "Conversa sem título",
              created_at: new Date().toISOString(),
            },
          });
        }
        if (metodo === "chat.buscar") {
          return Promise.resolve({ ok: true, resultado: { resultados: [] } });
        }
        return Promise.resolve({
          ok: false,
          erro: { codigo: "UI-001", mensagem: `teste sem resposta para ${metodo}` },
        });
      }
      return Promise.resolve(typeof resposta === "function" ? resposta(params) : resposta);
    },
    reiniciarNucleo: () => Promise.resolve({ estado: "pronto" }),
    aoEvento(ouvinte) {
      ouvintesEvento.add(ouvinte);
      return () => {
        ouvintesEvento.delete(ouvinte);
      };
    },
    aoEstadoNucleo(ouvinte) {
      ouvintesEstado.add(ouvinte);
      return () => {
        ouvintesEstado.delete(ouvinte);
      };
    },
    conectarPasta() {
      fake.conexoes += 1;
      return Promise.resolve(opcoes.conectar ?? CANCELADO);
    },
    projetosRecentes: () => Promise.resolve(opcoes.recentes ?? []),
    abrirProjetoRecente(indice) {
      fake.recentesAbertos.push(indice);
      return Promise.resolve(opcoes.abrirRecente ?? opcoes.conectar ?? CANCELADO);
    },
    lerPreferencias: () => Promise.resolve(opcoes.preferencias ?? {}),
    gravarPreferencias(parcial) {
      fake.gravacoes.push(parcial);
      return Promise.resolve(parcial);
    },
  };

  fake.api = api;
  fake.emitir = (evento) => {
    sequencia += 1;
    const envelope = {
      v: 1,
      id: `01JTESTE${String(sequencia).padStart(4, "0")}`,
      tipo: "evt" as const,
      ...evento,
    };
    act(() => {
      for (const ouvinte of ouvintesEvento) ouvinte(envelope);
    });
  };
  fake.emitirEstado = (estado) => {
    act(() => {
      for (const ouvinte of ouvintesEstado) ouvinte(estado);
    });
  };

  window.mapasfacil = api;
  return fake;
}

export function desligarPonteFake(): void {
  delete window.mapasfacil;
}
