# -*- coding: utf-8 -*-
"""Fecha pendências B1/B2 do template Dinâmica no ArcMap (Python 2.7).

Corrige camadas quebradas no template versionado:
- materializa ``shared/templates/SHP/`` a partir da pasta Harmonia (ou --origem-shp)
- reconecta ``AC`` → ``AREA_CONSOLIDADA.shp``
- reconecta ``PERIMETRO`` → ``CAR_ATP.shp`` (cópia de ATP.shp)
- reconecta camadas IBGE (MINIMAPA / UF_INSET) ao ``shared/bases/ibge`` local
- aponta ``LOGO`` para ``shared/templates/recursos/logo_imap_tom_escuro.png``

Uso (ArcMap fechado):
  C:\\Python27\\ArcGIS10.8\\python.exe ferramentas/fechar_m2_template_arcpy.py
  C:\\Python27\\ArcGIS10.8\\python.exe ferramentas/fechar_m2_template_arcpy.py --harmonia \"C:\\...\\Harmonia\"
"""
from __future__ import print_function

import argparse
import json
import os
import shutil
import sys

try:
    import arcpy
except ImportError:
    sys.stderr.write("arcpy indisponivel — execute com Python 2.7 do ArcMap\n")
    sys.exit(1)

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
MXD_PADRAO = os.path.join(REPO, "shared", "templates", "Dinamica_retrato.mxd")
SHP_TEMPLATE = os.path.join(REPO, "shared", "templates", "SHP")
IBGE = os.path.join(REPO, "shared", "bases", "ibge")
LOGO = os.path.join(REPO, "shared", "templates", "recursos", "logo_imap_tom_escuro.png")

EXT_SHP = (".shp", ".shx", ".dbf", ".prj", ".cpg", ".sbn", ".sbx", ".xml", ".qpj")


def _u(s):
    if s is None:
        return None
    if isinstance(s, unicode):  # noqa: F821
        return s
    return unicode(s, "utf-8")  # noqa: F821


def _achar_harmonia(raiz_downloads=None):
    raiz = raiz_downloads or os.path.join(os.path.expanduser("~"), "Downloads", "Analise_de_area")
    if not os.path.isdir(raiz):
        return None
    for nome in os.listdir(raiz):
        caminho = os.path.join(raiz, nome)
        if not os.path.isdir(caminho):
            continue
        if "harmonia" in nome.lower():
            return caminho
    return None


def _achar_shp_processado(pasta_harmonia, nome_base):
    padroes = [
        os.path.join(pasta_harmonia, "Arquivo Processado (1)", nome_base + ".shp"),
        os.path.join(pasta_harmonia, "Arquivo Processado", nome_base + ".shp"),
    ]
    for padrao in padroes:
        if os.path.isfile(padrao):
            return padrao
    alvo = nome_base.lower() + ".shp"
    for dirpath, _dirnames, filenames in os.walk(pasta_harmonia):
        for fn in filenames:
            if fn.lower() == alvo:
                return os.path.join(dirpath, fn)
    return None


def _copiar_shape(origem_shp, destino_shp):
    base_origem = os.path.splitext(origem_shp)[0]
    base_destino = os.path.splitext(destino_shp)[0]
    copiados = []
    for ext in EXT_SHP:
        src = base_origem + ext
        if os.path.isfile(src):
            dst = base_destino + ext
            shutil.copy2(src, dst)
            copiados.append(os.path.basename(dst))
    return copiados


def materializar_shp_template(origem_harmonia):
    if not os.path.isdir(SHP_TEMPLATE):
        os.makedirs(SHP_TEMPLATE)
    relatorio = {"origem_harmonia": origem_harmonia, "copias": []}

    mapa = (
        ("AREA_CONSOLIDADA.shp", "AREA_CONSOLIDADA"),
        ("CAR_ATP.shp", "ATP"),
    )
    for destino_nome, origem_nome in mapa:
        origem = _achar_shp_processado(origem_harmonia, origem_nome)
        if not origem:
            relatorio.setdefault("avisos", []).append(
                "shape ausente: {0} (procurado como {1})".format(destino_nome, origem_nome)
            )
            continue
        destino = os.path.join(SHP_TEMPLATE, destino_nome)
        copiados = _copiar_shape(origem, destino)
        relatorio["copias"].append(
            {"destino": destino_nome, "origem": origem, "arquivos": copiados}
        )
    return relatorio


