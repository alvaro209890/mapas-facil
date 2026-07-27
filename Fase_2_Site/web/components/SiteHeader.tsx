import Link from "next/link";
import { linkedinUrl } from "../lib/site";

export function SiteHeader() {
  return (
    <header className="site-header shell">
      <Link className="brand" href="/" aria-label="Mapas Fácil — página inicial">
        <span className="brand__mark" aria-hidden="true">
          <i />
          <i />
          <i />
        </span>
        <span>Mapas Fácil</span>
      </Link>
      <nav className="site-nav" aria-label="Navegação principal">
        <Link href="/#como-funciona">Como funciona</Link>
        <Link href="/requisitos">Requisitos</Link>
        <Link href="/contato">Contato</Link>
        <a href={linkedinUrl} target="_blank" rel="noreferrer">
          LinkedIn ↗
        </a>
      </nav>
      <Link className="header-download" href="/download">
        Download
        <span aria-hidden="true">↗</span>
      </Link>
    </header>
  );
}
