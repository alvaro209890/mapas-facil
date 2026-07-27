// Painel de chat do agente — timeline intercalada, markdown, tools e anexos.

import { Paperclip } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type ReactNode, type UIEvent } from "react";

import {
  aplicarEventoTimeline,
  cancelarPendentesTimeline,
  type BlocoTurno,
} from "../chat/timeline.js";
import { BlocoRaciocinio } from "../componentes/BlocoRaciocinio.js";
import { BolhaMarkdown } from "../componentes/BolhaMarkdown.js";
import {
  CampoEntrada,
  serializarAnexos,
  type AnexoRascunho,
} from "../componentes/CampoEntrada.js";
import { CartaoPergunta } from "../componentes/CartaoPergunta.js";
import type { EstadoTool } from "../componentes/CartaoTool.js";
import { EstadoVazio } from "../componentes/EstadoVazio.js";
import { GrupoTools } from "../componentes/GrupoTools.js";
import { IndicadorPensando } from "../componentes/IndicadorPensando.js";
import type { MapSpecEmUso } from "../estado/avisosSistema.js";
import { useAvisosSistema } from "../estado/avisosSistema.js";
import type {
  DadosChatRaciocinio,
  DadosChatTool,
  EnvelopeEvento,
} from "../estado/eventos.js";
import { ehChatPergunta } from "../estado/eventos.js";
import { api } from "../estado/ponte.js";
import estilos from "./PainelChat.module.css";

export interface ToolTraceHistorico {
  trace_id: string;
  tool: string;
  args_resumo?: string | null;
  resultado_resumo?: string | null;
  ms?: number | null;
  ok?: boolean;
  erro_codigo?: string | null;
}

export interface AnexoResumo {
  anexo_id?: string;
  nome?: string;
  nome_original?: string;
  mime?: string;
  bytes: number;
  caminho_local?: string;
}

