// Cena decorativa da `tela-login` — eco do hero do site (F2-04) dentro do
// design system dark do app. Tudo é SVG/CSS local: zero CDN, zero binário novo.
//
// Não é indicador de progresso: nada aqui é amarrado a evento do núcleo, e por
// isso a cena é `aria-hidden` e some inteira em `prefers-reduced-motion`
// (AP-07 proíbe spinner falso, não ornamento declaradamente decorativo).

import estilos from "./CenaMapaLogin.module.css";

/** Perímetro fictício — não corresponde a imóvel real. */
const PERIMETRO = "M118,96 L300,58 L338,244 L196,300 L104,236 Z";
const VEGETACAO = "M132,110 L286,74 L306,190 L206,232 L124,196 Z";
const CONSOLIDADA = "M212,214 L312,196 L330,242 L204,292 Z";

export function CenaMapaLogin() {
  return (
    <div className={estilos.cena} aria-hidden="true">
      <div className={estilos.halo} />

      <div className={estilos.prompt}>
        <span className={estilos.promptMarca}>›</span>
        <span>faça a Dinâmica desta pasta</span>
        <i className={estilos.cursor} />
      </div>

      <div className={estilos.papel}>
        <svg className={estilos.mapa} viewBox="0 0 420 340" role="presentation">
          <defs>
            <linearGradient id="mf-base" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#16241c" />
              <stop offset="55%" stopColor="#1c3126" />
              <stop offset="100%" stopColor="#14201a" />
            </linearGradient>
            <linearGradient id="mf-varredura" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="rgba(53,199,154,0)" />
              <stop offset="50%" stopColor="rgba(53,199,154,0.45)" />
              <stop offset="100%" stopColor="rgba(53,199,154,0)" />
            </linearGradient>
            <pattern id="mf-grade" width="42" height="42" patternUnits="userSpaceOnUse">
              <path d="M42 0 L0 0 0 42" fill="none" stroke="rgba(232,237,242,0.07)" strokeWidth="1" />
            </pattern>
          </defs>

          <rect width="420" height="340" fill="url(#mf-base)" />
          {/* Floresta manchada + talhões claros: é assim que o mosaico Planet
              da região lê de verdade — pastagem retangular sobre mata. */}
          <g className={estilos.textura}>
            <ellipse cx="96" cy="70" rx="74" ry="42" fill="#20362a" />
            <ellipse cx="330" cy="120" rx="88" ry="54" fill="#1a2c22" />
            <ellipse cx="150" cy="280" rx="96" ry="50" fill="#233a2c" />
            <ellipse cx="368" cy="286" rx="60" ry="38" fill="#1b2e23" />
          </g>
          <g className={estilos.talhoes}>
            <path d="M18,18 L128,4 L138,58 L28,74 Z" fill="#6d7a52" />
            <path d="M140,2 L226,0 L232,44 L148,56 Z" fill="#8a9463" />
            <path d="M330,20 L418,10 L420,62 L336,72 Z" fill="#5f6f4b" />
            <path d="M8,246 L96,232 L108,300 L20,318 Z" fill="#7c8558" />
            <path d="M262,300 L360,286 L372,340 L276,340 Z" fill="#6a7550" />
            <path d="M382,150 L420,146 L420,206 L386,210 Z" fill="#55663f" />
          </g>
          <rect width="420" height="340" fill="url(#mf-grade)" />

          <path className={estilos.camadaVeg} d={VEGETACAO} />
          <path className={estilos.camadaAc} d={CONSOLIDADA} />
          <path className={estilos.perimetro} d={PERIMETRO} />

          <rect className={estilos.varredura} width="420" height="90" fill="url(#mf-varredura)" />

          <g className={estilos.vertices}>
            <circle cx="118" cy="96" r="3.5" />
            <circle cx="300" cy="58" r="3.5" />
            <circle cx="338" cy="244" r="3.5" />
            <circle cx="196" cy="300" r="3.5" />
            <circle cx="104" cy="236" r="3.5" />
          </g>
        </svg>

        <div className={`${estilos.selo} ${estilos.seloAtp}`}>ATP</div>
        <div className={`${estilos.selo} ${estilos.seloAvn}`}>AVN</div>

        <div className={estilos.norte}>
          <span>N</span>
          <i />
        </div>
      </div>

      <div className={estilos.camadas}>
        <small>CAMADAS</small>
        <span className={estilos.linhaCamada} data-atraso="1">
          <i data-cor="base" /> Base satélite <b>ok</b>
        </span>
        <span className={estilos.linhaCamada} data-atraso="2">
          <i data-cor="atp" /> Limite ATP <b>ok</b>
        </span>
        <span className={estilos.linhaCamada} data-atraso="3">
          <i data-cor="avn" /> Vegetação nativa <b>ok</b>
        </span>
        <span className={estilos.linhaCamada} data-atraso="4">
          <i data-cor="ac" /> Área consolidada <b>ok</b>
        </span>
      </div>

      <div className={estilos.saidas}>
        <span className={estilos.saida} data-atraso="1">
          MXD <small>editável</small>
        </span>
        <span className={estilos.saida} data-atraso="2">
          PDF <small>conferência</small>
        </span>
      </div>

      <p className={estilos.legenda}>
        <span>DINÂMICA 2026</span>
        <span>1:60.000 · SIRGAS 2000 · UTM 22S</span>
      </p>
    </div>
  );
}
