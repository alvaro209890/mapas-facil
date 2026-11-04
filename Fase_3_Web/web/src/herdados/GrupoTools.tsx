/**
 * HERDADO de `Fase_1_Desktop/app/src/componentes/GrupoTools.tsx` (W6-01).
 *
 * Copiado com o mínimo de mudança: só o caminho dos imports (os tipos vêm de
 * `./tipos.ts` em vez das stores do desktop) e este cabeçalho. A proveniência fica
 * registrada porque o desktop continua sendo a referência visual: mudança de estilo
 * aqui deve ser pensada também lá, ou assumida como divergência.
 */
import { Check, ChevronDown, CircleStop, Wrench, X } from "lucide-react";
import { useState } from "react";

import { CartaoTool, formatarDuracao, type EstadoTool } from "./CartaoTool";
import estilos from "./GrupoTools.module.css";
import { nomeAmigavel } from "./rotulosTool";

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
  // Nomes legíveis e sem repetição ("Inspecionar shapefile ×2") para o grupo recolhido.
  const contagem = new Map<string, number>();
  for (const tool of tools) {
    const nome = nomeAmigavel(tool.tool);
    contagem.set(nome, (contagem.get(nome) ?? 0) + 1);
  }
  const legiveis = Array.from(contagem, ([nome, n]) => (n > 1 ? `${nome} ×${n}` : nome)).join(" · ");
  const falhas = tools.filter((tool) => tool.fase === "fim" && tool.ok === false).length;

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
        <span className={estilos.textos}>
          <span className={estilos.cabeca}>
            <span className={estilos.quantidade}>{rotuloQuantidade}</span>
            <span className={estilos.estado}>
              {estado.tipo === "falha" ? `${falhas} com falha` : estado.rotulo}
            </span>
          </span>
          <span className={estilos.nomes}>{legiveis}</span>
        </span>
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
