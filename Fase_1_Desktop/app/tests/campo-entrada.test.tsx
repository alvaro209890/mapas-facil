import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  CampoEntrada,
  LIMITE_ANEXO_BYTES,
} from "../src/componentes/CampoEntrada.js";

afterEach(cleanup);

describe("CampoEntrada", () => {
  it("colar uma imagem cria chip e entrega o File ao envio", async () => {
    const onEnviar = vi.fn();
    render(
      <CampoEntrada
        enviando={false}
        cancelando={false}
        onEnviar={onEnviar}
        onCancelar={() => undefined}
      />,
    );
    const imagem = new File(["png"], "mapa-colado.png", { type: "image/png" });
    fireEvent.paste(screen.getByRole("textbox"), {
      clipboardData: {
        items: [
          {
            kind: "file",
            type: "image/png",
            getAsFile: () => imagem,
          },
        ],
      },
    });

    expect(screen.getByText("mapa-colado.png")).toBeInTheDocument();
    expect(screen.getByText(/modelo atual é só texto/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Enviar" }));
    await waitFor(() => expect(onEnviar).toHaveBeenCalledTimes(1));
    expect(onEnviar.mock.calls[0][1]).toHaveLength(1);
    expect(onEnviar.mock.calls[0][1][0].arquivo).toBe(imagem);
  });

  it("recusa arquivo acima de 20 MB", () => {
    const { container } = render(
      <CampoEntrada
        enviando={false}
        cancelando={false}
        onEnviar={() => undefined}
        onCancelar={() => undefined}
      />,
    );
    const grande = new File(["x"], "grande.pdf", { type: "application/pdf" });
    Object.defineProperty(grande, "size", { value: LIMITE_ANEXO_BYTES + 1 });
    const input = container.querySelector('input[type="file"]');
    expect(input).not.toBeNull();
    fireEvent.change(input!, { target: { files: [grande] } });

    expect(screen.getByRole("alert")).toHaveTextContent("excede o limite de 20 MB");
    expect(screen.queryByText("grande.pdf")).toBeNull();
  });
});
