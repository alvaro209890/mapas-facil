# fontes/

Tipografia embarcada do app (F1-16 §Tipografia, decisão D15). **Nenhuma requisição a
CDN em runtime** — o app abre offline e não vaza navegação do usuário.

| Arquivo | Família | Tipo | Papel |
|---|---|---|---|
| `space-grotesk-latin*.woff2` | Space Grotesk | variável 300–700 | display / marca |
| `ibm-plex-sans-latin*.woff2` | IBM Plex Sans | variável 100–700 | interface / corpo |
| `ibm-plex-mono-{400,500}-latin*.woff2` | IBM Plex Mono | estática | hectares, coordenadas, códigos, JSON |

Subsets `latin` e `latin-ext` (pt-BR usa os dois). Os `@font-face` estão em
[`fontes.css`](fontes.css), com `font-display: block` e `unicode-range` por subset.

Licenças: ambas SIL Open Font License 1.1 — [`LICENSE-SpaceGrotesk.txt`](LICENSE-SpaceGrotesk.txt),
[`LICENSE-IBMPlex.txt`](LICENSE-IBMPlex.txt).

Origem dos binários: `fonts.googleapis.com/css2` (arquivos servidos por
`fonts.gstatic.com`), baixados uma vez e versionados aqui. Para atualizar, baixe de
novo e confira que as famílias variáveis continuam com **um arquivo por subset** —
o mesmo binário serve todos os pesos.
