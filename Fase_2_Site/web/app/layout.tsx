import type { Metadata } from "next";
import { headers } from "next/headers";
import "./globals.css";

const description =
  "Mapas Fácil transforma uma pasta de análise em mapas técnicos padronizados, com entrega em MXD e PDF no Windows.";

export async function generateMetadata(): Promise<Metadata> {
  const requestHeaders = await headers();
  const host =
    requestHeaders.get("x-forwarded-host") ?? requestHeaders.get("host");
  const protocol =
    requestHeaders.get("x-forwarded-proto") ??
    (host?.includes("localhost") ? "http" : "https");
  const metadataBase = host
    ? new URL(`${protocol}://${host}`)
    : new URL("http://localhost:3000");

  return {
    metadataBase,
    title: {
      default: "Mapas Fácil — do pedido ao mapa pronto",
      template: "%s — Mapas Fácil",
    },
    description,
    applicationName: "Mapas Fácil",
    openGraph: {
      type: "website",
      locale: "pt_BR",
      siteName: "Mapas Fácil",
      title: "Mapas Fácil — do pedido ao mapa pronto",
      description,
      images: [{ url: "/og.png", width: 1200, height: 630 }],
    },
    twitter: {
      card: "summary_large_image",
      title: "Mapas Fácil — do pedido ao mapa pronto",
      description,
      images: ["/og.png"],
    },
  };
}

export const viewport = {
  themeColor: "#07110e",
  colorScheme: "dark",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}
