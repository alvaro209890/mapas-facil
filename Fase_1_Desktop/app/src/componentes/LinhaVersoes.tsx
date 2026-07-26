// A6 — `linha-versoes`: troca de versão do MapSpec (F1-16 §A6).
//
// Liga com o primeiro `mapspec.atualizado`; sem evento, o componente não existe
// (AP-07) — nada de "v1" fixo antes de qualquer edição real acontecer. Cada
// troca de versão (evento novo ou clique) faz o painel de diff entrar com
// crossfade (`--mf-dur-3`) e as linhas alteradas piscarem uma vez em
// `--mf-acento-fraco`, via `key` no contêiner — CSS reinicia a animação no
// remount, sem `setInterval` nem estado de timer (AP-07).

import { ChevronLeft, ChevronRight } from "lucide-react";

import type { VersaoMapspec } from "../estado/mapspecVersoes.js";
import estilos from "./LinhaVersoes.module.css";

export interface PropsLinhaVersoes {
  versoes: VersaoMapspec[];
  indiceExibido: number;
  aoNavegar: (direcao: -1 | 1) => void;
  aoIrPara: (indice: number) => void;
}

export function LinhaVersoes({ versoes, indiceExibido, aoNavegar, aoIrPara }: PropsLinhaVersoes) {
  if (versoes.length === 0 || indiceExibido < 0) return null;
  const atual = versoes[indiceExibido];

  return (
    <div id="linha-versoes" className={estilos.raiz}>
      <div className={estilos.nav} role="group" aria-label="navegação de versões do mapa">
        <button
          type="button"
          className={estilos.seta}
          onClick={() => aoNavegar(-1)}
          disabled={indiceExibido <= 0}
          aria-label="versão anterior"
        >
          <ChevronLeft size={14} aria-hidden="true" />
        </button>
        <ol className={estilos.marcadores}>
          {versoes.map((v, indice) => (
            <li key={v.id}>
              <button
                type="button"
                className={estilos.marcador}
                data-ativo={indice === indiceExibido}
                onClick={() => aoIrPara(indice)}
                aria-current={indice === indiceExibido}
              >
                v{v.versao}
              </button>
            </li>
          ))}
        </ol>
        <button
          type="button"
          className={estilos.seta}
          onClick={() => aoNavegar(1)}
          disabled={indiceExibido >= versoes.length - 1}
          aria-label="próxima versão"
        >
          <ChevronRight size={14} aria-hidden="true" />
        </button>
      </div>

      {/* `key` = versão exibida: o remount reinicia o crossfade e o flash das
          linhas — é o mesmo evento (novo ou navegado) que "acende" a mudança. */}
      <div key={atual.chave} className={estilos.diffCard} data-testid="mapspec-diff">
        <p className={estilos.cabecalho}>
          versão {atual.versao}
          <span className={estilos.idCurto}>{atual.id.slice(-6)}</span>
        </p>
        {atual.diff.resumo.length === 0 ? (
          <p className={estilos.semAlteracao}>sem alterações de conteúdo nesta versão</p>
        ) : (
          <ul className={estilos.diffLista} aria-live="polite">
            {atual.diff.resumo.map((linha, indice) => (
              <li key={indice} className={estilos.diffLinha}>
                {linha}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
