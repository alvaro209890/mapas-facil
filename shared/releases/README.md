# releases/ — contrato do instalador desktop para o site

Cada tag `desktop-vX.Y.Z` no GitHub gera (via `.github/workflows/release-desktop.yml`):

| Artefato | Uso |
|---|---|
| `MapasFacil-Setup-X.Y.Z.exe` | instalador NSIS (download público) |
| `latest.yml` + `.blockmap` | auto-update (`electron-updater`) |
| `sha256.txt` | verificação manual / suporte |
| `download-manifest.json` | **fonte da página `/download` do site** |

## URL estável para o site

Após a primeira release publicada:

```
https://github.com/alvaro209890/mapas-facil/releases/latest/download/download-manifest.json
```

(Use a release marcada como *latest* no canal `stable`. Tags `desktop-v*-beta*` devem
criar release com `prerelease: true` para não virar latest.)

Schema: [`download-manifest.schema.json`](download-manifest.schema.json).

## Exemplo de consumo (front)

```ts
type Manifest = {
  versao: string;
  instalador: { url: string; sha256: string; nome: string; tamanho_bytes: number } | null;
  notas?: string;
};

const MANIFEST_URL =
  "https://github.com/alvaro209890/mapas-facil/releases/latest/download/download-manifest.json";

export async function carregarDesktopRelease(): Promise<Manifest> {
  const res = await fetch(MANIFEST_URL, { next: { revalidate: 300 } });
  if (!res.ok) throw new Error(`manifesto ${res.status}`);
  return res.json() as Promise<Manifest>;
}
```

Na UI: botão primário → `instalador.url`; texto secundário com `sha256` truncado + link para
`sha256.txt`. Instrução SmartScreen (beta sem Authenticode) nas `notas`.
