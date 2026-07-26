// Raiz do renderer. Três responsabilidades nesta fatia:
//   1. aplicar o tema salvo (escuro continua sendo o default do produto, D15/AP-08);
//   2. mostrar o banner de núcleo caído (`UI-001`) com o botão de reiniciar;
//   3. guarda de conta local (M5): sem sessão → `tela-login`.

import { useEffect, useState } from "react";

import { AppShell } from "./layout/AppShell.js";
import { carregarAuth, useAuth } from "./estado/auth.js";
import type { EstadoNucleo } from "./estado/ponte.js";
import { api, assinarEstadoNucleo } from "./estado/ponte.js";
import { TEMA_PADRAO, aplicarTema, ehTema } from "./estado/tema.js";
import { Login } from "./telas/Login.js";
import estilos from "./App.module.css";

const NUCLEO_INICIAL: EstadoNucleo = { estado: "iniciando", erro: null };

export function App() {
  const [nucleo, setNucleo] = useState<EstadoNucleo>(NUCLEO_INICIAL);
  const auth = useAuth();

  useEffect(() => assinarEstadoNucleo(setNucleo), []);

  useEffect(() => {
    let vivo = true;
    void api()
      ?.lerPreferencias()
      .then((preferencias) => {
        if (!vivo) return;
        const tema = preferencias["tema"];
        aplicarTema(ehTema(tema) ? tema : TEMA_PADRAO);
      });
    return () => {
      vivo = false;
    };
  }, []);

  useEffect(() => {
    if (nucleo.estado !== "pronto") return;
    void carregarAuth();
  }, [nucleo.estado]);

  const banner =
    nucleo.estado === "caido" ? (
      <div className={estilos.banner} role="alert">
        <span className={estilos.codigo}>{nucleo.erro?.codigo ?? "UI-001"}</span>
        <span>
          O núcleo do Mapas Fácil não está respondendo, então gerar mapa e ler a pasta ficam
          indisponíveis.
        </span>
        <span className={estilos.detalhe}>{nucleo.erro?.mensagem}</span>
        <button
          type="button"
          className={estilos.acao}
          onClick={() => {
            void api()?.reiniciarNucleo();
          }}
        >
          Reiniciar o núcleo
        </button>
      </div>
    ) : undefined;

  if (nucleo.estado === "pronto" && auth.estado !== "conectado" && auth.estado !== "carregando") {
    return <Login />;
  }

  if (nucleo.estado === "pronto" && auth.estado === "carregando") {
    return (
      <div className={estilos.banner} role="status">
        Verificando conta neste PC…
      </div>
    );
  }

  return <AppShell nucleo={nucleo} banner={banner} />;
}
