// C8 — `doctor-resumo` + diagnóstico completo, no rodapé do `painel-workspace`.
//
// Consome `doctor.rodar` e mais nada: cada linha existe porque o núcleo mandou o
// campo. Estado nunca é só cor — todo check tem ícone **e** texto (F1-16
// §Acessibilidade), e "não testado" aparece como não testado, não como verde.

import { ChevronDown, CircleAlert, CircleCheck, CircleHelp, TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";

import type { CheckDoctor, EstadoDoctor, TomCheck } from "../estado/doctor.js";
import { checksDoRelatorio, tomGeral, useDoctor } from "../estado/doctor.js";
import estilos from "./DoctorResumo.module.css";

const ICONE: Record<TomCheck, ReactNode> = {
  ok: <CircleCheck size={13} aria-hidden="true" />,
  aviso: <TriangleAlert size={13} aria-hidden="true" />,
  erro: <CircleAlert size={13} aria-hidden="true" />,
  desconhecido: <CircleHelp size={13} aria-hidden="true" />,
};

const PALAVRA: Record<TomCheck, string> = {
  ok: "ok",
  aviso: "atenção",
  erro: "problema",
  desconhecido: "não testado",
};

function Pastilha({ check }: { check: CheckDoctor }) {
  return (
    <span className={estilos.pastilha} data-tom={check.tom} data-check={check.id}>
      {ICONE[check.tom]}
      {check.rotulo}
    </span>
  );
}

export interface PropsDoctorResumo {
  estado: EstadoDoctor;
  aoRodar: () => void;
}

/**
 * Versão sem hook: quem já tem o relatório (o `AppShell` roda o doctor uma vez
 * para a tela inteira) usa esta e não dispara um segundo `doctor.rodar`.
 */
export function DoctorResumoPuro({ estado, aoRodar }: PropsDoctorResumo) {
  const { situacao, relatorio, erro } = estado;
  const rodar = aoRodar;

  if (relatorio === null) {
    return (
      <div id="doctor-resumo" className={estilos.doctor}>
        {situacao === "rodando" ? (
          <p className={estilos.estado}>verificando o ambiente…</p>
        ) : (
          <p className={estilos.estado}>
            <span className={estilos.codigo}>{erro?.codigo ?? "UI-001"}</span> diagnóstico
            indisponível — {erro?.mensagem}
          </p>
        )}
      </div>
    );
  }

  const checks = checksDoRelatorio(relatorio);
  const tom = tomGeral(checks);
  // No resumo cabem os quatro de sempre; o resto fica no diagnóstico completo.
  const destaque = checks.filter((check) =>
    ["motor", "arcmap", "chave-deepseek", "chave-sema"].includes(check.id),
  );

  return (
    <details id="doctor-resumo" className={estilos.doctor}>
      <summary className={estilos.resumo} aria-label={`ambiente: ${PALAVRA[tom]}`}>
        {destaque.map((check) => (
          <Pastilha key={check.id} check={check} />
        ))}
        <ChevronDown size={14} className={estilos.seta} aria-hidden="true" />
      </summary>

      <div className={estilos.lista}>
        {checks.map((check) => (
          <p key={check.id} className={estilos.check} data-check={check.id}>
            <span className={estilos.rotulo}>{check.rotulo}</span>
            <span className={`${estilos.valor} mf-num`} data-tom={check.tom}>
              {check.valor} · {PALAVRA[check.tom]}
            </span>
            {check.detalhe !== undefined && <span className={estilos.detalhe}>{check.detalhe}</span>}
          </p>
        ))}
      </div>

      <div className={estilos.linhaAcoes}>
        <button type="button" className={estilos.acao} onClick={rodar}>
          Verificar de novo
        </button>
        <button
          type="button"
          className={estilos.acao}
          onClick={() => void navigator.clipboard?.writeText(JSON.stringify(relatorio, null, 2))}
        >
          Copiar diagnóstico
        </button>
      </div>
    </details>
  );
}

/** Versão autônoma: roda o `doctor.rodar` por conta própria. */
export function DoctorResumo() {
  const estado = useDoctor();
  return <DoctorResumoPuro estado={estado} aoRodar={() => void estado.rodar()} />;
}
