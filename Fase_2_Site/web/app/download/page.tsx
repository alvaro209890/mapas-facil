import type { Metadata } from "next";
import Link from "next/link";
import { SiteFooter } from "../../components/SiteFooter";
import { SiteHeader } from "../../components/SiteHeader";
import {
  carregarDesktopRelease,
  DESKTOP_MANIFEST_URL,
  type DesktopDownloadManifest,
} from "../../lib/desktop-release";

export const metadata: Metadata = {
  title: "Download",
  description: "Baixe o Mapas Fácil para Windows — instalador da última release.",
};

function formatarBytes(n: number): string {
  if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(1)} GB`;
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(0)} MB`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)} KB`;
  return `${n} B`;
}

async function resolverDownload(): Promise<{
  manifesto: DesktopDownloadManifest | null;
  url: string | null;
  erro: string | null;
}> {
  const fallback = process.env.NEXT_PUBLIC_DOWNLOAD_URL?.trim() || null;
  try {
    const manifesto = await carregarDesktopRelease();
    const url = manifesto.instalador?.url ?? fallback;
    return { manifesto, url, erro: null };
  } catch (causa) {
    return {
      manifesto: null,
      url: fallback,
      erro: causa instanceof Error ? causa.message : String(causa),
    };
  }
}

export default async function DownloadPage() {
  const { manifesto, url, erro } = await resolverDownload();
  const pronto = Boolean(url);
  const versao = manifesto?.versao;
  const sha = manifesto?.instalador?.sha256;
  const tamanho = manifesto?.instalador?.tamanho_bytes;
  const notas = manifesto?.notas;

  return (
    <main className="subpage download-page">
      <div className="subpage__hero subpage__hero--compact">
        <SiteHeader />
        <div className="shell subpage__hero-content">
          <p className="eyebrow">Mapas Fácil para Windows</p>
          <h1>
            {pronto ? (
              <>
                Baixe e
                <span>comece.</span>
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
              {versao ? `Versão ${versao}` : "Versão para Windows"}
            </p>
            <h2>{pronto ? "Pronto para instalar." : "Instalador em breve."}</h2>
            <p>
              {pronto
                ? "Baixe o Mapas Fácil Setup para Windows 10/11 (x64). Crie sua conta local no primeiro uso; a chave DeepSeek é configurada por você nas Preferências (BYOK)."
                : "A primeira versão pública está em preparação. Esta página atualiza sozinha quando a release `desktop-v*` for publicada no GitHub."}
            </p>
            {pronto ? (
              <a className="button button--primary" href={url!}>
                Baixar para Windows <span aria-hidden="true">↓</span>
              </a>
            ) : (
              <div className="download__pending" role="status">
                <span aria-hidden="true" />
                Preparando a primeira versão
              </div>
            )}
            <small>
              Windows 10/11 ·{" "}
              {tamanho ? `${formatarBytes(tamanho)} · ` : null}
              {sha ? (
                <>
                  SHA-256 <code title={sha}>{sha.slice(0, 12)}…</code>
                  {" · "}
                </>
              ) : null}
              fonte:{" "}
              <a href={DESKTOP_MANIFEST_URL}>GitHub Releases</a>
              {erro && !pronto ? ` · ${erro}` : null}
            </small>
            {notas ? <p className="download__notas">{notas}</p> : null}
            <ul className="download__checklist">
              <li>Conta local (e-mail + senha) — funciona offline, sem site</li>
              <li>DeepSeek — você cola a chave em Preferências (não vem no instalador)</li>
              <li>ArcMap 10.6–10.8 — opcional para `.mxd` completo; PDF nativo funciona sem ele</li>
              <li>SmartScreen (beta sem certificado): Mais informações → Executar mesmo assim</li>
            </ul>
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
