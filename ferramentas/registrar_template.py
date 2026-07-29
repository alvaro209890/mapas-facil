#!/usr/bin/env python3
"""Registra template preparado no MANIFEST (sha256 + offsets)."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / "shared" / "templates" / "MANIFEST.json"
TEMPLATES_DIR = REPO / "shared" / "templates"

SENTINELAS = {
    "extent": [111111.0, 222222.0, 333333.0, 444444.0],
    "escala": [987654.0],
}


def sha256_arquivo(caminho: Path) -> str:
    digest = hashlib.sha256()
    with caminho.open("rb") as fh:
        for bloco in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def buscar_float64(caminho: Path, valor: float) -> list[int]:
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
    return offsets


def descobrir_offsets(caminho: Path, *, extent_vals: list[float] | None = None, escala_val: float | None = None) -> dict:
    if extent_vals is None:
        extent_vals = list(SENTINELAS["extent"])
    if escala_val is None:
        escala_val = float(SENTINELAS["escala"][0])
    # Sidecar gravado por preparar_sentinelas_arcpy.py (extent real pos-aspecto).
    sidecar = Path(str(caminho) + ".sentinelas.json")
    if sidecar.is_file():
        try:
            dados_sc = json.loads(sidecar.read_text(encoding="utf-8-sig"))
            if dados_sc.get("extent"):
                extent_vals = [float(x) for x in dados_sc["extent"]]
            if dados_sc.get("escala") is not None:
                escala_val = float(dados_sc["escala"])
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass

    dados = caminho.read_bytes()

    extent_offset = None
    primeiro = buscar_float64(caminho, extent_vals[0])
    for off in primeiro:
        if off + 32 > len(dados):
            continue
        ok = True
        for i, valor in enumerate(extent_vals):
            lido = struct.unpack("<d", dados[off + i * 8 : off + i * 8 + 8])[0]
            if abs(lido - valor) > 1e-4:
                ok = False
                break
        if ok:
            extent_offset = off
            break

    escala_offset = None
    escala_hits = buscar_float64(caminho, escala_val)
    if escala_hits:
        escala_offset = escala_hits[0]

    patch: dict = {"suportado": True, "offsets": {}}
    if extent_offset is not None:
        patch["offsets"]["extent"] = {
            "offset": extent_offset,
            "formato": "4×float64 LE",
            "sentinela": extent_vals[0],
            "sentinelas": extent_vals,
        }
    if escala_offset is not None:
        patch["offsets"]["escala"] = {
            "offset": escala_offset,
            "formato": "float64 LE",
            "sentinela": escala_val,
        }
    return patch


def main() -> int:
    parser = argparse.ArgumentParser(description="Registra template no MANIFEST.json")
    parser.add_argument("template_id", help="ID no MANIFEST (ex.: dinamica_retrato)")
    parser.add_argument(
        "mxd",
        type=Path,
        nargs="?",
        help="MXD preparado (padrao: shared/templates/<arquivo>)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra o que seria gravado sem alterar o MANIFEST",
    )
    parser.add_argument(
        "--crs-data-frame",
        help="Atualiza o CRS do data frame no MANIFEST (ex.: EPSG:3857).",
    )
    args = parser.parse_args()

    with MANIFEST.open(encoding="utf-8") as fh:
        manifesto = json.load(fh)

    tpl = next((t for t in manifesto["templates"] if t["id"] == args.template_id), None)
    if tpl is None:
        print(f"Template id nao encontrado: {args.template_id}", file=sys.stderr)
        return 1

    nome_arquivo = tpl.get("arquivo") or Path(tpl["fonte_acervo"]).name
    if not tpl.get("arquivo"):
        tpl["arquivo"] = nome_arquivo
    if args.crs_data_frame:
        tpl["crs_data_frame"] = args.crs_data_frame

    destino = args.mxd or (TEMPLATES_DIR / nome_arquivo)
    if not destino.is_file():
        print(f"MXD nao encontrado: {destino}", file=sys.stderr)
        return 1

    destino_final = TEMPLATES_DIR / nome_arquivo
    if destino.resolve() != destino_final.resolve():
        if args.dry_run:
            # --dry-run nunca escreve fora do tmp/entrada — soh calcula sha256/offsets
            # do arquivo indicado, sem tocar em shared/templates/.
            pass
        else:
            TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
            import shutil

            shutil.copy2(destino, destino_final)
            destino = destino_final

    digest = sha256_arquivo(destino)
    patch = descobrir_offsets(destino)

    tpl["sha256"] = digest
    tpl["patch"] = patch
    tpl["status"] = (
        "pronto"
        if patch.get("offsets", {}).get("extent") and patch.get("offsets", {}).get("escala")
        else "parcial"
    )

    resumo = {
        "id": args.template_id,
        "arquivo": nome_arquivo,
        "sha256": digest,
        "status": tpl["status"],
        "crs_data_frame": tpl.get("crs_data_frame"),
        "patch": patch,
    }

    if args.dry_run:
        print(json.dumps(resumo, ensure_ascii=False, indent=2))
        return 0

    with MANIFEST.open("w", encoding="utf-8") as fh:
        json.dump(manifesto, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    print(json.dumps(resumo, ensure_ascii=False, indent=2))
    if tpl["status"] != "pronto":
        print(
            "\nAVISO: offsets incompletos. Rode preparar_sentinelas_arcpy.py antes.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
