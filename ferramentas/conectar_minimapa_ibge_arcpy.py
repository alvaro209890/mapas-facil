# -*- coding: utf-8 -*-
"""Reconecta camadas do minimapa (e limites no mapa) aos shapefiles IBGE do repo.

Python 2.7 / ArcMap::

    C:\\Python27\\ArcGIS10.8\\python.exe ferramentas/conectar_minimapa_ibge_arcpy.py \\
        Referencias_IMAP/MXD shared/templates --in-place -o relatorio_conectar_minimapa.json

O que faz por MXD:
- Aponta MUNICIPIOS / Limite municipal / lml_municipio_a → shared/bases/ibge/lml_municipio_a
- Aponta UF / Limite estadual / lml_unidade_federacao_a → shared/bases/ibge/lml_uf_a
- Renomeia data frames candidatos → MAPA / MINIMAPA / UF_INSET
- Nomeia grafico fino → MINIMAPA_GUIA; retangulo no minimapa → MINIMAPA_RETANGULO
- Nomeia textos Vila Rica/MT → ROTULO_MUNICIPIO / UF_SELO
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


def _repo_ibge_dir():
    aqui = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    return os.path.join(aqui, "shared", "bases", "ibge")


def _eh_municipio_lyr(lyr):
    blob = (lyr.name or u"").lower()
    try:
        ds = (lyr.datasetName or u"").lower() if lyr.supports("DATASETNAME") else u""
    except Exception:
        ds = u""
    try:
        ws = (lyr.workspacePath or u"").lower() if lyr.supports("DATASOURCE") else u""
    except Exception:
        ws = u""
    return (
        u"municipio" in blob
        or u"municipal" in blob
        or u"lml_municipio" in blob
        or u"lml_municipio" in ds
        or u"municipio" in ds
        or (u"ibge" in ws and u"municipio" in ds)
    )


def _eh_uf_lyr(lyr):
    blob = (lyr.name or u"").lower()
    try:
        ds = (lyr.datasetName or u"").lower() if lyr.supports("DATASETNAME") else u""
    except Exception:
        ds = u""
    return (
        blob in (u"uf", u"limite estadual", u"estado")
        or u"unidade_federacao" in blob
        or u"unidade_federacao" in ds
        or u"lml_uf" in ds
        or ds == u"lml_uf_a"
    )


def _classificar_dfs(dfs):
    """MAPA = UTM/maior escala detalhe; MINIMAPA = webmerc menor; UF_INSET = geog pequeno."""
    infos = []
    for df in dfs:
        sr = df.spatialReference.factoryCode if df.spatialReference else 0
        area = float(df.elementWidth) * float(df.elementHeight)
        infos.append({"df": df, "sr": sr, "area": area, "scale": float(df.scale or 0)})
    # MAPA: prefer 3198x / alta escala detalhada (scale menor = mais zoom)
    utm = [i for i in infos if 31960 <= i["sr"] <= 31990] or [
        i for i in infos if i["sr"] not in (3857, 4326, 4674) and i["scale"] and i["scale"] < 500000
    ]
    mapa = min(utm, key=lambda c: c["scale"]) if utm else max(infos, key=lambda c: c["area"])
    resto = [i for i in infos if i["df"] is not mapa["df"]]
    web = [i for i in resto if i["sr"] == 3857]
    minimapa = min(web, key=lambda c: c["area"]) if web else (
        min(resto, key=lambda c: c["area"]) if resto else None
    )
    resto2 = [i for i in resto if minimapa is None or i["df"] is not minimapa["df"]]
    uf_inset = None
    geog = [i for i in resto2 if i["sr"] in (4326, 4674, 4618)]
    if geog:
        uf_inset = min(geog, key=lambda c: c["area"])
    return (
        mapa["df"],
        minimapa["df"] if minimapa else None,
        uf_inset["df"] if uf_inset else None,
    )


def _reconectar(lyr, pasta_ibge, dataset):
    try:
        lyr.replaceDataSource(pasta_ibge, "SHAPEFILE_WORKSPACE", dataset, True)
        return True, None
    except Exception as exc:
        return False, _as_text(exc)


def _nomear_graficos(mxd, df_minimapa, rel):
    graficos = []
    for g in arcpy.mapping.ListLayoutElements(mxd, "GRAPHIC_ELEMENT"):
        nome = g.name or u""
        # ignora data frames espelhados como graphic
        if nome in (u"MAPA", u"MINIMAPA", u"Layers", u"New Data Frame 2", u"UF_INSET"):
            continue
        w = float(g.elementWidth or 0)
        h = float(g.elementHeight or 0)
        if w <= 0 or h <= 0:
            continue
        graficos.append({"el": g, "w": w, "h": h, "x": float(g.elementPositionX), "y": float(g.elementPositionY), "ratio": min(w, h) / max(w, h)})

    # retangulo: pequeno, perto/dentro do minimapa
    ret_cands = [g for g in graficos if g["w"] < 1.2 and g["h"] < 1.2 and g["ratio"] > 0.4]
    if df_minimapa is not None:
        x0 = float(df_minimapa.elementPositionX)
        y0 = float(df_minimapa.elementPositionY)
        x1 = x0 + float(df_minimapa.elementWidth)
        y1 = y0 + float(df_minimapa.elementHeight)

        def perto(g):
            cx = g["x"] + g["w"] / 2.0
            cy = g["y"] + g["h"] / 2.0
            return (x0 - 0.5) <= cx <= (x1 + 0.5) and (y0 - 0.5) <= cy <= (y1 + 0.5)

        ret_cands = [g for g in ret_cands if perto(g)] or ret_cands

    if len(ret_cands) == 1:
        ret_cands[0]["el"].name = u"MINIMAPA_RETANGULO"
        rel["renomeados"].append(u"graphic -> MINIMAPA_RETANGULO")
    elif len(ret_cands) > 1:
        # menor area
        best = min(ret_cands, key=lambda g: g["w"] * g["h"])
        best["el"].name = u"MINIMAPA_RETANGULO"
        rel["renomeados"].append(u"graphic(menor) -> MINIMAPA_RETANGULO")
    else:
        rel["avisos"].append(u"MINIMAPA_RETANGULO nao identificado")

    # guia: bbox grande / alongado cobrindo do minimapa para cima
    guia_cands = [
        g
        for g in graficos
        if g["el"].name != u"MINIMAPA_RETANGULO"
        and (g["h"] > 3.0 or g["w"] > 3.0)
        and g["ratio"] < 0.95
    ]
    if len(guia_cands) >= 1:
        # preferir o que comeca perto do canto do minimapa
        best = max(guia_cands, key=lambda g: g["h"] * g["w"])
        best["el"].name = u"MINIMAPA_GUIA"
        rel["renomeados"].append(u"graphic -> MINIMAPA_GUIA")
    else:
        # fallback: mais fino
        finos = [g for g in graficos if g["el"].name != u"MINIMAPA_RETANGULO" and g["ratio"] < 0.35]
        if len(finos) == 1:
            finos[0]["el"].name = u"MINIMAPA_GUIA"
            rel["renomeados"].append(u"graphic(fino) -> MINIMAPA_GUIA")
        else:
            rel["avisos"].append(u"MINIMAPA_GUIA nao identificado")


def _nomear_textos(mxd, rel):
    for t in arcpy.mapping.ListLayoutElements(mxd, "TEXT_ELEMENT"):
        tx = (t.text or u"").strip()
        if not tx:
            continue
        # remove tags
        plain = tx.replace(u"<bol>", u"").replace(u"</bol>", u"").strip()
        if plain.upper() in (u"MT", u"GO", u"MS", u"RO", u"PA", u"TO", u"AM", u"AC", u"RR", u"AP"):
            if not t.name:
                t.name = u"UF_SELO"
                rel["renomeados"].append(u"text MT -> UF_SELO")
        elif len(plain) >= 3 and len(plain) <= 40 and u" " not in plain[:2]:
            # candidato a municipio (ex. Vila Rica)
            if plain[0].isupper() and not plain.startswith(u"METADADOS") and not plain.startswith(u"Sat"):
                # so nomeia se ainda sem nome e parece rotulo curto
                if not t.name and plain.count(u" ") <= 3 and not any(
                    k in plain.lower() for k in (u"fazenda", u"dinamica", u"escala", u"fonte", u"datum", u"area")
                ):
                    # evita titulo
                    if t.elementPositionY < 3.5:  # faixa inferior tipica (cm)
                        t.name = u"ROTULO_MUNICIPIO"
                        rel["renomeados"].append(u"text -> ROTULO_MUNICIPIO ({0})".format(plain))


def processar_mxd(caminho, pasta_ibge, in_place, pasta_saida):
    caminho = _as_path(os.path.abspath(_as_path(caminho)))
    rel = {
        "arquivo": _as_text(caminho),
        "ok": False,
        "reconectados": [],
        "renomeados": [],
        "avisos": [],
        "ms": 0,
    }
    t0 = time.time()
    pasta_tmp = tempfile.mkdtemp(prefix="mf_minimap_")
    trabalho = _as_path(os.path.join(pasta_tmp, "work.mxd"))
    destino = caminho if in_place else _as_path(
        os.path.join(_as_path(pasta_saida), os.path.basename(caminho))
    )
    mxd = None
    try:
        shutil.copy2(caminho, trabalho)
        mxd = arcpy.mapping.MapDocument(trabalho)
        try:
            mxd.relativePaths = True
        except Exception:
            pass

        dfs = arcpy.mapping.ListDataFrames(mxd)
        df_mapa, df_mini, df_uf = _classificar_dfs(dfs)
        if df_mapa is not None and df_mapa.name != u"MAPA":
            antigo = df_mapa.name
            df_mapa.name = u"MAPA"
            rel["renomeados"].append(u"df {0} -> MAPA".format(antigo))
        if df_mini is not None and df_mini.name != u"MINIMAPA":
            antigo = df_mini.name
            df_mini.name = u"MINIMAPA"
            rel["renomeados"].append(u"df {0} -> MINIMAPA".format(antigo))
        if df_uf is not None and df_uf.name not in (u"UF_INSET", u"MINIMAPA"):
            antigo = df_uf.name
            df_uf.name = u"UF_INSET"
            rel["renomeados"].append(u"df {0} -> UF_INSET".format(antigo))

        for df in arcpy.mapping.ListDataFrames(mxd):
            mun_layers = []
            for lyr in list(arcpy.mapping.ListLayers(mxd, "", df)):
                if _eh_municipio_lyr(lyr):
                    mun_layers.append(lyr)
                elif _eh_uf_lyr(lyr):
                    ok, err = _reconectar(lyr, pasta_ibge, "lml_uf_a")
                    if ok:
                        rel["reconectados"].append(
                            u"{0}/{1} -> lml_uf_a".format(df.name, lyr.name)
                        )
                        if lyr.name not in (u"UF", u"Limite estadual"):
                            antigo = lyr.name
                            try:
                                lyr.name = u"UF" if df.name == u"UF_INSET" else u"UF"
                                rel["renomeados"].append(
                                    u"lyr {0} -> UF".format(antigo)
                                )
                            except Exception:
                                pass
                    else:
                        rel["avisos"].append(u"UF falhou ({0}): {1}".format(lyr.name, err))

            # No minimapa: camada COM definition query = MUNICIPIOS (destaque);
            # sem query = MUNICIPIOS_ENTORNO (bege).
            for lyr in mun_layers:
                ok, err = _reconectar(lyr, pasta_ibge, "lml_municipio_a")
                if not ok:
                    rel["avisos"].append(
                        u"municipio falhou ({0}): {1}".format(lyr.name, err)
                    )
                    continue
                rel["reconectados"].append(
                    u"{0}/{1} -> lml_municipio_a".format(df.name, lyr.name)
                )
                try:
                    dq = lyr.definitionQuery if lyr.supports("DEFINITIONQUERY") else u""
                except Exception:
                    dq = u""
                antigo = lyr.name
                try:
                    if df.name == u"MINIMAPA":
                        if dq:
                            lyr.name = u"MUNICIPIOS"
                        else:
                            lyr.name = u"MUNICIPIOS_ENTORNO"
                    else:
                        lyr.name = u"MUNICIPIOS"
                    if antigo != lyr.name:
                        rel["renomeados"].append(
                            u"lyr {0} -> {1}".format(antigo, lyr.name)
                        )
                except Exception as exc:
                    rel["avisos"].append(
                        u"nao renomeou {0}: {1}".format(antigo, _as_text(exc))
                    )

        _nomear_graficos(mxd, df_mini, rel)
        _nomear_textos(mxd, rel)

        mxd.save()
        del mxd
        mxd = None
        shutil.copy2(trabalho, destino)
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


def _coletar(caminhos):
    out = []
    for c in caminhos:
        c = os.path.abspath(c)
        if os.path.isfile(c) and c.lower().endswith(".mxd"):
            out.append(c)
        elif os.path.isdir(c):
            for root, _d, files in os.walk(c):
                for f in files:
                    if f.lower().endswith(".mxd") and "__mf_tmp__" not in f:
                        out.append(os.path.join(root, f))
    vistos = set()
    uniq = []
    for p in sorted(out):
        if p not in vistos:
            vistos.add(p)
            uniq.append(p)
    return uniq


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("caminhos", nargs="+")
    ap.add_argument("--in-place", action="store_true")
    ap.add_argument("--ibge", default=None, help="Pasta com lml_municipio_a.shp / lml_uf_a.shp")
    ap.add_argument("-o", "--relatorio", default="relatorio_conectar_minimapa.json")
    ap.add_argument("--saida", default="shared/templates/_minimapa_ibge")
    args = ap.parse_args()

    pasta_ibge = _as_path(args.ibge or _repo_ibge_dir())
    if not os.path.isfile(os.path.join(pasta_ibge, "lml_municipio_a.shp")):
        sys.stderr.write("lml_municipio_a.shp ausente em {0}\n".format(pasta_ibge))
        sys.exit(1)
    if not os.path.isfile(os.path.join(pasta_ibge, "lml_uf_a.shp")):
        sys.stderr.write("lml_uf_a.shp ausente em {0}\n".format(pasta_ibge))
        sys.exit(1)

    mxds = _coletar(args.caminhos)
    _out(u"IBGE: {0}".format(_as_text(pasta_ibge)))
    _out(u"MXDs: {0}".format(len(mxds)))
    resultados = []
    for i, m in enumerate(mxds, 1):
        _out(u"[{0}/{1}] {2}".format(i, len(mxds), _as_text(m)))
        r = processar_mxd(m, pasta_ibge, args.in_place, args.saida)
        resultados.append(r)
        _out(
            u"  ok={0} recon={1} ms={2}".format(
                r["ok"], len(r["reconectados"]), r["ms"]
            )
        )
        for a in r["avisos"][:3]:
            _out(u"  ! {0}".format(a))

    resumo = {
        "total": len(resultados),
        "ok": sum(1 for r in resultados if r["ok"]),
        "falhas": sum(1 for r in resultados if not r["ok"]),
        "pasta_ibge": _as_text(pasta_ibge),
        "resultados": resultados,
    }
    with open(args.relatorio, "wb") as f:
        f.write(json.dumps(resumo, ensure_ascii=False, indent=2).encode("utf-8"))
    print("Relatorio:", args.relatorio)
    print(
        "resumo: ok={0}/{1} falhas={2}".format(
            resumo["ok"], resumo["total"], resumo["falhas"]
        )
    )
    return 0 if resumo["falhas"] == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
