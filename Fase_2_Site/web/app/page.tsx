import Link from "next/link";
import { CenaMapa } from "../components/CenaMapa";
import { SiteFooter } from "../components/SiteFooter";
import { SiteHeader } from "../components/SiteHeader";

export default function Home() {
  return (
    <main>
      <section className="hero" id="inicio">
        <SiteHeader />
        <div className="hero__grain" aria-hidden="true" />
        <div className="hero__orb hero__orb--one" aria-hidden="true" />
        <div className="hero__orb hero__orb--two" aria-hidden="true" />

        <div className="hero__content shell">
          <div className="hero__copy">
            <p className="eyebrow hero__eyebrow">
              Cartografia técnica, sem o caminho longo
            </p>
            <h1>
              Do pedido ao
              <span>mapa pronto.</span>
            </h1>
            <p className="hero__lead">
              O Mapas Fácil organiza sua análise, compõe as camadas e entrega
              mapas no padrão técnico — direto no seu Windows.
            </p>
            <div className="hero__actions">
              <Link className="button button--primary" href="/download">
                <span>Conhecer o download</span>
                <span className="button__arrow" aria-hidden="true">
                  ↗
                </span>
              </Link>
              <a className="button button--ghost" href="#como-funciona">
                Ver como funciona
              </a>
            </div>
            <div className="hero__footnote">
              <span className="hero__pulse" aria-hidden="true" />
              Aplicativo para Windows · MXD + PDF
            </div>
          </div>

          <CenaMapa />
        </div>

        <div className="hero__ticker" aria-label="Fluxo do Mapas Fácil">
          <div className="shell hero__ticker-inner">
            <span>Pasta de análise</span>
            <i aria-hidden="true" />
            <span>Leitura inteligente</span>
            <i aria-hidden="true" />
            <span>Camadas organizadas</span>
            <i aria-hidden="true" />
            <span>Padrão técnico</span>
            <i aria-hidden="true" />
            <span>MXD + PDF</span>
          </div>
        </div>
      </section>

      <section className="manifesto section shell" id="como-funciona">
        <div className="section__index" aria-hidden="true">
          01
        </div>
        <div className="manifesto__heading">
          <p className="eyebrow">O essencial permanece</p>
          <h2>
            O trabalho continua técnico.
            <span>O caminho fica mais simples.</span>
          </h2>
        </div>
        <div className="manifesto__copy">
          <p>
            Você descreve o mapa como falaria com alguém da equipe. O Mapas
            Fácil lê a pasta, entende os arquivos e conduz a montagem sem
            esconder o que está acontecendo.
          </p>
          <p className="manifesto__note">
            Mais clareza para produzir. Mais tempo para analisar.
          </p>
        </div>
      </section>

      <section className="workflow section">
        <div className="shell">
          <div className="section__topline">
            <p className="eyebrow">Uma sequência, não uma caixa-preta</p>
            <span>02 — Fluxo</span>
          </div>
          <div className="workflow__grid">
            <article className="workflow__item">
              <span className="workflow__number">01</span>
              <div className="workflow__line" aria-hidden="true" />
              <h3>Abra sua pasta</h3>
              <p>
                Shapefiles, referências e materiais do projeto entram no mesmo
                contexto de trabalho.
              </p>
              <span className="workflow__meta">Leitura local</span>
            </article>
            <article className="workflow__item">
              <span className="workflow__number">02</span>
              <div className="workflow__line" aria-hidden="true" />
              <h3>Peça o mapa</h3>
              <p>
                Escreva “faça a Dinâmica desta pasta”. O app identifica o
                modelo, as camadas e o próximo passo.
              </p>
              <span className="workflow__meta">Conversa orientada</span>
            </article>
            <article className="workflow__item">
              <span className="workflow__number">03</span>
              <div className="workflow__line" aria-hidden="true" />
              <h3>Acompanhe a composição</h3>
              <p>
                Base, imóvel, vegetação, município, legenda e metadados surgem
                em uma construção visível.
              </p>
              <span className="workflow__meta">Progresso real</span>
            </article>
            <article className="workflow__item">
              <span className="workflow__number">04</span>
              <div className="workflow__line" aria-hidden="true" />
              <h3>Receba os artefatos</h3>
              <p>
                O resultado sai pronto para revisão e continuidade técnica em
                MXD e PDF.
              </p>
              <span className="workflow__meta">Entrega editável</span>
            </article>
          </div>
        </div>
      </section>

      <section className="product section shell">
        <div className="product__visual">
          <div className="product__rings" aria-hidden="true" />
          <div className="product__window">
            <div className="product__window-top">
              <span />
              <span />
              <span />
              <small>Harmonia / Dinâmica 2026</small>
            </div>
            <div className="product__window-body">
              <div className="product__side">
                <span className="product__side-title">PROJETO</span>
                <span>ATP.shp</span>
                <span>AVN.shp</span>
                <span>Áreas consolidadas</span>
                <span>Referências</span>
              </div>
              <div className="product__chat">
                <div className="product__prompt">
                  Faça a Dinâmica desta pasta.
                </div>
                <div className="product__answer">
                  <span />
                  <span />
                  <span />
                </div>
                <div className="product__progress">
                  <i />
                  <small>montando layout e metadados</small>
                </div>
              </div>
              <div className="product__preview">
                <div className="product__map-mini" />
              </div>
            </div>
          </div>
        </div>

        <div className="product__copy">
          <p className="eyebrow">Feito para o fluxo real</p>
          <h2>Inteligência que trabalha junto com seu método.</h2>
          <p>
            O app foi pensado para o cotidiano de quem produz mapas: arquivos
            locais, padrões definidos, conferência e saída que continua
            editável.
          </p>
          <ul className="product__list">
            <li>
              <span>01</span>
              Seus arquivos permanecem no seu computador.
            </li>
            <li>
              <span>02</span>
              Cada etapa do mapa fica visível durante a geração.
            </li>
            <li>
              <span>03</span>
              ArcMap é opcional: o fluxo também entrega PDF nativo.
            </li>
          </ul>
          <Link className="text-link" href="/requisitos">
            Conferir requisitos <span aria-hidden="true">→</span>
          </Link>
        </div>
      </section>

      <section className="closing">
        <div className="closing__contours" aria-hidden="true" />
        <div className="shell closing__inner">
          <p className="eyebrow">Mapas Fácil para Windows</p>
          <h2>
            Menos caminho entre
            <span>entender e entregar.</span>
          </h2>
          <p>
            A primeira versão pública está sendo preparada. Conheça os
            requisitos e acompanhe a chegada do instalador.
          </p>
          <div className="closing__actions">
            <Link className="button button--light" href="/download">
              Ver disponibilidade
              <span className="button__arrow" aria-hidden="true">
                ↗
              </span>
            </Link>
            <Link className="button button--outline-light" href="/contato">
              Falar sobre o projeto
            </Link>
          </div>
        </div>
      </section>

      <SiteFooter />
    </main>
  );
}
