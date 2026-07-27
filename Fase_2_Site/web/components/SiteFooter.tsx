import Link from "next/link";
import {
  contactEmail,
  developerName,
  linkedinUrl,
  whatsappDisplay,
  whatsappUrl,
} from "../lib/site";

export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="shell site-footer__grid">
        <div>
          <Link className="brand brand--footer" href="/">
            <span className="brand__mark" aria-hidden="true">
              <i />
              <i />
              <i />
            </span>
            <span>Mapas Fácil</span>
          </Link>
          <p>Cartografia técnica, sem o caminho longo.</p>
        </div>
        <div className="site-footer__nav">
          <Link href="/#como-funciona">Como funciona</Link>
          <Link href="/requisitos">Requisitos</Link>
          <Link href="/download">Download</Link>
          <Link href="/contato">Contato</Link>
          <a href={linkedinUrl} target="_blank" rel="noreferrer">
            LinkedIn ↗
          </a>
        </div>
        <div className="site-footer__meta">
          <span>Aplicativo para Windows</span>
          <span>MXD + PDF</span>
          <span className="site-footer__developer-label">Desenvolvido por</span>
          <a href={linkedinUrl} target="_blank" rel="noreferrer">
            {developerName} ↗
          </a>
          <a href={whatsappUrl} target="_blank" rel="noreferrer">
            WhatsApp {whatsappDisplay}
          </a>
          <a href={`mailto:${contactEmail}`}>{contactEmail}</a>
          <span>© {new Date().getFullYear()} Mapas Fácil</span>
        </div>
      </div>
    </footer>
  );
}
