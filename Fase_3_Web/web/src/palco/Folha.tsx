/**
 * Folha do Mapa em SVG com mm reais e motion (W8-04 / W-07 §CamadaFolha).
 *
 * Responsável por renderizar a folha do mapa em mm reais:
 * - viewBox baseado nas dimensões reais da página em mm (ex: A3 = 297×420 mm);
 * - elementos do layout ordenados segundo ORDEM_LAYOUT de motion.py;
 * - cada elemento posicionado exatamente em sua caixa_mm;
 * - recorte PNG via <image> quando caminho está presente;
 * - texto via <text> com tamanho proporcional em mm reais quando conteudo está presente;
 * - snapshot do mapa encaixado na caixa do quadro do mapa;
 * - entrada animada via motion.g e AnimatePresence com fallback imediato se prefers-reduced-motion.
 */

import { AnimatePresence, motion } from 'motion/react';
import type { FormatoFolha, Orientacao } from '../componentes/formatos';
import { FORMATOS } from '../componentes/formatos';
import { useReducedMotion } from './useReducedMotion';
import estilos from './Folha.module.css';

export interface CaixaMm {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

export interface DadosFolha {
  formato?: FormatoFolha | string | undefined;
  orientacao?: Orientacao | string | undefined;
  largura_mm?: number | undefined;
  altura_mm?: number | undefined;
}

export interface ElementoFolhaDados {
  elemento: string;
  sequencia?: number | undefined;
  total?: number | undefined;
  folha?: DadosFolha | Record<string, unknown> | null | undefined;
  caixa_mm?: CaixaMm | Record<string, unknown> | null | undefined;
  conteudo?: Record<string, unknown> | string | null | undefined;
  caminho?: string | null | undefined;
  visivel?: boolean | undefined;
}

export interface ElementoSelecionado {
  id: string;
  tipo: string;
  bbox_mm: CaixaMm;
  coord_geo?: [number, number] | undefined;
}

export interface PropriedadesFolha {
  formato?: FormatoFolha | string | undefined;
  orientacao?: Orientacao | string | undefined;
  folha?: DadosFolha | undefined;
  elementos?: Record<string, ElementoFolhaDados> | ElementoFolhaDados[] | undefined;
  elementosVisiveis?: readonly string[] | undefined;
  snapshotMapa?: string | null | undefined;
  reduzirMovimento?: boolean | undefined;
  fatorPx?: number | undefined;
  className?: string | undefined;
  elementoSelecionado?: string | null | undefined;
  aoSelecionarElemento?: ((elemento: ElementoSelecionado) => void) | undefined;
}

/** Ordem canônica em que o motor nativo desenha a folha (motion.py / ORDEM_LAYOUT). */
export const ORDEM_LAYOUT = [
  'grade',
  'grade_linhas',
  'titulo_caixa',
  'norte',
  'metadados',
  'escala_grafica',
  'creditos',
  'legenda',
  'minimapa',
  'logo',
  'tabela',
] as const;

/** Mapeamento de elemento para a respectiva caixa do perfil Harmonia. */
export const ELEMENTO_PARA_CAIXA: Record<string, string> = {
  titulo_caixa: 'titulo',
  norte: 'rosa',
  minimapa: 'minimapa',
  metadados: 'metadados',
  escala_grafica: 'metadados',
  creditos: 'metadados',
  legenda: 'legenda',
  tabela: 'tabela',
  logo: 'logo',
  grade: 'mapa',
  grade_linhas: 'mapa',
};

// Caixas padrão de perfil Harmonia para A4 em retrato (210 × 297 mm)
const CAIXAS_PADRAO_RETRATO: Record<string, CaixaMm> = {
  mapa: { x0: 7.0, y0: 5.0, x1: 203.5, y1: 257.0 },
  titulo: { x0: 63.7, y0: 3.6, x1: 132.7, y1: 21.8 },
  rosa: { x0: 186.3, y0: 4.0, x1: 202.0, y1: 27.0 },
  minimapa: { x0: 0.0, y0: 262.0, x1: 62.0, y1: 297.0 },
  metadados: { x0: 64.9, y0: 265.2, x1: 120.0, y1: 291.2 },
  legenda: { x0: 131.8, y0: 266.0, x1: 172.0, y1: 295.0 },
  logo: { x0: 175.0, y0: 265.0, x1: 208.0, y1: 292.0 },
  tabela: { x0: 67.1, y0: 236.3, x1: 203.0, y1: 256.3 },
};

// Caixas padrão de perfil Harmonia para A4 em paisagem (297 × 210 mm)
const CAIXAS_PADRAO_PAISAGEM: Record<string, CaixaMm> = {
  mapa: { x0: 5.6, y0: 4.8, x1: 291.1, y1: 168.5 },
  titulo: { x0: 107.2, y0: 3.0, x1: 185.0, y1: 20.5 },
  rosa: { x0: 276.7, y0: 4.3, x1: 288.5, y1: 21.7 },
  minimapa: { x0: 2.0, y0: 172.0, x1: 62.0, y1: 208.0 },
  metadados: { x0: 76.4, y0: 173.8, x1: 156.2, y1: 205.3 },
  legenda: { x0: 177.1, y0: 172.0, x1: 227.0, y1: 208.2 },
  logo: { x0: 245.0, y0: 175.0, x1: 292.0, y1: 205.0 },
  tabela: { x0: 80.0, y0: 140.0, x1: 285.0, y1: 160.0 },
};

/** Fator de conversão tipográfico: 1 pt = 25.4 / 72 mm ≈ 0.3528 mm */
const MM_POR_PT = 25.4 / 72;

export function obterDimensoesFolha(
  formatoProp?: string | undefined,
  orientacaoProp?: string | undefined,
  folhaProp?: DadosFolha | undefined,
): { largura_mm: number; altura_mm: number; formato: FormatoFolha; orientacao: Orientacao } {
  const formatoBruto = folhaProp?.formato ?? formatoProp ?? 'A3';
  const formatoValido = (
    ['A4', 'A3', 'A2', 'A1', 'A0'].includes(formatoBruto) ? formatoBruto : 'A3'
  ) as FormatoFolha;

  const orientacaoBruta = folhaProp?.orientacao ?? orientacaoProp ?? 'retrato';
  const orientacaoValida = (orientacaoBruta === 'paisagem' ? 'paisagem' : 'retrato') as Orientacao;

  if (
    typeof folhaProp?.largura_mm === 'number' &&
    typeof folhaProp?.altura_mm === 'number' &&
    folhaProp.largura_mm > 0 &&
    folhaProp.altura_mm > 0
  ) {
    return {
      largura_mm: folhaProp.largura_mm,
      altura_mm: folhaProp.altura_mm,
      formato: formatoValido,
      orientacao: orientacaoValida,
    };
  }

  const medidas = FORMATOS[formatoValido];
  const largura_mm = orientacaoValida === 'paisagem' ? medidas.altura_mm : medidas.largura_mm;
  const altura_mm = orientacaoValida === 'paisagem' ? medidas.largura_mm : medidas.altura_mm;

  return {
    largura_mm,
    altura_mm,
    formato: formatoValido,
    orientacao: orientacaoValida,
  };
}

/** Calcula o fator k da folha em relação a A4 retrato (largura 210 mm). */
function fatorEscalaK(formato: FormatoFolha): number {
  return FORMATOS[formato].largura_mm / FORMATOS.A4.largura_mm;
}

function extrairCaixaMm(caixa: unknown): CaixaMm | null {
  if (!caixa || typeof caixa !== 'object') return null;
  const c = caixa as Record<string, unknown>;
  const x0 = typeof c.x0 === 'number' ? c.x0 : undefined;
  const y0 = typeof c.y0 === 'number' ? c.y0 : undefined;
  const x1 = typeof c.x1 === 'number' ? c.x1 : undefined;
  const y1 = typeof c.y1 === 'number' ? c.y1 : undefined;
  if (x0 !== undefined && y0 !== undefined && x1 !== undefined && y1 !== undefined) {
    return { x0, y0, x1, y1 };
  }
  return null;
}

/** Obtém a caixa em mm do elemento, usando a do evento ou a do perfil Harmonia. */
function obterCaixaElemento(
  el: ElementoFolhaDados,
  formato: FormatoFolha,
  orientacao: Orientacao,
): CaixaMm {
  const extraida = extrairCaixaMm(el.caixa_mm);
  if (extraida) {
    return extraida;
  }

  const nomeCaixa = ELEMENTO_PARA_CAIXA[el.elemento] ?? 'mapa';
  const tabelaBase = orientacao === 'paisagem' ? CAIXAS_PADRAO_PAISAGEM : CAIXAS_PADRAO_RETRATO;
  const caixaBase = tabelaBase[nomeCaixa] ?? tabelaBase.mapa!;
  const k = fatorEscalaK(formato);

  return {
    x0: Number((caixaBase.x0 * k).toFixed(2)),
    y0: Number((caixaBase.y0 * k).toFixed(2)),
    x1: Number((caixaBase.x1 * k).toFixed(2)),
    y1: Number((caixaBase.y1 * k).toFixed(2)),
  };
}

/** Calcula tamanho de fonte em mm reais proporcional ao elemento e perfil. */
function obterTamanhoFonteMm(
  elemento: string,
  orientacao: Orientacao,
  k: number,
  alturaCaixaMm: number,
): number {
  let ptBase = 9.0;
  if (elemento === 'titulo_caixa') {
    ptBase = orientacao === 'paisagem' ? 26.0 : 24.0;
  } else if (elemento === 'legenda') {
    ptBase = orientacao === 'paisagem' ? 10.0 : 8.0;
  } else if (elemento === 'metadados' || elemento === 'creditos' || elemento === 'escala_grafica') {
    ptBase = orientacao === 'paisagem' ? 11.0 : 9.0;
  } else if (elemento === 'grade' || elemento === 'grade_linhas') {
    ptBase = 6.0;
  }

  const tamanhoMm = ptBase * k * MM_POR_PT;
  // Limita ao espaço vertical da caixa para não estourar a borda
  return Number(Math.min(tamanhoMm, Math.max(1.5, alturaCaixaMm * 0.75)).toFixed(2));
}

function obterIndiceOrdem(nome: string): number {
  const indice = (ORDEM_LAYOUT as readonly string[]).indexOf(nome);
  return indice >= 0 ? indice : 999;
}

export function Folha({
  formato: formatoProp,
  orientacao: orientacaoProp,
  folha: folhaProp,
  elementos,
  elementosVisiveis,
  snapshotMapa,
  reduzirMovimento: reduzirMovimentoProp,
  fatorPx = 1,
  className,
  elementoSelecionado,
  aoSelecionarElemento,
}: PropriedadesFolha) {
  const reducaoDetectada = useReducedMotion();
  const reduzir = reduzirMovimentoProp ?? reducaoDetectada;

  // Normaliza lista de elementos
  const listaElementos: ElementoFolhaDados[] = Array.isArray(elementos)
    ? elementos
    : elementos
      ? Object.values(elementos)
      : [];

  // Se houver algum elemento com dados de folha e não foi passada folha explícita, aproveita
  const primeiroElementoComFolha = listaElementos.find((e) => e.folha);
  const folhaEfetiva = folhaProp ?? primeiroElementoComFolha?.folha ?? undefined;

  const { largura_mm, altura_mm, formato, orientacao } = obterDimensoesFolha(
    formatoProp,
    orientacaoProp,
    folhaEfetiva,
  );

  const k = fatorEscalaK(formato);

  // Filtra elementos visíveis e ordena conforme ORDEM_LAYOUT
  const elementosFiltrados = listaElementos
    .filter((el) => {
      if (elementosVisiveis !== undefined) {
        return elementosVisiveis.includes(el.elemento);
      }
      return el.visivel !== false;
    })
    .sort((a, b) => obterIndiceOrdem(a.elemento) - obterIndiceOrdem(b.elemento));

  // Caixa do quadro do mapa
  const elementoGrade = listaElementos.find(
    (e) => e.elemento === 'grade' || e.elemento === 'grade_linhas',
  );
  const caixaMapa =
    extrairCaixaMm(elementoGrade?.caixa_mm) ??
    obterCaixaElemento({ elemento: 'grade' }, formato, orientacao);
  const larguraMapa = Math.max(1, caixaMapa.x1 - caixaMapa.x0);
  const alturaMapa = Math.max(1, caixaMapa.y1 - caixaMapa.y0);

  const viewBoxLargura = largura_mm * fatorPx;
  const viewBoxAltura = altura_mm * fatorPx;

  return (
    <div className={`${estilos.folhaWrapper} ${className ?? ''}`} data-testid="palco-folha">
      <svg
        className={estilos.folhaSvg}
        viewBox={`0 0 ${viewBoxLargura} ${viewBoxAltura}`}
        preserveAspectRatio="xMidYMid meet"
        width="100%"
        height="100%"
        xmlns="http://www.w3.org/2000/svg"
        role="img"
        aria-label={`Folha ${formato} ${orientacao} (${largura_mm}×${altura_mm} mm)`}
      >
        {/* Papel da Folha (fundo branco em mm reais) */}
        <rect
          x={0}
          y={0}
          width={largura_mm}
          height={altura_mm}
          className={estilos.papel}
          data-testid="papel-folha"
        />

        {/* Quadro do Mapa (fundo escuro + snapshot do mapa quando disponível; clicável) */}
        <g
          id="camada-quadro-mapa"
          data-elemento="quadro-mapa"
          tabIndex={0}
          role="button"
          aria-label="Quadro do mapa"
          className={`${estilos.elementoClicavel} ${elementoSelecionado === 'quadro-mapa' ? estilos.elementoSelecionado : ''}`}
          onClick={() => {
            aoSelecionarElemento?.({
              id: 'quadro_mapa',
              tipo: 'mapa',
              bbox_mm: caixaMapa,
              coord_geo: [Number((caixaMapa.x0 + larguraMapa / 2).toFixed(2)), Number((caixaMapa.y0 + alturaMapa / 2).toFixed(2))],
            });
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              aoSelecionarElemento?.({
                id: 'quadro_mapa',
                tipo: 'mapa',
                bbox_mm: caixaMapa,
              });
            }
          }}
        >
          {snapshotMapa ? (
            <image
              href={snapshotMapa}
              x={caixaMapa.x0}
              y={caixaMapa.y0}
              width={larguraMapa}
              height={alturaMapa}
              preserveAspectRatio="none"
              data-elemento="snapshot-mapa"
              data-testid="snapshot-mapa"
            />
          ) : (
            <g>
              <rect
                x={caixaMapa.x0}
                y={caixaMapa.y0}
                width={larguraMapa}
                height={alturaMapa}
                className={estilos.quadroMapaFundo}
                data-testid="quadro-mapa-placeholder"
              />
              <text
                x={caixaMapa.x0 + larguraMapa / 2}
                y={caixaMapa.y0 + alturaMapa / 2}
                className={estilos.quadroMapaPlaceholderTexto}
              >
                [Quadro do Mapa]
              </text>
            </g>
          )}
        </g>

        {/* Elementos de layout com entrada animada motion */}
        <AnimatePresence>
          {elementosFiltrados.map((el) => {
            const caixa = obterCaixaElemento(el, formato, orientacao);
            const largura = Math.max(0.1, caixa.x1 - caixa.x0);
            const altura = Math.max(0.1, caixa.y1 - caixa.y0);
            const centroX = caixa.x0 + largura / 2;
            const centroY = caixa.y0 + altura / 2;
            const tamanhoFonteMm = obterTamanhoFonteMm(el.elemento, orientacao, k, altura);

            const propsAnimacao = reduzir
              ? {
                  initial: false as const,
                  animate: { opacity: 1, scale: 1 },
                  transition: { duration: 0 },
                }
              : {
                  initial: { opacity: 0, scale: 0.96 },
                  animate: { opacity: 1, scale: 1 },
                  exit: { opacity: 0 },
                  transition: { duration: 0.36, ease: [0.2, 0.8, 0.2, 1] as const },
                };

            const estaSelecionado = elementoSelecionado === el.elemento;
            return (
              <motion.g
                key={el.elemento}
                id={`elemento-${el.elemento}`}
                data-elemento={el.elemento}
                tabIndex={0}
                role="button"
                aria-label={`Elemento ${el.elemento}`}
                className={`${estilos.elementoClicavel} ${estaSelecionado ? estilos.elementoSelecionado : ''}`}
                onClick={(e) => {
                  e.stopPropagation();
                  aoSelecionarElemento?.({
                    id: el.elemento,
                    tipo: el.elemento,
                    bbox_mm: caixa,
                  });
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    e.stopPropagation();
                    aoSelecionarElemento?.({
                      id: el.elemento,
                      tipo: el.elemento,
                      bbox_mm: caixa,
                    });
                  }
                }}
                {...propsAnimacao}
                style={{
                  transformOrigin: `${centroX}px ${centroY}px`,
                }}
              >
                {/* 1. Elemento com recorte PNG: usa <image> */}
                {el.caminho ? (
                  <image
                    href={el.caminho}
                    x={caixa.x0}
                    y={caixa.y0}
                    width={largura}
                    height={altura}
                    preserveAspectRatio="xMidYMid meet"
                  />
                ) : el.conteudo ? (
                  /* 2. Elemento com texto: usa <text> com tamanho de fonte proporcional ao mm */
                  typeof el.conteudo === 'string' ? (
                    <text
                      x={caixa.x0 + 2 * k}
                      y={caixa.y0 + altura / 2}
                      dominantBaseline="middle"
                      fontSize={tamanhoFonteMm}
                      fontFamily="var(--mf-fonte-display, sans-serif)"
                      fontWeight={el.elemento === 'titulo_caixa' ? '600' : 'normal'}
                      fill="#111111"
                      className={estilos.textoElemento}
                    >
                      {el.conteudo}
                    </text>
                  ) : (
                    <text
                      x={caixa.x0 + 2 * k}
                      y={caixa.y0 + tamanhoFonteMm}
                      fontSize={tamanhoFonteMm}
                      fontFamily="var(--mf-fonte-mono, monospace)"
                      fill="#222222"
                      className={estilos.textoElemento}
                    >
                      {Object.entries(el.conteudo).map(([chave, val], i) => (
                        <tspan
                          key={chave}
                          x={caixa.x0 + 2 * k}
                          dy={i === 0 ? 0 : tamanhoFonteMm * 1.3}
                        >
                          {`${chave}: ${String(val)}`}
                        </tspan>
                      ))}
                    </text>
                  )
                ) : el.elemento === 'grade' || el.elemento === 'grade_linhas' ? (
                  /* 3. Grade do mapa (traço de contorno) */
                  <rect
                    x={caixa.x0}
                    y={caixa.y0}
                    width={largura}
                    height={altura}
                    fill="none"
                    stroke="#1b242c"
                    strokeWidth={0.5 * k}
                  />
                ) : (
                  /* 4. Bloco de layout com nome do elemento */
                  <g>
                    <rect
                      x={caixa.x0}
                      y={caixa.y0}
                      width={largura}
                      height={altura}
                      fill="rgba(0, 0, 0, 0.03)"
                      stroke="rgba(0, 0, 0, 0.25)"
                      strokeWidth={0.3 * k}
                      strokeDasharray={`${2 * k},${2 * k}`}
                    />
                    <text
                      x={centroX}
                      y={centroY}
                      textAnchor="middle"
                      dominantBaseline="middle"
                      fontSize={Math.max(1.5, Math.min(largura / 8, altura / 4, 3.8 * k))}
                      fill="#555555"
                      fontFamily="var(--mf-fonte-mono, monospace)"
                      className={estilos.textoElemento}
                    >
                      [{el.elemento}]
                    </text>
                  </g>
                )}
              </motion.g>
            );
          })}
        </AnimatePresence>
      </svg>
    </div>
  );
}
