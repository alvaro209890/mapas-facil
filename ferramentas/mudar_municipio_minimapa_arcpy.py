# -*- coding: utf-8 -*-
"""Troca o municipio do minimapa: definition query + rotulo + retangulo/linha-guia.

Python 2.7 / ArcMap. Exige MXD ja conectado (conectar_minimapa_ibge_arcpy.py).

Uso::

    C:\\Python27\\ArcGIS10.8\\python.exe ferramentas/mudar_municipio_minimapa_arcpy.py \\
        Referencias_IMAP/MXD/Dinamica_2026.mxd --municipio "Vila Rica" --uf-sigla MT \\
        --uf-nome "Mato Grosso" --in-place

    # Lote a partir de um JSON {arquivo, municipio, uf_sigla, uf_nome, lon, lat}
    C:\\Python27\\ArcGIS10.8\\python.exe ferramentas/mudar_municipio_minimapa_arcpy.py \\
        --lote jobs_municipio.json --in-place -o relatorio_mudar_municipio.json

Comportamento (padrao Harmonia / PDF Mapas/01):
1. MUNICIPIOS (destaque laranja): \"nome\" = '<municipio>'
2. MUNICIPIOS_ENTORNO: sem filtro (bege)
3. UF / UF_INSET: \"nome\" = '<uf_nome>'
4. Extent do MINIMAPA enquadra o municipio (+ padding)
5. ROTULO_MUNICIPIO e UF_SELO atualizados
6. MINIMAPA_RETANGULO centrado no centroide do imovel (ou --lon/--lat)
7. MINIMAPA_GUIA (linha em L) reposicionada do retangulo ate a moldura do MAPA
"""
from __future__ import print_function

import argparse
import json
import os
import shutil
import sys
import tempfile
import time

try:
    import arcpy
except ImportError:
    sys.stderr.write("arcpy indisponivel\n")
    sys.exit(1)


def _as_text(msg):
    if msg is None:
        return u""
    if isinstance(msg, unicode):  # noqa: F821
        return msg
    if isinstance(msg, str):
        for enc in ("mbcs", "cp1252", "utf-8", "latin-1"):
            try:
                return msg.decode(enc)
            except Exception:
                continue
        return msg.decode("latin-1", "replace")
    return unicode(msg)  # noqa: F821


def _as_path(msg):
    if isinstance(msg, str):
        return msg
    if isinstance(msg, unicode):  # noqa: F821
        try:
            return msg.encode("mbcs")
        except Exception:
            return msg.encode("utf-8", "replace")
    return str(msg)


def _out(msg):
    try:
        print(_as_text(msg))
    except Exception:
        sys.stdout.write(repr(msg) + "\n")


def _dq_nome(valor):
    # Escapa aspas simples do SQL do ArcMap
    v = _as_text(valor).replace(u"'", u"''")
    return u'"nome" = \'{0}\''.format(v)


def _map_to_page(df, mx, my):
    """Coordenada de mapa → coordenada de pagina (cm) do layout ArcMap."""
    ext = df.extent
    w = float(ext.XMax - ext.XMin) or 1.0
    h = float(ext.YMax - ext.YMin) or 1.0
    px = float(df.elementPositionX) + (float(mx) - float(ext.XMin)) / w * float(df.elementWidth)
    py = float(df.elementPositionY) + (float(my) - float(ext.YMin)) / h * float(df.elementHeight)
    return px, py


def _xy_from_geom(geom):
    """Extrai (x, y) de PointGeometry / Point / Polygon do arcpy."""
    if geom is None:
        return None
    try:
        if hasattr(geom, "firstPoint") and geom.firstPoint is not None:
            return float(geom.firstPoint.X), float(geom.firstPoint.Y)
    except Exception:
        pass
    try:
        c = geom.centroid
        if hasattr(c, "firstPoint") and c.firstPoint is not None:
            return float(c.firstPoint.X), float(c.firstPoint.Y)
        return float(c.X), float(c.Y)
    except Exception:
        pass
    try:
        return float(geom.X), float(geom.Y)
    except Exception:
        return None


