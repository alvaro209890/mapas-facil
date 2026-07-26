// C7 — estado do workspace no renderer.
//
// Os tipos abaixo **espelham a resposta real** de `workspace.abrir` do núcleo
// (`nucleo/mapasfacil_nucleo/workspace/`), e a fixture do teste é gerada por
// `tests/fixtures/gerar-fixture-workspace.py` chamando esse mesmo código — a UI
// não inventa campo que o núcleo não devolve.
//
// Quem abre a pasta é o processo main (diálogo nativo + `workspace.abrir`); daqui
// só saem chamadas NDJSON e o índice que voltou. Nenhum acesso a disco (fsguard).

import { useCallback, useEffect, useState } from "react";

import type { ProjetoRecente } from "./ponte.js";
import { api } from "./ponte.js";

export interface AvisoShapefile {
  codigo: string;
  mensagem: string;
}

export interface CrsShapefile {
  epsg: number | null;
  resumo: string | null;
  zona_utm_sugerida: number | null;
  adivinhado: boolean;
}

export interface Shapefile {
  caminho: string;
  papel: string | null;
  id_local: string;
  tipo_geometria: string;
  feicoes: number;
  campos: string[];
  bbox: { xmin: number; ymin: number; xmax: number; ymax: number };
  crs: CrsShapefile;
  area_ha: number | null;
  geometrias_corrigidas: number;
  encoding_dbf: string | null;
  vazia: boolean;
  avisos: AvisoShapefile[];
  valido: boolean;
}

export interface ArquivoPdf {
  caminho: string;
  recibo_car: boolean;
}

export interface IndiceWorkspace {
  raiz: string;
  shapefiles: Shapefile[];
  pdfs: ArquivoPdf[];
  zips: { caminho: string }[];
  outros: { caminho: string; tipo: string }[];
  fontes_locais: string[];
  recibo_car: string | null;
}

/** Recibo do CAR já parseado pelo núcleo. **Nunca tem CPF** (AP-09). */
export interface ReciboCar {
  nome_imovel: string | null;
  municipio: string | null;
  uf: string | null;
  car_estadual: string | null;
  recibo_federal: string | null;
  area_total_ha: number | null;
  situacao: string | null;
}

export interface DoctorNoWorkspace {
  nucleo: string;
  pronto_para_mxd: boolean;
  motor_preferido: string;
}

export interface RespostaWorkspaceAbrir {
  workspace: IndiceWorkspace;
  recibo: ReciboCar | null;
  doctor: DoctorNoWorkspace;
}

export interface ErroUi {
  codigo: string;
  mensagem: string;
}

export type SituacaoWorkspace = "vazio" | "abrindo" | "aberto" | "erro";

export interface EstadoWorkspace {
  situacao: SituacaoWorkspace;
  indice: IndiceWorkspace | null;
  recibo: ReciboCar | null;
  doctor: DoctorNoWorkspace | null;
  erro: ErroUi | null;
  recentes: ProjetoRecente[];
}

const INICIAL: EstadoWorkspace = {
  situacao: "vazio",
  indice: null,
  recibo: null,
  doctor: null,
  erro: null,
  recentes: [],
};

const SEM_PONTE: ErroUi = {
  codigo: "UI-001",
  mensagem: "O núcleo não está disponível nesta janela, então conectar pasta não funciona.",
};

/** Nome do projeto para o breadcrumb: a última pasta do caminho, sem o resto. */
export function nomeDoProjeto(indice: IndiceWorkspace | null): string | undefined {
  if (indice === null) return undefined;
  const partes = indice.raiz.split(/[\\/]/).filter((parte) => parte.length > 0);
  return partes[partes.length - 1] ?? indice.raiz;
}

/** Shapefile com problema que o técnico precisa ver antes de gerar mapa. */
export function problemasDoShapefile(shapefile: Shapefile): string[] {
  const problemas = shapefile.avisos.map((aviso) => `${aviso.codigo} · ${aviso.mensagem}`);
  if (shapefile.vazia) problemas.push("Shapefile sem nenhuma feição.");
  return problemas;
}

