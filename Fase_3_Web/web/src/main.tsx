import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App.tsx";
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
