import { Check, ChevronDown, CircleStop, Wrench, X } from "lucide-react";
import { useState } from "react";

import { CartaoTool, formatarDuracao, type EstadoTool } from "./CartaoTool.js";
import estilos from "./GrupoTools.module.css";

export interface PropsGrupoTools {
  id: string;
  tools: EstadoTool[];
}

function estadoAgregado(tools: EstadoTool[]) {
  if (tools.some((tool) => tool.cancelada === true)) {
    return { rotulo: "interrompido", tipo: "cancelado" as const, Icone: CircleStop };
  }
  if (tools.some((tool) => tool.fase === "fim" && tool.ok === false)) {
    return { rotulo: "com falha", tipo: "falha" as const, Icone: X };
  }
  if (tools.some((tool) => tool.fase === "inicio")) {
    return { rotulo: "em execução", tipo: "pendente" as const, Icone: Wrench };
  }
  return { rotulo: "concluído", tipo: "ok" as const, Icone: Check };
}

export function GrupoTools({ id, tools }: PropsGrupoTools) {
  const [expandido, setExpandido] = useState(false);
  if (tools.length === 0) return null;

  const estado = estadoAgregado(tools);
  const duracao = tools.reduce((total, tool) => total + (tool.ms ?? 0), 0);
  const rotuloQuantidade = `${tools.length} ${tools.length === 1 ? "ferramenta" : "ferramentas"}`;
  const detalhesId = `grupo-tools-detalhes-${id}`;
  const nomes = tools.map((tool) => tool.tool).join(", ");

  return (
    <section
      id={`grupo-tools-${id}`}
      className={estilos.grupo}
      data-bloco="tools"
      data-estado={estado.tipo}
      aria-label={`${rotuloQuantidade}: ${nomes}`}
    >
      <button
        type="button"
        className={estilos.resumo}
        onClick={() => setExpandido((valor) => !valor)}
        aria-expanded={expandido}
        aria-controls={detalhesId}
      >
        <span
          className={estilos.icone}
          data-pendente={estado.tipo === "pendente" ? "sim" : "nao"}
          aria-hidden="true"
        >
          <estado.Icone size={14} />
        </span>
        <span className={estilos.quantidade}>{rotuloQuantidade}</span>
        <span className={estilos.estado}>{estado.rotulo}</span>
        {duracao > 0 && <span className={estilos.duracao}>· {formatarDuracao(duracao)}</span>}
        <ChevronDown
          className={estilos.chevron}
          data-expandido={expandido ? "sim" : "nao"}
          size={15}
          aria-hidden="true"
        />
      </button>
      {expandido && (
        <div id={detalhesId} className={estilos.lista}>
          {tools.map((tool) => (
            <CartaoTool key={tool.traceId} estado={tool} />
          ))}
        </div>
      )}
    </section>
  );
}