function ehResposta(valor: unknown): valor is RespostaWorkspaceAbrir {
  if (typeof valor !== "object" || valor === null) return false;
  const bruto = valor as Partial<RespostaWorkspaceAbrir>;
  return typeof bruto.workspace === "object" && bruto.workspace !== null;
}

export interface AcoesWorkspace {
  conectar: () => Promise<void>;
  abrirRecente: (indice: number) => Promise<void>;
  reindexar: () => Promise<void>;
}

export function useWorkspace(): EstadoWorkspace & AcoesWorkspace {
  const [estado, setEstado] = useState<EstadoWorkspace>(INICIAL);

  const carregarRecentes = useCallback(async () => {
    const recentes = (await api()?.projetosRecentes()) ?? [];
    setEstado((anterior) => ({ ...anterior, recentes }));
  }, []);

  useEffect(() => {
    void carregarRecentes();
  }, [carregarRecentes]);

  const aplicar = useCallback(
    (resposta: { ok?: boolean; resultado?: unknown; erro?: ErroUi } | undefined) => {
      if (resposta?.ok === true && ehResposta(resposta.resultado)) {
        const dados = resposta.resultado;
        setEstado((anterior) => ({
          ...anterior,
          situacao: "aberto",
          indice: dados.workspace,
          recibo: dados.recibo ?? null,
          doctor: dados.doctor ?? null,
          erro: null,
        }));
        return true;
      }
      setEstado((anterior) => ({
        ...anterior,
        situacao: "erro",
        erro: resposta?.erro ?? {
          codigo: "UI-001",
          mensagem: "O núcleo respondeu algo que este app não entendeu.",
        },
      }));
      return false;
    },
    [],
  );

  const conectar = useCallback(async () => {
    const ponte = api();
    if (ponte === undefined) {
      setEstado((anterior) => ({ ...anterior, situacao: "erro", erro: SEM_PONTE }));
      return;
    }
    setEstado((anterior) => ({ ...anterior, situacao: "abrindo", erro: null }));
    const resposta = await ponte.conectarPasta();
    if (resposta.cancelado) {
      // Fechar o diálogo não é erro: volta exatamente para onde estava.
      setEstado((anterior) => ({
        ...anterior,
        situacao: anterior.indice === null ? "vazio" : "aberto",
      }));
      return;
    }
    if (aplicar(resposta)) await carregarRecentes();
  }, [aplicar, carregarRecentes]);

  const abrirRecente = useCallback(
    async (indice: number) => {
      const ponte = api();
      if (ponte === undefined) {
        setEstado((anterior) => ({ ...anterior, situacao: "erro", erro: SEM_PONTE }));
        return;
      }
      setEstado((anterior) => ({ ...anterior, situacao: "abrindo", erro: null }));
      const resposta = await ponte.abrirProjetoRecente(indice);
      if (aplicar(resposta)) await carregarRecentes();
    },
    [aplicar, carregarRecentes],
  );

  /** Reindexa sob demanda — o watcher (`workspace.mudou`) é de outro marco. */
  const reindexar = useCallback(async () => {
    const ponte = api();
    if (ponte === undefined) return;
    setEstado((anterior) => ({ ...anterior, situacao: "abrindo", erro: null }));
    const resposta = await ponte.chamar("workspace.reindexar");
    if (resposta.ok === true && typeof resposta.resultado === "object" && resposta.resultado !== null) {
      const bruto = resposta.resultado as { workspace?: IndiceWorkspace };
      if (bruto.workspace !== undefined) {
        setEstado((anterior) => ({
          ...anterior,
          situacao: "aberto",
          indice: bruto.workspace ?? anterior.indice,
          erro: null,
        }));
        return;
      }
    }
    aplicar(resposta);
  }, [aplicar]);

  return { ...estado, conectar, abrirRecente, reindexar };
}