export interface MensagemChat {
  message_id?: string;
  papel: string;
  conteudo: string;
  seq?: number;
  cancelada?: boolean;
  tool_traces?: ToolTraceHistorico[];
  anexos?: AnexoResumo[];
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
    "CH-004": "Remova o anexo inválido e tente novamente.",
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

function estadoDoTrace(trace: ToolTraceHistorico): EstadoTool {
  return {
    traceId: trace.trace_id,
    tool: trace.tool,
    fase: "fim",
    ...(trace.args_resumo ? { argsResumo: trace.args_resumo } : {}),
    ...(trace.resultado_resumo ? { resultadoResumo: trace.resultado_resumo } : {}),
    ...(typeof trace.ms === "number" ? { ms: trace.ms } : {}),
    ok: trace.ok !== false,
  };
}

function formatarBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} KB`;
  }
  return `${(bytes / (1024 * 1024)).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} MB`;
}

function AnexosDaMensagem({ anexos }: { anexos?: AnexoResumo[] }) {
  if (!anexos || anexos.length === 0) return null;
  return (
    <div className={estilos.anexosMensagem} aria-label={`${anexos.length} anexos`}>
      {anexos.map((anexo, indice) => {
        const nome = anexo.nome ?? anexo.nome_original ?? `anexo ${indice + 1}`;
        return (
          <span key={anexo.anexo_id ?? `${nome}-${indice}`} className={estilos.anexoMensagem}>
            <Paperclip size={12} aria-hidden="true" />
            <span title={nome}>{nome}</span>
            <small>{formatarBytes(anexo.bytes)}</small>
          </span>
        );
      })}
    </div>
  );
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
  const [enviando, setEnviando] = useState(false);
  const [blocos, setBlocos] = useState<BlocoTurno[]>([]);
  const [erro, setErro] = useState<string | null>(null);
  const [cancelando, setCancelando] = useState(false);
  const conversaRef = useRef<HTMLDivElement | null>(null);
  const fimRef = useRef<HTMLDivElement | null>(null);
  const pertoDoFimRef = useRef(true);
  const conversaAtualRef = useRef(conversationId);
  conversaAtualRef.current = conversationId;

  const carregar = useCallback(async (cid: string) => {
    const ponte = api();
    if (ponte === undefined) return;
    const resp = await ponte.chamar("chat.abrir_conversa", { conversation_id: cid, limite: 50 });
    if (conversaAtualRef.current !== cid) return;
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
    setBlocos([]);
    setErro(null);
    setEnviando(false);
    setCancelando(false);
    pertoDoFimRef.current = true;
    if (conversationId) void carregar(conversationId);
  }, [carregar, conversationId]);

  useEffect(() => {
    const ponte = api();
    if (ponte === undefined) return;
    return ponte.aoEvento((evento: EnvelopeEvento) => {
      if (evento.evento === "chat.delta") {
        const texto = String((evento.dados as { texto?: string }).texto ?? "");
        setBlocos((atuais) => aplicarEventoTimeline(atuais, { tipo: "texto", dados: { texto } }));
      }
      if (evento.evento === "chat.raciocinio") {
        const texto = String((evento.dados as { texto?: string }).texto ?? "");
        setBlocos((atuais) =>
          aplicarEventoTimeline(atuais, {
            tipo: "raciocinio",
            dados: { texto } satisfies DadosChatRaciocinio,
          }),
        );
      }
      if (evento.evento === "chat.tool") {
        const dados = evento.dados as unknown as DadosChatTool;
        if (typeof dados.trace_id === "string" && typeof dados.tool === "string") {
          setBlocos((atuais) => aplicarEventoTimeline(atuais, { tipo: "tool", dados }));
        }
      }
      if (ehChatPergunta(evento)) {
        setBlocos((atuais) =>
          aplicarEventoTimeline(atuais, { tipo: "pergunta", dados: evento.dados }),
        );
      }
    });
  }, []);

  useEffect(() => {
    if (!pertoDoFimRef.current) return;
    fimRef.current?.scrollIntoView?.({ block: "end" });
  }, [mensagens, blocos, erro, avisosSistema.length]);

  function aoRolar(evento: UIEvent<HTMLDivElement>) {
    const alvo = evento.currentTarget;
    pertoDoFimRef.current = alvo.scrollHeight - alvo.scrollTop - alvo.clientHeight <= 48;
  }

  // A1: turno despachado sem evento visível. Não há texto de raciocínio inventado.
  const pensando = enviando && blocos.length === 0;

  const cancelar = useCallback(async () => {
    if (!conversationId || !enviando) return;
    const ponte = api();
    if (ponte === undefined) return;
    setCancelando(true);
    setBlocos(cancelarPendentesTimeline);
    await ponte.chamar("chat.cancelar", { conversation_id: conversationId });
  }, [conversationId, enviando]);

  // F1-02: Esc cancela o turno do chat, nunca o job de mapa.
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

  async function enviar(texto: string, anexos: AnexoRascunho[] = []) {
    const mensagem = texto.trim() || (anexos.length > 0 ? "Anexo enviado para referência." : "");
    if (!conversationId || !mensagem || enviando) return;
    const ponte = api();
    if (ponte === undefined) {
      setErro("Núcleo indisponível.");
      return;
    }

    let anexosPayload;
    try {
      anexosPayload = await serializarAnexos(anexos);
    } catch {
      setErro("UI-004: não foi possível ler o anexo. Remova o arquivo e tente novamente.");
      return;
    }

    setEnviando(true);
    setCancelando(false);
    setBlocos([]);
    setErro(null);
    setMensagens((atuais) => [
      ...atuais,
      {
        papel: "usuario",
        conteudo: mensagem,
        anexos: anexos.map((anexo) => ({
          nome: anexo.nome,
          mime: anexo.mime,
          bytes: anexo.bytes,
        })),
      },
    ]);
    const resp = await ponte.chamar("chat.enviar", {
      conversation_id: conversationId,
      mensagem,
      ...(anexosPayload.length > 0 ? { anexos: anexosPayload } : {}),
    });
    if (conversaAtualRef.current !== conversationId) return;
    setEnviando(false);
    setCancelando(false);
    if (!resp.ok) {
      await carregar(conversationId);
      setBlocos([]);
      setErro(mensagemDeErro(resp.erro));
      return;
    }
    await carregar(conversationId);
    setBlocos([]);
  }

  function renderizarBloco(bloco: BlocoTurno) {
    let conteudo: ReactNode;
    if (bloco.tipo === "texto") {
      conteudo = <BolhaMarkdown markdown={bloco.markdown} streaming={bloco.streaming} />;
    } else if (bloco.tipo === "tools") {
      conteudo = <GrupoTools id={bloco.id} tools={bloco.tools} />;
    } else if (bloco.tipo === "raciocinio") {
      conteudo = (
        <BlocoRaciocinio id={bloco.id} texto={bloco.texto} streaming={bloco.streaming} />
      );
    } else {
      conteudo = (
        <CartaoPergunta
          dados={bloco.dados}
          aoResponder={(resposta) => enviar(resposta)}
        />
      );
    }
    return (
      <div
        key={bloco.id}
        className={estilos.blocoTimeline}
        data-bloco={bloco.tipo}
        data-bloco-id={bloco.id}
      >
        {conteudo}
      </div>
    );
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
      <div
        ref={conversaRef}
        className={estilos.conversa}
        role="log"
        aria-live="polite"
        onScroll={aoRolar}
      >
        {mensagens.length === 0 && blocos.length === 0 && (
          <EstadoVazio
            titulo="Conversa pronta"
            descricao={
              semChaveIa
                ? "Sem chave DeepSeek o chat não chama a IA (IA-001) — use a galeria à direita."
                : "Digite um pedido, por exemplo: “faz a Dinâmica 2026 dessa pasta”."
            }
          />
        )}
        {mensagens.map((mensagem, indice) => {
          const chave = mensagem.message_id ?? `${mensagem.papel}-${mensagem.seq ?? indice}`;
          if (mensagem.papel === "assistente") {
            const traces = (mensagem.tool_traces ?? []).map(estadoDoTrace);
            return (
              <div key={chave} className={estilos.turnoHistorico} data-turno="historico">
                {traces.length > 0 && (
                  <div
                    className={estilos.blocoTimeline}
                    data-bloco="tools"
                    data-bloco-id={`historico-tools-${chave}`}
                  >
                    <GrupoTools id={`historico-${chave}`} tools={traces} />
                  </div>
                )}
                {mensagem.conteudo && (
                  <div
                    className={estilos.blocoTimeline}
                    data-bloco="texto"
                    data-bloco-id={`historico-texto-${chave}`}
                  >
                    <BolhaMarkdown
                      markdown={mensagem.conteudo}
                      cancelada={mensagem.cancelada === true}
                    />
                  </div>
                )}
              </div>
            );
          }
          return (
            <article key={chave} className={estilos.bolhaUsuario} data-papel={mensagem.papel}>
              <span className={estilos.papel}>{mensagem.papel}</span>
              <p className={estilos.textoUsuario}>{mensagem.conteudo}</p>
              <AnexosDaMensagem anexos={mensagem.anexos} />
            </article>
          );
        })}
        <div className={estilos.turnoAoVivo} data-turno="ao-vivo">
          {blocos.map(renderizarBloco)}
        </div>
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
      <CampoEntrada
        key={conversationId}
        disabled={semChaveIa}
        enviando={enviando}
        cancelando={cancelando}
        placeholder={
          semChaveIa ? "Configure a chave DeepSeek ou use a galeria…" : "Mensagem (Ctrl+Enter)"
        }
        onEnviar={enviar}
        onCancelar={cancelar}
      />
    </div>
  );
}
