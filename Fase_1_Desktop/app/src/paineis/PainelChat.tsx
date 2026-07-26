// Painel de chat do agente (M7) — consome chat.enviar + eventos chat.delta/tool.

import { useCallback, useEffect, useRef, useState, type FormEvent, type KeyboardEvent, type ReactNode } from "react";

import { EstadoVazio } from "../componentes/EstadoVazio.js";
import { IndicadorPensando } from "../componentes/IndicadorPensando.js";
import type { EstadoTool } from "../componentes/CartaoTool.js";
import { ListaCartoesTool, aplicarEventoTool, cancelarPendentes } from "../componentes/CartaoTool.js";
import { api } from "../estado/ponte.js";
import type { MapSpecEmUso } from "../estado/avisosSistema.js";
import { useAvisosSistema } from "../estado/avisosSistema.js";
import type { DadosChatTool, EnvelopeEvento } from "../estado/eventos.js";
import estilos from "./PainelChat.module.css";

export interface MensagemChat {
  message_id?: string;
  papel: string;
  conteudo: string;
  seq?: number;
  cancelada?: boolean;
}

/** Erro do núcleo → frase acionável. Código estável na frente, sempre (F1-06). */
export function mensagemDeErro(erro?: { codigo?: string; mensagem?: string }): string {
  const codigo = erro?.codigo ?? "erro";
  const base = erro?.mensagem ?? "falha ao falar com o agente";
  const acao: Record<string, string> = {
    "IA-001": "Configure a chave DeepSeek ou use a galeria de modelos.",
    "IA-010": "O provedor está fora do ar. A galeria continua funcionando.",
    "IA-030": "Peça para continuar — o turno recomeça a contagem de rodadas.",
    "IA-040": "Ramifique a conversa para continuar a partir do resumo.",
    "IA-041": "Abra um chat novo; esta conversa atingiu o teto de tokens.",
    "IA-050": "Peça para continuar de onde parou.",
  };
  return acao[codigo] ? `${codigo}: ${base} ${acao[codigo]}` : `${codigo}: ${base}`;
}

export interface PropsPainelChat {
  conversationId: string | null;
  semChaveIa: boolean;
  bannerChave?: ReactNode;
  bannerArc?: ReactNode;
  /** MapSpec em construção — define a gravidade do aviso de arquivo removido (F1-02 §Watcher). */
  mapspecAtivo?: MapSpecEmUso | null;
}

export function PainelChat({
  conversationId,
  semChaveIa,
  bannerChave,
  bannerArc,
  mapspecAtivo = null,
}: PropsPainelChat) {
  const { avisos: avisosSistema, dispensar } = useAvisosSistema(mapspecAtivo);
  const [mensagens, setMensagens] = useState<MensagemChat[]>([]);
  const [rascunho, setRascunho] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [streaming, setStreaming] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [tools, setTools] = useState<EstadoTool[]>([]);
  const [cancelando, setCancelando] = useState(false);
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
        const dados = evento.dados as unknown as DadosChatTool;
        if (typeof dados.trace_id === "string" && typeof dados.tool === "string") {
          setTools((anterior) => aplicarEventoTool(anterior, dados));
        }
      }
    });
  }, []);

  useEffect(() => {
    fimRef.current?.scrollIntoView?.({ block: "end" });
  }, [mensagens, streaming]);

  // A1: o turno foi despachado e ainda não veio texto nem tool. É estado real do
  // turno, não timer — some no primeiro `chat.delta` (AP-07 / F1-16 §A1).
  const pensando = enviando && streaming === "" && tools.length === 0;

  const cancelar = useCallback(async () => {
    if (!conversationId || !enviando) return;
    const ponte = api();
    if (ponte === undefined) return;
    setCancelando(true);
    setTools(cancelarPendentes);
    await ponte.chamar("chat.cancelar", { conversation_id: conversationId });
  }, [conversationId, enviando]);

  // F1-02: Esc cancela o **turno** do chat, nunca o job de mapa (esse tem botão próprio).
  useEffect(() => {
    if (!enviando) return;
    const ouvinte = (evento: globalThis.KeyboardEvent) => {
      if (evento.key !== "Escape") return;
      evento.preventDefault();
      void cancelar();
    };
    window.addEventListener("keydown", ouvinte);
    return () => window.removeEventListener("keydown", ouvinte);
  }, [cancelar, enviando]);

  async function enviar(texto: string) {
    if (!conversationId || !texto.trim() || enviando) return;
    const ponte = api();
    if (ponte === undefined) {
      setErro("Núcleo indisponível.");
      return;
    }
    setEnviando(true);
    setCancelando(false);
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
    setCancelando(false);
    setStreaming("");
    if (!resp.ok) {
      // IA-030/IA-040/IA-050 já gravaram o parcial no transcript: recarregar
      // mostra o que o agente chegou a produzir, em vez de perder o turno.
      // O erro é setado DEPOIS: `carregar` limpa o erro quando dá certo.
      await carregar(conversationId);
      setErro(mensagemDeErro(resp.erro));
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
            {m.cancelada === true && (
              <p className={estilos.tools}>resposta interrompida por você</p>
            )}
          </div>
        ))}
        {streaming && (
          <div className={estilos.bolha} data-papel="assistente" data-streaming="sim">
            <span className={estilos.papel}>assistente</span>
            <p className={estilos.texto}>
              {streaming}
              <span className={estilos.cursor} aria-hidden="true" />
            </p>
          </div>
        )}
        <ListaCartoesTool tools={tools} />
        {/* F1-02 §Watcher — aviso do SISTEMA: não é turno, não vai ao LLM, não
            entra no transcript. Só existe se `workspace.mudou` chegou (AP-07). */}
        {avisosSistema.map((aviso) => (
          <p
            key={aviso.id}
            className={estilos.avisoSistema}
            data-testid="aviso-sistema"
            data-nivel={aviso.nivel}
            role={aviso.nivel === "alerta" ? "alert" : "status"}
          >
            <span className={estilos.avisoSistemaTexto}>{aviso.texto}</span>
            <button
              type="button"
              className={estilos.avisoSistemaFechar}
              onClick={() => dispensar(aviso.id)}
              aria-label={`dispensar aviso sobre ${aviso.caminho}`}
            >
              ×
            </button>
          </p>
        ))}
        {pensando && <IndicadorPensando />}
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
        {enviando ? (
          <button
            type="button"
            className={estilos.enviar}
            onClick={() => void cancelar()}
            disabled={cancelando}
          >
            {cancelando ? "Parando…" : "Parar"}
          </button>
        ) : (
          <button
            type="submit"
            className={estilos.enviar}
            disabled={semChaveIa || !rascunho.trim()}
          >
            Enviar
          </button>
        )}
      </form>
    </div>
  );
}
