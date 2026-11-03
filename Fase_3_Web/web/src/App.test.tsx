import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { App } from "./App.tsx";

describe("casca do app", () => {
  it("renderiza o nome do produto", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: "Mapas Fácil" })).toBeInTheDocument();
  });
});
