// F1-06 §Pergunta ao usuário — cartão de `chat.pergunta`: o agente não sabe
// decidir sozinho (ex.: shapefile sem papel canônico reconhecido) e pede uma
// escolha estruturada. Clicar num chip ou enviar o campo livre vira só uma
// mensagem normal de usuário — reaproveita 100% do laço de turno existente.

import { useState, type FormEvent } from "react";
import { HelpCircle } from "lucide-react";

import type { DadosChatPergunta } from "../estado/eventos.js";
import estilos from "./CartaoPergunta.module.css";

export interface PropsCartaoPergunta {
  dados: DadosChatPergunta;
  /** Chama `enviar(texto)` do PainelChat — chip ou texto livre, mesmo caminho. */
  aoResponder: (texto: string) => void;
}

export function CartaoPergunta({ dados, aoResponder }: PropsCartaoPergunta) {
  const [texto, setTexto] = useState("");

  function aoClicarChip(rotulo: string) {
    aoResponder(rotulo);
  }

  function aoSubmeter(evento: FormEvent) {
    evento.preventDefault();
    const valor = texto.trim();
    if (!valor) return;
    aoResponder(valor);
    setTexto("");
  }

  return (
    <article className={estilos.cartao} data-testid="cartao-pergunta">
      <div className={estilos.cabecalho}>
        <HelpCircle size={15} aria-hidden="true" className={estilos.icone} />
        <p className={estilos.pergunta}>{dados.pergunta}</p>
      </div>
      {dados.opcoes.length > 0 && (
        <div className={estilos.chips} role="group" aria-label="opções de resposta">
          {dados.opcoes.map((opcao) => (
            <button
              key={opcao.id}
              type="button"
              className={estilos.chip}
              onClick={() => aoClicarChip(opcao.rotulo)}
            >
              {opcao.rotulo}
            </button>
          ))}
        </div>
      )}
      {dados.permite_texto_livre && (
        <form className={estilos.formLivre} onSubmit={aoSubmeter}>
          <input
            type="text"
            className={estilos.campoLivre}
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            placeholder="Ou digite sua resposta…"
            aria-label="resposta livre"
          />
          <button type="submit" className={estilos.botaoLivre} disabled={!texto.trim()}>
            Responder
          </button>
        </form>
      )}
    </article>
  );
}
