/**
 * Casca do app: rotas e guarda de sessão (W6).
 *
 * O que importa: sem sessão a URL vira `/entrar?volta=...`, e `volta=` só aceita caminho
 * interno — `//evil.com` seria redirect aberto.
 */

import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App, depoisDoLogin } from "./App.tsx";
import { useSessao } from "./estado/sessao";

const fetchFalso = vi.fn();

beforeEach(() => {
  vi.stubGlobal("fetch", fetchFalso);
  fetchFalso.mockReset();
  useSessao.setState({
    estado: "expirada",
    usuario: null,
    csrf: null,
    precisaTrocarSenha: false,
    erro: null,
    carregando: false,
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("destino depois do login", () => {
  it("aceita caminho interno", () => {
    expect(depoisDoLogin("?volta=%2Fprojetos%2Fp1")).toBe("/projetos/p1");
  });

  it("recusa redirect aberto e cai em /projetos", () => {
    expect(depoisDoLogin("?volta=%2F%2Fevil.com")).toBe("/projetos");
    expect(depoisDoLogin("?volta=https%3A%2F%2Fevil.com")).toBe("/projetos");
    expect(depoisDoLogin("")).toBe("/projetos");
  });
});

describe("casca do app", () => {
  it("sem sessão mostra a tela de entrada", () => {
    window.history.pushState({}, "", "/projetos");
    render(<App />);
    expect(screen.getByRole("heading", { name: "Mapas Fácil" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Entrar" })).toBeInTheDocument();
  });
});
