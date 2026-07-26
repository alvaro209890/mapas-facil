// F6 / F1-17 §Reabrir — transcrição da conversa guardada, no `painel-chat`.
//
// Somente leitura, e de propósito: enviar mensagem é `chat.enviar` (M7). O que esta
// tela prova é o critério de aceite do M6 — reabrir devolve as mensagens na ordem,
// com os traços de tool, o `compact_summary` recolhido no topo e paginação para
// cima. Sem streaming, sem cursor piscando, sem spinner de nada (AP-07).

import { useEffect, useRef } from "react";
import { ChevronUp, FolderOpen, Wrench } from "lucide-react";

import type { ConversaAberta, MensagemConversa, TracoTool } from "../estado/conversas.js";
import estilos from "./Transcricao.module.css";

const ROTULO_PAPEL: Record<MensagemConversa["papel"], string> = {
  usuario: "você",
  assistente: "assistente",
  sistema: "sistema",
  tool: "ferramenta",
};

export interface PropsTranscricao {
  aberta: ConversaAberta;
  /** Nome da pasta conectada, para a faixa de "conversa de outra pasta". */
  pastaAberta: string | null;
  aoCarregarAnteriores: () => void;
  aoFechar: () => void;
}

export function Transcricao({
  aberta,
  pastaAberta,
  aoCarregarAnteriores,
  aoFechar,
}: PropsTranscricao) {
  const { conversa, mensagens, compact_summary: resumo, total, focoSeq } = aberta;
  const raiz = useRef<HTMLDivElement | null>(null);
  const tracesPorMensagem = new Map<string, TracoTool[]>();
  for (const traco of aberta.tool_traces) {
    if (traco.message_id === null) continue;
    const atuais = tracesPorMensagem.get(traco.message_id) ?? [];
    atuais.push(traco);
    tracesPorMensagem.set(traco.message_id, atuais);
  }

  // Busca com Enter abre "na mensagem encontrada": rola até ela, sem animação
  // inventada — é um `scrollIntoView` amarrado a um dado que existe.
  useEffect(() => {
    if (focoSeq === undefined) return;
    raiz.current
      ?.querySelector(`[data-seq="${focoSeq}"]`)
      ?.scrollIntoView({ block: "center" });
  }, [focoSeq, mensagens.length]);

  const outraPasta =
    conversa.workspace_nome !== null && conversa.workspace_nome !== pastaAberta;

  return (
    <div className={estilos.raiz} ref={raiz}>
      <header className={estilos.cabecalho}>
        <div>
          <h2 className={estilos.titulo}>{conversa.title}</h2>
          <p className={estilos.meta}>
            <span className="mf-num">{total}</span> mensagens
            {conversa.modelo !== null && ` · ${conversa.modelo}`}
            {conversa.parent_conversation_id !== null &&
              ` · ramo a partir do seq ${conversa.parent_message_seq ?? "?"}`}
          </p>
        </div>
        <button type="button" className={estilos.fechar} onClick={aoFechar}>
          Fechar
        </button>
      </header>

      {outraPasta && (
        // O plano é explícito: mostrar a faixa e **não** trocar o workspace sozinho.
        <p className={estilos.faixaPasta} role="note">
          <FolderOpen size={13} aria-hidden="true" /> Esta conversa é da pasta{" "}
          <strong>{conversa.workspace_nome}</strong>. Abrir a pasta continua sendo uma ação
          sua (Ctrl+O) — nada foi trocado.
        </p>
      )}

      {aberta.tem_anteriores && (
        <button type="button" className={estilos.anteriores} onClick={aoCarregarAnteriores}>
          <ChevronUp size={13} aria-hidden="true" /> Carregar mensagens anteriores
        </button>
      )}

      {resumo !== null && (
        <details className={estilos.resumo}>
          <summary>
            resumo das mensagens até o seq{" "}
            <span className="mf-num">{conversa.compact_ate_seq ?? 0}</span>
          </summary>
          <p>{resumo}</p>
        </details>
      )}

      <ol className={estilos.mensagens}>
        {mensagens.map((mensagem) => (
          <li
            key={mensagem.message_id}
            data-seq={mensagem.seq}
            data-papel={mensagem.papel}
            data-foco={mensagem.seq === focoSeq || undefined}
            className={estilos.mensagem}
          >
            <span className={estilos.papel}>{ROTULO_PAPEL[mensagem.papel]}</span>
            <p className={estilos.conteudo}>{mensagem.conteudo}</p>
            {mensagem.cancelada && <span className={estilos.cancelada}>turno cancelado</span>}
            {(tracesPorMensagem.get(mensagem.message_id) ?? []).map((traco) => (
              <p key={traco.trace_id} className={estilos.traco} data-ok={traco.ok || undefined}>
                <Wrench size={12} aria-hidden="true" /> {traco.tool}
                {traco.args_resumo !== null && ` · ${traco.args_resumo}`}
                {traco.ms !== null && (
                  <>
                    {" · "}
                    <span className="mf-num">{traco.ms}</span> ms
                  </>
                )}
                {!traco.ok && ` · ${traco.erro_codigo ?? "falhou"}`}
              </p>
            ))}
          </li>
        ))}
      </ol>
    </div>
  );
}
