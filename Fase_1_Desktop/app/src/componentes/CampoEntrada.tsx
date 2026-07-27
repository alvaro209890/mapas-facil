import { FileText, Image as ImageIcon, Paperclip, SendHorizontal, Square, X } from "lucide-react";
import {
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type ClipboardEvent,
  type DragEvent,
  type FormEvent,
  type KeyboardEvent,
} from "react";

import estilos from "./CampoEntrada.module.css";

export const LIMITE_ANEXO_BYTES = 20 * 1024 * 1024;
export const MAX_ANEXOS_POR_TURNO = 5;

export interface AnexoRascunho {
  id: string;
  nome: string;
  mime: string;
  bytes: number;
  arquivo: File;
  previewUrl?: string;
}

export interface AnexoParaEnvio {
  nome: string;
  mime: string;
  bytes: number;
  base64: string;
}

export interface PropsCampoEntrada {
  disabled?: boolean;
  enviando: boolean;
  cancelando: boolean;
  placeholder?: string;
  onEnviar: (texto: string, anexos: AnexoRascunho[]) => void | Promise<void>;
  onCancelar: () => void | Promise<void>;
}

function idLocal(indice: number): string {
  return globalThis.crypto?.randomUUID?.() ?? `anexo-${Date.now()}-${indice}`;
}

function ehImagem(file: File): boolean {
  return file.type.startsWith("image/");
}

function formatarBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} KB`;
  }
  return `${(bytes / (1024 * 1024)).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} MB`;
}

function arquivoParaBase64(arquivo: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const leitor = new FileReader();
    leitor.onerror = () => reject(leitor.error ?? new Error("Falha ao ler o anexo."));
    leitor.onload = () => {
      const resultado = String(leitor.result ?? "");
      const separador = resultado.indexOf(",");
      resolve(separador >= 0 ? resultado.slice(separador + 1) : resultado);
    };
    leitor.readAsDataURL(arquivo);
  });
}

export async function serializarAnexos(anexos: AnexoRascunho[]): Promise<AnexoParaEnvio[]> {
  return Promise.all(
    anexos.map(async (anexo) => ({
      nome: anexo.nome,
      mime: anexo.mime || "application/octet-stream",
      bytes: anexo.bytes,
      base64: await arquivoParaBase64(anexo.arquivo),
    })),
  );
}

export function CampoEntrada({
  disabled = false,
  enviando,
  cancelando,
  placeholder = "Mensagem (Ctrl+Enter)",
  onEnviar,
  onCancelar,
}: PropsCampoEntrada) {
  const [texto, setTexto] = useState("");
  const [anexos, setAnexos] = useState<AnexoRascunho[]>([]);
  const [erro, setErro] = useState<string | null>(null);
  const [arrastando, setArrastando] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const anexosRef = useRef(anexos);
  anexosRef.current = anexos;

  useEffect(
    () => () => {
      for (const anexo of anexosRef.current) {
        if (anexo.previewUrl) URL.revokeObjectURL(anexo.previewUrl);
      }
    },
    [],
  );

  useEffect(() => {
    const campo = textareaRef.current;
    if (!campo) return;
    campo.style.height = "auto";
    campo.style.height = `${Math.min(campo.scrollHeight, 176)}px`;
  }, [texto]);

  function adicionarArquivos(files: File[]) {
    if (files.length === 0) return;
    const vagas = MAX_ANEXOS_POR_TURNO - anexos.length;
    if (vagas <= 0) {
      setErro(`Você pode anexar até ${MAX_ANEXOS_POR_TURNO} arquivos por turno.`);
      return;
    }

    const aceitos: AnexoRascunho[] = [];
    const mensagens: string[] = [];
    for (const [indice, arquivo] of files.slice(0, vagas).entries()) {
      if (arquivo.size > LIMITE_ANEXO_BYTES) {
        mensagens.push(`${arquivo.name}: excede o limite de 20 MB.`);
        continue;
      }
      const previewUrl =
        ehImagem(arquivo) && typeof URL.createObjectURL === "function"
          ? URL.createObjectURL(arquivo)
          : undefined;
      aceitos.push({
        id: idLocal(indice),
        nome: arquivo.name || `imagem-colada-${indice + 1}.png`,
        mime: arquivo.type || "application/octet-stream",
        bytes: arquivo.size,
        arquivo,
        ...(previewUrl ? { previewUrl } : {}),
      });
    }
    if (files.length > vagas) {
      mensagens.push(`Máximo de ${MAX_ANEXOS_POR_TURNO} anexos por turno.`);
    }
    setAnexos((atuais) => [...atuais, ...aceitos]);
    setErro(mensagens.length > 0 ? mensagens.join(" ") : null);
  }

  function removerAnexo(id: string) {
    setAnexos((atuais) => {
      const alvo = atuais.find((anexo) => anexo.id === id);
      if (alvo?.previewUrl) URL.revokeObjectURL(alvo.previewUrl);
      return atuais.filter((anexo) => anexo.id !== id);
    });
    setErro(null);
  }

  function aoSelecionar(evento: ChangeEvent<HTMLInputElement>) {
    adicionarArquivos(Array.from(evento.target.files ?? []));
    evento.target.value = "";
  }

  function aoColar(evento: ClipboardEvent<HTMLTextAreaElement>) {
    const imagens = Array.from(evento.clipboardData.items)
      .filter((item) => item.kind === "file" && item.type.startsWith("image/"))
      .map((item) => item.getAsFile())
      .filter((file): file is File => file !== null);
    if (imagens.length === 0) return;
    evento.preventDefault();
    adicionarArquivos(imagens);
  }

  function aoSoltar(evento: DragEvent<HTMLFormElement>) {
    evento.preventDefault();
    setArrastando(false);
    adicionarArquivos(Array.from(evento.dataTransfer.files ?? []));
  }

  function limparAposEnvio() {
    for (const anexo of anexos) {
      if (anexo.previewUrl) URL.revokeObjectURL(anexo.previewUrl);
    }
    setTexto("");
    setAnexos([]);
    setErro(null);
  }

  function enviar() {
    const limpo = texto.trim();
    if (disabled || enviando || (limpo === "" && anexos.length === 0)) return;
    const anexosAtuais = anexos;
    limparAposEnvio();
    void onEnviar(limpo, anexosAtuais);
  }

  function aoSubmit(evento: FormEvent) {
    evento.preventDefault();
    enviar();
  }

  function aoTecla(evento: KeyboardEvent<HTMLTextAreaElement>) {
    if (evento.key === "Enter" && !evento.shiftKey && (evento.ctrlKey || evento.metaKey)) {
      evento.preventDefault();
      enviar();
    }
  }

  return (
    <form
      className={estilos.formulario}
      data-arrastando={arrastando ? "sim" : "nao"}
      onSubmit={aoSubmit}
      onDragEnter={(evento) => {
        evento.preventDefault();
        if (evento.dataTransfer.types.includes("Files")) setArrastando(true);
      }}
      onDragOver={(evento) => evento.preventDefault()}
      onDragLeave={(evento) => {
        if (!evento.currentTarget.contains(evento.relatedTarget as Node | null)) {
          setArrastando(false);
        }
      }}
      onDrop={aoSoltar}
    >
      <input
        ref={inputRef}
        className={estilos.inputArquivo}
        type="file"
        multiple
        onChange={aoSelecionar}
        tabIndex={-1}
      />
      {anexos.length > 0 && (
        <div className={estilos.anexos} aria-label={`${anexos.length} anexos selecionados`}>
          {anexos.map((anexo) => (
            <div key={anexo.id} className={estilos.chip}>
              {anexo.previewUrl ? (
                <img className={estilos.preview} src={anexo.previewUrl} alt="" />
              ) : anexo.mime.startsWith("image/") ? (
                <ImageIcon size={16} aria-hidden="true" />
              ) : (
                <FileText size={16} aria-hidden="true" />
              )}
              <span className={estilos.nomeAnexo} title={anexo.nome}>
                {anexo.nome}
              </span>
              <span className={estilos.tamanho}>{formatarBytes(anexo.bytes)}</span>
              <button
                type="button"
                className={estilos.remover}
                onClick={() => removerAnexo(anexo.id)}
                aria-label={`Remover ${anexo.nome}`}
              >
                <X size={13} aria-hidden="true" />
              </button>
            </div>
          ))}
        </div>
      )}
      {anexos.length > 0 && (
        <p className={estilos.avisoVisao} role="status">
          Os anexos serão guardados no histórico. O modelo atual é só texto e não vê imagens.
        </p>
      )}
      {erro && (
        <p className={estilos.erro} role="alert">
          {erro}
        </p>
      )}
      <div className={estilos.linha}>
        <button
          type="button"
          className={estilos.acao}
          onClick={() => inputRef.current?.click()}
          disabled={disabled || enviando}
          aria-label="Anexar arquivo"
          title="Anexar arquivo (máx. 20 MB)"
        >
          <Paperclip size={18} aria-hidden="true" />
        </button>
        <textarea
          ref={textareaRef}
          id="campo-entrada"
          className={estilos.textarea}
          value={texto}
          onChange={(evento) => setTexto(evento.target.value)}
          onKeyDown={aoTecla}
          onPaste={aoColar}
          placeholder={placeholder}
          rows={2}
          disabled={disabled || enviando}
          aria-label="Mensagem"
        />
        {enviando ? (
          <button
            type="button"
            className={estilos.enviar}
            data-acao="parar"
            onClick={() => void onCancelar()}
            disabled={cancelando}
            aria-label={cancelando ? "Parando" : "Parar"}
          >
            <Square size={14} fill="currentColor" aria-hidden="true" />
            <span>{cancelando ? "Parando…" : "Parar"}</span>
          </button>
        ) : (
          <button
            type="submit"
            className={estilos.enviar}
            disabled={disabled || (texto.trim() === "" && anexos.length === 0)}
            aria-label="Enviar"
          >
            <SendHorizontal size={17} aria-hidden="true" />
            <span>Enviar</span>
          </button>
        )}
      </div>
      {arrastando && <span className={estilos.drop}>Solte para anexar</span>}
    </form>
  );
}
