// C5 — `AppShell`: os quatro painéis de F1-02, redimensionáveis, com as larguras
// persistidas em `config.json` pelo IPC de preferências.
//
// Escopo desta fatia: o esqueleto e a `barra-progresso-job`. O conteúdo de cada
// painel (`barra-chats` C7/M6, `painel-workspace` C7, `painel-chat` M7,
// `painel-direito` M4) é placeholder honesto — diz o que falta, não finge dado
// que o núcleo não mandou.

import type { ReactNode } from "react";
import { PanelLeftClose, PanelLeftOpen } from "lucide-react";

import { BarraProgressoJob } from "../componentes/BarraProgressoJob.js";
import type { PainelLateral } from "../estado/preferencias.js";
import { usePaineis } from "../estado/preferencias.js";
import type { EstadoNucleo } from "../estado/ponte.js";
import { Divisor } from "./Divisor.js";
import { TopoApp } from "./TopoApp.js";
import estilos from "./AppShell.module.css";

export interface PropsAppShell {
  nucleo: EstadoNucleo;
  /** Banner de `UI-001` e afins, renderizado entre o topo e os painéis. */
  banner?: ReactNode;
}

interface PropsPainel {
  id: string;
  titulo: string;
  largura?: number;
  className?: string;
  aoColapsar?: () => void;
  children: ReactNode;
}

function Painel({ id, titulo, largura, className, aoColapsar, children }: PropsPainel) {
  const classe = className === undefined ? estilos.painel : `${estilos.painel} ${className}`;
  return (
    <section
      id={id}
      className={classe}
      aria-label={titulo}
      style={largura === undefined ? undefined : { flex: `0 0 ${largura}px`, width: largura }}
    >
      <div className={estilos.cabecalho}>
        <span className={estilos.titulo}>{titulo}</span>
        {aoColapsar !== undefined && (
          <button
            type="button"
            className={estilos.botaoColapso}
            onClick={aoColapsar}
            aria-label={`colapsar ${titulo}`}
          >
            <PanelLeftClose size={14} aria-hidden="true" />
          </button>
        )}
      </div>
      <div className={estilos.conteudo}>{children}</div>
    </section>
  );
}

function Trilho({ titulo, aoAbrir }: { titulo: string; aoAbrir: () => void }) {
  return (
    <button type="button" className={estilos.trilho} onClick={aoAbrir} aria-label={`abrir ${titulo}`}>
      <PanelLeftOpen size={16} aria-hidden="true" />
    </button>
  );
}

function Pendente({ titulo, nota }: { titulo: string; nota: string }) {
  return (
    <div className={estilos.placeholder}>
      <strong>{titulo}</strong>
      <span>{nota}</span>
    </div>
  );
}

export function AppShell({ nucleo, banner }: PropsAppShell) {
  const { paineis, definirLargura, alternarColapso, gravar } = usePaineis();
  const { larguras, colapsados } = paineis;

  const divisor = (painel: PainelLateral, rotulo: string, invertido = false) => (
    <Divisor
      painel={painel}
      rotulo={rotulo}
      largura={larguras[painel]}
      invertido={invertido}
      aoRedimensionar={(largura) => definirLargura(painel, largura)}
      aoSoltar={gravar}
    />
  );

  return (
    <div className={estilos.shell}>
      <TopoApp nucleo={nucleo.estado} />
      {banner}
      <div className={estilos.corpo}>
        {colapsados.barraChats ? (
          <Trilho titulo="conversas" aoAbrir={() => alternarColapso("barraChats")} />
        ) : (
          <>
            <Painel
              id="barra-chats"
              titulo="conversas"
              largura={larguras.barraChats}
              aoColapsar={() => alternarColapso("barraChats")}
            >
              <Pendente
                titulo="Sem histórico ainda"
                nota="A persistência de conversas é o M6 (F1-17); a lista aparece aqui quando existir."
              />
            </Painel>
            {divisor("barraChats", "conversas")}
          </>
        )}

        {colapsados.workspace ? (
          <Trilho titulo="pasta do projeto" aoAbrir={() => alternarColapso("workspace")} />
        ) : (
          <>
            <Painel
              id="painel-workspace"
              titulo="pasta do projeto"
              largura={larguras.workspace}
              aoColapsar={() => alternarColapso("workspace")}
            >
              <Pendente
                titulo="Nenhuma pasta conectada"
                nota="A árvore com feições, CRS e área em hectare é o C7; conectar pasta é do processo main (Ctrl+O, C10)."
              />
            </Painel>
            {divisor("workspace", "pasta do projeto")}
          </>
        )}

        <section
          id="painel-chat"
          className={`${estilos.painel} ${estilos.painelChat}`}
          aria-label="conversa"
        >
          <div className={estilos.conversa} role="log" aria-live="polite">
            <Pendente
              titulo="Chat do agente ainda não implementado"
              nota="Streaming, cartões de tool e bloco de raciocínio dependem de chat.delta e chat.tool, que o núcleo ainda não emite (M7)."
            />
          </div>
          <div className={estilos.rodapeChat}>
            <BarraProgressoJob />
            <p className={estilos.entradaDesativada}>
              campo-entrada — C7/M7: enviar depende do agente e de mapa.gerar pela galeria.
            </p>
          </div>
        </section>

        {divisor("painelDireito", "preview e artefatos", true)}
        <Painel
          id="painel-direito"
          titulo="preview e artefatos"
          largura={larguras.painelDireito}
          className={estilos.painelDireito}
        >
          <Pendente
            titulo="Sem mapa gerado"
            nota="As abas preview, galeria, mapspec e checks chegam no M4; o preview em construção precisa do MapSpec do job."
          />
        </Painel>
      </div>
    </div>
  );
}
