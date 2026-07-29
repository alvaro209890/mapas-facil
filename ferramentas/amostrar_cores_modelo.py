#!/usr/bin/env python3
"""Amostra as cores oficiais direto dos PDFs-modelo, item de legenda por item.

Transcrever cor de legenda de olho erra — e errou: `ac` estava `#FF00FF` no
código e é `#C500FF` no modelo; `auas` estava `#FF8000` e é `#E59800`. Este
script tira a opinião do caminho: rasteriza o modelo a 300 dpi, acha o rótulo de
cada item da legenda e devolve a cor dominante do quadradinho à esquerda dele.

O resultado alimenta `motores/estilos.py` — que é conferido por
`nucleo/tests/test_estilos_modelo.py` para não regredir.

    python3 ferramentas/amostrar_cores_modelo.py
    python3 ferramentas/amostrar_cores_modelo.py --pdf Tipologia.pdf --json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MODELOS_PADRAO = RAIZ / "Testes" / "01_analise_04_Julio" / "Modelo" / "Mapas"

PT_MM = 72.0 / 25.4
DPI = 300
LARGURA_AMOSTRA_MM = 24.0
"""Faixa varrida à esquerda do rótulo — cabe o maior quadradinho do acervo."""

FRACAO_RODAPE = 0.82
"""Só a faixa inferior tem legenda; acima disso é mapa."""

IGNORAR = {"METADADOS", "METADADOS IMAGEM", "LEGENDA", "MT", "VILA RICA", "LEGENDA:"}


def _quase_branco(cor: tuple[int, int, int]) -> bool:
    return all(canal > 245 for canal in cor)


def amostrar(caminho: Path) -> list[dict]:
    import fitz
    import numpy as np

    doc = fitz.open(caminho)
    try:
        page = doc[0]
        pix = page.get_pixmap(dpi=DPI)
        arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        arr = arr[:, :, :3]
        escala = DPI / 72.0
        altura_mm = page.rect.height / PT_MM

        itens: list[dict] = []
        for bloco in page.get_text("dict")["blocks"]:
            for linha in bloco.get("lines", []):
                spans = linha.get("spans", [])
                if not spans:
                    continue
                texto = "".join(s["text"] for s in spans).strip()
                if not texto or texto.upper() in IGNORAR or "°" in texto:
                    continue
                if ":" in texto and not texto.lower().startswith("tipologia"):
                    continue  # linha de metadado ("Datum: …"), não item de legenda
                x0 = min(s["bbox"][0] for s in spans)
                y0 = min(s["bbox"][1] for s in spans)
                y1 = max(s["bbox"][3] for s in spans)
                if y0 / PT_MM < altura_mm * FRACAO_RODAPE:
                    continue

                topo = int(y0 * escala)
                base = max(topo + 1, int(y1 * escala))
                esquerda = max(0, int((x0 - LARGURA_AMOSTRA_MM * PT_MM / 72.0 * 72.0) * escala))
                esquerda = max(0, int((x0 - LARGURA_AMOSTRA_MM * PT_MM) * escala))
                direita = max(esquerda + 1, int((x0 - 1.2 * PT_MM) * escala))
                faixa = arr[topo:base, esquerda:direita].reshape(-1, 3)
                if not len(faixa):
                    continue
                contagem = Counter(
                    tuple(int(v) for v in px) for px in faixa if not _quase_branco(tuple(px))
                )
                dominantes = contagem.most_common(3)
                if not dominantes:
                    continue
                itens.append(
                    {
                        "rotulo": texto,
                        "cores": [
                            {
                                "hex": "#%02X%02X%02X" % cor,
                                "cobertura_pct": round(100 * n / len(faixa), 1),
                            }
                            for cor, n in dominantes
                        ],
                    }
                )
        return itens
    finally:
        doc.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modelos", type=Path, default=MODELOS_PADRAO)
    parser.add_argument("--pdf", help="amostra só este modelo (nome do arquivo)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not args.modelos.is_dir():
        print(f"Pasta de modelos ausente: {args.modelos}", file=sys.stderr)
        return 2

    alvos = (
        [args.modelos / args.pdf]
        if args.pdf
        else [p for p in sorted(args.modelos.glob("*.pdf")) if p.name != "Mapas_unidos.pdf"]
    )
    saida = {}
    for caminho in alvos:
        if not caminho.is_file():
            print(f"[FALHA] {caminho.name} não existe", file=sys.stderr)
            return 2
        itens = amostrar(caminho)
        saida[caminho.name] = itens
        if not args.json:
            print(f"### {caminho.name}")
            for item in itens:
                cores = " ".join(f"{c['hex']}({c['cobertura_pct']}%)" for c in item["cores"][:2])
                print(f"   {item['rotulo'][:46]:<48} {cores}")

    if args.json:
        print(json.dumps(saida, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
