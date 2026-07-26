// C8 — `doctor.rodar` no renderer.
//
// Os campos abaixo são exatamente os que `nucleo/mapasfacil_nucleo/doctor.py`
// devolve. A UI **não inventa check**: o que o núcleo não reporta não aparece, e
// o que ele reporta como `nao_testado` é mostrado como não testado, não como ok.
//
// `sondar_arcpy` fica de fora de propósito: a sondagem é lenta e só faz sentido
// sob demanda no Windows (F1-13 bloco C / F1-04).

import { useCallback, useEffect, useState } from "react";

import { api, assinarEstadoNucleo } from "./ponte.js";
import type { ErroUi } from "./workspace.js";

export interface TemplateDoctor {
  id: string;
  sha256_ok: boolean;
  patch_ok: boolean;
  status: string;
}

export interface ArcMapDoctor {
  encontrado: boolean;
  caminho?: string | null;
  python?: string | null;
  versao?: string | null;
  licenca?: string | null;
  arcmap_aberto?: boolean;
  instavel?: boolean;
  nota?: string | null;
}

export interface RelatorioDoctor {
  so: string;
  arquitetura: string;
  nucleo: string;
  python: string;
  arcmap: ArcMapDoctor;
  gdal: { ogr2ogr: string | null; versao: string | null };
  templates: TemplateDoctor[];
  chaves: { deepseek: boolean; sema: boolean; planet: boolean };
  rede: Record<string, string>;
  espaco_livre_gb: number | null;
  pronto_para_mxd: boolean;
  motor_preferido: string;
}

export type SituacaoDoctor = "rodando" | "pronto" | "erro";

export interface EstadoDoctor {
  situacao: SituacaoDoctor;
  relatorio: RelatorioDoctor | null;
  erro: ErroUi | null;
}

function ehRelatorio(valor: unknown): valor is RelatorioDoctor {
  if (typeof valor !== "object" || valor === null) return false;
  const bruto = valor as Partial<RelatorioDoctor>;
  return typeof bruto.nucleo === "string" && typeof bruto.motor_preferido === "string";
}

export function useDoctor(): EstadoDoctor & { rodar: () => Promise<void> } {
  const [estado, setEstado] = useState<EstadoDoctor>({
    situacao: "rodando",
    relatorio: null,
    erro: null,
  });

  const rodar = useCallback(async () => {
    const ponte = api();
    if (ponte === undefined) {
      setEstado({
        situacao: "erro",
        relatorio: null,
        erro: { codigo: "UI-001", mensagem: "O núcleo não está disponível nesta janela." },
      });
      return;
    }
    setEstado((anterior) => ({ ...anterior, situacao: "rodando" }));
    const resposta = await ponte.chamar("doctor.rodar");
    if (resposta.ok && ehRelatorio(resposta.resultado)) {
      setEstado({ situacao: "pronto", relatorio: resposta.resultado, erro: null });
      return;
    }
    setEstado((anterior) => ({
      situacao: "erro",
      relatorio: anterior.relatorio,
      erro: resposta.erro ?? {
        codigo: "UI-001",
        mensagem: "O núcleo respondeu um diagnóstico que este app não entendeu.",
      },
    }));
  }, []);

  useEffect(() => {
    void rodar();
    // Núcleo que volta do `UI-001` merece um diagnóstico novo, sem o usuário pedir.
    return assinarEstadoNucleo((nucleo) => {
      if (nucleo.estado === "pronto") void rodar();
    });
  }, [rodar]);

  return { ...estado, rodar };
}

export type TomCheck = "ok" | "aviso" | "erro" | "desconhecido";

export interface CheckDoctor {
  id: string;
  rotulo: string;
  valor: string;
  tom: TomCheck;
  detalhe?: string;
}

/** Traduz o relatório em linhas de UI. Só o que o núcleo mandou vira check. */
export function checksDoRelatorio(relatorio: RelatorioDoctor): CheckDoctor[] {
  const templatesOk = relatorio.templates.filter((t) => t.sha256_ok).length;
  const chaves = relatorio.chaves;

  const checks: CheckDoctor[] = [
    {
      id: "nucleo",
      rotulo: "núcleo",
      valor: `v${relatorio.nucleo} · Python ${relatorio.python}`,
      tom: "ok",
      detalhe: `${relatorio.so} · ${relatorio.arquitetura}`,
    },
    {
      id: "motor",
      rotulo: "motor de mapa",
      valor: relatorio.motor_preferido,
      tom: relatorio.pronto_para_mxd ? "ok" : "aviso",
      detalhe: relatorio.pronto_para_mxd
        ? "pronto para gerar .mxd"
        : "o .mxd sai pelo caminho de template e o PDF pelo motor nativo",
    },
    {
      id: "arcmap",
      rotulo: "ArcMap",
      valor: relatorio.arcmap.encontrado
        ? (relatorio.arcmap.versao ?? "instalado")
        : "não encontrado",
      tom: relatorio.arcmap.encontrado ? "ok" : "aviso",
      detalhe: relatorio.arcmap.nota ?? undefined,
    },
    {
      id: "templates",
      rotulo: "templates",
      valor: `${templatesOk} de ${relatorio.templates.length} com sha256`,
      tom: templatesOk === 0 ? "erro" : templatesOk === relatorio.templates.length ? "ok" : "aviso",
      detalhe: relatorio.templates.map((t) => `${t.id}: ${t.status}`).join(" · "),
    },
    {
      id: "ogr2ogr",
      rotulo: "ogr2ogr",
      valor: relatorio.gdal.ogr2ogr === null ? "não encontrado" : "disponível",
      tom: relatorio.gdal.ogr2ogr === null ? "erro" : "ok",
      detalhe: relatorio.gdal.ogr2ogr ?? "sem ogr2ogr o núcleo não recorta camada",
    },
    {
      id: "chave-deepseek",
      rotulo: "chave DeepSeek",
      valor: chaves.deepseek ? "configurada" : "ausente",
      tom: chaves.deepseek ? "ok" : "aviso",
      detalhe: chaves.deepseek ? undefined : "sem IA o app continua: galeria e geração funcionam",
    },
    {
      id: "chave-sema",
      rotulo: "authkey SEMA",
      valor: chaves.sema ? "configurada" : "ausente",
      tom: chaves.sema ? "ok" : "aviso",
    },
    {
      id: "chave-planet",
      rotulo: "chave Planet",
      valor: chaves.planet ? "configurada" : "ausente",
      tom: chaves.planet ? "ok" : "aviso",
    },
  ];

  for (const [servico, situacao] of Object.entries(relatorio.rede)) {
    checks.push({
      id: `rede-${servico}`,
      rotulo: `rede ${servico}`,
      valor: situacao === "nao_testado" ? "não testado" : situacao.replace(/_/g, " "),
      tom: situacao === "nao_testado" ? "desconhecido" : situacao === "ok" ? "ok" : "aviso",
    });
  }

  if (relatorio.espaco_livre_gb !== null) {
    checks.push({
      id: "espaco",
      rotulo: "espaço livre",
      valor: `${relatorio.espaco_livre_gb} GB`,
      tom: relatorio.espaco_livre_gb < 5 ? "aviso" : "ok",
    });
  }

  return checks;
}

/** Pior tom da lista — é o que o chip resumido mostra. */
export function tomGeral(checks: CheckDoctor[]): TomCheck {
  if (checks.some((check) => check.tom === "erro")) return "erro";
  if (checks.some((check) => check.tom === "aviso")) return "aviso";
  return "ok";
}
