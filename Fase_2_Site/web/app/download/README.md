# Placeholder — página /download

Quando o App Router existir, use:

```tsx
import { carregarDesktopRelease } from "../lib/desktop-release";

export default async function DownloadPage() {
  const m = await carregarDesktopRelease();
  if (!m.instalador) {
    return <p>Instalador ainda não publicado. Aguarde a tag desktop-v*.</p>;
  }
  return (
    <main>
      <h1>Mapas Fácil para Windows</h1>
      <p>Versão {m.versao}</p>
      <a href={m.instalador.url}>Baixar {m.instalador.nome}</a>
      <p>SHA-256: <code>{m.instalador.sha256}</code></p>
      <p>{m.notas}</p>
    </main>
  );
}
```

Contrato: [`../../../shared/releases/README.md`](../../../shared/releases/README.md).
Guia de build: [`../../../Fase_1_Desktop/EMPACOTAMENTO.md`](../../../Fase_1_Desktop/EMPACOTAMENTO.md).
