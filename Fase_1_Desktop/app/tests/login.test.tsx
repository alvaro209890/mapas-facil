// Tela de login local (M5).

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { Login } from "../src/telas/Login.js";

const chamar = vi.fn();

vi.mock("../src/estado/ponte.js", () => ({
  api: () => ({ chamar }),
}));

describe("Login", () => {
  beforeEach(() => {
    chamar.mockReset();
  });

  it("cria conta e mostra erro tipado", async () => {
    const user = userEvent.setup();
    chamar.mockResolvedValueOnce({
      ok: false,
      erro: { codigo: "AUTH-070", mensagem: "Já existe uma conta com este e-mail neste PC." },
    });
    render(<Login />);
    await user.type(screen.getByLabelText(/e-mail/i), "a@b.com");
    await user.type(screen.getByLabelText(/^senha$/i), "abcdefgh");
    await user.click(screen.getByRole("button", { name: /criar e entrar/i }));
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("AUTH-070");
    });
    expect(chamar).toHaveBeenCalledWith(
      "conta.criar",
      expect.objectContaining({ email: "a@b.com", senha: "abcdefgh" }),
    );
  });

  it("entra com lembrar neste PC", async () => {
    const user = userEvent.setup();
    chamar.mockResolvedValueOnce({
      ok: true,
      resultado: {
        conta: { id: "1", email: "a@b.com", nome: null },
        sessao: { estado: "conectado" },
      },
    });
    render(<Login />);
    await user.click(screen.getByRole("tab", { name: /entrar/i }));
    await user.type(screen.getByLabelText(/e-mail/i), "a@b.com");
    await user.type(screen.getByLabelText(/^senha$/i), "abcdefgh");
    await user.click(screen.getByRole("button", { name: /^entrar$/i }));
    await waitFor(() => {
      expect(chamar).toHaveBeenCalledWith(
        "conta.entrar",
        expect.objectContaining({
          email: "a@b.com",
          senha: "abcdefgh",
          lembrar_neste_pc: true,
        }),
      );
    });
  });
});
