#!/usr/bin/env python3
"""Servidor das análises publicadas — entrega os PDFs prontos ao cliente.

Roda neste PC, escuta só em `127.0.0.1`, e quem publica na internet é o tunnel
do Cloudflare. Serve **apenas** o que foi publicado de propósito por
`ferramentas/publicar_analise.py`; nenhuma outra pasta do disco é alcançável.

O que ele deliberadamente **não** faz:

- não lista nada fora da pasta de publicação;
- não aceita upload, não executa job, não abre rota de escrita — é só leitura;
- não segue link simbólico para fora da raiz (o caminho é resolvido e conferido);
- não deixa ser indexado (`X-Robots-Tag: noindex` + `robots.txt`).

⚠️ **Sem senha, por decisão do dono do sistema (2026-07-29).** Quem tiver a URL
vê os mapas — e mapa de análise traz número do CAR, nome da propriedade e a
geometria do imóvel do cliente. Para fechar depois, é uma política do Cloudflare
Access no hostname; nada muda aqui. Ver `docs/analise-entrega-cloudflare.md`.

    python3 Fase_2_Site/deploy/servidor_analises.py --raiz ~/MapasFacil_Publicado
"""

from __future__ import annotations

import argparse
import html
import json
import os
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORTA_PADRAO = 3081
RAIZ_PADRAO = Path.home() / "MapasFacil_Publicado"
NOME_MANIFESTO = "analise.json"

ESTILO = """
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body { margin: 0; font: 16px/1.55 system-ui, -apple-system, "Segoe UI", sans-serif;
       background: #0f1115; color: #e6e8ec; }
main { max-width: 62rem; margin: 0 auto; padding: 2.5rem 1.25rem 4rem; }
h1 { font-size: 1.6rem; margin: 0 0 .3rem; letter-spacing: -.01em; }
p.sub { margin: 0 0 2rem; color: #99a1b3; }
.cartao { display: block; padding: 1rem 1.15rem; margin: 0 0 .7rem; border-radius: 12px;
          background: #171a21; border: 1px solid #262b36; text-decoration: none; color: inherit; }
.cartao:hover { border-color: #3d6fe0; background: #1b1f28; }
.cartao b { display: block; font-size: 1.05rem; }
.cartao span { color: #99a1b3; font-size: .87rem; }
ul { list-style: none; padding: 0; margin: 1.2rem 0 0; }
li { padding: .55rem .2rem; border-bottom: 1px solid #232833; display: flex;
     justify-content: space-between; gap: 1rem; }
li a { color: #8fb4ff; text-decoration: none; }
li a:hover { text-decoration: underline; }
.voltar { display: inline-block; margin-bottom: 1.4rem; color: #8fb4ff; text-decoration: none; }
.destaque { border-color: #3d6fe0; }
footer { margin-top: 3rem; color: #6b7386; font-size: .82rem; }
@media (prefers-color-scheme: light) {
  body { background: #f6f7f9; color: #14171f; }
  .cartao { background: #fff; border-color: #e2e5ea; }
  .cartao:hover { background: #f0f4ff; }
  li { border-bottom-color: #e6e9ee; }
}
"""


def _tamanho(bytes_: int) -> str:
    for unidade in ("B", "KB", "MB", "GB"):
        if bytes_ < 1024 or unidade == "GB":
            return f"{bytes_:.0f} {unidade}" if unidade == "B" else f"{bytes_:.1f} {unidade}"
        bytes_ /= 1024
    return f"{bytes_:.1f} GB"


def _manifesto(pasta: Path) -> dict:
    caminho = pasta / NOME_MANIFESTO
    if not caminho.is_file():
        return {}
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


