// Barra de conversas — histórico local (M6 / F1-17).

import { useMemo, useState, type FormEvent, type KeyboardEvent } from "react";
import { FolderSearch, MessageSquarePlus, Search, Trash2 } from "lucide-react";

import { EstadoVazio } from "../componentes/EstadoVazio.js";
import {
  agruparPorData,
  type ConversaResumo,
  type ResultadoBusca,
} from "../estado/conversas.js";
import estilos from "./BarraChats.module.css";

export interface PropsBarraChats {
  situacao: "idle" | "carregando" | "pronta" | "erro";
  conversas: ConversaResumo[];
  busca: string;
  resultadosBusca: ResultadoBusca[];
  filtrarPastaAtual: boolean;
  conversaAtiva: string | null;
  workspaceNome: string | null;
  erro: { codigo: string; mensagem: string } | null;
  aoCriar: () => void;
  aoBuscar: (termo: string) => void;
  aoSelecionar: (id: string) => void;
  aoAlternarFiltro: () => void;
  aoApagar: (id: string) => void;
}

export function BarraChats(props: PropsBarraChats) {
  const [termo, setTermo] = useState(props.busca);
  const grupos = useMemo(() => agruparPorData(props.conversas), [props.conversas]);
  const emBusca = termo.trim().length > 0;

  function submeterBusca(evento: FormEvent) {
    evento.preventDefault();
    props.aoBuscar(termo);
  }

  function aoTeclaBusca(evento: KeyboardEvent<HTMLInputElement>) {
    if (evento.key === "Escape") {
      setTermo("");
      props.aoBuscar("");
    }
  }

  return (
    <div className={estilos.raiz}>
      <div className={estilos.toolbar}>
        <button type="button" className={estilos.botao} onClick={props.aoCriar} aria-label="Nova conversa">
          <MessageSquarePlus size={14} aria-hidden="true" />
          Novo
        </button>
        <button
          type="button"
          className={`${estilos.botao} ${props.filtrarPastaAtual ? estilos.botaoAtivo : ""}`}
          onClick={props.aoAlternarFiltro}
          aria-pressed={props.filtrarPastaAtual}
          title="Só desta pasta"
        >
          <FolderSearch size={14} aria-hidden="true" />
          Pasta
        </button>
      </div>

      <form onSubmit={submeterBusca} role="search">
        <label
          htmlFor="busca-chats"
          style={{ position: "absolute", width: 1, height: 1, overflow: "hidden" }}
        >
          Buscar conversas
        </label>
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <Search size={14} aria-hidden="true" />
          <input
            id="busca-chats"
            className={estilos.busca}
            value={termo}
            onChange={(e) => setTermo(e.target.value)}
            onKeyDown={aoTeclaBusca}
            placeholder="Buscar (Ctrl+F)"
            autoComplete="off"
          />
        </div>
      </form>

      {props.erro !== null && (
        <p className={estilos.estado} role="alert">
          {props.erro.codigo}: {props.erro.mensagem}
        </p>
      )}

      {props.situacao === "carregando" && props.conversas.length === 0 && (
        <p className={estilos.estado}>Carregando conversas…</p>
      )}

      {emBusca ? (
        <div className={estilos.lista} aria-label="resultados da busca">
          {props.resultadosBusca.length === 0 ? (
            <p className={estilos.estado}>Nenhum resultado para “{termo.trim()}”.</p>
          ) : (
            props.resultadosBusca.map((r) => (
              <button
                key={`${r.conversation_id}-${r.message_id}`}
                type="button"
                className={estilos.item}
                onClick={() => props.aoSelecionar(r.conversation_id)}
              >
                <span className={estilos.titulo}>{r.title}</span>
                <span className={estilos.trecho}>{r.trecho_destacado}</span>
              </button>
            ))
          )}
        </div>
      ) : props.conversas.length === 0 && props.situacao === "pronta" ? (
        <EstadoVazio
          titulo="Nenhuma conversa ainda"
          descricao="Crie um chat com Novo. O histórico fica só neste PC (D20) e sobrevive ao fechar o app."
          icone={<MessageSquarePlus size={18} aria-hidden="true" />}
        />
      ) : (
        <div className={estilos.lista} aria-label="lista de conversas">
          {grupos.map((grupo) => (
            <div key={grupo.rotulo} className={estilos.grupo}>
              <div className={estilos.rotuloGrupo}>{grupo.rotulo}</div>
              {grupo.itens.map((c) => (
                <ItemChat
                  key={c.conversation_id}
                  conversa={c}
                  ativo={props.conversaAtiva === c.conversation_id}
                  workspaceAberto={props.workspaceNome}
                  aoSelecionar={() => props.aoSelecionar(c.conversation_id)}
                  aoApagar={() => props.aoApagar(c.conversation_id)}
                />
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ItemChat({
  conversa,
  ativo,
  workspaceAberto,
  aoSelecionar,
  aoApagar,
}: {
  conversa: ConversaResumo;
  ativo: boolean;
  workspaceAberto: string | null;
  aoSelecionar: () => void;
  aoApagar: () => void;
}) {
  const pastaDiferente =
    conversa.workspace_nome !== null &&
    workspaceAberto !== null &&
    conversa.workspace_nome !== workspaceAberto;

  return (
    <div className={`${estilos.item} ${ativo ? estilos.itemAtivo : ""}`}>
      <button type="button" className={estilos.item} style={{ border: "none", padding: 0 }} onClick={aoSelecionar}>
        <span className={estilos.titulo}>{conversa.title}</span>
        {pastaDiferente && <span className={estilos.meta}>{conversa.workspace_nome}</span>}
        {conversa.ultimo_trecho && <span className={estilos.trecho}>{conversa.ultimo_trecho}</span>}
      </button>
      <button
        type="button"
        className={estilos.botao}
        aria-label={`Apagar ${conversa.title}`}
        onClick={(e) => {
          e.stopPropagation();
          if (window.confirm(`Apagar “${conversa.title}”?`)) aoApagar();
        }}
      >
        <Trash2 size={12} aria-hidden="true" />
      </button>
    </div>
  );
}
