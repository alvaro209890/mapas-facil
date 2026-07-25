#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Recupera arquivos de um ZIP truncado (sem central directory / EOCD).

OneDrive e downloads interrompidos costumam gerar exatamente isso:
  - cabeçalhos locais (PK\\x03\\x04) intactos no início
  - arquivo cortado no meio de uma entrada
  - unzip/7z falham com "End-of-central-directory signature not found"

Uso:
    python3 ferramentas/recuperar_zip_truncado.py ARQUIVO.zip -o PASTA_SAIDA

Só grava entradas cujo tamanho bate com o data descriptor (completas).
A última entrada truncada é reportada e, por padrão, NÃO é gravada
(use --incluir-truncados para inspecionar).
"""
from __future__ import annotations

import argparse
import struct
import sys
import zlib
from pathlib import Path

LOCAL = b"PK\x03\x04"
DD = b"PK\x07\x08"
CENTRAL = b"PK\x01\x02"


def parse_entries(data: bytes):
    n = len(data)
    pos = 0
    entries = []
    truncated = None

    while pos + 30 <= n:
        if data[pos : pos + 4] != LOCAL:
            nxt = data.find(LOCAL, pos + 1)
            if nxt < 0:
                break
            pos = nxt
            continue

        (
            _ver,
            flag,
            method,
            _t,
            _d,
            crc,
            csize,
            _usize,
            namelen,
            extralen,
        ) = struct.unpack_from("<HHHHHIIIHH", data, pos + 4)
        name_start = pos + 30
        name_end = name_start + namelen
        extra_end = name_end + extralen
        if extra_end > n:
            truncated = ("header-cut", pos)
            break
        name = data[name_start:name_end]
        try:
            fname = name.decode("utf-8")
        except UnicodeDecodeError:
            fname = name.decode("cp437", errors="replace")

        payload_start = extra_end
        has_dd = bool(flag & 0x08)

        if method not in (0, 8):
            nxt = data.find(LOCAL, payload_start)
            if nxt < 0:
                break
            pos = nxt
            continue

        if has_dd and csize == 0:
            search = payload_start
            found = False
            while search < n:
                i1 = data.find(LOCAL, search)
                i2 = data.find(CENTRAL, search)
                i3 = data.find(DD, search)
                idxs = [i for i in (i1, i2, i3) if i is not None and i >= 0]
                if not idxs:
                    truncated = (fname, "eof")
                    entries.append((fname, method, data[payload_start:], False, crc))
                    pos = n
                    found = True
                    break
                end = min(idxs)

                if i3 >= 0 and end == i3 and end + 16 <= n:
                    d_crc, d_csize, _d_usize = struct.unpack_from("<III", data, end + 4)
                    payload = data[payload_start:end]
                    if len(payload) == d_csize:
                        entries.append((fname, method, payload, True, d_crc))
                        pos = end + 16
                        found = True
                        break
                    search = end + 4
                    continue

                if end - 16 >= payload_start and data[end - 16 : end - 12] == DD:
                    d_crc, d_csize, _d_usize = struct.unpack_from("<III", data, end - 12)
                    payload = data[payload_start : end - 16]
                    if len(payload) == d_csize:
                        entries.append((fname, method, payload, True, d_crc))
                        pos = end
                        found = True
                        break
                if end - 12 >= payload_start:
                    d_crc, d_csize, _d_usize = struct.unpack_from("<III", data, end - 12)
                    payload = data[payload_start : end - 12]
                    if len(payload) == d_csize:
                        entries.append((fname, method, payload, True, d_crc))
                        pos = end
                        found = True
                        break
                search = end + 4

            if not found and truncated is None:
                truncated = (fname, "no-dd-match")
                entries.append((fname, method, data[payload_start:], False, crc))
                pos = n
            continue

        payload_end = payload_start + csize
        if payload_end > n:
            truncated = (fname, "payload-cut")
            entries.append((fname, method, data[payload_start:], False, crc))
            break
        payload = data[payload_start:payload_end]
        next_pos = payload_end
        if has_dd:
            if next_pos + 16 <= n and data[next_pos : next_pos + 4] == DD:
                next_pos += 16
            elif next_pos + 12 <= n:
                next_pos += 12
        entries.append((fname, method, payload, True, crc))
        pos = next_pos

    return entries, truncated


def write_entries(entries, out_dir: Path, incluir_truncados: bool) -> tuple[int, int]:
    written = skipped = 0
    for fname, method, payload, complete, _crc in entries:
        if not complete and not incluir_truncados:
            print(f"SKIP truncado: {fname} ({len(payload)} bytes)", file=sys.stderr)
            skipped += 1
            continue
        rel = Path(fname)
        if rel.is_absolute() or ".." in rel.parts:
            print(f"SKIP inseguro: {fname}", file=sys.stderr)
            skipped += 1
            continue
        dest = out_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if method == 8:
            try:
                raw = zlib.decompress(payload, -15)
            except Exception as e:
                print(f"FAIL deflate {fname}: {e}", file=sys.stderr)
                skipped += 1
                continue
        else:
            raw = payload
        dest.write_bytes(raw)
        written += 1
        mark = "OK" if complete else "TRUNC"
        print(f"{mark:5} {len(raw):10}  {fname}")
    return written, skipped


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("zip", type=Path)
    ap.add_argument("-o", "--out", type=Path, required=True)
    ap.add_argument(
        "--incluir-truncados",
        action="store_true",
        help="grava também a última entrada incompleta (só para inspeção)",
    )
    args = ap.parse_args()
    data = args.zip.read_bytes()
    print(f"lendo {args.zip} ({len(data)} bytes)")
    entries, truncated = parse_entries(data)
    print(f"entradas parseadas: {len(entries)}")
    if truncated:
        print(f"truncamento: {truncated}")
    args.out.mkdir(parents=True, exist_ok=True)
    w, s = write_entries(entries, args.out, args.incluir_truncados)
    print(f"gravados={w} pulados={s}")
    if truncated:
        print(
            "\nAVISO: o ZIP de origem está incompleto. "
            "Rebaixe do OneDrive se faltar arquivo crítico.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
