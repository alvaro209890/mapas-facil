import Image from "next/image";

export function CenaMapa() {
  return (
    <div className="map-scene" aria-label="Demonstração animada da geração de um mapa">
      <div className="map-scene__halo" aria-hidden="true" />
      <div className="map-scene__prompt">
        <span className="map-scene__prompt-mark">›</span>
        <span>faça a Dinâmica desta pasta</span>
        <i aria-hidden="true" />
      </div>

      <div className="map-scene__stage">
        <div className="map-scene__topbar" aria-hidden="true">
          <span>PROJETO / ÁREA DEMONSTRATIVA</span>
          <span className="map-scene__live">
            <i />
            PROCESSANDO
          </span>
        </div>

        <div className="map-scene__rail" aria-hidden="true">
          <span className="is-done">01</span>
          <span className="is-done">02</span>
          <span className="is-active">03</span>
          <span>04</span>
        </div>

        <div className="map-scene__layers" aria-hidden="true">
          <small>CAMADAS / 05</small>
          <span className="layer-row layer-row--base">
            <i />
            BASE SATÉLITE
            <b>OK</b>
          </span>
          <span className="layer-row layer-row--atp">
            <i />
            LIMITE ATP
            <b>OK</b>
          </span>
          <span className="layer-row layer-row--avn">
            <i />
            VEGETAÇÃO
            <b>OK</b>
          </span>
          <span className="layer-row layer-row--ac">
            <i />
            USO DO SOLO
            <b>OK</b>
          </span>
          <span className="layer-row layer-row--mun">
            <i />
            MUNICÍPIO
            <b>OK</b>
          </span>
        </div>

        <div className="map-paper">
          <div className="map-paper__edge" aria-hidden="true" />
          <div className="map-paper__image map-paper__image--base">
            <Image
              src="/mapa-demo-ficticio.webp"
              alt=""
              fill
              priority
              unoptimized
              sizes="(max-width: 900px) 58vw, 320px"
            />
          </div>
          <div className="map-paper__image map-paper__image--final">
            <Image
              src="/mapa-demo-ficticio.webp"
              alt="Mapa técnico demonstrativo com propriedade fictícia e geometria aleatória"
              fill
              priority
              unoptimized
              sizes="(max-width: 900px) 58vw, 320px"
            />
          </div>
          <div className="map-paper__scan" aria-hidden="true" />
          <div className="map-paper__parcel-trace" aria-hidden="true">
            <i />
            <i />
            <i />
            <i />
            <i />
            <i />
          </div>
          <div className="map-paper__crosshair" aria-hidden="true" />
          <div className="map-paper__label map-paper__label--one">ATP</div>
          <div className="map-paper__label map-paper__label--two">AVN</div>
          <div className="map-paper__label map-paper__label--three">AC</div>
        </div>

        <div className="map-scene__metadata" aria-hidden="true">
          <small>METADADOS</small>
          <span>
            Escala <b>1:12.000</b>
          </span>
          <span>
            Datum <b>SIRGAS 2000</b>
          </span>
          <span>
            Layout <b>IMAP A3</b>
          </span>
        </div>

        <div className="map-scene__legend" aria-hidden="true">
          <small>LEGENDA</small>
          <span>
            <i className="swatch swatch--forest" /> Formação florestal
          </span>
          <span>
            <i className="swatch swatch--open" /> Vegetação aberta
          </span>
          <span>
            <i className="swatch swatch--use" /> Uso agropecuário
          </span>
          <span>
            <i className="swatch swatch--water" /> Corpos d&apos;água
          </span>
        </div>

        <div className="map-scene__minimap" aria-hidden="true">
          <span />
          <i />
          <b>N</b>
        </div>

        <div className="map-scene__orbit" aria-hidden="true">
          <span>78%</span>
          <small>COMPOSIÇÃO</small>
        </div>

        <div className="map-scene__status">
          <span className="map-scene__status-dot" aria-hidden="true" />
          <div className="map-scene__status-track">
            <span>Lendo arquivos da pasta</span>
            <span>Compondo camadas locais</span>
            <span>Aplicando padrão técnico</span>
            <span>Mapa e artefatos prontos</span>
          </div>
        </div>

        <div className="map-scene__export map-scene__export--mxd">
          <span>MXD</span>
          <small>editável</small>
        </div>
        <div className="map-scene__export map-scene__export--pdf">
          <span>PDF</span>
          <small>conferência</small>
        </div>
        <div className="map-scene__done" aria-hidden="true">
          <i>✓</i>
          <span>
            2 ARQUIVOS GERADOS
            <small>prontos para conferência</small>
          </span>
        </div>
      </div>

      <div className="map-scene__caption">
        <span>DINÂMICA 2026</span>
        <span>PROGRESSO REAL · 07/10</span>
      </div>
    </div>
  );
}
