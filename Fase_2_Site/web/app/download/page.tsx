import type { Metadata } from "next";
import Link from "next/link";
import { SiteFooter } from "../../components/SiteFooter";
import { SiteHeader } from "../../components/SiteHeader";
import { formatBytes, resolveDownloadInfo } from "../../lib/download";

export const metadata: Metadata = {
  title: "Download",
  description:
    "Baixe o instalador Windows do Mapas Fácil (versão estável no GitHub Releases).",
};

export default async function DownloadPage() {
  const info = await resolveDownloadInfo();
  const tamanho = formatBytes(info.tamanhoBytes);
  const downloadUrl = info.url?.trim() || "";

  return (
    <main className="subpage download-page">
      <div className="subpage__hero subpage__hero--compact">
        <SiteHeader />
        <div className="shell subpage__hero-content">
          <p className="eyebrow">Mapas Fácil para Windows</p>
          <h1>
            {downloadUrl ? (
              <>
                Instalador
                <span>pronto.</span>
              </>
            ) : (
              <>
                O instalador está
                <span>a caminho.</span>
              </>
            )}
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
            <p className="eyebrow">
              {downloadUrl
                ? `Versão ${info.versao} · Windows x64`
                : "Versão para Windows"}
            </p>
            <h2>{downloadUrl ? "Pronto para instalar." : "Instalador em breve."}</h2>
            <p>
              {downloadUrl
                ? "Baixe o Mapas Fácil, crie sua conta local e use o chat com a DeepSeek já liberada no login. O ArcMap é opcional."
                : "A primeira versão pública está em preparação. Esta página será atualizada assim que o pacote estiver pronto para uso."}
            </p>
            {downloadUrl ? (
              <a
                className="button button--primary"
                href={downloadUrl}
                rel="noopener noreferrer"
              >
                Baixar para Windows <span aria-hidden="true">↓</span>
              </a>
            ) : (
              <div className="download__pending" role="status">
                <span aria-hidden="true" />
                Preparando a primeira versão
              </div>
            )}
            {downloadUrl ? (
              <ul className="download__meta">
                <li>
                  <span>Arquivo</span>
                  <code>{info.nome}</code>
                </li>
                {tamanho ? (
                  <li>
                    <span>Tamanho</span>
                    <code>{tamanho}</code>
                  </li>
                ) : null}
                {info.sha256 ? (
                  <li>
                    <span>SHA-256</span>
                    <code>{info.sha256}</code>
                  </li>
                ) : null}
              </ul>
            ) : null}
            <small>
              {downloadUrl
                ? info.notas ||
                  "Windows 10/11 · Instalador hospedado no GitHub Releases."
                : "Windows 10/11 · O arquivo do instalador não é hospedado no repositório do projeto."}{" "}
              Conta e chave DeepSeek ficam só no PC — não neste site.
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
