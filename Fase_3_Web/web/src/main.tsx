import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App.tsx";
// Ordem importa: fontes → tokens → reset → scrollbar → base (W6-01).
import "./estilos/fontes/fontes.css";
import "./estilos/tokens.css";
import "./estilos/reset.css";
import "./estilos/scrollbar.css";
import "./estilos/base.css";

const raiz = document.getElementById("raiz");
if (!raiz) {
  throw new Error("WB-001: elemento #raiz não existe no index.html");
}

createRoot(raiz).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
