# -*- coding: utf-8 -*-
"""Corrige LOGO + nomes do minimapa no template Dinamica (ArcPy 2.7).

Regras Harmonia (medidas no acervo):
- MINIMAPA_RETANGULO — quadrado vermelho pequeno (~0,12 cm)
- MINIMAPA_GUIA — linha em L (bbox grande na ancora ~0,75×2,16)
- MINIMAPA — outro graphic grande na mesma ancora (legado do acervo)

Uso:
  C:\\Python27\\ArcGIS10.8\\python.exe ferramentas/corrigir_template_b1_arcpy.py \\
    shared/templates/Dinamica_retrato.mxd \\
    --logo \"Referencias_IMAP/Logos IMAP/LOGOTIPO SEM FUNDO/TOM ESCURO.png\"
"""
from __future__ import print_function

import argparse
import os
import shutil
import sys
import tempfile

import arcpy

LOGO_PADRAO = os.path.join(
    "Referencias_IMAP", "Logos IMAP", "LOGOTIPO SEM FUNDO", "TOM ESCURO.png"
)


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def corrigir(caminho, logo):
    pasta = tempfile.mkdtemp(prefix="mf_b1_")
    tmp = os.path.join(pasta, "tmp.mxd")
    shutil.copy2(caminho, tmp)
    mxd = arcpy.mapping.MapDocument(tmp)
    aplicados = []
    avisos = []

    pics = arcpy.mapping.ListLayoutElements(mxd, "PICTURE_ELEMENT")
    if len(pics) == 1:
        p = pics[0]
        if _safe(lambda: p.name) != "LOGO":
            p.name = "LOGO"
            aplicados.append("picture -> LOGO")
        if logo and os.path.isfile(logo):
            try:
                p.sourceImage = os.path.abspath(logo)
                aplicados.append("LOGO.sourceImage = " + os.path.abspath(logo))
            except Exception as exc:
                avisos.append("LOGO.sourceImage falhou: {0}".format(exc))
        elif not (_safe(lambda: p.sourceImage) or ""):
            avisos.append("LOGO sem sourceImage")
    else:
        avisos.append("{0} picture elements".format(len(pics)))

    grandes = []
    for el in arcpy.mapping.ListLayoutElements(mxd, "GRAPHIC_ELEMENT"):
        x = _safe(lambda: el.elementPositionX) or 0
        y = _safe(lambda: el.elementPositionY) or 0
        w = _safe(lambda: el.elementWidth) or 0
        h = _safe(lambda: el.elementHeight) or 0
        if w < 0.3 and h < 0.3 and 0.9 <= x <= 1.0:
            if (_safe(lambda: el.name) or "") != "MINIMAPA_RETANGULO":
                el.name = "MINIMAPA_RETANGULO"
                aplicados.append("RETANGULO @({0:.2f},{1:.2f})".format(x, y))
        elif abs(x - 0.7534) < 0.05 and abs(y - 2.1648) < 0.05 and w > 1.0:
            grandes.append((w * h, el, w, h))
        elif abs(x - 0.7668) < 0.02 and abs(y - 2.187) < 0.02:
            if (_safe(lambda: el.name) or "") != "UF_INSET":
                el.name = "UF_INSET"
                aplicados.append("UF_INSET graphic")

    grandes.sort(key=lambda t: t[0], reverse=True)
    if len(grandes) >= 1:
        if (_safe(lambda: grandes[0][1].name) or "") != "MINIMAPA_GUIA":
            grandes[0][1].name = "MINIMAPA_GUIA"
            aplicados.append(
                "MINIMAPA_GUIA ({0:.2f}x{1:.2f})".format(grandes[0][2], grandes[0][3])
            )
    if len(grandes) >= 2:
        if (_safe(lambda: grandes[1][1].name) or "") != "MINIMAPA":
            grandes[1][1].name = "MINIMAPA"
            aplicados.append(
                "MINIMAPA graphic ({0:.2f}x{1:.2f})".format(grandes[1][2], grandes[1][3])
            )

    mxd.save()
    del mxd
    shutil.copy2(tmp, caminho)
    try:
        shutil.rmtree(pasta)
    except Exception:
        pass
    return aplicados, avisos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mxd")
    ap.add_argument("--logo", default=LOGO_PADRAO)
    args = ap.parse_args()
    if not os.path.isfile(args.mxd):
        sys.stderr.write("MXD ausente: {0}\n".format(args.mxd))
        return 1
    aplicados, avisos = corrigir(args.mxd, args.logo)
    print("Aplicados ({0}):".format(len(aplicados)))
    for a in aplicados:
        print("  +", a)
    print("Avisos ({0}):".format(len(avisos)))
    for a in avisos:
        print("  !", a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
