// `topo-app` — marca, projeto conectado, doctor e conta (F1-16 §Layout e IDs).
//
// C10: botão da paleta (`Ctrl+K`) e atalho visual do doctor (`F1`). Conta local
// (M5): chip com e-mail + sair. Ícone é `lucide-react`; emoji é proibido.

import { Activity, CircleUser, Command, LogOut } from "lucide-react";

import estilos from "./TopoApp.module.css";

export interface PropsTopoApp {
  /** Nome da pasta conectada. Sem pasta, o breadcrumb diz isso — não fica vazio. */
  projeto?: string;
  /** Estado da ponte com o núcleo, para o chip de ambiente. */
  nucleo: "parado" | "iniciando" | "pronto" | "caido";
  /** E-mail da conta local conectada (M5). */
  contaEmail?: string | null;
  aoSair?: () => void;
  aoAbrirPaleta?: () => void;
  aoAbrirDoctor?: () => void;
}

const ROTULO_NUCLEO: Record<PropsTopoApp["nucleo"], string> = {
  parado: "núcleo parado",
  iniciando: "núcleo iniciando",
  pronto: "núcleo pronto",
  caido: "núcleo fora do ar",
};

export function TopoApp({
  projeto,
  nucleo,
  contaEmail,
  aoSair,
  aoAbrirPaleta,
  aoAbrirDoctor,
}: PropsTopoApp) {
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
        <span
          id="conta-menu"
          className={estilos.chip}
          data-estado={contaEmail ? "conectado" : "ausente"}
          title={contaEmail ?? "sem conta"}
        >
          <CircleUser size={14} aria-hidden="true" />
          {contaEmail ?? "sem conta"}
        </span>
        {contaEmail && aoSair ? (
          <button
            type="button"
            className={estilos.chipBotao}
            onClick={aoSair}
            aria-label="sair da conta"
            title="Sair (mantém o histórico local)"
          >
            <LogOut size={14} aria-hidden="true" />
            Sair
          </button>
        ) : null}
      </span>
    </header>
  );
}
