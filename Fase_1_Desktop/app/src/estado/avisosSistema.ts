// F1-02 §Watcher — arquivo que aparece/some na pasta vira **aviso do sistema no
// chat**, nunca mensagem do agente (não custa turno, não vai para o LLM, não
// entra no transcript).
//
// O núcleo já filtra `.lock`, `~$*`, `.tmp` e a pasta de saída durante o job
// (`workspace/watcher.py`) e já monta o `resumo` legível ("apareceu AUAS.shp
// (AUAS) · 8 feições · 491,26 ha"). Aqui só decidimos **gravidade**: sumir um
// arquivo que o MapSpec ativo usa é alerta; o resto é informação.

import { useEffect, useState } from "react";

import type { EnvelopeEvento, MudancaWorkspace } from "./eventos.js";
import { ehWorkspaceMudou } from "./eventos.js";
import { assinarEventos } from "./ponte.js";

export type NivelAviso = "info" | "alerta";

export interface AvisoSistema {
  id: string;
  texto: string;
  nivel: NivelAviso;
  caminho: string;
  acao: MudancaWorkspace["acao"];
}

/** Só os últimos: a pasta pode mexer muito durante uma extração de ZIP. */
export const MAX_AVISOS_SISTEMA = 20;

/** MapSpec reduzido ao que importa aqui — evita acoplar ao schema inteiro. */
export interface MapSpecEmUso {
  camadas?: { fonte?: string }[];
}

/** `local.ATP` → `atp`; qualquer outra fonte (catálogo) não vem do disco. */
function fontesLocaisEmUso(mapspec: MapSpecEmUso | null): Set<string> {
  const ids = new Set<string>();
  for (const camada of mapspec?.camadas ?? []) {
    const fonte = camada.fonte;
    if (typeof fonte === "string" && fonte.startsWith("local.")) {
      ids.add(fonte.slice("local.".length).toLowerCase());
    }
  }
  return ids;
}

/** `SHP/ATP.shp` → `atp` (stem, que é o `id_local` do índice). */
export function idLocalDoCaminho(caminho: string): string {
  const nome = caminho.split("/").pop() ?? caminho;
  const semExtensao = nome.replace(/\.[^.]+$/, "");
  return semExtensao.toLowerCase();
}

/**
 * Uma mudança → aviso, ou `null` quando não vale interromper o usuário.
 *
 * Pura: é o que o teste exercita. `modificado` não vira aviso — arquivo sendo
 * reescrito por outro programa geraria ruído constante sem informação nova.
 */
export function avisoDaMudanca(
  mudanca: MudancaWorkspace,
  mapspec: MapSpecEmUso | null,
  idEvento: string,
): AvisoSistema | null {
  if (mudanca.acao === "modificado") return null;

  const usadas = fontesLocaisEmUso(mapspec);
  const emUso = usadas.has(idLocalDoCaminho(mudanca.caminho));
  const base = mudanca.resumo ?? `${mudanca.acao} ${mudanca.caminho}`;

  if (mudanca.acao === "removido") {
    return {
      id: `${idEvento}:${mudanca.caminho}`,
      // Sumir arquivo que o mapa em construção usa é o caso que estraga a
      // geração sem avisar — por isso vira alerta, não linha na lista.
      nivel: emUso ? "alerta" : "info",
      texto: emUso
        ? `${base} — o mapa atual usa esta camada; gerar agora vai falhar ou sair incompleto.`
        : base,
      caminho: mudanca.caminho,
      acao: mudanca.acao,
    };
  }

  return {
    id: `${idEvento}:${mudanca.caminho}`,
    nivel: "info",
    texto: base,
    caminho: mudanca.caminho,
    acao: mudanca.acao,
  };
}

export function aplicarMudancas(
  anterior: AvisoSistema[],
  mudancas: MudancaWorkspace[],
  mapspec: MapSpecEmUso | null,
  idEvento: string,
): AvisoSistema[] {
  const novos = mudancas
    .map((m) => avisoDaMudanca(m, mapspec, idEvento))
    .filter((a): a is AvisoSistema => a !== null);
  if (novos.length === 0) return anterior;
  const juntos = [...anterior, ...novos];
  return juntos.length > MAX_AVISOS_SISTEMA ? juntos.slice(-MAX_AVISOS_SISTEMA) : juntos;
}

/**
 * Assina `workspace.mudou` e devolve os avisos de sistema do chat.
 *
 * `mapspec` entra como parâmetro (não por store global) porque a gravidade do
 * aviso depende do mapa que está em construção **agora**.
 */
export function useAvisosSistema(mapspec: MapSpecEmUso | null): {
  avisos: AvisoSistema[];
  dispensar: (id: string) => void;
} {
  const [avisos, setAvisos] = useState<AvisoSistema[]>([]);

  useEffect(() => {
    return assinarEventos((evento: EnvelopeEvento) => {
      if (!ehWorkspaceMudou(evento)) return;
      setAvisos((anterior) =>
        aplicarMudancas(anterior, evento.dados.mudancas, mapspec, evento.id),
      );
    });
  }, [mapspec]);

  return {
    avisos,
    dispensar: (id) => setAvisos((anterior) => anterior.filter((a) => a.id !== id)),
  };
}