class Handler(SimpleHTTPRequestHandler):
    """Só leitura, só dentro da raiz, sem indexação."""

    raiz: Path

    def end_headers(self) -> None:  # noqa: N802 — API do http.server
        self.send_header("X-Robots-Tag", "noindex, nofollow, noarchive")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, formato: str, *args) -> None:  # noqa: N802
        agora = datetime.now(timezone.utc).isoformat(timespec="seconds")
        print(f"{agora} {self.address_string()} {formato % args}", flush=True)

    def do_GET(self) -> None:  # noqa: N802
        caminho = self.path.split("?", 1)[0].split("#", 1)[0]
        if caminho == "/robots.txt":
            corpo = b"User-agent: *\nDisallow: /\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)
            return
        if caminho in ("/", "/index.html"):
            self._pagina(self._html_indice())
            return
        if caminho.rstrip("/").count("/") == 1 and not caminho.endswith(".pdf"):
            slug = caminho.strip("/")
            pasta = self._resolver(slug)
            if pasta is not None and pasta.is_dir():
                self._pagina(self._html_analise(slug, pasta))
                return
        super().do_GET()

    # -- resolução segura ------------------------------------------------- #

    def _resolver(self, relativo: str) -> Path | None:
        """Caminho dentro da raiz, ou `None` — barra `..` e link para fora."""
        try:
            alvo = (self.raiz / relativo).resolve()
        except OSError:
            return None
        raiz = self.raiz.resolve()
        return alvo if alvo == raiz or raiz in alvo.parents else None

    # -- páginas ----------------------------------------------------------- #

    def _pagina(self, corpo_html: str) -> None:
        corpo = corpo_html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def _moldura(self, titulo: str, miolo: str) -> str:
        return (
            "<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            "<meta name='robots' content='noindex, nofollow'>"
            f"<title>{html.escape(titulo)}</title><style>{ESTILO}</style></head>"
            f"<body><main>{miolo}"
            "<footer>Mapas Fácil · IMAP Engenharia e Soluções</footer>"
            "</main></body></html>"
        )

    def _html_indice(self) -> str:
        pastas = sorted(
            (p for p in self.raiz.iterdir() if p.is_dir() and not p.name.startswith(".")),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not pastas:
            miolo = (
                "<h1>Análises publicadas</h1>"
                "<p class='sub'>Nenhuma análise publicada ainda.</p>"
            )
            return self._moldura("Mapas Fácil — análises", miolo)

        cartoes = []
        for pasta in pastas:
            meta = _manifesto(pasta)
            nome = html.escape(str(meta.get("imovel") or pasta.name))
            municipio = html.escape(str(meta.get("municipio") or ""))
            quando = html.escape(str(meta.get("publicado_em") or ""))[:10]
            n_pdf = len(list(pasta.glob("*.pdf")))
            detalhe = " · ".join(x for x in (municipio, f"{n_pdf} mapas", quando) if x)
            cartoes.append(
                f"<a class='cartao' href='/{html.escape(pasta.name)}/'>"
                f"<b>{nome}</b><span>{detalhe}</span></a>"
            )
        miolo = (
            "<h1>Análises publicadas</h1>"
            "<p class='sub'>Clique para abrir os mapas de cada imóvel.</p>"
            + "".join(cartoes)
        )
        return self._moldura("Mapas Fácil — análises", miolo)

    def _html_analise(self, slug: str, pasta: Path) -> str:
        meta = _manifesto(pasta)
        nome = html.escape(str(meta.get("imovel") or slug))
        linhas = []
        compilado = pasta / "Analise_de_area.pdf"
        if compilado.is_file():
            linhas.append(
                f"<li class='destaque'><a href='/{html.escape(slug)}/{compilado.name}'>"
                "Série completa (PDF único)</a>"
                f"<span>{_tamanho(compilado.stat().st_size)}</span></li>"
            )
        for pdf in sorted(pasta.glob("*.pdf")):
            if pdf.name == compilado.name:
                continue
            linhas.append(
                f"<li><a href='/{html.escape(slug)}/{html.escape(pdf.name)}'>"
                f"{html.escape(pdf.stem.replace('_', ' '))}</a>"
                f"<span>{_tamanho(pdf.stat().st_size)}</span></li>"
            )
        sub = " · ".join(
            x
            for x in (
                html.escape(str(meta.get("municipio") or "")),
                html.escape(str(meta.get("car") or "")),
                f"{len(linhas)} arquivos",
            )
            if x
        )
        miolo = (
            "<a class='voltar' href='/'>← todas as análises</a>"
            f"<h1>{nome}</h1><p class='sub'>{sub}</p><ul>{''.join(linhas)}</ul>"
        )
        return self._moldura(f"{nome} — Mapas Fácil", miolo)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raiz", type=Path, default=RAIZ_PADRAO)
    parser.add_argument("--porta", type=int, default=PORTA_PADRAO)
    parser.add_argument("--host", default="127.0.0.1", help="nunca 0.0.0.0: quem expõe é o tunnel")
    args = parser.parse_args()

    raiz = args.raiz.expanduser().resolve()
    raiz.mkdir(parents=True, exist_ok=True)
    os.chdir(raiz)

    Handler.raiz = raiz
    servidor = ThreadingHTTPServer((args.host, args.porta), partial(Handler, directory=str(raiz)))
    print(f"servindo {raiz} em http://{args.host}:{args.porta}", flush=True)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
