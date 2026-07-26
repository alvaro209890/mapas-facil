// Preferências locais (Ctrl+,). Nesta fatia: só o tema. Escuro é o default do
// produto (D15/AP-08); claro é opção explícita, gravada em config.json.

import { useEffect, useId, useState } from "react";

import { api } from "../estado/ponte.js";
import type { Tema } from "../estado/tema.js";
import { TEMA_PADRAO, aplicarTema, ehTema } from "../estado/tema.js";
import estilos from "./Preferencias.module.css";

export interface PropsPreferencias {
  aberta: boolean;
  aoFechar: () => void;
}

export function Preferencias({ aberta, aoFechar }: PropsPreferencias) {
  const tituloId = useId();
  const [tema, setTema] = useState<Tema>(TEMA_PADRAO);

  useEffect(() => {
    if (!aberta) return;
    let vivo = true;
    void api()
      ?.lerPreferencias()
      .then((preferencias) => {
        if (!vivo) return;
        const salvo = preferencias["tema"];
        setTema(ehTema(salvo) ? salvo : TEMA_PADRAO);
      });
    return () => {
      vivo = false;
    };
  }, [aberta]);

  if (!aberta) return null;

  const escolher = (proximo: Tema) => {
    setTema(proximo);
    aplicarTema(proximo);
    void api()?.gravarPreferencias({ tema: proximo });
  };

  return (
    <div
      className={estilos.raiz}
      role="presentation"
      onMouseDown={(evento) => {
        if (evento.target === evento.currentTarget) aoFechar();
      }}
    >
      <div
        id="preferencias"
        className={estilos.dialogo}
        role="dialog"
        aria-modal="true"
        aria-labelledby={tituloId}
      >
        <h2 id={tituloId} className={estilos.titulo}>
          Preferências
        </h2>
        <p className={estilos.texto}>
          Opções locais deste computador. Segredos (chaves, tokens) nunca entram aqui — vão para o
          cofre do sistema quando o marco correspondente existir.
        </p>
        <div className={estilos.campo}>
          <span className={estilos.rotulo}>Tema</span>
          <div className={estilos.opcoes} role="radiogroup" aria-label="tema">
            <button
              type="button"
              role="radio"
              aria-checked={tema === "escuro"}
              data-ativo={tema === "escuro"}
              className={estilos.opcao}
              onClick={() => escolher("escuro")}
            >
              Escuro (padrão)
            </button>
            <button
              type="button"
              role="radio"
              aria-checked={tema === "claro"}
              data-ativo={tema === "claro"}
              className={estilos.opcao}
              onClick={() => escolher("claro")}
            >
              Claro
            </button>
          </div>
        </div>
        <div className={estilos.acoes}>
          <button type="button" className={estilos.botao} data-primario="true" onClick={aoFechar}>
            Fechar
          </button>
        </div>
      </div>
    </div>
  );
}

/** Alterna escuro ↔ claro e grava. Usado pela paleta sem abrir o diálogo. */
export async function alternarTema(): Promise<Tema> {
  const preferencias = (await api()?.lerPreferencias()) ?? {};
  const atual = ehTema(preferencias["tema"]) ? preferencias["tema"] : TEMA_PADRAO;
  const proximo: Tema = atual === "escuro" ? "claro" : "escuro";
  aplicarTema(proximo);
  await api()?.gravarPreferencias({ tema: proximo });
  return proximo;
}
