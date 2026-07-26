// `topo-app` — marca, projeto conectado, doctor e conta (F1-16 §Layout e IDs).
//
// Nesta fatia (C5) os três chips à direita são **indicadores**, não menus: doctor
// (C8), conta (M5) e a árvore do projeto (C7) são de marcos posteriores. Ícone é
// `lucide-react`; emoji em componente de interface é proibido (F1-16).

import { Activity, CircleUser } from "lucide-react";

import estilos from "./TopoApp.module.css";

export interface PropsTopoApp {
  /** Nome da pasta conectada. Sem pasta, o breadcrumb diz isso — não fica vazio. */
  projeto?: string;
  /** Estado da ponte com o núcleo, para o chip de ambiente. */
  nucleo: "parado" | "iniciando" | "pronto" | "caido";
}

const ROTULO_NUCLEO: Record<PropsTopoApp["nucleo"], string> = {
  parado: "núcleo parado",
  iniciando: "núcleo iniciando",
  pronto: "núcleo pronto",
  caido: "núcleo fora do ar",
};

export function TopoApp({ projeto, nucleo }: PropsTopoApp) {
  return (
    <header id="topo-app" className={estilos.topo}>
      <span className={estilos.marca}>Mapas Fácil</span>
      <span className={estilos.breadcrumb}>{projeto ?? "nenhuma pasta conectada"}</span>
      <span className={estilos.chips}>
        <span id="doctor-chip" className={estilos.chip} data-estado={nucleo}>
          <Activity size={14} aria-hidden="true" />
          {ROTULO_NUCLEO[nucleo]}
        </span>
        <span id="conta-menu" className={estilos.chip} data-estado="ausente">
          <CircleUser size={14} aria-hidden="true" />
          sem conta
        </span>
      </span>
    </header>
  );
}
