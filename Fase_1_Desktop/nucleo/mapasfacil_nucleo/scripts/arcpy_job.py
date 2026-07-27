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


def _aplicar_basemap_wmts(df, e):
    """Adiciona Planet como WMTS vivo (nao raster local) — nao trava o export.

    URL: https://api.planet.com/basemaps/v1/mosaics/wmts?api_key=...
    Camada = basemap_mosaico (ex.: global_monthly_2026_03_mosaic).
    """
    chave = e.get(u"planet_api_key")
    mosaico = e.get(u"basemap_mosaico")
    tmp = e.get(u"tmp")
    if not chave or not mosaico or not tmp:
        return False
    url = u"https://api.planet.com/basemaps/v1/mosaics/wmts?api_key=%s" % _u(chave)
    conn_dir = os.path.join(_u(tmp), u"wmts_conn")
    try:
        if not os.path.isdir(conn_dir):
            os.makedirs(conn_dir)
    except Exception:
        return False

    # ArcMap 10.8: CreateGISServerConnectionFile aceita WMTS_SERVER em builds recentes.
    for server_type in (u"WMTS_SERVER", u"WMS_SERVER"):
        try:
            arcpy.mapping.CreateGISServerConnectionFile(
                u"USE_GIS_SERVICES",
                conn_dir,
                u"planet",
                url,
                server_type,
                True,
                u"SAVE_USERNAME",
                u"",
                u"",
                u"SAVE_PASSWORD",
                False,
            )
        except Exception:
            continue
        # Procura arquivo de conexao gerado
        for nome in os.listdir(conn_dir):
            baixo = nome.lower()
            if not (baixo.endswith(u".wmts") or baixo.endswith(u".wms") or baixo.endswith(u".ags")):
                continue
            caminho_conn = os.path.join(conn_dir, nome)
            try:
                # Tenta abrir a conexao como Layer (funciona para .wms em varios 10.x)
                lyr = arcpy.mapping.Layer(caminho_conn)
                # Se for grupo, procura o mosaico pelo nome
                if lyr.isGroupLayer:
                    for sub in lyr:
                        if mosaico.lower() in (sub.name or u"").lower() or mosaico.lower() in (
                            getattr(sub, u"datasetName", u"") or u""
                        ).lower():
                            arcpy.mapping.AddLayer(df, sub, u"BOTTOM")
                            return True
                    # Sem match: adiciona o primeiro sublayer
                    for sub in lyr:
                        arcpy.mapping.AddLayer(df, sub, u"BOTTOM")
                        return True
                else:
                    arcpy.mapping.AddLayer(df, lyr, u"BOTTOM")
                    return True
            except Exception:
                continue
    return False


def _aplicar_basemap_raster(df, e):
    """Fallback: PNG local georeferenciado (pode ser lento — so se WMTS falhar)."""
    caminho = e.get(u"basemap_raster")
    if not caminho:
        return False
    caminho = _u(caminho)
    if not os.path.isfile(caminho):
        return False
    try:
        if os.environ.get("MAPASFACIL_BUILD_PYRAMIDS") == "1":
            try:
                arcpy.BuildPyramids_management(caminho)
            except Exception:
                pass
        resultado = arcpy.MakeRasterLayer_management(caminho, u"BASEMAP_PLANET")
        nova = resultado.getOutput(0)
        arcpy.mapping.AddLayer(df, nova, u"BOTTOM")
        return True
    except Exception:
        return False


def _aplicar_basemap(df, e):
    """Preferir WMTS vivo; raster local so como fallback explicito."""
    if _aplicar_basemap_wmts(df, e):
        return
    # Raster local: so se MAPASFACIL_BASEMAP_RASTER=1 (evita hang no smoke).
    if os.environ.get("MAPASFACIL_BASEMAP_RASTER") == "1":
        _aplicar_basemap_raster(df, e)


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


def _workspaces_das_camadas(mxd):
    """Pastas de workspace atuais (API estável — sem replaceDataSource/Describe)."""
    pastas = []
    vistos = set()
    for df in arcpy.mapping.ListDataFrames(mxd):
        for lyr in arcpy.mapping.ListLayers(mxd, u"", df):
            if lyr.isGroupLayer:
                continue
            try:
                if not lyr.supports(u"DATASOURCE"):
                    continue
                ds = lyr.dataSource
            except Exception:
                continue
            if not ds:
                continue
            pasta = os.path.dirname(ds)
            chave = pasta.lower()
            if chave in vistos:
                continue
            vistos.add(chave)
            pastas.append(pasta)
    return pastas


def _reponte_workspaces(mxd, pasta_template_shp, pasta_saida_shp, pasta_ibge=None):
    """Troca workspaces via findAndReplaceWorkspacePaths (F1-04 — sem replaceDataSource).

    - pastas de dados do projeto → pasta_saida_shp
    - pastas IBGE → pasta_ibge (se informada)
    """
    destino_shp = _u(pasta_saida_shp)
    destino_ibge = _u(pasta_ibge) if pasta_ibge else None
    if not destino_shp and not destino_ibge:
        return

    candidatos = []
    if pasta_template_shp:
        candidatos.append(_u(pasta_template_shp))
    candidatos.extend(_workspaces_das_camadas(mxd))

    vistos = set()
    for origem in candidatos:
        if not origem:
            continue
        chave = origem.lower()
        if chave in vistos:
            continue
        vistos.add(chave)

        eh_ibge = (u"ibge" in chave) or (u"lml_" in chave) or (
            os.path.basename(origem).lower() in (u"ibge", u"bases")
        )
        if eh_ibge:
            if destino_ibge and chave != destino_ibge.lower():
                try:
                    mxd.findAndReplaceWorkspacePaths(origem, destino_ibge, False)
                except Exception:
                    pass
            continue

        if destino_shp and chave != destino_shp.lower():
            try:
                mxd.findAndReplaceWorkspacePaths(origem, destino_shp, False)
            except Exception:
                pass


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

        # Reponta workspaces (template + paths absolutos herdados).
        # Sem replaceDataSource — trava neste ArcMap (F1-04).
        _reponte_workspaces(
            mxd,
            e.get(u"pasta_template_shp"),
            e.get(u"pasta_saida_shp"),
            e.get(u"pasta_ibge"),
        )

        _aplicar_basemap(df, e)
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
        if legenda_nomes:
            # So filtra quando uma lista explicita vem no payload — lista vazia
            # (caminho T1 ainda nao a preenche) nao deve esvaziar a legenda inteira.
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
            # Com basemap, BEST@300dpi estoura timeout (~10 min). NORMAL@150
            # fecha em ~1 min; MAPASFACIL_PDF_HQ=1 volta ao modo entrega.
            hq = os.environ.get("MAPASFACIL_PDF_HQ") == "1"
            arcpy.mapping.ExportToPDF(
                mxd,
                _u(e[u"saida_pdf"]),
                resolution=300 if hq else 150,
                image_quality=u"BEST" if hq else u"NORMAL",
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
