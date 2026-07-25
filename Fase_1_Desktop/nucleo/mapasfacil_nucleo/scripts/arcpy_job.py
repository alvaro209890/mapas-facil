# -*- coding: utf-8 -*-
"""Executado pelo Python 2.7 do ArcMap. NUNCA importado pelo nucleo 3.12."""
from __future__ import print_function

import codecs
import json
import os
import shutil
import sys

EXIT_TIMEOUT = 124

try:
    import arcpy
except ImportError:
    sys.stderr.write("arcpy nao disponivel\n")
    sys.exit(1)


def _u(s):
    if s is None:
        return None
    if isinstance(s, unicode):  # noqa: F821 — py2
        return s
    return unicode(s, "utf-8")  # noqa: F821


def main():
    job_path = os.environ.get("MAPASFACIL_JOB_JSON")
    if not job_path:
        sys.stderr.write("MAPASFACIL_JOB_JSON ausente\n")
        sys.exit(1)

    with codecs.open(job_path, "r", "utf-8") as fh:
        e = json.load(fh)

    arcpy.env.overwriteOutput = True
    # Trabalhar sobre copia — MapDocument mantem lock no arquivo aberto.
    trabalho = os.path.join(_u(e[u"tmp"]), u"trabalho.mxd")
    shutil.copy2(_u(e[u"template"]), trabalho)

    mxd = arcpy.mapping.MapDocument(trabalho)
    quebradas = []
    escala_final = None
    crs_code = None
    erro = None

    try:
        mxd.relativePaths = True
        df = arcpy.mapping.ListDataFrames(mxd, u"MAPA")[0]

        mxd.findAndReplaceWorkspacePaths(
            _u(e[u"pasta_template_shp"]),
            _u(e[u"pasta_saida_shp"]),
            False,
        )

        camadas_visiveis = set(e.get(u"camadas_visiveis") or [])
        for lyr in arcpy.mapping.ListLayers(mxd, u"", df):
            if lyr.name == u"MUNICIPIOS":
                lyr.definitionQuery = u'"%s" = \'%s\'' % (
                    e[u"campo_municipio"],
                    e[u"municipio"],
                )
            elif lyr.name == u"UF":
                lyr.definitionQuery = u'"%s" = \'%s\'' % (
                    e[u"campo_uf"],
                    e[u"uf_extenso"],
                )
            elif lyr.name in camadas_visiveis:
                lyr.visible = True

        bbox = e[u"bbox_no_crs_do_data_frame"]
        df.extent = arcpy.Extent(*bbox)
        df.scale = e[u"escala"]

        textos = dict(
            (t.name, t) for t in arcpy.mapping.ListLayoutElements(mxd, u"TEXT_ELEMENT")
        )
        for nome, valor in (e.get(u"textos") or {}).items():
            if nome in textos:
                textos[nome].text = _u(valor) if valor else u" "

        for fig in arcpy.mapping.ListLayoutElements(mxd, u"PICTURE_ELEMENT"):
            if fig.name in (e.get(u"imagens") or {}):
                fig.sourceImage = _u(e[u"imagens"][fig.name])

        for g in arcpy.mapping.ListLayoutElements(mxd, u"GRAPHIC_ELEMENT"):
            graf = (e.get(u"graficos") or {}).get(g.name)
            if graf:
                g.elementPositionX = graf[u"x"]
                g.elementPositionY = graf[u"y"]

        legenda_nomes = set(e.get(u"legenda") or [])
        for leg in arcpy.mapping.ListLayoutElements(mxd, u"LEGEND_ELEMENT", u"LEGENDA"):
            leg.autoAdd = False
            for item in leg.listLegendItemLayers():
                if item.name not in legenda_nomes:
                    leg.removeItem(item)

        quebradas = [l.name for l in arcpy.mapping.ListBrokenDataSources(mxd)]
        escala_final = df.scale
        crs_code = df.spatialReference.factoryCode

        saidas = e.get(u"saidas") or []
        if u"mxd" in saidas and e.get(u"saida_mxd"):
            mxd.saveACopy(_u(e[u"saida_mxd"]))
        if u"pdf" in saidas and e.get(u"saida_pdf"):
            arcpy.mapping.ExportToPDF(
                mxd,
                _u(e[u"saida_pdf"]),
                resolution=300,
                image_quality=u"BEST",
                colorspace=u"RGB",
                compress_vectors=True,
                image_compression=u"ADAPTIVE",
                embed_fonts=True,
                georef_info=True,
            )
        if u"png" in saidas and e.get(u"saida_png"):
            arcpy.mapping.ExportToPNG(mxd, _u(e[u"saida_png"]), resolution=96)
    except Exception as exc:  # noqa: BLE001 — relatorio para o nucleo 3.12
        erro = unicode(exc)  # noqa: F821
    finally:
        relatorio = {
            u"quebradas": quebradas,
            u"escala": escala_final,
            u"crs": crs_code,
            u"erro": erro,
        }
        rel_path = e.get(u"relatorio")
        if rel_path:
            with codecs.open(_u(rel_path), "w", "utf-8") as fh:
                json.dump(relatorio, fh, ensure_ascii=False)
        del mxd

    if erro:
        sys.exit(1)


if __name__ == "__main__":
    main()
