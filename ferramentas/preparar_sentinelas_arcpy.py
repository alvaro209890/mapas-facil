# -*- coding: utf-8 -*-
"""Grava extent/escala sentinela no data frame MAPA (calibração de offsets B2)."""
from __future__ import print_function

import argparse
import os
import shutil
import sys

try:
    import arcpy
except ImportError:
    sys.stderr.write("arcpy indisponivel — execute com Python 2.7 do ArcMap\n")
    sys.exit(1)

EXTENT_SENTINELA = (111111.0, 222222.0, 333333.0, 444444.0)
ESCALA_SENTINELA = 987654.0


def aplicar(mxd_entrada, mxd_saida, df_nome="MAPA"):
    if os.path.abspath(mxd_entrada) != os.path.abspath(mxd_saida):
        shutil.copy2(mxd_entrada, mxd_saida)
    mxd = arcpy.mapping.MapDocument(mxd_saida)
    try:
        mxd.relativePaths = True
        dfs = arcpy.mapping.ListDataFrames(mxd, df_nome)
        if not dfs:
            raise RuntimeError("Data frame nao encontrado: {0}".format(df_nome))
        df = dfs[0]
        df.extent = arcpy.Extent(*EXTENT_SENTINELA)
        df.scale = ESCALA_SENTINELA
        # ArcMap ajusta o extent pela proporcao do data frame — as sentinelas
        # reais no binario sao as que o arcpy devolve depois do save.
        e = df.extent
        extent_real = (float(e.XMin), float(e.YMin), float(e.XMax), float(e.YMax))
        escala_real = float(df.scale)
        mxd.save()
    finally:
        del mxd
    print("Salvo:", mxd_saida)
    print("Extent pedido:", EXTENT_SENTINELA)
    print("Extent real (pos-aspecto):", extent_real)
    print("Escala:", escala_real)
    sidecar = mxd_saida + ".sentinelas.json"
    try:
        import json

        with open(sidecar, "w") as fh:
            json.dump(
                {
                    "extent_pedido": list(EXTENT_SENTINELA),
                    "extent": list(extent_real),
                    "escala": escala_real,
                },
                fh,
                indent=2,
            )
        print("Sidecar:", sidecar)
    except Exception as exc:
        print("Nao gravou sidecar:", exc)
    print("Proximo passo:")
    print(
        "  python ferramentas/inspecionar_mxd_offsets.py \"{0}\"".format(mxd_saida)
    )
    print(
        "  python ferramentas/registrar_template.py dinamica_retrato \"{0}\"".format(mxd_saida)
    )
    return extent_real, escala_real


def main():
    parser = argparse.ArgumentParser(
        description="Aplica valores sentinela para descoberta de offsets no .mxd"
    )
    parser.add_argument("mxd", help="MXD de entrada (sera copiado)")
    parser.add_argument(
        "-o",
        "--saida",
        help="MXD de saida (padrao: sobrescreve entrada apos backup .bak)",
    )
    parser.add_argument("--df", default="MAPA", help="Nome do data frame (padrao: MAPA)")
    args = parser.parse_args()

    saida = args.saida or args.mxd
    if saida == args.mxd:
        backup = args.mxd + ".bak"
        shutil.copy2(args.mxd, backup)
        print("Backup:", backup)

    aplicar(args.mxd, saida, df_nome=args.df)
    return 0


if __name__ == "__main__":
    sys.exit(main())
