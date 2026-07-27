# -*- coding: utf-8 -*-
"""Inspeciona um .mxd via arcpy (Python 2.7 do ArcMap). Uso na preparação B1/B2."""
from __future__ import print_function

import argparse
import json
import sys

try:
    import arcpy
except ImportError:
    sys.stderr.write("arcpy indisponivel — execute com Python 2.7 do ArcMap\n")
    sys.exit(1)

# Contrato F1-04 — nomes canônicos esperados no template Dinâmica.
CAMADAS_CANONICAS = {
    "PERIMETRO",
    "AVN",
    "AC",
    "AUAS",
    "APP",
    "ARL",
    "NASCENTE",
    "MUNICIPIOS",
    "UF",
    "TEMATICA",
    "BASEMAP",
}

ELEMENTOS_OBRIGATORIOS = {
    "DATAFRAME": {"MAPA", "MINIMAPA"},
    "TEXT": {"TITULO", "METADADOS", "ROTULO_IMOVEL"},
    "LEGEND": {"LEGENDA"},
    "PICTURE": {"LOGO"},
    "MAPSURROUND": {"NORTE"},
    "GRAPHIC": {"MINIMAPA_RETANGULO", "MINIMAPA_GUIA"},
}


def _safe(getter, default=None):
    try:
        return getter()
    except (NameError, AttributeError, ValueError):
        return default


def inspecionar(caminho_mxd):
    mxd = arcpy.mapping.MapDocument(caminho_mxd)
    rel = {
        "arquivo": caminho_mxd,
        "relativePaths": mxd.relativePaths,
        "data_frames": [],
        "camadas": [],
        "text_elements": [],
        "graphics": [],
        "pictures": [],
        "legends": [],
        "mapsurrounds": [],
        "broken": [],
        "diagnostico": {},
    }

    nomes_df = set()
    nomes_camada = set()
    nomes_text = set()
    nomes_graphic = set()
    nomes_picture = set()
    nomes_legend = set()
    nomes_mapsurround = set()

    for df in arcpy.mapping.ListDataFrames(mxd):
        nomes_df.add(df.name)
        rel["data_frames"].append(
            {
                "name": df.name,
                "scale": df.scale,
                "extent": [
                    df.extent.XMin,
                    df.extent.YMin,
                    df.extent.XMax,
                    df.extent.YMax,
                ],
                "sr": _safe(lambda: df.spatialReference.factoryCode),
            }
        )
        for lyr in arcpy.mapping.ListLayers(mxd, "", df):
            nomes_camada.add(lyr.name)
            info = {
                "df": df.name,
                "name": lyr.name,
                "visible": _safe(lambda: lyr.visible),
            }
            rel["camadas"].append(info)

    for el in arcpy.mapping.ListLayoutElements(mxd, "TEXT_ELEMENT"):
        nome = _safe(lambda: el.name)
        nomes_text.add(nome)
        rel["text_elements"].append(
            {
                "name": nome,
                "x": el.elementPositionX,
                "y": el.elementPositionY,
                "text": (el.text or "")[:120],
                "chars": len(el.text or ""),
            }
        )

    for el in arcpy.mapping.ListLayoutElements(mxd, "GRAPHIC_ELEMENT"):
        nome = _safe(lambda: el.name)
        nomes_graphic.add(nome)
        rel["graphics"].append(
            {
                "name": nome,
                "x": el.elementPositionX,
                "y": el.elementPositionY,
            }
        )

    for el in arcpy.mapping.ListLayoutElements(mxd, "PICTURE_ELEMENT"):
        nome = _safe(lambda: el.name)
        nomes_picture.add(nome)
        rel["pictures"].append(
            {
                "name": nome,
                "source": (el.sourceImage or "")[:120],
            }
        )

    for el in arcpy.mapping.ListLayoutElements(mxd, "LEGEND_ELEMENT"):
        nome = _safe(lambda: el.name)
        nomes_legend.add(nome)
        rel["legends"].append({"name": nome})

    for el in arcpy.mapping.ListLayoutElements(mxd, "MAPSURROUND_ELEMENT"):
        nome = _safe(lambda: el.name)
        nomes_mapsurround.add(nome)
        rel["mapsurrounds"].append({"name": nome})

    rel["broken"] = []
    try:
        for lyr in arcpy.mapping.ListBrokenDataSources(mxd):
            rel["broken"].append(
                {
                    "df": _safe(lambda: lyr.dataFrame.name),
                    "name": _safe(lambda: lyr.name),
                }
            )
    except Exception:
        pass

    faltam_df = sorted(ELEMENTOS_OBRIGATORIOS["DATAFRAME"] - nomes_df)
    faltam_text = sorted(ELEMENTOS_OBRIGATORIOS["TEXT"] - nomes_text)
    faltam_graphic = sorted(ELEMENTOS_OBRIGATORIOS["GRAPHIC"] - nomes_graphic)
    faltam_picture = sorted(ELEMENTOS_OBRIGATORIOS["PICTURE"] - nomes_picture)
    faltam_legend = sorted(ELEMENTOS_OBRIGATORIOS["LEGEND"] - nomes_legend)
    faltam_ms = sorted(ELEMENTOS_OBRIGATORIOS["MAPSURROUND"] - nomes_mapsurround)

    camadas_nao_canonicas = sorted(
        n for n in nomes_camada if n not in CAMADAS_CANONICAS and not n.startswith("World")
    )

    rel["diagnostico"] = {
        "relative_paths_ok": bool(mxd.relativePaths),
        "faltam_data_frames": faltam_df,
        "faltam_text_elements": faltam_text,
        "faltam_graphics": faltam_graphic,
        "faltam_pictures": faltam_picture,
        "faltam_legends": faltam_legend,
        "faltam_mapsurrounds": faltam_ms,
        "camadas_nao_canonicas": camadas_nao_canonicas,
        "camadas_canonicas_presentes": sorted(CAMADAS_CANONICAS & nomes_camada),
        "camadas_canonicas_faltando": sorted(CAMADAS_CANONICAS - nomes_camada),
        "quebradas": len(rel["broken"]),
        "nomes_quebrados": sorted(
            {b.get("name") for b in rel["broken"] if b.get("name")}
        ),
        "pronto_b1": not any(
            [
                faltam_df,
                faltam_text,
                faltam_graphic,
                faltam_picture,
                faltam_legend,
                faltam_ms,
                not mxd.relativePaths,
            ]
        ),
    }

    del mxd
    return rel


