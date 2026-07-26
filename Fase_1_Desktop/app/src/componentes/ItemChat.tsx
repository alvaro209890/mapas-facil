// F6 / F1-17 §Comportamento na interface — uma linha da `barra-chats`.
//
// O menu de contexto é o do plano: renomear · arquivar · ramificar daqui · apagar.
// Apagar pede confirmação; renomear usa o título atual como valor inicial. Nada
// aqui fala com o núcleo — quem chama `chat.*` é a `BarraChats`.

import { useEffect, useRef, useState } from "react";
import { Archive, ArchiveRestore, GitBranch, MoreVertical, Pencil, Trash2 } from "lucide-react";

import type { ItemConversa } from "../estado/conversas.js";
import estilos from "./ItemChat.module.css";

export interface PropsItemChat {
  conversa: ItemConversa;
  ativa: boolean;
  /** Nome da pasta aberta; o item só mostra a dele quando difere. */
  pastaAberta: string | null;
  aoAbrir: () => void;
  aoRenomear: (title: string) => void;
  aoArquivar: (arquivada: boolean) => void;
  aoRamificar: () => void;
  aoApagar: () => void;
}

export function ItemChat({
  conversa,
  ativa,
  pastaAberta,
  aoAbrir,
  aoRenomear,
  aoArquivar,
  aoRamificar,
  aoApagar,
}: PropsItemChat) {
  const [menuAberto, setMenuAberto] = useState(false);
  const [renomeando, setRenomeando] = useState(false);
  const [confirmandoApagar, setConfirmandoApagar] = useState(false);
  const [rascunho, setRascunho] = useState(conversa.title);
  const campo = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (renomeando) campo.current?.focus();
  }, [renomeando]);

  const pastaDiferente =
    conversa.workspace_nome !== null && conversa.workspace_nome !== pastaAberta;

  const confirmarRenome = () => {
    const limpo = rascunho.trim();
    setRenomeando(false);
    setMenuAberto(false);
    if (limpo.length > 0 && limpo !== conversa.title) aoRenomear(limpo);
  };

  if (renomeando) {
    return (
      <li className={estilos.item}>
        <input
          ref={campo}
          className={estilos.campoRenome}
          value={rascunho}
          aria-label={`novo título de ${conversa.title}`}
          onChange={(evento) => setRascunho(evento.target.value)}
          onBlur={confirmarRenome}
          onKeyDown={(evento) => {
            if (evento.key === "Enter") confirmarRenome();
            if (evento.key === "Escape") {
              setRascunho(conversa.title);
              setRenomeando(false);
            }
          }}
        />
      </li>
    );
  }

  return (
    <li className={estilos.item} data-ativa={ativa || undefined}>
      <button type="button" className={estilos.alvo} onClick={aoAbrir} aria-current={ativa}>
        <span className={estilos.titulo}>{conversa.title}</span>
        <span className={estilos.meta}>
          <span className="mf-num">{conversa.mensagens_total}</span> msg
          {conversa.ramificada && <span className={estilos.selo}>ramo</span>}
          {conversa.arquivada && <span className={estilos.selo}>arquivada</span>}
          {pastaDiferente && <span className={estilos.pasta}>{conversa.workspace_nome}</span>}
        </span>
        {conversa.ultimo_trecho !== null && (
          <span className={estilos.trecho}>{conversa.ultimo_trecho}</span>
        )}
      </button>

      <button
        type="button"
        className={estilos.botaoMenu}
        aria-label={`ações de ${conversa.title}`}
        aria-expanded={menuAberto}
        onClick={() => setMenuAberto((aberto) => !aberto)}
      >
        <MoreVertical size={14} aria-hidden="true" />
      </button>

      {menuAberto && (
        <div className={estilos.menu} role="menu">
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setRascunho(conversa.title);
              setRenomeando(true);
            }}
          >
            <Pencil size={13} aria-hidden="true" /> Renomear
          </button>
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setMenuAberto(false);
              aoArquivar(!conversa.arquivada);
            }}
          >
            {conversa.arquivada ? (
              <>
                <ArchiveRestore size={13} aria-hidden="true" /> Desarquivar
              </>
            ) : (
              <>
                <Archive size={13} aria-hidden="true" /> Arquivar
              </>
            )}
          </button>
          <button
            type="button"
            role="menuitem"
            disabled={conversa.mensagens_total === 0}
            title={
              conversa.mensagens_total === 0
                ? "Conversa sem mensagem não tem de onde ramificar"
                : undefined
            }
            onClick={() => {
              setMenuAberto(false);
              aoRamificar();
            }}
          >
            <GitBranch size={13} aria-hidden="true" /> Ramificar daqui
          </button>
          {confirmandoApagar ? (
            <div className={estilos.confirma}>
              <span>Apagar “{conversa.title}”? Os anexos também vão.</span>
              <button
                type="button"
                className={estilos.destrutivo}
                onClick={() => {
                  setConfirmandoApagar(false);
                  setMenuAberto(false);
                  aoApagar();
                }}
              >
                Apagar mesmo
              </button>
              <button type="button" onClick={() => setConfirmandoApagar(false)}>
                Cancelar
              </button>
            </div>
          ) : (
            <button
              type="button"
              role="menuitem"
              className={estilos.destrutivo}
              onClick={() => setConfirmandoApagar(true)}
            >
              <Trash2 size={13} aria-hidden="true" /> Apagar
            </button>
          )}
        </div>
      )}
    </li>
  );
}