def _centroide_imovel(mxd, df_mapa, lon=None, lat=None):
    """Retorna PointGeometry no CRS de origem (4326 se lon/lat; senao CRS do data frame)."""
    if lon is not None and lat is not None:
        return arcpy.PointGeometry(
            arcpy.Point(float(lon), float(lat)), arcpy.SpatialReference(4326)
        )

    nomes = (
        u"PERIMETRO",
        u"Fazenda_Unificada",
        u"Fazenda Harmonia",
        u"ATP",
        u"AREA_TOTAL",
    )
    for df in arcpy.mapping.ListDataFrames(mxd):
        for nome in nomes:
            layers = arcpy.mapping.ListLayers(mxd, nome, df)
            if not layers:
                continue
            lyr = layers[0]
            try:
                ext = lyr.getExtent()
                if ext is None or ext.XMin is None:
                    continue
                cx = (float(ext.XMin) + float(ext.XMax)) / 2.0
                cy = (float(ext.YMin) + float(ext.YMax)) / 2.0
                sr = df.spatialReference
                return arcpy.PointGeometry(arcpy.Point(cx, cy), sr)
            except Exception:
                continue
    return None


def _project_to_df(geom, df):
    if geom is None or df is None:
        return None
    try:
        return geom.projectAs(df.spatialReference)
    except Exception:
        return geom


def _copiar_destino(origem, destino):
    """Copia binaria com retry — evita Errno 22 / lock do MapDocument."""
    origem = _as_path(origem)
    destino = _as_path(destino)
    ultimo = None
    for _ in range(8):
        try:
            with open(origem, "rb") as src:
                data = src.read()
            with open(destino, "wb") as dst:
                dst.write(data)
            return True, None
        except Exception as exc:
            ultimo = exc
            time.sleep(0.6)
    return False, _as_text(ultimo)


def _aplicar_queries(mxd, municipio, uf_nome, rel):
    for df in arcpy.mapping.ListDataFrames(mxd):
        for lyr in arcpy.mapping.ListLayers(mxd, "", df):
            nome = lyr.name or u""
            if not lyr.supports("DEFINITIONQUERY"):
                continue
            if nome == u"MUNICIPIOS":
                lyr.definitionQuery = _dq_nome(municipio)
                rel["queries"].append(u"{0}/MUNICIPIOS".format(df.name))
            elif nome == u"MUNICIPIOS_ENTORNO":
                lyr.definitionQuery = u""
            elif nome in (u"UF", u"Limite estadual") or (
                nome == u"Limite municipal" and df.name == u"MAPA"
            ):
                # Limite municipal no MAPA principal tambem segue o municipio da propriedade
                if u"municipal" in nome.lower() or nome == u"MUNICIPIOS":
                    lyr.definitionQuery = _dq_nome(municipio)
                    rel["queries"].append(u"{0}/{1}".format(df.name, nome))
                else:
                    lyr.definitionQuery = _dq_nome(uf_nome)
                    rel["queries"].append(u"{0}/{1}".format(df.name, nome))
            elif nome == u"Limite municipal":
                lyr.definitionQuery = _dq_nome(municipio)
                rel["queries"].append(u"{0}/{1}".format(df.name, nome))


def _zoom_minimapa(mxd, df_mini, municipio, padding=1.25):
    if df_mini is None:
        return False
    lyr = None
    for cand in arcpy.mapping.ListLayers(mxd, u"MUNICIPIOS", df_mini):
        lyr = cand
        break
    if lyr is None:
        for cand in arcpy.mapping.ListLayers(mxd, "", df_mini):
            if u"municipio" in (cand.name or u"").lower() or u"municipal" in (cand.name or u"").lower():
                try:
                    cand.definitionQuery = _dq_nome(municipio)
                except Exception:
                    pass
                lyr = cand
                break
    if lyr is None:
        return False
    try:
        lyr.definitionQuery = _dq_nome(municipio)
        ext = lyr.getExtent()
        if ext is None or ext.XMin is None:
            return False
        # padding
        cx = (float(ext.XMin) + float(ext.XMax)) / 2.0
        cy = (float(ext.YMin) + float(ext.YMax)) / 2.0
        half_w = (float(ext.XMax) - float(ext.XMin)) / 2.0 * float(padding)
        half_h = (float(ext.YMax) - float(ext.YMin)) / 2.0 * float(padding)
        df_mini.extent = arcpy.Extent(cx - half_w, cy - half_h, cx + half_w, cy + half_h)
        return True
    except Exception:
        return False


