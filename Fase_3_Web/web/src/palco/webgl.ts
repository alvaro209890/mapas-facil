/**
 * Detecção e fallback de WebGL (W8-07 / W-07 §Mapa base do palco).
 *
 * Código canônico de fallback: WB-001.
 * Quando o ambiente não suporta WebGL (jsdom, máquinas sem aceleração 3D ou restrição
 * de navegador), o palco cai diretamente para o modo folha / resultado sem instanciar
 * o canvas do MapLibre GL, mantendo os eventos fluindo e as camadas listadas.
 */

export const CODIGO_SEM_WEBGL = 'WB-001';
export const MENSAGEM_SEM_WEBGL =
  'Aceleração gráfica WebGL indisponível (WB-001): modo folha ativado.';

/**
 * Verifica se o navegador atual suporta contexto WebGL (WebGL 1 ou WebGL 2).
 */
export function suportaWebGL(): boolean {
  if (typeof window === 'undefined' || typeof document === 'undefined') {
    return false;
  }

  // Em ambientes sem suporte ou jsdom, o construtor global não existe
  if (typeof window.WebGLRenderingContext === 'undefined') {
    return false;
  }

  try {
    const canvas = document.createElement('canvas');
    const gl =
      canvas.getContext('webgl2') ||
      canvas.getContext('webgl') ||
      canvas.getContext('experimental-webgl');

    return gl !== null && gl !== undefined;
  } catch {
    return false;
  }
}
