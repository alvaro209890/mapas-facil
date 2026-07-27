// Aviso de versão nova (F1-11 P2). Aparece só quando há algo a fazer: some
// em `ocioso`/`verificando` para não virar ruído permanente no topo.
//
// Nada baixa nem instala sozinho — o main usa `autoDownload = false` e cada
// passo aqui é um clique. A barra de progresso reflete `download-progress` do
// electron-updater, não um timer decorativo (AP-07).

import { useEffect, useState } from "react";

import { api, type EstadoAtualizacao } from "../estado/ponte.js";
import estilos from "./BarraAtualizacao.module.css";

export function BarraAtualizacao() {
  const [estado, setEstado] = useState<EstadoAtualizacao>({ fase: "ocioso" });
  const [ocupado, setOcupado] = useState(false);

  useEffect(() => {
    const ponte = api();
    if (!ponte?.aoAtualizacao) return;
    const cancelar = ponte.aoAtualizacao(setEstado);
    let vivo = true;
    void ponte.atualizacaoAtual?.().then((atual) => {
      if (vivo && atual) setEstado(atual);
    });
    return () => {
      vivo = false;
      cancelar();
    };
  }, []);

  if (estado.fase === "ocioso" || estado.fase === "verificando") return null;

  if (estado.fase === "erro") {
    return (
      <div className={estilos.barra} data-tom="aviso" role="status">
        <span className={estilos.texto}>
          Não consegui verificar atualizações. O app continua funcionando normalmente.
        </span>
        <span className={estilos.detalhe}>{estado.mensagem}</span>
      </div>
    );
  }

  if (estado.fase === "baixando") {
    return (
      <div className={estilos.barra} role="status">
        <span className={estilos.texto}>Baixando a atualização… {estado.pct}%</span>
        <span className={estilos.trilho} aria-hidden="true">
          <i style={{ width: `${estado.pct}%` }} />
        </span>
      </div>
    );
  }

  if (estado.fase === "pronta") {
    return (
      <div className={estilos.barra} data-tom="pronta" role="status">
        <span className={estilos.texto}>
          Versão {estado.versao} pronta para instalar. O app fecha e reabre atualizado.
        </span>
        <button
          type="button"
          className={estilos.acao}
          onClick={() => {
            setOcupado(true);
            void api()?.instalarAtualizacao?.();
          }}
          disabled={ocupado}
        >
          {ocupado ? "Reiniciando…" : "Reiniciar e instalar"}
        </button>
      </div>
    );
  }

  return (
    <div className={estilos.barra} role="status">
      <span className={estilos.texto}>Versão {estado.versao} disponível.</span>
      <button
        type="button"
        className={estilos.acao}
        onClick={() => {
          setOcupado(true);
          void api()
            ?.baixarAtualizacao?.()
            .finally(() => setOcupado(false));
        }}
        disabled={ocupado}
      >
        {ocupado ? "Baixando…" : "Atualizar agora"}
      </button>
    </div>
  );
}
