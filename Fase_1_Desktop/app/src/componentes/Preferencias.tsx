// Preferências locais (Ctrl+,). Tema + chave DeepSeek no cofre do SO (A11).
// Escuro é o default (D15/AP-08). Segredos nunca ficam em config.json — só no cofre.

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
  const [temChave, setTemChave] = useState(false);
  const [chaveNova, setChaveNova] = useState("");
  const [statusCofre, setStatusCofre] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);

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
    void api()
      ?.chamar("cofre.existe", { chave: "deepseek_api_key" })
      .then((res) => {
        if (!vivo) return;
        const existe =
          res.ok === true &&
          typeof res.resultado === "object" &&
          res.resultado !== null &&
          (res.resultado as { existe?: boolean }).existe === true;
        setTemChave(existe);
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

  const salvarChave = async () => {
    const valor = chaveNova.trim();
    if (!valor) {
      setStatusCofre("cole a chave antes de salvar");
      return;
    }
    setSalvando(true);
    setStatusCofre(null);
    const res = await api()?.chamar("cofre.definir", {
      chave: "deepseek_api_key",
      valor,
    });
    setChaveNova(""); // descarta o texto do renderer (A11)
    setSalvando(false);
    if (res?.ok === true) {
      setTemChave(true);
      setStatusCofre("chave gravada no cofre deste computador");
      return;
    }
    setStatusCofre(res?.erro?.mensagem ?? "não foi possível gravar a chave");
  };

  const testarChave = async () => {
    setSalvando(true);
    setStatusCofre(null);
    const res = await api()?.chamar("cofre.testar", { chave: "deepseek_api_key" });
    setSalvando(false);
    if (res?.ok === true && typeof res.resultado === "object" && res.resultado !== null) {
      const r = res.resultado as { ok?: boolean; ms?: number; erro?: string };
      if (r.ok) {
        setStatusCofre(
          typeof r.ms === "number" ? `chave ok · ${r.ms} ms` : "chave ok",
        );
        return;
      }
      setStatusCofre(r.erro ?? "teste falhou");
      return;
    }
    setStatusCofre(res?.erro?.mensagem ?? "não foi possível testar");
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
          Opções locais deste computador. A chave DeepSeek vai para o cofre do sistema
          (Credential Manager / Secret Service) — nunca para o chat nem para config.json.
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

        <div className={estilos.campo}>
          <span className={estilos.rotulo}>
            Chave DeepSeek {temChave ? "· configurada" : "· ausente"}
          </span>
          <input
            type="password"
            className={estilos.input}
            autoComplete="off"
            spellCheck={false}
            placeholder={temChave ? "colar nova chave para substituir" : "sk-…"}
            value={chaveNova}
            onChange={(e) => setChaveNova(e.target.value)}
            aria-label="chave DeepSeek"
          />
          <div className={estilos.acoesCofre}>
            <button
              type="button"
              className={estilos.botao}
              data-primario="true"
              disabled={salvando}
              onClick={() => void salvarChave()}
            >
              Salvar no cofre
            </button>
            <button
              type="button"
              className={estilos.botao}
              disabled={salvando || !temChave}
              onClick={() => void testarChave()}
            >
              Testar
            </button>
          </div>
          {statusCofre !== null && (
            <p className={estilos.statusCofre} role="status">
              {statusCofre}
            </p>
          )}
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
