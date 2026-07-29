"""Medição da anatomia de um PDF de mapa, em milímetros (F1-09).

Por que existe: o diff raster só é honesto quando o **dado** é o mesmo. Contra
os PDFs-modelo do acervo — outro imóvel, outra imagem, outro ano — comparar
pixel a pixel não diz nada. O que dá para comparar, e é exatamente o que o
padrão Harmonia define, é a **anatomia**: onde está o quadro do mapa, a caixa
de título, o bloco de metadados, a legenda, quantos rótulos DMS existem em cada
borda.

Duas fontes de medida, ambas sem ArcGIS:

- **texto** — `fitz` devolve o bbox de cada palavra em pontos, que viram mm;
- **traço** — a moldura preta do quadro é detectada no raster por linhas
  escuras longas.

Serve para o validador de conformidade e para a regressão visual do CI.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import fitz
import numpy as np

from mapasfacil_nucleo.validacao.comparar_pdf import rasterizar_pdf

PT_POR_MM = 72.0 / 25.4
DPI_TRACO = 100
LIMIAR_ESCURO = 110
"""RGB abaixo disto conta como traço preto da moldura."""

FRACAO_LINHA = 0.55
"""Fração da largura/altura que uma linha precisa cobrir para ser moldura."""


def _pt_para_mm(valor: float) -> float:
    return valor / PT_POR_MM


def _px_para_mm(valor: float, dpi: int) -> float:
    return valor / dpi * 25.4


def _caixa_mm(bbox: Any) -> dict[str, float]:
    return {
        "x0": round(_pt_para_mm(bbox[0]), 2),
        "y0": round(_pt_para_mm(bbox[1]), 2),
        "x1": round(_pt_para_mm(bbox[2]), 2),
        "y1": round(_pt_para_mm(bbox[3]), 2),
    }


def _unir(caixas: list[dict[str, float]]) -> dict[str, float] | None:
    if not caixas:
        return None
    return {
        "x0": round(min(c["x0"] for c in caixas), 2),
        "y0": round(min(c["y0"] for c in caixas), 2),
        "x1": round(max(c["x1"] for c in caixas), 2),
        "y1": round(max(c["y1"] for c in caixas), 2),
    }


def _palavras(pdf: Path, pagina: int = 0) -> list[dict[str, Any]]:
    doc = fitz.open(pdf)
    try:
        page = doc[pagina]
        saida: list[dict[str, Any]] = []
        for palavra in page.get_text("words"):
            x0, y0, x1, y1, texto = palavra[0], palavra[1], palavra[2], palavra[3], palavra[4]
            saida.append(
                {
                    "texto": str(texto),
                    "caixa_mm": _caixa_mm((x0, y0, x1, y1)),
                    "altura_pt": y1 - y0,
                }
            )
        return saida
    finally:
        doc.close()


def _pagina_mm(pdf: Path, pagina: int = 0) -> dict[str, float]:
    doc = fitz.open(pdf)
    try:
        rect = doc[pagina].rect
        return {
            "largura": round(_pt_para_mm(rect.width), 1),
            "altura": round(_pt_para_mm(rect.height), 1),
        }
    finally:
        doc.close()


def detectar_quadro(pdf: Path, *, dpi: int = DPI_TRACO, pagina: int = 0) -> dict[str, float] | None:
    """Moldura preta do quadro do mapa, em mm — a maior caixa fechada da página."""
    arr = rasterizar_pdf(pdf, dpi=dpi, pagina=pagina)
    escuro = np.all(arr < LIMIAR_ESCURO, axis=2)
    altura, largura = escuro.shape

    linhas = np.where(escuro.sum(axis=1) >= largura * FRACAO_LINHA)[0]
    colunas = np.where(escuro.sum(axis=0) >= altura * FRACAO_LINHA)[0]
    if linhas.size < 2 or colunas.size < 2:
        return None

    return {
        "x0": round(_px_para_mm(float(colunas.min()), dpi), 2),
        "y0": round(_px_para_mm(float(linhas.min()), dpi), 2),
        "x1": round(_px_para_mm(float(colunas.max()), dpi), 2),
        "y1": round(_px_para_mm(float(linhas.max()), dpi), 2),
    }


def _e_rotulo_dms(texto: str) -> bool:
    return "°" in texto and ("'" in texto or '"' in texto)


def medir(pdf: Path, *, pagina: int = 0) -> dict[str, Any]:
    """Anatomia do PDF em mm: quadro, título, metadados, legenda e grade."""
    pdf = Path(pdf)
    palavras = _palavras(pdf, pagina)
    pagina_mm = _pagina_mm(pdf, pagina)
    quadro = detectar_quadro(pdf, pagina=pagina)

    dms = [p for p in palavras if _e_rotulo_dms(p["texto"])]
    outras = [p for p in palavras if not _e_rotulo_dms(p["texto"])]

    # Título: a maior fonte do terço superior da página. A rosa dos ventos do
    # acervo é o glifo `µ` da fonte ESRI North, e sai maior que o título — daí
    # exigir palavra de verdade, com pelo menos duas letras ou dígitos.
    topo = [
        p
        for p in outras
        if p["caixa_mm"]["y1"] <= pagina_mm["altura"] * 0.35
        and len([c for c in p["texto"] if c.isalnum()]) >= 2
    ]
    titulo = None
    if topo:
        maior = max(p["altura_pt"] for p in topo)
        linha_titulo = [p for p in topo if p["altura_pt"] >= maior * 0.85]
        titulo = _unir([p["caixa_mm"] for p in linha_titulo])
        texto_titulo = " ".join(
            p["texto"] for p in sorted(linha_titulo, key=lambda p: p["caixa_mm"]["x0"])
        )
    else:
        texto_titulo = ""

    # Faixa inferior: tudo abaixo do quadro (ou dos 80% da página, sem quadro).
    corte = quadro["y1"] if quadro else pagina_mm["altura"] * 0.8
    rodape = [p for p in outras if p["caixa_mm"]["y0"] >= corte]

    metadados_palavras = [p for p in rodape if "METADADOS" in p["texto"].upper()]
    metadados = None
    if metadados_palavras:
        ancora = metadados_palavras[0]["caixa_mm"]
        # O bloco é a coluna de texto que nasce no título METADADOS.
        coluna = [
            p
            for p in rodape
            if p["caixa_mm"]["x1"] >= ancora["x0"] - 25 and p["caixa_mm"]["x0"] <= ancora["x1"] + 25
        ]
        metadados = _unir([p["caixa_mm"] for p in coluna])

    legenda_palavras = [p for p in rodape if p["texto"].strip().upper() in ("LEGENDA", "LEGENDA:")]
    legenda = None
    if legenda_palavras:
        ancora = legenda_palavras[0]["caixa_mm"]
        # Filtra por `x0`: usar `x1` puxa para dentro da legenda a última
        # palavra da linha do datum ("… UTM 22 S"), que termina depois da
        # margem esquerda da coluna sem nunca começar nela.
        coluna = [p for p in rodape if p["caixa_mm"]["x0"] >= ancora["x0"] - 3]
        legenda = _unir([p["caixa_mm"] for p in coluna])

    # Rótulos DMS por borda, usando o quadro como referência.
    bordas = {"superior": 0, "inferior": 0, "esquerda": 0, "direita": 0}
    if quadro:
        meio_x = (quadro["x0"] + quadro["x1"]) / 2
        for p in dms:
            caixa = p["caixa_mm"]
            cy = (caixa["y0"] + caixa["y1"]) / 2
            cx = (caixa["x0"] + caixa["x1"]) / 2
            if cy < quadro["y0"]:
                bordas["superior"] += 1
            elif cy > quadro["y1"]:
                bordas["inferior"] += 1
            elif cx < meio_x:
                bordas["esquerda"] += 1
            else:
                bordas["direita"] += 1

    return {
        "pdf": str(pdf),
        "pagina_mm": pagina_mm,
        "orientacao": "paisagem" if pagina_mm["largura"] > pagina_mm["altura"] else "retrato",
        "quadro_mapa": quadro,
        "titulo": {"caixa_mm": titulo, "texto": texto_titulo},
        "metadados": metadados,
        "legenda": legenda,
        "rotulos_dms": {"total": len(dms), "por_borda": bordas},
        "palavras": len(palavras),
    }


def _delta(a: dict[str, float] | None, b: dict[str, float] | None) -> dict[str, float] | None:
    if not a or not b:
        return None
    return {k: round(b[k] - a[k], 2) for k in ("x0", "y0", "x1", "y1")}


def comparar(
    modelo: dict[str, Any],
    gerado: dict[str, Any],
    *,
    tolerancia_mm: float = 6.0,
) -> dict[str, Any]:
    """Confronta duas anatomias e diz onde o gerado saiu do padrão medido."""
    itens: list[dict[str, Any]] = []

    def _check(id_: str, chave: str, descricao: str, campos: tuple[str, ...] = ("x0", "y0", "x1", "y1")) -> None:
        delta = _delta(modelo.get(chave), gerado.get(chave))
        if delta is None:
            itens.append(
                {
                    "id": id_,
                    "ok": False,
                    "mensagem": f"{descricao}: ausente no modelo ou no gerado",
                    "delta_mm": None,
                }
            )
            return
        pior = max(abs(delta[c]) for c in campos)
        itens.append(
            {
                "id": id_,
                "ok": pior <= tolerancia_mm,
                "mensagem": f"{descricao}: maior desvio {pior:.1f} mm (tolerância {tolerancia_mm:.1f} mm)",
                "delta_mm": delta,
                "campos_comparados": list(campos),
            }
        )

    def _check_centro(id_: str, chave: str, descricao: str) -> None:
        """Bloco centralizado: compara o centro em x e a base em y."""
        caixa_modelo = modelo.get(chave)
        caixa_gerado = gerado.get(chave)
        if not caixa_modelo or not caixa_gerado:
            itens.append(
                {
                    "id": id_,
                    "ok": False,
                    "mensagem": f"{descricao}: ausente no modelo ou no gerado",
                    "delta_mm": None,
                }
            )
            return
        centro_modelo = (caixa_modelo["x0"] + caixa_modelo["x1"]) / 2
        centro_gerado = (caixa_gerado["x0"] + caixa_gerado["x1"]) / 2
        delta = {
            "centro_x": round(centro_gerado - centro_modelo, 2),
            "y1": round(caixa_gerado["y1"] - caixa_modelo["y1"], 2),
        }
        pior = max(abs(v) for v in delta.values())
        itens.append(
            {
                "id": id_,
                "ok": pior <= tolerancia_mm,
                "mensagem": (
                    f"{descricao}: maior desvio {pior:.1f} mm "
                    f"(tolerância {tolerancia_mm:.1f} mm)"
                ),
                "delta_mm": delta,
                "campos_comparados": ["centro_x", "y1"],
            }
        )

    _check("A01", "quadro_mapa", "Quadro do mapa")
    # Metadados e legenda são blocos de **conteúdo variável**: o nome do imóvel
    # e o número de classes mudam a largura e a altura legitimamente. O que o
    # padrão fixa é a âncora — mas a âncora não é a mesma nos dois blocos.
    #
    # O bloco de metadados é **centralizado** (nos próprios modelos, o `x0` das
    # suas linhas varia ~14 mm entre si); comparar a margem esquerda dele mede
    # comprimento de texto, não posição: "Satélite/Sensor: SPOT" contra
    # "Satélite/Sensor: SPOT HRV 2008" dava 8 mm de "desvio" com o bloco
    # centrado no mesmo lugar, com erro simétrico dos dois lados. A âncora certa
    # é o centro. Já a legenda é alinhada à esquerda, e ali `x0` é a âncora real.
    _check_centro("A03", "metadados", "Bloco de metadados (âncora)")
    _check("A04", "legenda", "Legenda (âncora)", campos=("x0", "y1"))

    delta_titulo = _delta(
        (modelo.get("titulo") or {}).get("caixa_mm"), (gerado.get("titulo") or {}).get("caixa_mm")
    )
    if delta_titulo is None:
        itens.append({"id": "A02", "ok": False, "mensagem": "Caixa de título ausente", "delta_mm": None})
    else:
        pior = max(abs(v) for v in delta_titulo.values())
        itens.append(
            {
                "id": "A02",
                "ok": pior <= tolerancia_mm * 2,  # o título varia com o comprimento do texto
                "mensagem": f"Caixa de título: maior desvio {pior:.1f} mm",
                "delta_mm": delta_titulo,
            }
        )

    mod_bordas = (modelo.get("rotulos_dms") or {}).get("por_borda") or {}
    ger_bordas = (gerado.get("rotulos_dms") or {}).get("por_borda") or {}
    faltando = [b for b in ("superior", "inferior", "esquerda", "direita") if not ger_bordas.get(b)]
    itens.append(
        {
            "id": "A05",
            "ok": not faltando,
            "mensagem": (
                "Rótulos DMS nas 4 bordas"
                if not faltando
                else f"Bordas sem rótulo DMS: {', '.join(faltando)}"
            ),
            "modelo": mod_bordas,
            "gerado": ger_bordas,
        }
    )

    itens.append(
        {
            "id": "A06",
            "ok": modelo.get("orientacao") == gerado.get("orientacao"),
            "mensagem": f"Orientação {gerado.get('orientacao')} (modelo {modelo.get('orientacao')})",
        }
    )

    return {
        "tolerancia_mm": tolerancia_mm,
        "itens": itens,
        "ok": all(i["ok"] for i in itens),
        "falhas": [i["id"] for i in itens if not i["ok"]],
    }
