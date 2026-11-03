/**
 * Formatos de folha do produto — espelho de `projetos_repo.FORMATOS` no servidor (A4 … A0).
 *
 * Os mm são os da ISO 216 em **retrato**; a orientação só troca largura por altura. O
 * servidor tem a palavra final (`SV-091`), aqui é para desenhar e validar antes de enviar.
 */

export const FORMATOS = {
  A4: { largura_mm: 210, altura_mm: 297, area_m2: 0.0625 },
  A3: { largura_mm: 297, altura_mm: 420, area_m2: 0.125 },
  A2: { largura_mm: 420, altura_mm: 594, area_m2: 0.25 },
  A1: { largura_mm: 594, altura_mm: 841, area_m2: 0.5 },
  A0: { largura_mm: 841, altura_mm: 1189, area_m2: 1 },
} as const;

export type FormatoFolha = keyof typeof FORMATOS;
export type Orientacao = 'retrato' | 'paisagem';

/** Do menor para o maior — é a ordem em que os cartões aparecem na tela. */
export const ORDEM_FORMATOS: FormatoFolha[] = ['A4', 'A3', 'A2', 'A1', 'A0'];

export const ORIENTACOES: Orientacao[] = ['retrato', 'paisagem'];

/** Quantas folhas A4 cabem nesta: serve para o texto "equivale a 4 folhas A4". */
export function equivalenciaA4(formato: FormatoFolha): number {
  return Math.round(FORMATOS[formato].area_m2 / FORMATOS.A4.area_m2);
}

export function textoFolha(formato: FormatoFolha, orientacao: Orientacao): string {
  const f = FORMATOS[formato];
  const l = orientacao === 'paisagem' ? f.altura_mm : f.largura_mm;
  const a = orientacao === 'paisagem' ? f.largura_mm : f.altura_mm;
  return `${formato} · ${orientacao} · ${l}×${a} mm`;
}

/** O ZIP do imóvel: até 2 GB no servidor (`MF_UPLOAD_MAX_MB`). */
export const ZIP_MAX_MB = 2048;

export function problemasZip(arquivo: File): string | null {
  if (!arquivo.name.toLowerCase().endsWith('.zip')) {
    return 'O arquivo precisa ser um .zip do pacote do imóvel.';
  }
  if (arquivo.size === 0) return 'O arquivo está vazio.';
  if (arquivo.size > ZIP_MAX_MB * 1024 * 1024) {
    return `O pacote tem ${(arquivo.size / 1024 / 1024).toFixed(0)} MB; o limite é ${ZIP_MAX_MB} MB.`;
  }
  return null;
}
