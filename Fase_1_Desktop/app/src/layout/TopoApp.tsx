// `topo-app` — marca, projeto conectado, doctor e conta (F1-16 §Layout e IDs).
//
// C10: botão da paleta (`Ctrl+K`) e atalho visual do doctor (`F1`). Conta continua
// indicador até M5. Ícone é `lucide-react`; emoji em componente é proibido.

import { Activity, CircleUser, Command } from "lucide-react";

import estilos from "./TopoApp.module.css";

export interface PropsTopoApp {
  /** Nome da pasta conectada. Sem pasta, o breadcrumb diz isso — não fica vazio. */
  projeto?: string;
  /** Estado da ponte com o núcleo, para o chip de ambiente. */
  nucleo: "parado" | "iniciando" | "pronto" | "caido";
  aoAbrirPaleta?: () => void;
  aoAbrirDoctor?: () => void;
}

const ROTULO_NUCLEO: Record<PropsTopoApp["nucleo"], string> = {
  parado: "núcleo parado",
  iniciando: "núcleo iniciando",
  pronto: "núcleo pronto",
  caido: "núcleo fora do ar",
};

export function TopoApp({ projeto, nucleo, aoAbrirPaleta, aoAbrirDoctor }: PropsTopoApp) {
  return (
    <header id="topo-app" className={estilos.topo}>
      <span className={estilos.marca}>Mapas Fácil</span>
      <span className={estilos.breadcrumb}>{projeto ?? "nenhuma pasta conectada"}</span>
      <span className={estilos.chips}>
        <button
          type="button"
          id="botao-paleta"
          className={estilos.chipBotao}
          onClick={aoAbrirPaleta}
          aria-label="abrir paleta de comandos"
          title="Paleta de comandos (Ctrl+K)"
        >
          <Command size={14} aria-hidden="true" />
          Ctrl+K
        </button>
        <button
          type="button"
          id="doctor-chip"
          className={estilos.chipBotao}
          data-estado={nucleo}
          onClick={aoAbrirDoctor}
          aria-label="verificar ambiente"
          title="Doctor (F1)"
        >
          <Activity size={14} aria-hidden="true" />
          {ROTULO_NUCLEO[nucleo]}
        </button>
        <span id="conta-menu" className={estilos.chip} data-estado="ausente">
          <CircleUser size={14} aria-hidden="true" />
          sem conta
        </span>
      </span>
    </header>
  );
}
