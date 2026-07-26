// Painel de chat do agente (M7) — consome chat.enviar + eventos chat.delta/tool.

import { useCallback, useEffect, useRef, useState, type FormEvent, type KeyboardEvent, type ReactNode } from "react";

import { EstadoVazio } from "../componentes/EstadoVazio.js";
import { api } from "../estado/ponte.js";
import type { EnvelopeEvento } from "../estado/eventos.js";
import estilos from "./PainelChat.module.css";

export interface MensagemChat {
  message_id?: string;
  papel: string;
  conteudo: string;
  seq?: number;
}

export interface PropsPainelChat {
  conversationId: string | null;
  semChaveIa: boolean;
  bannerChave?: ReactNode;
  bannerArc?: ReactNode;
}

export function PainelChat({ conversationId, semChaveIa, bannerChave, bannerArc }: PropsPainelChat) {
  const [mensagens, setMensagens] = useState<MensagemChat[]>([]);
  const [rascunho, setRascunho] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [streaming, setStreaming] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [tools, setTools] = useState<string[]>([]);
  const fimRef = useRef<HTMLDivElement | null>(null);

  const carregar = useCallback(async (cid: string) => {
    const ponte = api();
    if (ponte === undefined) return;
    const resp = await ponte.chamar("chat.abrir_conversa", { conversation_id: cid, limite: 50 });
    if (!resp.ok || typeof resp.resultado !== "object" || resp.resultado === null) {
      setErro(resp.erro?.mensagem ?? "Falha ao abrir conversa.");
      return;
    }
    const bruto = resp.resultado as { mensagens?: MensagemChat[] };
    setMensagens(bruto.mensagens ?? []);
    setErro(null);
  }, []);

  useEffect(() => {
    setMensagens([]);
    setStreaming("");
    setTools([]);
    setErro(null);
    if (conversationId) void carregar(conversationId);
  }, [carregar, conversationId]);

  useEffect(() => {
    const ponte = api();
    if (ponte === undefined) return;
    return ponte.aoEvento((evento: EnvelopeEvento) => {
      if (evento.evento === "chat.delta") {
        const texto = String((evento.dados as { texto?: string }).texto ?? "");
        setStreaming((s) => s + texto);
      }
      if (evento.evento === "chat.tool") {
        const dados = evento.dados as { tool?: string; fase?: string };
        if (dados.fase === "inicio" && dados.tool) {
          setTools((t) => [...t, dados.tool!]);
        }
      }
    });
  }, []);

  useEffect(() => {
    fimRef.current?.scrollIntoView?.({ block: "end" });
  }, [mensagens, streaming]);

  async function enviar(texto: string) {
    if (!conversationId || !texto.trim() || enviando) return;
    const ponte = api();
    if (ponte === undefined) {
      setErro("Núcleo indisponível.");
      return;
    }
    setEnviando(true);
    setStreaming("");
    setTools([]);
    setErro(null);
    setMensagens((m) => [...m, { papel: "usuario", conteudo: texto.trim() }]);
    setRascunho("");
    const resp = await ponte.chamar("chat.enviar", {
      conversation_id: conversationId,
      mensagem: texto.trim(),
    });
    setEnviando(false);
    setStreaming("");
    if (!resp.ok) {
      setErro(`${resp.erro?.codigo ?? "erro"}: ${resp.erro?.mensagem ?? "falha"}`);
      if (resp.erro?.codigo === "IA-001") {
        /* banner de chave já cobre */
      }
      return;
    }
    await carregar(conversationId);
  }

  function aoSubmit(evento: FormEvent) {
    evento.preventDefault();
    void enviar(rascunho);
  }

  function aoTecla(evento: KeyboardEvent<HTMLTextAreaElement>) {
    if (evento.key === "Enter" && !evento.shiftKey && (evento.ctrlKey || evento.metaKey)) {
      evento.preventDefault();
      void enviar(rascunho);
    }
  }

  if (!conversationId) {
    return (
      <div className={estilos.raiz}>
        <div className={estilos.conversa} role="log" aria-live="polite">
          <EstadoVazio
            titulo="Nenhuma conversa selecionada"
            descricao="Crie ou abra um chat na barra à esquerda (Ctrl+N). O agente usa a galeria quando há modelo pronto."
          />
          {bannerChave}
          {bannerArc}
        </div>
      </div>
    );
  }

  return (
    <div className={estilos.raiz}>
      <div className={estilos.conversa} role="log" aria-live="polite">
        {mensagens.length === 0 && !streaming && (
          <EstadoVazio
            titulo="Conversa pronta"
            descricao={
              semChaveIa
                ? "Sem chave DeepSeek o chat não chama a IA (IA-001) — use a galeria à direita."
                : "Digite um pedido, por exemplo: “faz a Dinâmica 2026 dessa pasta”."
            }
          />
        )}
        {mensagens.map((m, i) => (
          <div key={m.message_id ?? `${m.papel}-${i}`} className={estilos.bolha} data-papel={m.papel}>
            <span className={estilos.papel}>{m.papel}</span>
            <p className={estilos.texto}>{m.conteudo}</p>
          </div>
        ))}
        {streaming && (
          <div className={estilos.bolha} data-papel="assistente">
            <span className={estilos.papel}>assistente</span>
            <p className={estilos.texto}>{streaming}</p>
          </div>
        )}
        {tools.length > 0 && (
          <p className={estilos.tools} aria-live="polite">
            tools: {tools.join(" · ")}
          </p>
        )}
        {erro && (
          <p className={estilos.erro} role="alert">
            {erro}
          </p>
        )}
        {bannerChave}
        {bannerArc}
        <div ref={fimRef} />
      </div>
      <form className={estilos.entrada} onSubmit={aoSubmit}>
        <textarea
          id="campo-entrada"
          className={estilos.textarea}
          value={rascunho}
          onChange={(e) => setRascunho(e.target.value)}
          onKeyDown={aoTecla}
          placeholder={semChaveIa ? "Configure a chave DeepSeek ou use a galeria…" : "Mensagem (Ctrl+Enter)"}
          rows={2}
          disabled={enviando || semChaveIa}
        />
        <button type="submit" className={estilos.enviar} disabled={enviando || semChaveIa || !rascunho.trim()}>
          {enviando ? "…" : "Enviar"}
        </button>
      </form>
    </div>
  );
}