def _reconectar(lyr, pasta, dataset):
    try:
        lyr.replaceDataSource(_u(pasta), "SHAPEFILE_WORKSPACE", _u(dataset), True)
        return True, None
    except Exception as exc:
        return False, _u(str(exc))


def _quebradas_mxd(mxd):
    try:
        return [(_u(l.name), _u(l.dataFrame.name)) for l in arcpy.mapping.ListBrokenDataSources(mxd)]
    except Exception:
        return []


def _fixar_ac(mxd, df, aplicados, erros):
    """AC dentro de BASEMAP nao suporta replaceDataSource — recria no MAPA e remove o grupo."""
    alvo_ac = os.path.join(SHP_TEMPLATE, "AREA_CONSOLIDADA.shp")
    if not os.path.isfile(alvo_ac):
        return

    ac_raiz = None
    ac_em_basemap = None
    basemap_grp = None
    for lyr in arcpy.mapping.ListLayers(mxd, "", df):
        ln = lyr.longName or ""
        if lyr.name == "BASEMAP" and lyr.isGroupLayer:
            basemap_grp = lyr
        if lyr.name == "AC":
            if ln == "AC":
                ac_raiz = lyr
            elif "BASEMAP" in ln:
                ac_em_basemap = lyr

    if ac_raiz and not ac_raiz.isBroken:
        aplicados.append("AC ja ok na raiz do MAPA")
        if basemap_grp and ac_em_basemap:
            arcpy.mapping.RemoveLayer(df, basemap_grp)
            aplicados.append("BASEMAP removido (AC fantasma em grupo)")
        return

    if ac_em_basemap or (basemap_grp and not ac_raiz):
        nova = arcpy.mapping.Layer(alvo_ac)
        nova.name = "AC"
        nova.visible = True
        arcpy.mapping.AddLayer(df, nova, "TOP")
        aplicados.append("AC recriada de SHP\\AREA_CONSOLIDADA.shp")
        if basemap_grp:
            arcpy.mapping.RemoveLayer(df, basemap_grp)
            aplicados.append("BASEMAP removido (grupo com AC quebrada)")
        return

    for lyr in arcpy.mapping.ListLayers(mxd, "AC", df):
        if lyr.supports("DATASOURCE"):
            ok, err = _reconectar(lyr, SHP_TEMPLATE, "AREA_CONSOLIDADA")
            if ok:
                aplicados.append("AC -> SHP\\AREA_CONSOLIDADA.shp")
            else:
                erros.append("AC: " + (err or "falhou"))
        break


