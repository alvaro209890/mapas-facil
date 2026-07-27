# F2-04 — Frontend do site (landing e download)

## Objetivo

Especificar o site Next.js em `Fase_2_Site/web/`: páginas públicas de marketing e distribuição
do instalador, com **hero cinematográfico** (mapa sendo gerado em motion/vídeo). Sem chat, sem
login, sem MapSpec funcional (D21).

**Código:** implementado em 2026-07-27 após pedido explícito do dono.

## Estado atual vs alvo

| Item | Atual | Alvo |
|---|---|---|
| Código | Next.js App Router + TypeScript em `web/` | implementado |
| Páginas | home, requisitos, download e contato | implementadas |
| Auth / chat / mapa funcional | ausentes | **fora da v1**, como definido |
| Motion / vídeo de mapa | fallback procedural CSS + folha fictícia | implementado; vídeo real continua opcional |

## Dependências

| Precisa de | Estado |
|---|---|
| [F2-00](00-visao-e-escopo.md) / [F2-01](01-arquitetura.md) | reescritos |
| Instalador M10 para URL real | opcional — UI “em breve” |
| Gravação do app (vídeo demo) | opcional — v1 pode ser CSS/SVG; slot para WebM/MP4 |
| Design system do Electron | **não** obrigatório; site tem visual próprio de marketing |

## Stack (quando for implementar)

| Componente | Escolha | Por quê |
|---|---|---|
| Framework | Next.js (App Router), TypeScript strict | SSR/estático |
| Estilo | CSS próprio + tokens (sem shadcn dashboard) | fora do genérico |
| Motion | CSS + JS leve; **vídeo** em `public/` quando existir | demo estilo short de produto |
| Deploy | [F2-06](06-deploy-tunnel-neste-pc.md) | PC servidor |

## Estrutura de pastas

```
web/
├── app/
│   ├── layout.tsx
│   ├── page.tsx                 # landing + hero motion
│   ├── requisitos/page.tsx
│   ├── download/page.tsx
│   └── contato/page.tsx
├── components/
│   ├── CenaMapa.tsx             # loop CSS/SVG ou <video>
│   ├── SiteHeader.tsx
│   ├── SiteFooter.tsx
│   └── CtaDownload.tsx
├── public/
│   ├── demo-mapa.webm          # opcional — gravação real do app
│   └── demo-mapa.mp4           # fallback opcional
├── package.json
└── README.md
```

Sem `/login`, `/signup`, `/chat`.

---

## Direção visual e motion (vinculante)

