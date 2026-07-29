#!/usr/bin/env python3
"""Mede a anatomia dos PDFs-modelo da série e grava o padrão em `shared/padrao-imap/`.

Por que existe: o perfil Harmonia **não é um layout só**. Medindo os 20 modelos
do acervo, o quadro do mapa vai de 151 mm a 169 mm de base entre os paisagem —
diferença de 17 mm, quase três vezes a tolerância. Fixar um retângulo médio faz
todo mapa sair um pouco errado; medir cada modelo faz cada mapa sair igual ao
seu modelo.

A saída (`shared/padrao-imap/anatomia_serie.json`) é **dado versionado**: o motor
nativo lê de lá o retângulo de cada mapa da série. Regerar exige o acervo em
`Testes/` (gitignored), então o JSON entra no Git e o acervo não.

    python3 ferramentas/medir_modelos_serie.py
    python3 ferramentas/medir_modelos_serie.py --modelos /caminho/Modelo/Mapas
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "Fase_1_Desktop" / "nucleo"))

MODELOS_PADRAO = RAIZ / "Testes" / "01_analise_04_Julio" / "Modelo" / "Mapas"
DESTINO_PADRAO = RAIZ / "shared" / "padrao-imap" / "anatomia_serie.json"

# PDF-modelo → id do mapa na série (o mesmo id que `analise/serie.py` usa).
MAPAS: dict[str, str] = {
    "Alertas_MAPBIOMAS_2.pdf": "alertas_mapbiomas",
    "Alertas_PRODES_VF.pdf": "alertas_prodes",
    "DLA.pdf": "dla",
    "Unidade_de_Conservação.pdf": "unidades_conservacao",
    "Tipologia.pdf": "tipologia",
    "Terras_Indigenas.pdf": "terras_indigenas",
    "TCR.pdf": "tcr",
    "PEF.pdf": "pef",
    "Embargos_SEMA_SIGA_Poligono.pdf": "embargos_sema_siga",
    "Embargos_IBAMA.pdf": "embargos_ibama",
    "Areas_Cultivaveis_VF.pdf": "areas_cultivaveis",
    "Dinamica_2026_quantitativos.pdf": "dinamica_quantitativos",
    "Dinamica_2026.pdf": "dinamica_2026",
    "Dinamica_2023.pdf": "dinamica_2023",
    "Dinamica_2019.pdf": "dinamica_2019",
    "Dinamica_2017.pdf": "dinamica_2017",
    "Dinamica_2013.pdf": "dinamica_2013",
    "Dinamica_2008_SPOT.pdf": "dinamica_2008_spot",
    "Dinamica_2008_LANDSAT.pdf": "dinamica_2008_landsat",
    "Dinamica_2000.pdf": "dinamica_2000",
}

PT_MM = 72.0 / 25.4


def _linhas(page, *, y_min_mm: float) -> list[dict]:
    """Linhas de texto abaixo de `y_min_mm`, em mm, com tamanho de fonte."""
    import fitz  # noqa: F401 — só para deixar claro de onde vem `page`

    saida: list[dict] = []
    for bloco in page.get_text("dict")["blocks"]:
        for linha in bloco.get("lines", []):
            spans = linha.get("spans", [])
            if not spans:
                continue
            texto = "".join(s["text"] for s in spans).strip()
            if not texto:
                continue
            x0 = min(s["bbox"][0] for s in spans) / PT_MM
            y0 = min(s["bbox"][1] for s in spans) / PT_MM
            x1 = max(s["bbox"][2] for s in spans) / PT_MM
            y1 = max(s["bbox"][3] for s in spans) / PT_MM
            if (y0 + y1) / 2 < y_min_mm:
                continue
            saida.append(
                {
                    "texto": texto,
                    "caixa": [round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)],
                    "pt": round(max(s["size"] for s in spans), 1),
                }
            )
    return sorted(saida, key=lambda t: (t["caixa"][1], t["caixa"][0]))


def _bloco_por_ancora(linhas: list[dict], ancoras: tuple[str, ...], *, folga_x: float) -> dict | None:
    """Caixa do bloco que nasce numa âncora textual (METADADOS/LEGENDA)."""
    inicio = next(
        (t for t in linhas if any(t["texto"].upper().startswith(a) for a in ancoras)), None
    )
    if inicio is None:
        return None
    ax0, ay0, ax1, _ = inicio["caixa"]
    centro_ancora = (ax0 + ax1) / 2
    coluna = [
        t
        for t in linhas
        if t["caixa"][1] >= ay0 - 1
        and (t["caixa"][0] >= ax0 - folga_x)
        and abs((t["caixa"][0] + t["caixa"][2]) / 2 - centro_ancora) <= folga_x * 2.5
    ]
    if not coluna:
        coluna = [inicio]
    # O `pt` do bloco é o dos **itens**, não o do título: na legenda o título
    # "Legenda" tem 9,1 pt e os itens 6,2 pt. Usar o maior fazia o rótulo
    # "Limite municipal" quebrar em duas linhas, coisa que o modelo não faz.
    itens = [t for t in coluna if t is not inicio]
    pts = sorted(t["pt"] for t in itens) or [inicio["pt"]]
    return {
        "caixa": [
            round(min(t["caixa"][0] for t in coluna), 2),
            round(min(t["caixa"][1] for t in coluna), 2),
            round(max(t["caixa"][2] for t in coluna), 2),
            round(max(t["caixa"][3] for t in coluna), 2),
        ],
        "linhas": [t["texto"] for t in coluna],
        "pt": pts[len(pts) // 2],
        "pt_titulo": inicio["pt"],
        "titulo": inicio["texto"],
    }


def medir_modelo(caminho: Path) -> dict:
    import fitz

    from mapasfacil_nucleo.validacao import anatomia as anatomia_mod

    medida = anatomia_mod.medir(caminho)
    doc = fitz.open(caminho)
    try:
        page = doc[0]
        largura = page.rect.width / PT_MM
        altura = page.rect.height / PT_MM
        quadro = medida.get("quadro_mapa") or {}
        corte = float(quadro.get("y1") or altura * 0.82)
        linhas = _linhas(page, y_min_mm=corte)
        metadados = _bloco_por_ancora(linhas, ("METADADOS",), folga_x=18.0)
        legenda = _bloco_por_ancora(linhas, ("LEGENDA",), folga_x=12.0)
    finally:
        doc.close()

    # A caixa vem de `anatomia.medir` — a **mesma** função que depois compara o
    # PDF gerado com o modelo. Medir aqui com heurística própria (coluna mais
    # estreita) deslocava o centro do bloco em ~9 mm, e o mapa saía com o texto
    # centralizado num lugar que o validador considerava errado. Daqui só vêm o
    # tamanho de fonte, o título do bloco e as linhas, que `medir` não devolve.
    if metadados and medida.get("metadados"):
        caixa = medida["metadados"]
        metadados["caixa"] = [caixa["x0"], caixa["y0"], caixa["x1"], caixa["y1"]]
    if legenda and medida.get("legenda"):
        caixa = medida["legenda"]
        legenda["caixa"] = [caixa["x0"], caixa["y0"], caixa["x1"], caixa["y1"]]

    titulo = (medida.get("titulo") or {}).get("caixa_mm")
    return {
        "modelo_pdf": caminho.name,
        "pagina_mm": [round(largura, 1), round(altura, 1)],
        "orientacao": medida["orientacao"],
        "mapa": [quadro.get("x0"), quadro.get("y0"), quadro.get("x1"), quadro.get("y1")]
        if quadro
        else None,
        "titulo": [titulo["x0"], titulo["y0"], titulo["x1"], titulo["y1"]] if titulo else None,
        "titulo_texto": (medida.get("titulo") or {}).get("texto") or "",
        "metadados": metadados,
        "legenda": legenda,
        "rotulos_dms": medida.get("rotulos_dms"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modelos", type=Path, default=MODELOS_PADRAO)
    parser.add_argument("--destino", type=Path, default=DESTINO_PADRAO)
    args = parser.parse_args()

    if not args.modelos.is_dir():
        print(f"Pasta de modelos ausente: {args.modelos}", file=sys.stderr)
        print("Ela é gitignored (dado de proprietário) — copie o acervo antes.", file=sys.stderr)
        return 2

    anatomias: dict[str, dict] = {}
    faltando: list[str] = []
    for pdf_nome, mapa_id in MAPAS.items():
        caminho = args.modelos / pdf_nome
        if not caminho.is_file():
            faltando.append(pdf_nome)
            continue
        anatomias[mapa_id] = medir_modelo(caminho)
        quadro = anatomias[mapa_id]["mapa"]
        print(f"[ok] {mapa_id:<24} {anatomias[mapa_id]['orientacao']:<9} quadro={quadro}")

    if faltando:
        print(f"[aviso] {len(faltando)} modelo(s) ausente(s): {', '.join(faltando)}", file=sys.stderr)

    args.destino.parent.mkdir(parents=True, exist_ok=True)
    args.destino.write_text(
        json.dumps(
            {
                "_descricao": (
                    "Anatomia medida dos PDFs-modelo da série Análise de área (perfil "
                    "Harmonia). Gerado por ferramentas/medir_modelos_serie.py a partir do "
                    "acervo em Testes/ (gitignored). Unidade: milímetros, origem no topo-"
                    "esquerda da página. É o gabarito que o motor nativo segue por mapa."
                ),
                "perfil": "harmonia",
                "mapas": anatomias,
            },
            ensure_ascii=False,
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"\n{len(anatomias)} mapas medidos → {args.destino.relative_to(RAIZ)}")
    return 0 if not faltando else 1


if __name__ == "__main__":
    sys.exit(main())
