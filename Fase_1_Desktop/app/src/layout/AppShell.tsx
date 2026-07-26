// C5 — `AppShell`: os quatro painéis de F1-02, redimensionáveis, com as larguras
// persistidas em `config.json` pelo IPC de preferências.
//
// O `painel-workspace` já é real (C7) e o rodapé dele é o `doctor-resumo` (C8) —
// o doctor roda **uma vez** aqui e o resultado desce por prop. `barra-chats`
// (M6), `painel-chat` (M7) e `painel-direito` (M4) mostram estado vazio honesto,
// que diz de qual marco cada coisa é (C9); nada finge dado do núcleo.

import type { ReactNode } from "react";
import { Map as MapaIcone, MessageSquare, PanelLeftClose, PanelLeftOpen } from "lucide-react";

import { BarraProgressoJob } from "../componentes/BarraProgressoJob.js";
import { DoctorResumoPuro } from "../componentes/DoctorResumo.js";
import { EstadoVazio, SemArcMap, SemChaveDeepSeek } from "../componentes/EstadoVazio.js";
import { useDoctor } from "../estado/doctor.js";
import type { PainelLateral } from "../estado/preferencias.js";
import { usePaineis } from "../estado/preferencias.js";
import type { EstadoNucleo } from "../estado/ponte.js";
import { nomeDoProjeto, useWorkspace } from "../estado/workspace.js";
import { Workspace } from "../paineis/Workspace.js";
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

export function AppShell({ nucleo, banner }: PropsAppShell) {
  const { paineis, definirLargura, alternarColapso, gravar } = usePaineis();
  const { larguras, colapsados } = paineis;
  const workspace = useWorkspace();
  const doctor = useDoctor();

  // Informativos que o doctor sustenta com dado real; sem relatório, nada aparece.
  const semChaveIa = doctor.relatorio !== null && !doctor.relatorio.chaves.deepseek;
  const semArcMap = doctor.relatorio !== null && !doctor.relatorio.arcmap.encontrado;

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
      <TopoApp nucleo={nucleo.estado} projeto={nomeDoProjeto(workspace.indice)} />
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
              <EstadoVazio
                titulo="Sem histórico ainda"
                descricao="A persistência de conversas é do M6 (F1-17). Enquanto ela não existe, nada é guardado entre sessões — e o app não finge que guardou."
                icone={<MessageSquare size={18} aria-hidden="true" />}
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
              <Workspace
                estado={workspace}
                aoConectar={() => void workspace.conectar()}
                aoAbrirRecente={(indice) => void workspace.abrirRecente(indice)}
                aoReindexar={() => void workspace.reindexar()}
                rodape={
                  <DoctorResumoPuro estado={doctor} aoRodar={() => void doctor.rodar()} />
                }
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
            <EstadoVazio
              titulo="Chat do agente ainda não implementado"
              descricao="Streaming, cartões de tool e bloco de raciocínio dependem de chat.delta e chat.tool, que o núcleo ainda não emite (M7)."
              icone={<MessageSquare size={18} aria-hidden="true" />}
            />
            {semChaveIa && <SemChaveDeepSeek />}
            {semArcMap && <SemArcMap motor={doctor.relatorio?.motor_preferido ?? "nativo"} />}
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
          <EstadoVazio
            titulo="Sem mapa gerado"
            descricao="As abas preview, galeria, mapspec e checks chegam no M4; o preview em construção precisa do MapSpec do job."
            icone={<MapaIcone size={18} aria-hidden="true" />}
          />
        </Painel>
      </div>
    </div>
  );
}
