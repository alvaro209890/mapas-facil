/**
 * Cartão da folha (W6-06).
 *
 * Desenha a folha na **proporção real** do formato (A4 … A0), já com o giro quando a
 * orientação é paisagem. Não é enfeite: o usuário precisa ver que A0 é 8× A4 e que a
 * paisagem inverte a largura — errar isso na fábrica de mapas é o que faz o layout sair
 * com o título fora da folha.
 */

import { FORMATOS, type FormatoFolha, type Orientacao } from './formatos';
import estilos from './CartaoFolha.module.css';

export interface CartaoFolhaProps {
  formato: FormatoFolha;
  orientacao: Orientacao;
  selecionado?: boolean;
  aoEscolher?: (formato: FormatoFolha) => void;
  /** Lado maior do desenho em px (o menor vem pela proporção). */
  lado?: number;
}

/** Lado menor da folha em mm, em retrato. */
function medidas(formato: FormatoFolha): { largura: number; altura: number } {
  const f = FORMATOS[formato];
  return { largura: f.largura_mm, altura: f.altura_mm };
}

export function CartaoFolha({
  formato,
  orientacao,
  selecionado = false,
  aoEscolher,
  lado = 64,
}: CartaoFolhaProps) {
  const { largura, altura } = medidas(formato);
  const paisagem = orientacao === 'paisagem';
  const l = paisagem ? altura : largura;
  const a = paisagem ? largura : altura;
  const escala = lado / Math.max(l, a);
  const larguraPx = Math.round(l * escala);
  const alturaPx = Math.round(a * escala);

  const conteudo = (
    <>
      <span
        className={estilos.folha}
        style={{ width: `${larguraPx}px`, height: `${alturaPx}px` }}
        aria-hidden="true"
      >
        <span className={estilos.titulo} />
        <span className={estilos.campo} />
        <span className={estilos.legenda} />
      </span>
      <span className={estilos.rotulo}>
        {formato}
        <small>
          {l}×{a} mm
        </small>
      </span>
    </>
  );

  if (!aoEscolher) {
    return (
      <div className={seleselecionado(selecionado)} data-formato={formato}>
        {conteudo}
      </div>
    );
  }

  return (
    <button
      type="button"
      className={seleselecionado(selecionado)}
      data-formato={formato}
      aria-pressed={selecionado}
      aria-label={`Folha ${formato}, ${l} por ${a} milímetros`}
      onClick={() => aoEscolher(formato)}
    >
      {conteudo}
    </button>
  );
}

function seleselecionado(selecionado: boolean): string {
  const base = estilos.cartao ?? '';
  return selecionado ? `${base} ${estilos.ativo ?? ''}`.trim() : base;
}
