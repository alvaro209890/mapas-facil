// A5 — `painel-preview`: o mapa sendo construído (F1-16 §A5).
//
// Duas fases, e as duas são progresso real:
//
//   Fase 1 (esqueleto) — a pilha de camadas do MapSpec, em ordem de desenho.
//   Cada linha acende quando `job.progresso` traz o `item` correspondente, ou
//   quando `job.artefato_parcial` anuncia aquela camada materializada. As
//   molduras (tabela, minimapa, legenda) acendem nas etapas em que nascem.
//
//   Fase 2 (artefato real) — quando chega `preview_png`, a imagem entra com
//   crossfade de `--mf-dur-3` sobre a anterior. O PDF final marca o fim.
//
// Sem evento nenhum, o painel mostra o esqueleto apagado e diz que está
// esperando — nunca uma barra falsa nem uma imagem de exemplo (AP-07).

import { useEffect, useState } from "react";

import { EstadoVazio } from "../componentes/EstadoVazio.js";
import type { EstadoArtefatos } from "../estado/artefatos.js";
import { useArtefatosJob, useImagemArtefato } from "../estado/artefatos.js";
import { indiceDaEtapa, rotuloDaEtapa } from "../estado/eventos.js";
import type { EstadoProgressoJob } from "../estado/progressoJob.js";
import { useProgressoJob } from "../estado/progressoJob.js";
import estilos from "./Preview.module.css";

export interface CamadaPreview {
  id: string;
  nome_no_mxd?: string;
  legenda?: string | null;
  ordem?: number;
}

export interface MapSpecPreview {
  titulo?: string;
  camadas?: CamadaPreview[];
  elementos_layout?: Record<string, boolean>;
}

export interface PropsPreview {
  mapspec: MapSpecPreview | null;
  /** Injetados nos testes; em produção vêm dos hooks de evento. */
  progresso?: EstadoProgressoJob | null;
  artefatos?: EstadoArtefatos;
}

/** Elemento de layout → etapa em que ele nasce (F1-16 §A5 fase 1). */
export const ETAPA_DO_ELEMENTO: Record<string, string> = {
  tabela: "gerando_tabela",
  minimapa: "aplicando_layout",
  legenda: "aplicando_layout",
};

export type EstadoLinha = "pendente" | "pronta";

/**
 * Uma camada está pronta quando o núcleo disse que está: `item` de
 * `job.progresso` ou artefato `camada`. Pura — é o que o teste exercita.
 */
export function estadoDaCamada(
  camadaId: string,
  progresso: EstadoProgressoJob | null,
  artefatos: EstadoArtefatos,
): EstadoLinha {
  if (artefatos.camadas.some((c) => c.camadaId === camadaId)) return "pronta";
  if (progresso?.item === camadaId) return "pronta";
  return "pendente";
}

/** Moldura acesa quando a etapa em que ela nasce já foi alcançada pelo job. */
export function estadoDoElemento(
  elemento: string,
  progresso: EstadoProgressoJob | null,
): EstadoLinha {
  const etapa = ETAPA_DO_ELEMENTO[elemento];
  if (etapa === undefined || progresso === null) return "pendente";
  return progresso.indice >= indiceDaEtapa(etapa) ? "pronta" : "pendente";
}

export function Preview({ mapspec, progresso, artefatos }: PropsPreview) {
  const progressoVivo = useProgressoJob();
  const artefatosVivos = useArtefatosJob();
  const prog = progresso === undefined ? progressoVivo : progresso;
  const arte = artefatos ?? artefatosVivos;

  // Fase 2: a imagem só existe se o núcleo mandou o caminho. Duas camadas para o
  // crossfade — a anterior fica embaixo até a nova terminar de aparecer.
  const imagem = useImagemArtefato(arte.previewPng);
  const [pilhaImagem, setPilhaImagem] = useState<{ atual: string | null; previa: string | null }>({
    atual: null,
    previa: null,
  });

  useEffect(() => {
    if (imagem.src === null) return;
    setPilhaImagem((anterior) =>
      anterior.atual === imagem.src ? anterior : { atual: imagem.src, previa: anterior.atual },
    );
  }, [imagem.src]);

  const camadaVisual = pilhaImagem.atual;

  if (mapspec === null) {
    return (
      <div id="painel-preview" className={estilos.raiz}>
        <EstadoVazio
          titulo="Sem mapa para pré-visualizar"
          descricao="Monte um modelo na galeria ou peça um mapa no chat — o preview acompanha a geração etapa a etapa."
        />
      </div>
    );
  }

  const camadas = [...(mapspec.camadas ?? [])].sort(
    (a, b) => (a.ordem ?? 0) - (b.ordem ?? 0),
  );
  const elementos = Object.entries(mapspec.elementos_layout ?? {})
    .filter(([nome, ligado]) => ligado && ETAPA_DO_ELEMENTO[nome] !== undefined)
    .map(([nome]) => nome);

  return (
    <div id="painel-preview" className={estilos.raiz}>
      <div
        className={estilos.palco}
        data-fase={camadaVisual === null ? "esqueleto" : "artefato"}
        data-final={arte.pdf === null ? "nao" : "sim"}
      >
        {pilhaImagem.previa !== null && (
          <img className={estilos.imagem} src={pilhaImagem.previa} alt="" data-camada="previa" />
        )}
        {camadaVisual !== null && (
          <img
            key={camadaVisual}
            className={`${estilos.imagem} ${estilos.entrando}`}
            src={camadaVisual}
            alt={`pré-visualização de ${mapspec.titulo ?? "mapa"} em construção`}
            data-camada="atual"
            data-artefato={arte.previewPng ?? undefined}
          />
        )}
        {camadaVisual === null && (
          <ul className={estilos.pilha} aria-label="camadas do mapa">
            {camadas.map((camada) => (
              <li
                key={camada.id}
                className={estilos.linha}
                data-camada={camada.id}
                data-estado={estadoDaCamada(camada.id, prog, arte)}
              >
                <span className={estilos.marca} aria-hidden="true" />
                <span className={estilos.nome}>
                  {camada.legenda ?? camada.nome_no_mxd ?? camada.id}
                </span>
              </li>
            ))}
            {elementos.map((elemento) => (
              <li
                key={elemento}
                className={`${estilos.linha} ${estilos.moldura}`}
                data-elemento={elemento}
                data-estado={estadoDoElemento(elemento, prog)}
              >
                <span className={estilos.marca} aria-hidden="true" />
                <span className={estilos.nome}>{elemento}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <p className={estilos.rodape} aria-live="polite">
        {arte.pdf !== null ? (
          <span className={estilos.final}>PDF pronto · {arte.pdf}</span>
        ) : prog !== null ? (
          <>
            <span>{rotuloDaEtapa(prog.etapa)}</span>
            <span className={`${estilos.pct} mf-num`}>{prog.pct}%</span>
          </>
        ) : (
          <span className={estilos.espera}>esperando a geração começar</span>
        )}
      </p>
      {arte.tabelaPng !== null && (
        <p className={estilos.rodape} data-tabela="pronta">
          <span>tabela de quantitativos pronta</span>
        </p>
      )}
      {imagem.erro !== null && (
        <p className={estilos.rodape} role="alert">
          {imagem.erro}
        </p>
      )}
    </div>
  );
}
