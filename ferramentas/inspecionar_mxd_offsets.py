#!/usr/bin/env python3
"""Localiza valores float64 no .mxd para registrar offsets no MANIFEST (preparação B1/B2)."""
from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path


def buscar_float64(caminho: Path, valor: float, *, tolerancia: float = 1e-6) -> list[int]:
    dados = caminho.read_bytes()
    alvo = struct.pack("<d", valor)
    offsets: list[int] = []
    inicio = 0
    while True:
        idx = dados.find(alvo, inicio)
        if idx < 0:
            break
        offsets.append(idx)
        inicio = idx + 1
    if not offsets:
        # fallback com tolerância numérica
        for off in range(0, len(dados) - 7):
            lido = struct.unpack("<d", dados[off : off + 8])[0]
            if abs(lido - valor) < tolerancia:
                offsets.append(off)
    return offsets


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspeciona offsets float64 em .mxd")
    parser.add_argument("mxd", type=Path, help="Caminho do .mxd")
    parser.add_argument(
        "--sentinela",
        type=float,
        action="append",
        default=[111111.0, 222222.0, 333333.0, 444444.0, 987654.0],
        help="Valores sentinela a procurar (repetível)",
    )
    args = parser.parse_args()
    if not args.mxd.is_file():
        print(f"Arquivo não encontrado: {args.mxd}", file=sys.stderr)
        return 1

    print(f"Arquivo: {args.mxd} ({args.mxd.stat().st_size} bytes)")
    for valor in args.sentinela:
        offsets = buscar_float64(args.mxd, valor)
        print(f"  {valor!r}: {len(offsets)} ocorrência(s)")
        for off in offsets[:20]:
            print(f"    offset {off}")
        if len(offsets) > 20:
            print(f"    … +{len(offsets) - 20} omitidas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
