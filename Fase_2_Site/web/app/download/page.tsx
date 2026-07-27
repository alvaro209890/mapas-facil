import type { Metadata } from "next";
import Link from "next/link";
import { SiteFooter } from "../../components/SiteFooter";
import { SiteHeader } from "../../components/SiteHeader";

export const metadata: Metadata = {
  title: "Download",
  description: "Baixe o Mapas Fácil para Windows quando o instalador estiver disponível.",
};

export default function DownloadPage() {
  const downloadUrl = process.env.NEXT_PUBLIC_DOWNLOAD_URL?.trim();

  return (
    <main className="subpage download-page">
      <div className="subpage__hero subpage__hero--compact">
        <SiteHeader />
        <div className="shell subpage__hero-content">
          <p className="eyebrow">Mapas Fácil para Windows</p>
          <h1>
            O instalador está
            <span>a caminho.</span>
          </h1>
        </div>
      </div>

      <section className="download section shell">
        <div className="download__card">
          <div className="download__visual" aria-hidden="true">
            <div className="download__mark">
              <i />
              <i />
              <i />
            </div>
            <span>MF</span>
          </div>
          <div className="download__content">
            <p className="eyebrow">Versão para Windows</p>
            <h2>{downloadUrl ? "Pronto para instalar." : "Instalador em breve."}</h2>
            <p>
              {downloadUrl
                ? "Baixe a versão atual do Mapas Fácil e siga as instruções do instalador."
                : "A primeira versão pública está em preparação. Esta página será atualizada assim que o pacote estiver pronto para uso."}
            </p>
            {downloadUrl ? (
              <a className="button button--primary" href={downloadUrl}>
                Baixar para Windows <span aria-hidden="true">↓</span>
              </a>
            ) : (
              <div className="download__pending" role="status">
                <span aria-hidden="true" />
                Preparando a primeira versão
              </div>
            )}
            <small>
              Windows 10/11 · O arquivo do instalador não é hospedado no
              repositório do projeto.
            </small>
          </div>
        </div>

        <div className="download__links">
          <Link href="/requisitos">
            <span>01</span>
            Conferir requisitos
            <i aria-hidden="true">→</i>
          </Link>
          <Link href="/contato">
            <span>02</span>
            Falar sobre o projeto
            <i aria-hidden="true">→</i>
          </Link>
        </div>
      </section>
      <SiteFooter />
    </main>
  );
}