def _atualizar_textos(mxd, municipio, uf_sigla, rel):
    for t in arcpy.mapping.ListLayoutElements(mxd, "TEXT_ELEMENT"):
        nome = t.name or u""
        plain = (t.text or u"").replace(u"<bol>", u"").replace(u"</bol>", u"").strip()
        if nome == u"ROTULO_MUNICIPIO" or plain in (
            u"Vila Rica",
            u"Querência",
            u"Querencia",
        ):
            t.text = _as_text(municipio)
            if not t.name:
                t.name = u"ROTULO_MUNICIPIO"
            rel["textos"].append(u"ROTULO_MUNICIPIO={0}".format(municipio))
        elif nome == u"UF_SELO" or plain.upper() in (u"MT", u"GO", u"MS"):
            t.text = _as_text(uf_sigla).upper()
            if not t.name:
                t.name = u"UF_SELO"
            rel["textos"].append(u"UF_SELO={0}".format(uf_sigla))


def _mover_retangulo_e_guia(mxd, df_mapa, df_mini, geom_imovel, rel):
    """Move MINIMAPA_RETANGULO e reposiciona MINIMAPA_GUIA em L ate a moldura do MAPA."""
    if df_mini is None or geom_imovel is None:
        rel["avisos"].append(u"sem geometria/minimapa para mover retangulo")
        return

    g_proj = _project_to_df(geom_imovel, df_mini)
    xy = _xy_from_geom(g_proj)
    if xy is None:
        rel["avisos"].append(u"centroide invalido")
        return
    mx, my = xy

    px, py = _map_to_page(df_mini, mx, my)

    ret = None
    guia = None
    for g in arcpy.mapping.ListLayoutElements(mxd, "GRAPHIC_ELEMENT"):
        if g.name == u"MINIMAPA_RETANGULO":
            ret = g
        elif g.name == u"MINIMAPA_GUIA":
            guia = g

    # fallback: menor graphic dentro do minimapa
    if ret is None:
        x0 = float(df_mini.elementPositionX)
        y0 = float(df_mini.elementPositionY)
        x1 = x0 + float(df_mini.elementWidth)
        y1 = y0 + float(df_mini.elementHeight)
        cands = []
        for g in arcpy.mapping.ListLayoutElements(mxd, "GRAPHIC_ELEMENT"):
            w = float(g.elementWidth or 0)
            h = float(g.elementHeight or 0)
            if w <= 0 or h <= 0 or w > 1.2 or h > 1.2:
                continue
            cx = float(g.elementPositionX) + w / 2.0
            cy = float(g.elementPositionY) + h / 2.0
            if x0 - 0.3 <= cx <= x1 + 0.3 and y0 - 0.3 <= cy <= y1 + 0.3:
                cands.append(g)
        if cands:
            ret = min(cands, key=lambda g: float(g.elementWidth) * float(g.elementHeight))
            ret.name = u"MINIMAPA_RETANGULO"

    if ret is not None:
        rw = float(ret.elementWidth)
        rh = float(ret.elementHeight)
        ret.elementPositionX = px - rw / 2.0
        ret.elementPositionY = py - rh / 2.0
        rel["graficos"].append(
            u"MINIMAPA_RETANGULO -> ({0:.3f},{1:.3f})".format(
                ret.elementPositionX, ret.elementPositionY
            )
        )
        rx2 = ret.elementPositionX + rw
        ry2 = ret.elementPositionY + rh
    else:
        rel["avisos"].append(u"MINIMAPA_RETANGULO ausente")
        rx2, ry2 = px, py
        rw = rh = 0.3

    # Linha em L: do canto superior-direito do retangulo ate a base do MAPA (canto esquerdo)
    if df_mapa is None:
        return
    # alvo: meio da base do quadro do mapa principal
    tx = float(df_mapa.elementPositionX) + 0.15
    ty = float(df_mapa.elementPositionY)
    # origem L: topo-direita do retangulo
    ox = rx2
    oy = ry2

    if guia is None:
        for g in arcpy.mapping.ListLayoutElements(mxd, "GRAPHIC_ELEMENT"):
            if g.name in (u"MINIMAPA_RETANGULO", u"MAPA", u"MINIMAPA", u"UF_INSET", u"Layers"):
                continue
            w = float(g.elementWidth or 0)
            h = float(g.elementHeight or 0)
            if h > 3.0 or w > 3.0:
                guia = g
                guia.name = u"MINIMAPA_GUIA"
                break

    if guia is None:
        rel["avisos"].append(u"MINIMAPA_GUIA ausente — retangulo movido sozinho")
        return

    # Posiciona o bbox do graphic para cobrir a polilinha em L (ox,oy)→(tx,oy)→(tx,ty)
    # O graphic existente e uma linha em L; ao ajustar X/Y/W/H o traco acompanha o bbox.
    x_min = min(ox, tx)
    x_max = max(ox, tx)
    y_min = min(oy, ty)
    y_max = max(oy, ty)
    # Garante tamanho minimo
    if x_max - x_min < 0.2:
        x_max = x_min + 0.2
    if y_max - y_min < 0.2:
        y_max = y_min + 0.2
    guia.elementPositionX = x_min
    guia.elementPositionY = y_min
    guia.elementWidth = x_max - x_min
    guia.elementHeight = y_max - y_min
    rel["graficos"].append(
        u"MINIMAPA_GUIA L ({0:.2f},{1:.2f})->({2:.2f},{3:.2f})".format(ox, oy, tx, ty)
    )


