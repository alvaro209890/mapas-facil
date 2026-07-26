// painel-galeria-detalhe — mapeamento sugerido + Montar → MapSpec (F1-15).
// Não chama mapa.gerar: mapspec.validar fica no meio (próximo passo do fluxo).

import type { ModeloDetalhe } from "../estado/galeria.js";
import estilos from "./GaleriaDetalhe.module.css";

export interface PropsGaleriaDetalhe {
  detalhe: ModeloDetalhe;
  mapspec: Record<string, unknown> | null;
  avisos: string[];
  erro: { codigo: string; mensagem: string } | null;
  montando: boolean;
  aoVoltar: () => void;
  aoMontar: () => void;
}

export function GaleriaDetalhe({
  detalhe,
  mapspec,
  avisos,
  erro,
  montando,
  aoVoltar,
  aoMontar,
}: PropsGaleriaDetalhe) {
  const podeMontar = detalhe.status === "pronto" || detalhe.status === "parcial";

  return (
    <div id="painel-galeria-detalhe" className={estilos.raiz}>
      <button type="button" className={estilos.voltar} onClick={aoVoltar}>
        ← voltar à galeria
      </button>
      <h2 className={estilos.titulo}>{detalhe.nome}</h2>
      <p className={estilos.desc}>{detalhe.descricao}</p>
      {detalhe.motivo !== null && <p className={estilos.aviso}>{detalhe.motivo}</p>}

      <div className={estilos.bloco}>
        <span className={estilos.rotulo}>mapeamento sugerido</span>
        <ul className={estilos.lista}>
          {detalhe.requisitos_camadas.map((req) => (
            <li key={req.papel} className={estilos.item}>
              <span>
                {req.papel}
                {req.obrigatorio ? " *" : ""}
              </span>
              <span className="mf-num">{detalhe.mapeamento_sugerido[req.papel] ?? "—"}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className={estilos.acoes}>
        <button
          type="button"
          className={estilos.botao}
          data-primario="true"
          disabled={!podeMontar || montando}
          onClick={aoMontar}
        >
          {montando ? "montando…" : "Montar MapSpec"}
        </button>
      </div>

      {erro !== null && (
        <p className={estilos.erro} role="alert">
          <span className="mf-num">{erro.codigo}</span> · {erro.mensagem}
        </p>
      )}

      {avisos.length > 0 && (
        <div className={estilos.bloco}>
          <span className={estilos.rotulo}>avisos</span>
          {avisos.map((aviso) => (
            <p key={aviso} className={estilos.aviso}>
              {aviso}
            </p>
          ))}
        </div>
      )}

      {mapspec !== null && (
        <div className={estilos.bloco} id="painel-mapspec">
          <span className={estilos.rotulo}>MapSpec montado</span>
          <pre className={estilos.json}>{JSON.stringify(mapspec, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}
