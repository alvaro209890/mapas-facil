// C10 — `PaletaComandos` (`Ctrl+K`). Diálogo de comando: filtrar, ↑↓, Enter, Esc.
// Comandos indisponíveis aparecem com motivo (M4/M6) — nunca executam no silêncio.

import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from "react";

import type { Comando, IdComando } from "./comandos.js";
import { filtrarComandos, listarComandos, rotuloDoGrupo } from "./comandos.js";
import estilos from "./PaletaComandos.module.css";

export interface PropsPaletaComandos {
  aberta: boolean;
  temPasta: boolean;
  aoFechar: () => void;
  aoExecutar: (id: IdComando) => void;
}

export function PaletaComandos({ aberta, temPasta, aoFechar, aoExecutar }: PropsPaletaComandos) {
  const tituloId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [consulta, setConsulta] = useState("");
  const [indiceAtivo, setIndiceAtivo] = useState(0);

  const comandos = useMemo(
    () => filtrarComandos(listarComandos({ temPasta }), consulta),
    [consulta, temPasta],
  );

  useEffect(() => {
    if (!aberta) return;
    setConsulta("");
    setIndiceAtivo(0);
    const foco = window.setTimeout(() => inputRef.current?.focus(), 0);
    return () => window.clearTimeout(foco);
  }, [aberta]);

  useEffect(() => {
    setIndiceAtivo(0);
  }, [consulta]);

  if (!aberta) return null;

  const executar = (comando: Comando) => {
    if (!comando.disponivel) return;
    aoExecutar(comando.id);
    aoFechar();
  };

  const noTeclado = (evento: KeyboardEvent<HTMLInputElement>) => {
    if (evento.key === "Escape") {
      evento.preventDefault();
      evento.stopPropagation();
      aoFechar();
      return;
    }
    if (evento.key === "ArrowDown") {
      evento.preventDefault();
      setIndiceAtivo((atual) => Math.min(atual + 1, Math.max(comandos.length - 1, 0)));
      return;
    }
    if (evento.key === "ArrowUp") {
      evento.preventDefault();
      setIndiceAtivo((atual) => Math.max(atual - 1, 0));
      return;
    }
    if (evento.key === "Enter") {
      evento.preventDefault();
      const comando = comandos[indiceAtivo];
      if (comando !== undefined) executar(comando);
    }
  };

  let grupoAnterior: string | null = null;

  return (
    <div
      className={estilos.raiz}
      role="presentation"
      onMouseDown={(evento) => {
        if (evento.target === evento.currentTarget) aoFechar();
      }}
    >
      <div
        id="paleta-comandos"
        className={estilos.dialogo}
        role="dialog"
        aria-modal="true"
        aria-labelledby={tituloId}
      >
        <h2 id={tituloId} className="sr-only" style={{ position: "absolute", width: 1, height: 1, overflow: "hidden" }}>
          Paleta de comandos
        </h2>
        <input
          ref={inputRef}
          className={estilos.busca}
          type="search"
          placeholder="Filtrar comandos…"
          value={consulta}
          aria-controls="paleta-comandos-lista"
          aria-autocomplete="list"
          onChange={(evento) => setConsulta(evento.target.value)}
          onKeyDown={noTeclado}
        />
        <div id="paleta-comandos-lista" className={estilos.lista} role="listbox" aria-label="comandos">
          {comandos.length === 0 ? (
            <p className={estilos.vazio}>Nenhum comando combina com essa busca.</p>
          ) : (
            comandos.map((comando, indice) => {
              const cabecalho =
                comando.grupo !== grupoAnterior ? (
                  <p key={`g-${comando.grupo}`} className={estilos.grupo}>
                    {rotuloDoGrupo(comando.grupo)}
                  </p>
                ) : null;
              grupoAnterior = comando.grupo;
              return (
                <div key={comando.id}>
                  {cabecalho}
                  <button
                    type="button"
                    role="option"
                    aria-selected={indice === indiceAtivo}
                    data-comando={comando.id}
                    data-disponivel={comando.disponivel}
                    data-ativo={indice === indiceAtivo}
                    className={estilos.item}
                    disabled={!comando.disponivel}
                    onMouseEnter={() => setIndiceAtivo(indice)}
                    onClick={() => executar(comando)}
                  >
                    <span className={estilos.rotulo}>{comando.rotulo}</span>
                    {comando.atalho !== undefined && (
                      <span className={estilos.atalho}>{comando.atalho}</span>
                    )}
                    <span className={estilos.descricao}>{comando.descricao}</span>
                    {comando.motivo !== undefined && (
                      <span className={estilos.motivo}>{comando.motivo}</span>
                    )}
                  </button>
                </div>
              );
            })
          )}
        </div>
        <p className={estilos.rodape}>↑↓ navegar · Enter executar · Esc fechar · Ctrl+K abrir</p>
      </div>
    </div>
  );
}
