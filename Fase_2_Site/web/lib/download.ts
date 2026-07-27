/**
 * Contrato do manifesto publicado na release desktop (M10).
 * Fonte canônica: releases/latest/download/download-manifest.json
 */
export type DownloadManifest = {
  schema: string;
  canal: string;
  versao: string;
  tag: string;
  publicado_em?: string;
  requisitos?: string[];
  instalador: {
    nome: string;
    url: string;
    sha256: string;
    tamanho_bytes: number;
  };
  notas?: string;
};

export type DownloadInfo = {
  url: string;
  versao: string;
  nome: string;
  sha256: string;
  tamanhoBytes: number;
  notas?: string;
  fonte: "env" | "manifest" | "fallback";
};

/** Manifesto da release estável no GitHub (público). */
export const DEFAULT_MANIFEST_URL =
  "https://github.com/alvaro209890/mapas-facil/releases/latest/download/download-manifest.json";

/**
 * Fallback embutido alinhado a desktop-v0.5.0 — usado se o fetch do
 * manifesto falhar (rede/GitHub). Atualizar junto com a próxima release.
 */
export const FALLBACK_DOWNLOAD: DownloadInfo = {
  url: "https://github.com/alvaro209890/mapas-facil/releases/download/desktop-v0.5.1/MapasFacil-Setup-0.5.1.exe",
  versao: "0.5.1",
  nome: "MapasFacil-Setup-0.5.1.exe",
  sha256: "b9fa04029c6181ac6154618720f50b1906df4b96f5fc15c249d9db8dea0f55e9",
  tamanhoBytes: 139250070,
  notas:
    "Corrige o app não abrir, o login pedido duas vezes e as camadas WMS/WMTS que exigiam configuração manual. Sem Authenticode — no SmartScreen use Mais informações → Executar mesmo assim.",
  fonte: "fallback",
};

export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return "";
  const mb = bytes / (1024 * 1024);
  return `${mb.toFixed(1).replace(".", ",")} MB`;
}

function fromManifest(
  manifest: DownloadManifest,
  fonte: DownloadInfo["fonte"],
): DownloadInfo | null {
  const instalador = manifest.instalador;
  if (!instalador?.url?.trim()) return null;
  return {
    url: instalador.url.trim(),
    versao: manifest.versao || "?",
    nome: instalador.nome || "MapasFacil-Setup.exe",
    sha256: instalador.sha256 || "",
    tamanhoBytes: instalador.tamanho_bytes || 0,
    notas: manifest.notas,
    fonte,
  };
}

async function fetchManifest(url: string): Promise<DownloadManifest | null> {
  try {
    const res = await fetch(url, {
      headers: { Accept: "application/json" },
      // Cache curto no Node; vinext/Next podem ignorar — ok.
      next: { revalidate: 300 },
    } as RequestInit);
    if (!res.ok) return null;
    return (await res.json()) as DownloadManifest;
  } catch {
    return null;
  }
}

/**
 * Resolve o instalador na ordem:
 * 1. NEXT_PUBLIC_DOWNLOAD_URL (override manual)
 * 2. Manifesto (env ou DEFAULT_MANIFEST_URL)
 * 3. FALLBACK_DOWNLOAD (desktop-v0.5.0)
 */
export async function resolveDownloadInfo(): Promise<DownloadInfo> {
  const direct = process.env.NEXT_PUBLIC_DOWNLOAD_URL?.trim();
  if (direct) {
    return {
      url: direct,
      versao: process.env.NEXT_PUBLIC_DOWNLOAD_VERSION?.trim() || FALLBACK_DOWNLOAD.versao,
      nome: process.env.NEXT_PUBLIC_DOWNLOAD_NAME?.trim() || FALLBACK_DOWNLOAD.nome,
      sha256: process.env.NEXT_PUBLIC_DOWNLOAD_SHA256?.trim() || FALLBACK_DOWNLOAD.sha256,
      tamanhoBytes: Number(process.env.NEXT_PUBLIC_DOWNLOAD_BYTES) || FALLBACK_DOWNLOAD.tamanhoBytes,
      notas: FALLBACK_DOWNLOAD.notas,
      fonte: "env",
    };
  }

  const manifestUrl =
    process.env.NEXT_PUBLIC_DOWNLOAD_MANIFEST_URL?.trim() || DEFAULT_MANIFEST_URL;
  const manifest = await fetchManifest(manifestUrl);
  if (manifest) {
    const info = fromManifest(manifest, "manifest");
    if (info) return info;
  }

  return FALLBACK_DOWNLOAD;
}