O site **não** é brochure estático. A home deve parecer um **demo de produto cinematográfico** —
camadas se montando, tela viva, morph entre estados. Referência de *sensação* (não de layout a
copiar): [short de UI em motion](https://youtube.com/shorts/yVXsS59LYJ0).

### Composição do hero (primeira viewport — uma só)

1. Marca **Mapas Fácil** em escala hero (não só no nav).
2. Uma headline + uma frase curta.
3. Um grupo de CTA (download + requisitos).
4. **Âncora visual full-bleed:** cena da **geração de um mapa** (folha IMAP, camadas, saída
   `.mxd`/PDF) — não foto stock, não dashboard, não cards.

Sem badges flutuantes, chips de promo ou stats strips em cima da cena.

### Storyboard do loop (~12–20 s)

Com `prefers-reduced-motion: reduce` → frame estático do mapa **pronto**, sem loop.

| Tempo (aprox.) | O que aparece |
|---|---|
| 0–2 s | Prompt / pasta (“faz a Dinâmica desta pasta”) |
| 2–6 s | Camadas encaixando (base → ATP → AVN → AC → município / minimapa) |
| 6–10 s | Folha IMAP: escala, rótulos, seta-norte, metadados |
| 10–14 s | Artefatos `.mxd` + PDF “saindo” da cena |
| 14–20 s | Crossfade / morph de volta ao início |

### Duas camadas de mídia (prioridade)

1. **Vídeo real** (`public/demo-mapa.webm` ou `.mp4`): gravação do app gerando mapa — `autoplay`
   `muted` `loop` `playsInline`. Preferido quando o arquivo existir.
2. **Fallback procedural** (CSS + DOM + raster demonstrativo fictício): mesma narrativa do
   storyboard, sem depender de vídeo. Implementado na v1 até haver gravação aprovada.

A UI detecta o arquivo de vídeo; se ausente, usa o fallback. Nunca quebrar a home sem mídia.

### Tom visual (fora do genérico)

| Fazer | Evitar |
|---|---|
| Paleta terra/floresta + papel de mapa (tinta profunda, ocre, cream de folha) | Roxo-indigo de IA; cream+terracota editorial genérico |
| Tipografia expressiva (`next/font`) | Inter / Roboto / Arial / system stack |
| Motion com presença (camadas, parallax leve, morph de folha) | Spinner, Lottie “rocket”, glow neon |
| Full-bleed da cena de mapa | Cards no hero, pill clusters, métricas |

Tokens e tipografia vivem em `web/` (não precisa espelhar o Electron).

### Aceite de motion (quando implementar)

- [x] ≥3 movimentos intencionais na home (marca, ciclo de camadas, CTA e artefatos)
- [x] `prefers-reduced-motion` → estado final estático
- [x] Slot de vídeo documentado; fallback procedural funciona sem o arquivo
- [x] Sem login, sem chat, sem mapa “funcional” — só storytelling de marketing

---

## Conteúdo por página

### Home (`/`)

Hero conforme acima. Mensagem: o produto é um **app Windows**; o site conta a história e
distribui o instalador.

### Requisitos (`/requisitos`)

- Windows 10/11
- Conta criada **no app** (e-mail + senha local) — não no site
- ArcMap opcional (com: `.mxd` via ArcPy; sem: patch + PDF nativo)
- Chave DeepSeek do usuário (BYOK) no Credential Manager — nunca no site

### Download (`/download`)

| Estado | UI |
|---|---|
| `NEXT_PUBLIC_DOWNLOAD_URL` definida | botão “Baixar para Windows” |
| URL vazia | “Instalador em breve” (sem 404 mentiroso) |

Não versionar `.exe` no git.

### Contato (`/contato`)

`NEXT_PUBLIC_CONTACT_EMAIL` / `NEXT_PUBLIC_REPO_URL`. Mailto basta na v1 — sem form com banco.

## Contratos

- Variáveis: [F2-01](01-arquitetura.md#variáveis-site).
- Nenhuma API de mapas ou auth.
- Headers de segurança: [F2-06](06-deploy-tunnel-neste-pc.md).

## Tarefas agentáveis

- [x] Scaffold Next.js/vinext em `Fase_2_Site/web/`
- [x] Landing + `CenaMapa` (fallback CSS/DOM com mapa inteiramente fictício)
- [x] Páginas requisitos / download / contato
- [x] `.env.example` + README (`npm run dev` / `npm run build`)
- [ ] (Opcional) gravar `demo-mapa.webm` a partir do app e colocar em `public/`

## Critérios de aceite

- [x] `npm run dev` sobe a home e as quatro rotas respondem HTTP 200
- [x] Hero com motion procedural + reduced-motion
- [x] Sem rotas `/login`, `/signup`, `/chat`
- [x] Download sem URL → “Instalador em breve”
- [x] Nenhum segredo versionado; mapa e polígono da demonstração são fictícios

## Fora de escopo

- Implementar agora sem pedido explícito
- App autenticado, chat web, preview MapSpec funcional
- Backend FastAPI

## Anti-padrões

| Não faça | Por quê |
|---|---|
| Começar código antes do ok do dono | pedido explícito: só plano |
| Copiar layout de chat do legado | D21 |
| Login no site | F1-14 no desktop |
| Hero só texto, sem cena de mapa | motion é obrigatório |
| Roxo glow / Inter / cards de stats no 1º viewport | genérico de IA |
| Embutir `.exe` no repositório | release M10 |

## Relação com o legado

Textos antigos (chat + agente WS + painel MapSpec) são **obsoletos**.
