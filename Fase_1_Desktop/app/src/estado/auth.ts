// Estado de conta local (M5 / F1-14). O renderer só guarda {id, email, nome} —
// nunca senha nem hash.

import { useEffect, useState } from "react";

import { api, type RespostaNucleo } from "./ponte.js";

export type EstadoAuth = "desconectado" | "conectando" | "conectado" | "carregando";

export interface ContaPublica {
  id: string;
  email: string;
  nome?: string | null;
}

export interface SnapshotAuth {
  estado: EstadoAuth;
  conta: ContaPublica | null;
  erro: { codigo: string; mensagem: string } | null;
}

type Ouvinte = (snap: SnapshotAuth) => void;

let snap: SnapshotAuth = {
  estado: "carregando",
  conta: null,
  erro: null,
};
const ouvintes = new Set<Ouvinte>();

function publicar(proximo: SnapshotAuth): void {
  snap = proximo;
  for (const o of ouvintes) o(snap);
}

function lerResultado(resposta: RespostaNucleo): {
  estado: EstadoAuth;
  conta: ContaPublica | null;
} {
  const r = (resposta.resultado ?? {}) as {
    estado?: string;
    conta?: ContaPublica | null;
    sessao?: { estado?: string };
  };
  if (r.sessao?.estado === "conectado" || r.estado === "conectado") {
    const conta =
      r.conta ??
      ((resposta.resultado as { conta?: ContaPublica })?.conta ?? null);
    return { estado: "conectado", conta };
  }
  if (r.conta && (r.sessao?.estado === "conectado" || !r.estado)) {
    return { estado: "conectado", conta: r.conta };
  }
  return {
    estado: (r.estado as EstadoAuth) || "desconectado",
    conta: r.conta ?? null,
  };
}

export function obterAuth(): SnapshotAuth {
  return snap;
}

/** Testes: volta o singleton ao estado inicial. */
export function resetarAuth(): void {
  publicar({ estado: "carregando", conta: null, erro: null });
}

export function assinarAuth(ouvinte: Ouvinte): () => void {
  ouvintes.add(ouvinte);
  ouvinte(snap);
  return () => {
    ouvintes.delete(ouvinte);
  };
}

export async function carregarAuth(): Promise<SnapshotAuth> {
  const ponte = api();
  if (!ponte) {
    publicar({ estado: "desconectado", conta: null, erro: null });
    return snap;
  }
  publicar({ ...snap, estado: "carregando", erro: null });
  const resposta = await ponte.chamar("conta.estado", {});
  if (!resposta.ok) {
    publicar({
      estado: "desconectado",
      conta: null,
      erro: resposta.erro ?? { codigo: "AUTH-050", mensagem: "Falha ao ler a conta." },
    });
    return snap;
  }
  const lido = lerResultado(resposta);
  // Se o núcleo restaurou sessão no boot, conta.estado já vem conectado.
  publicar({ estado: lido.estado === "conectado" ? "conectado" : "desconectado", conta: lido.conta, erro: null });
  return snap;
}

export async function criarConta(input: {
  email: string;
  senha: string;
  nome?: string;
}): Promise<SnapshotAuth> {
  publicar({ ...snap, estado: "conectando", erro: null });
  const resposta = await api()!.chamar("conta.criar", input);
  if (!resposta.ok) {
    publicar({
      estado: "desconectado",
      conta: null,
      erro: resposta.erro ?? { codigo: "AUTH-050", mensagem: "Não foi possível criar a conta." },
    });
    return snap;
  }
  const lido = lerResultado(resposta);
  publicar({ estado: "conectado", conta: lido.conta, erro: null });
  return snap;
}

export async function entrarConta(input: {
  email: string;
  senha: string;
  lembrar_neste_pc?: boolean;
}): Promise<SnapshotAuth> {
  publicar({ ...snap, estado: "conectando", erro: null });
  const resposta = await api()!.chamar("conta.entrar", {
    email: input.email,
    senha: input.senha,
    lembrar_neste_pc: input.lembrar_neste_pc ?? true,
  });
  if (!resposta.ok) {
    publicar({
      estado: "desconectado",
      conta: null,
      erro: resposta.erro ?? { codigo: "AUTH-002", mensagem: "E-mail ou senha incorretos." },
    });
    return snap;
  }
  const lido = lerResultado(resposta);
  publicar({ estado: "conectado", conta: lido.conta, erro: null });
  return snap;
}

export async function sairConta(esquecerEstePc = false): Promise<SnapshotAuth> {
  await api()?.chamar("conta.sair", { esquecer_este_pc: esquecerEstePc });
  publicar({ estado: "desconectado", conta: null, erro: null });
  return snap;
}

export function useAuth(): SnapshotAuth {
  const [atual, setAtual] = useState(snap);
  useEffect(() => assinarAuth(setAtual), []);
  return atual;
}
