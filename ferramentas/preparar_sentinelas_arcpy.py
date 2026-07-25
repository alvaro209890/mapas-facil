# -*- coding: utf-8 -*-
"""Grava extent/escala sentinela no data frame MAPA (calibração de offsets B2)."""
from __future__ import print_function

import argparse
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
        mxd.save()
    finally:
        del mxd
    print("Salvo:", mxd_saida)
    print("Extent:", EXTENT_SENTINELA)
    print("Escala:", ESCALA_SENTINELA)
    print("Proximo passo:")
    print(
        "  python ferramentas/inspecionar_mxd_offsets.py \"{0}\"".format(mxd_saida)
    )


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