def corrigir_template(mxd_caminho, dry_run=False):
    aplicados = []
    avisos = []
    erros = []

    mxd = arcpy.mapping.MapDocument(mxd_caminho)
    try:
        if not mxd.relativePaths:
            mxd.relativePaths = True
            aplicados.append("relativePaths=True")

        # LOGO relativo ao template
        if os.path.isfile(LOGO):
            for pic in arcpy.mapping.ListLayoutElements(mxd, "PICTURE_ELEMENT"):
                if (pic.name or "") == "LOGO":
                    rel_logo = os.path.relpath(LOGO, os.path.dirname(mxd_caminho))
                    pic.sourceImage = rel_logo.replace("/", "\\")
                    aplicados.append("LOGO -> " + pic.sourceImage)

        alvo_ac = os.path.join(SHP_TEMPLATE, "AREA_CONSOLIDADA.shp")
        alvo_per = os.path.join(SHP_TEMPLATE, "CAR_ATP.shp")
        if not os.path.isfile(alvo_ac):
            avisos.append("AREA_CONSOLIDADA ausente em SHP/ — rode materializar antes")
        if not os.path.isfile(alvo_per):
            avisos.append("CAR_ATP ausente em SHP/ — rode materializar antes")

        dfs_mapa = arcpy.mapping.ListDataFrames(mxd, "MAPA")
        if dfs_mapa:
            _fixar_ac(mxd, dfs_mapa[0], aplicados, erros)

        for df in arcpy.mapping.ListDataFrames(mxd):
            for lyr in arcpy.mapping.ListLayers(mxd, "", df):
                nome = lyr.name or ""
                if nome == "AC":
                    continue
                if nome == "PERIMETRO" and os.path.isfile(alvo_per):
                    ok, err = _reconectar(lyr, SHP_TEMPLATE, "CAR_ATP")
                    if ok:
                        aplicados.append("PERIMETRO -> SHP\\CAR_ATP.shp")
                    else:
                        erros.append("PERIMETRO: " + (err or "falhou"))
                elif nome in ("MUNICIPIOS", "MUNICIPIOS_ENTORNO") and os.path.isfile(
                    os.path.join(IBGE, "lml_municipio_a.shp")
                ):
                    ok, err = _reconectar(lyr, IBGE, "lml_municipio_a")
                    if ok:
                        aplicados.append("{0} -> ibge\\lml_municipio_a".format(nome))
                    elif lyr.isBroken:
                        erros.append(nome + ": " + (err or "falhou"))
                elif nome == "UF" and os.path.isfile(os.path.join(IBGE, "lml_uf_a.shp")):
                    dataset = "lml_uf_a"
                    ok, err = _reconectar(lyr, IBGE, dataset)
                    if ok:
                        aplicados.append("UF ({0}) -> ibge\\lml_uf_a".format(df.name))
                    elif lyr.isBroken:
                        erros.append("UF({0}): ".format(df.name) + (err or "falhou"))

        quebradas_antes = _quebradas_mxd(mxd)
        if not dry_run:
            mxd.save()
        quebradas_depois = _quebradas_mxd(mxd)
    finally:
        del mxd

    return {
        "aplicados": aplicados,
        "avisos": avisos,
        "erros": erros,
        "quebradas_antes": quebradas_antes,
        "quebradas_depois": quebradas_depois,
    }


def _json_safe(obj):
    if isinstance(obj, dict):
        return {_json_safe(k): _json_safe(v) for k, v in obj.iteritems()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(x) for x in obj]
    if isinstance(obj, str):
        try:
            return obj.decode("utf-8")
        except UnicodeDecodeError:
            return obj.decode("latin-1")
    return obj


def main():
    parser = argparse.ArgumentParser(description="Fecha template M2 (AC + paths relativos)")
    parser.add_argument("--mxd", default=MXD_PADRAO, help="MXD do template")
    parser.add_argument(
        "--harmonia",
        help="Pasta do projeto Harmonia (default: auto em Downloads/Analise_de_area)",
    )
    parser.add_argument("--sem-materializar", action="store_true", help="Nao copia SHP/")
    parser.add_argument("--dry-run", action="store_true", help="Nao salva o MXD")
    parser.add_argument("-o", "--saida-json", help="Gravar relatorio JSON")
    args = parser.parse_args()

    if not os.path.isfile(args.mxd):
        sys.stderr.write("MXD ausente: {0}\n".format(args.mxd))
        return 1

    relatorio = {"mxd": args.mxd, "repo": REPO}

    if not args.sem_materializar:
        harmonia = args.harmonia or _achar_harmonia()
        if not harmonia:
            sys.stderr.write("Pasta Harmonia nao encontrada — use --harmonia\n")
            return 2
        relatorio["materializar"] = materializar_shp_template(harmonia)

    relatorio["corrigir"] = corrigir_template(args.mxd, dry_run=args.dry_run)

    payload = json.dumps(_json_safe(relatorio), ensure_ascii=False, indent=2).encode("utf-8")
    if args.saida_json:
        with open(args.saida_json, "wb") as fh:
            fh.write(payload)
        print("Relatorio: " + args.saida_json)
    else:
        sys.stdout.write(payload)
        sys.stdout.write("\n")

    depois = relatorio["corrigir"]["quebradas_depois"]
    if relatorio["corrigir"]["erros"]:
        return 3
    # BASEMAP vazio nao conta — so camadas com nome
    criticas = [q for q in depois if q[0] and q[0] != "BASEMAP"]
    if criticas and not args.dry_run:
        print("Ainda quebradas:", criticas, file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
