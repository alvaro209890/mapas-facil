#!/usr/bin/env python3
"""Publica uma análise já gerada para o cliente baixar.

Copia os PDFs de `<projeto>/Mapas/` para a pasta que o servidor de análises
serve, junto de um manifesto com o nome do imóvel, município e CAR. Nada além de
PDF é copiado — o `.shp` do cliente, o relatório interno e o cache ficam onde
estão.

    python3 ferramentas/publicar_analise.py ~/Documentos/MapasFacil_Aruana
    python3 ferramentas/publicar_analise.py ~/.../projeto --slug aruana-i
    python3 ferramentas/publicar_analise.py --listar
    python3 ferramentas/publicar_analise.py --remover aruana-i

⚠️ Publicar torna os mapas acessíveis por link, **sem senha** (decisão de
2026-07-29). Mapa de análise mostra número do CAR, nome da propriedade e a
geometria do imóvel. Publique só o que o cliente pode receber, e use
`--remover` quando não precisar mais. Ver `docs/analise-entrega-cloudflare.md`.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

RAIZ_PUBLICACAO = Path.home() / "MapasFacil_Publicado"
NOME_MANIFESTO = "analise.json"
RELATORIO = "analise_de_area_relatorio.json"


def _slug(texto: str) -> str:
    normalizado = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    limpo = re.sub(r"[^a-zA-Z0-9]+", "-", normalizado).strip("-").lower()
    return limpo or "analise"


def _identidade(pasta_mapas: Path) -> dict:
    """Nome, município e CAR saem do relatório da própria execução."""
    caminho = pasta_mapas / RELATORIO
    if not caminho.is_file():
        return {}
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    imovel = dados.get("imovel") or {}
    municipio = (imovel.get("municipio") or {}).get("nome") or ""
    resumo = dados.get("resumo") or {}
    return {
        "imovel": imovel.get("nome"),
        "municipio": municipio,
        "car": imovel.get("car_estadual"),
        "mapas_gerados": resumo.get("gerados"),
        "anatomia_verde": resumo.get("anatomia_verde"),
    }


def publicar(projeto: Path, *, raiz: Path, slug: str | None) -> Path:
    pasta_mapas = projeto / "Mapas"
    if not pasta_mapas.is_dir():
        raise SystemExit(f"Sem pasta Mapas/ em {projeto} — gere a análise antes.")
    pdfs = sorted(pasta_mapas.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"Nenhum PDF em {pasta_mapas}.")

    meta = _identidade(pasta_mapas)
    destino = raiz / (slug or _slug(str(meta.get("imovel") or projeto.name)))
    destino.mkdir(parents=True, exist_ok=True)

    # Limpa PDFs antigos do destino: republicar não pode deixar mapa velho para trás.
    for antigo in destino.glob("*.pdf"):
        antigo.unlink()
    for pdf in pdfs:
        shutil.copy2(pdf, destino / pdf.name)

    manifesto = {
        **meta,
        "slug": destino.name,
        "arquivos": len(pdfs),
        "publicado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "origem": str(projeto),
    }
    (destino / NOME_MANIFESTO).write_text(
        json.dumps(manifesto, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return destino


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("projeto", nargs="?", type=Path, help="pasta do projeto com Mapas/ dentro")
    parser.add_argument("--slug", help="nome na URL (padrão: derivado do nome do imóvel)")
    parser.add_argument("--raiz", type=Path, default=RAIZ_PUBLICACAO)
    parser.add_argument("--listar", action="store_true")
    parser.add_argument("--remover", metavar="SLUG")
    args = parser.parse_args()

    raiz = args.raiz.expanduser().resolve()
    raiz.mkdir(parents=True, exist_ok=True)

    if args.remover:
        alvo = (raiz / args.remover).resolve()
        if raiz not in alvo.parents:
            raise SystemExit("Slug inválido.")
        if not alvo.is_dir():
            raise SystemExit(f"Não publicado: {args.remover}")
        shutil.rmtree(alvo)
        print(f"removido: {args.remover}")
        return 0

    if args.listar or not args.projeto:
        pastas = sorted(p for p in raiz.iterdir() if p.is_dir())
        if not pastas:
            print(f"nenhuma análise publicada em {raiz}")
            return 0
        for pasta in pastas:
            manifesto = pasta / NOME_MANIFESTO
            meta = json.loads(manifesto.read_text(encoding="utf-8")) if manifesto.is_file() else {}
            print(
                f"{pasta.name:<28} {meta.get('imovel') or '?':<28} "
                f"{meta.get('arquivos', len(list(pasta.glob('*.pdf'))))} PDFs  "
                f"{str(meta.get('publicado_em') or '')[:10]}"
            )
        return 0

    destino = publicar(args.projeto.expanduser().resolve(), raiz=raiz, slug=args.slug)
    print(f"publicado em {destino}")
    print(f"URL: https://analises.cursar.space/{destino.name}/")
    print("Sem senha: quem tiver o link vê os mapas. Use --remover quando não precisar mais.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
