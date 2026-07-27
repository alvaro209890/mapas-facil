/**
 * Cliente do manifesto de download do desktop (GitHub Releases).
 * Cole no site (Next.js /download) — ver shared/releases/README.md.
 */

export const DESKTOP_MANIFEST_URL =
  "https://github.com/alvaro209890/mapas-facil/releases/latest/download/download-manifest.json";

export type DesktopInstalador = {
  nome: string;
  url: string;
  sha256: string;
  tamanho_bytes: number;
};

export type DesktopDownloadManifest = {
  schema: "mapasfacil.download_manifest/1";
  canal: "stable" | "beta";
  versao: string;
  tag: string;
  publicado_em: string;
  instalador: DesktopInstalador | null;
  notas?: string;
};

export async function carregarDesktopRelease(
  url: string = DESKTOP_MANIFEST_URL,
): Promise<DesktopDownloadManifest> {
  const res = await fetch(url, {
    headers: { Accept: "application/json" },
    // Next.js: revalidate a cada 5 min se usado em Server Component
    next: { revalidate: 300 },
  } as RequestInit);
  if (!res.ok) {
    throw new Error(`Falha ao ler manifesto do desktop (${res.status})`);
  }
  return (await res.json()) as DesktopDownloadManifest;
}
