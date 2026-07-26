// C1 — entrada do renderer. Ordem dos estilos importa: fontes → tokens → reset.
//
// D15 / AP-08: escuro é o default do **produto**, decidido aqui, não por
// `prefers-color-scheme`. O tema claro só entra se a preferência do usuário disser,
// e quem aplica isso é o `App` depois de ler `config.json` pelo IPC.
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import "./estilos/fontes/fontes.css";
import "./estilos/tokens.css";
import "./estilos/reset.css";

import { App } from "./App.js";
import { TEMA_PADRAO, aplicarTema } from "./estado/tema.js";

aplicarTema(TEMA_PADRAO);

const raiz = document.getElementById("raiz");
if (raiz === null) {
  throw new Error("UI-002 · o elemento #raiz não existe no index.html");
}

createRoot(raiz).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