def processar_um(caminho, municipio, uf_sigla, uf_nome, lon, lat, in_place, pasta_saida):
    caminho = _as_path(os.path.abspath(_as_path(caminho)))
    rel = {
        "arquivo": _as_text(caminho),
        "municipio": _as_text(municipio),
        "ok": False,
        "queries": [],
        "textos": [],
        "graficos": [],
        "avisos": [],
        "ms": 0,
    }
    t0 = time.time()
    pasta_tmp = tempfile.mkdtemp(prefix="mf_mun_")
    trabalho = _as_path(os.path.join(pasta_tmp, "work.mxd"))
    destino = caminho if in_place else _as_path(
        os.path.join(_as_path(pasta_saida), os.path.basename(caminho))
    )
    mxd = None
    try:
        shutil.copy2(caminho, trabalho)
        mxd = arcpy.mapping.MapDocument(trabalho)
        dfs = {df.name: df for df in arcpy.mapping.ListDataFrames(mxd)}
        df_mapa = dfs.get(u"MAPA")
        df_mini = dfs.get(u"MINIMAPA")
        if df_mapa is None or df_mini is None:
            lista = arcpy.mapping.ListDataFrames(mxd)
            # MAPA = maior area de pagina; MINIMAPA = menor (exceto inset UF geog)
            ordenados = sorted(
                lista,
                key=lambda d: float(d.elementWidth) * float(d.elementHeight),
                reverse=True,
            )
            if df_mapa is None and ordenados:
                df_mapa = ordenados[0]
            if df_mini is None and len(ordenados) > 1:
                # prefer web mercator
                web = [
                    d
                    for d in ordenados[1:]
                    if d.spatialReference and d.spatialReference.factoryCode == 3857
                ]
                df_mini = web[0] if web else ordenados[1]

        _aplicar_queries(mxd, municipio, uf_nome, rel)
        # Limite municipal no MAPA
        if df_mapa is not None:
            for lyr in arcpy.mapping.ListLayers(mxd, "", df_mapa):
                n = (lyr.name or u"").lower()
                if u"municipal" in n or lyr.name == u"MUNICIPIOS":
                    if lyr.supports("DEFINITIONQUERY"):
                        lyr.definitionQuery = _dq_nome(municipio)

        zoom_ok = _zoom_minimapa(mxd, df_mini, municipio)
        if not zoom_ok:
            rel["avisos"].append(u"zoom MINIMAPA falhou / sem extent")

        _atualizar_textos(mxd, municipio, uf_sigla, rel)

        geom = _centroide_imovel(mxd, df_mapa, lon, lat)
        _mover_retangulo_e_guia(mxd, df_mapa, df_mini, geom, rel)

        mxd.save()
        del mxd
        mxd = None
        time.sleep(0.4)
        ok_copy, err_copy = _copiar_destino(trabalho, destino)
        if not ok_copy:
            raise IOError(u"falha ao gravar destino: {0}".format(err_copy))
        rel["ok"] = True
    except Exception as exc:
        rel["avisos"].append(u"ERRO: {0}".format(_as_text(exc)))
        rel["ok"] = False
    finally:
        if mxd is not None:
            try:
                del mxd
            except Exception:
                pass
        try:
            shutil.rmtree(pasta_tmp, ignore_errors=True)
        except Exception:
            pass
        rel["ms"] = int((time.time() - t0) * 1000)
    return rel


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mxd", nargs="?", help="Arquivo .mxd unico")
    ap.add_argument("--municipio", default=None)
    ap.add_argument("--uf-sigla", default="MT")
    ap.add_argument("--uf-nome", default="Mato Grosso")
    ap.add_argument("--lon", type=float, default=None, help="Longitude WGS84 do imovel")
    ap.add_argument("--lat", type=float, default=None, help="Latitude WGS84 do imovel")
    ap.add_argument("--lote", default=None, help="JSON lista de jobs")
    ap.add_argument("--in-place", action="store_true")
    ap.add_argument("--saida", default="shared/templates/_municipio")
    ap.add_argument("-o", "--relatorio", default="relatorio_mudar_municipio.json")
    ap.add_argument(
        "--aplicar-acervo-harmonia",
        action="store_true",
        help="Aplica Vila Rica/MT em todos MXDs de Referencias_IMAP + templates",
    )
    args = ap.parse_args()

    jobs = []
    if args.lote:
        jobs = json.loads(open(args.lote, "rb").read().decode("utf-8"))
    elif args.aplicar_acervo_harmonia:
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
        pastas = [
            os.path.join(root, "Referencias_IMAP", "MXD"),
            os.path.join(root, "Referencias_IMAP", "Mapas"),
            os.path.join(root, "shared", "templates"),
        ]
        # Centroide aproximado Fazenda Harmonia (Vila Rica/MT) — lon/lat WGS84
        lon_h, lat_h = -52.15, -9.95
        for pasta in pastas:
            if not os.path.isdir(pasta):
                continue
            for dirpath, _d, files in os.walk(pasta):
                for f in files:
                    if f.lower().endswith(".mxd") and "__mf_tmp__" not in f:
                        jobs.append(
                            {
                                "arquivo": os.path.join(dirpath, f),
                                "municipio": u"Vila Rica",
                                "uf_sigla": u"MT",
                                "uf_nome": u"Mato Grosso",
                                "lon": lon_h,
                                "lat": lat_h,
                            }
                        )
    elif args.mxd and args.municipio:
        jobs = [
            {
                "arquivo": args.mxd,
                "municipio": args.municipio,
                "uf_sigla": args.uf_sigla,
                "uf_nome": args.uf_nome,
                "lon": args.lon,
                "lat": args.lat,
            }
        ]
    else:
        ap.print_help()
        return 1

    resultados = []
    for i, job in enumerate(jobs, 1):
        arq = job["arquivo"]
        _out(u"[{0}/{1}] {2} -> {3}".format(i, len(jobs), _as_text(arq), job["municipio"]))
        r = processar_um(
            arq,
            job["municipio"],
            job.get("uf_sigla") or u"MT",
            job.get("uf_nome") or u"Mato Grosso",
            job.get("lon"),
            job.get("lat"),
            args.in_place,
            args.saida,
        )
        resultados.append(r)
        _out(u"  ok={0} ms={1}".format(r["ok"], r["ms"]))
        for a in r["avisos"][:4]:
            _out(u"  ! {0}".format(a))

    resumo = {
        "total": len(resultados),
        "ok": sum(1 for r in resultados if r["ok"]),
        "falhas": sum(1 for r in resultados if not r["ok"]),
        "resultados": resultados,
    }
    with open(args.relatorio, "wb") as f:
        f.write(json.dumps(resumo, ensure_ascii=False, indent=2).encode("utf-8"))
    print("Relatorio:", args.relatorio)
    print("resumo: ok={0}/{1} falhas={2}".format(resumo["ok"], resumo["total"], resumo["falhas"]))
    return 0 if resumo["falhas"] == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