def main():
    parser = argparse.ArgumentParser(description="Inspeciona .mxd com arcpy")
    parser.add_argument("mxd", help="Caminho do .mxd")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Saída JSON (padrão se stdout não for TTY)",
    )
    parser.add_argument("-o", "--saida", help="Gravar JSON neste arquivo (UTF-8)")
    args = parser.parse_args()
    rel = inspecionar(args.mxd)
    payload = json.dumps(rel, ensure_ascii=False, indent=2)
    if args.saida:
        import codecs

        with codecs.open(args.saida, "w", "utf-8") as fh:
            fh.write(payload)
        print("Gravado:", args.saida)
        d = rel["diagnostico"]
        print("pronto_b1:", d["pronto_b1"])
        return 0
    saida_json = args.json or not sys.stdout.isatty()
    if saida_json:
        print(payload.encode("utf-8"))
    else:
        d = rel["diagnostico"]
        print("Arquivo:", rel["arquivo"])
        print("relativePaths:", rel["relativePaths"])
        print("Data frames:", [x["name"] for x in rel["data_frames"]])
        print("Camadas ({0}):".format(len(rel["camadas"])))
        for c in rel["camadas"]:
            print("  - {0} ({1})".format(c["name"], c["df"]))
        print("Quebradas:", rel["broken"] or "(nenhuma)")
        print("--- diagnostico B1 ---")
        print("pronto_b1:", d["pronto_b1"])
        if d["faltam_data_frames"]:
            print("  faltam data frames:", d["faltam_data_frames"])
        if d["faltam_text_elements"]:
            print("  faltam textos:", d["faltam_text_elements"])
        if d["camadas_nao_canonicas"]:
            print("  camadas a renomear/remover:", d["camadas_nao_canonicas"])
        if d["camadas_canonicas_faltando"]:
            print("  canonicas faltando:", d["camadas_canonicas_faltando"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
