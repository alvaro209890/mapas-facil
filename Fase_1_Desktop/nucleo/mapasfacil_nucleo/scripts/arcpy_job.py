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


def _dq(campo, valor):
    v = _u(valor).replace(u"'", u"''")
    return u'"%s" = \'%s\'' % (_u(campo), v)


def _aplicar_queries(mxd, e):
    municipio = e.get(u"municipio")
    uf_extenso = e.get(u"uf_extenso")
    campo_m = e.get(u"campo_municipio") or u"nome"
    campo_u = e.get(u"campo_uf") or u"nome"
    camadas_visiveis = set(e.get(u"camadas_visiveis") or [])
    for df in arcpy.mapping.ListDataFrames(mxd):
        for lyr in arcpy.mapping.ListLayers(mxd, u"", df):
            nome = lyr.name or u""
            if not lyr.supports(u"DEFINITIONQUERY"):
                if nome in camadas_visiveis:
                    lyr.visible = True
                continue
            if nome == u"MUNICIPIOS" or nome == u"Limite municipal":
                if municipio:
                    lyr.definitionQuery = _dq(campo_m, municipio)
            elif nome == u"MUNICIPIOS_ENTORNO":
                lyr.definitionQuery = u""
            elif nome in (u"UF", u"Limite estadual"):
                if uf_extenso:
                    lyr.definitionQuery = _dq(campo_u, uf_extenso)
            elif nome in camadas_visiveis:
                lyr.visible = True


def _zoom_minimapa(mxd, e):
    """Enquadra o municipio no DF MINIMAPA (extent do job ou getExtent da camada)."""
    dfs = arcpy.mapping.ListDataFrames(mxd, u"MINIMAPA")
    if not dfs:
        return
    df = dfs[0]
    ext_job = e.get(u"extent_minimapa")
    if ext_job and len(ext_job) == 4:
        df.extent = arcpy.Extent(*[float(v) for v in ext_job])
        return
    layers = arcpy.mapping.ListLayers(mxd, u"MUNICIPIOS", df)
    if not layers:
        return
    try:
        ext = layers[0].getExtent()
        if ext is None or ext.XMin is None:
            return
        pad = float(e.get(u"padding_minimapa") or 1.25)
        cx = (float(ext.XMin) + float(ext.XMax)) / 2.0
        cy = (float(ext.YMin) + float(ext.YMax)) / 2.0
        hw = (float(ext.XMax) - float(ext.XMin)) / 2.0 * pad
        hh = (float(ext.YMax) - float(ext.YMin)) / 2.0 * pad
        df.extent = arcpy.Extent(cx - hw, cy - hh, cx + hw, cy + hh)
    except Exception:
        pass


def _aplicar_graficos(mxd, e):
    graficos = e.get(u"graficos") or {}
    for g in arcpy.mapping.ListLayoutElements(mxd, u"GRAPHIC_ELEMENT"):
        graf = graficos.get(g.name)
        if not graf:
            continue
        if u"x" in graf:
            g.elementPositionX = float(graf[u"x"])
        if u"y" in graf:
            g.elementPositionY = float(graf[u"y"])
        if u"width_cm" in graf:
            g.elementWidth = float(graf[u"width_cm"])
        if u"height_cm" in graf:
            g.elementHeight = float(graf[u"height_cm"])


def main():
    job_path = os.environ.get("MAPASFACIL_JOB_JSON")
    if not job_path:
        sys.stderr.write("MAPASFACIL_JOB_JSON ausente\n")
        sys.exit(1)

    with codecs.open(job_path, "r", "utf-8") as fh:
        e = json.load(fh)

    arcpy.env.overwriteOutput = True
    trabalho = os.path.join(_u(e[u"tmp"]), u"trabalho.mxd")
    shutil.copy2(_u(e[u"template"]), trabalho)

    mxd = arcpy.mapping.MapDocument(trabalho)
    quebradas = []
    escala_final = None
    crs_code = None
    erro = None

    try:
        mxd.relativePaths = True
        dfs_mapa = arcpy.mapping.ListDataFrames(mxd, u"MAPA")
        if not dfs_mapa:
            raise RuntimeError("data frame MAPA ausente no template")
        df = dfs_mapa[0]

        if e.get(u"pasta_template_shp") and e.get(u"pasta_saida_shp"):
            mxd.findAndReplaceWorkspacePaths(
                _u(e[u"pasta_template_shp"]),
                _u(e[u"pasta_saida_shp"]),
                False,
            )

        # IBGE do repo: reponta MUNICIPIOS/UF se o job informar pasta
        pasta_ibge = e.get(u"pasta_ibge")
        if pasta_ibge:
            for dframe in arcpy.mapping.ListDataFrames(mxd):
                for lyr in arcpy.mapping.ListLayers(mxd, u"", dframe):
                    nome = lyr.name or u""
                    try:
                        if nome in (u"MUNICIPIOS", u"MUNICIPIOS_ENTORNO", u"Limite municipal"):
                            lyr.replaceDataSource(
                                _u(pasta_ibge), u"SHAPEFILE_WORKSPACE", u"lml_municipio_a", True
                            )
                        elif nome in (u"UF", u"Limite estadual"):
                            lyr.replaceDataSource(
                                _u(pasta_ibge), u"SHAPEFILE_WORKSPACE", u"lml_uf_a", True
                            )
                    except Exception:
                        pass

        _aplicar_queries(mxd, e)
        _zoom_minimapa(mxd, e)

        bbox = e[u"bbox_no_crs_do_data_frame"]
        df.extent = arcpy.Extent(*bbox)
        if e.get(u"escala"):
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

        _aplicar_graficos(mxd, e)

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
    except Exception as exc:  # noqa: BLE001
        erro = unicode(exc)  # noqa: F821
    finally:
        relatorio = {
            u"quebradas": quebradas,
            u"escala": escala_final,
            u"crs": crs_code,
            u"erro": erro,
            u"minimapa": bool(e.get(u"municipio")),
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
