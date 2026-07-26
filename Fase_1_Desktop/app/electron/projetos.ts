// C7 — projetos recentes em `config.json`. Só nome e caminho da pasta escolhida
// pelo usuário no diálogo nativo; segredo nenhum mora aqui (F1-01).
//
// O renderer nunca manda um caminho para cá: ele pede "abrir o recente nº 2" e
// quem traduz índice → caminho é o processo main.
import { basename } from "node:path";

import type { ArquivoPreferencias } from "./preferencias.js";

export const CHAVE_RECENTES = "projetos_recentes";
const MAXIMO = 8;

export interface ProjetoRecente {
  nome: string;
  caminho: string;
  abertoEm: string;
}

/** O que o renderer pode ver: sem caminho absoluto, com o índice para reabrir. */
export interface ProjetoRecenteVisivel {
  indice: number;
  nome: string;
  abertoEm: string;
}

function ehRecente(valor: unknown): valor is ProjetoRecente {
  if (typeof valor !== "object" || valor === null) return false;
  const item = valor as Partial<ProjetoRecente>;
  return typeof item.nome === "string" && typeof item.caminho === "string";
}

export function lerRecentes(preferencias: ArquivoPreferencias): ProjetoRecente[] {
  const bruto = preferencias.ler()[CHAVE_RECENTES];
  if (!Array.isArray(bruto)) return [];
  return bruto.filter(ehRecente).slice(0, MAXIMO);
}

export function visiveis(recentes: ProjetoRecente[]): ProjetoRecenteVisivel[] {
  return recentes.map((projeto, indice) => ({
    indice,
    nome: projeto.nome,
    abertoEm: projeto.abertoEm,
  }));
}

/** Move o projeto para o topo da lista (ou insere), sem duplicar caminho. */
export function registrar(
  preferencias: ArquivoPreferencias,
  caminho: string,
  agora: string = new Date().toISOString(),
): ProjetoRecente[] {
  const anteriores = lerRecentes(preferencias).filter((projeto) => projeto.caminho !== caminho);
  const lista = [{ nome: basename(caminho), caminho, abertoEm: agora }, ...anteriores].slice(
    0,
    MAXIMO,
  );
  preferencias.gravar({ [CHAVE_RECENTES]: lista });
  return lista;
}
