"""Gera o `imovel_ficticio.zip` sintético para testes e para o piloto (W4-08).

Nunca usa dado de cliente: geometria inventada, CPF inventado, recibo de mentira.
O ZIP tem a mesma **forma** de um pacote do SIMCAR (CAR/ com shapefile, recibo em
PDF na raiz) para exercitar extração, indexação e o fluxo do chat.

    python Fase_3_Web/fixtures/gerar_zip_sintetico.py --destino /tmp/imovel_ficticio.zip

Os shapefiles são escritos à mão (não dependem de GDAL): um `.shp` mínimo com um
polígono, `.shx`, `.dbf` e `.prj` em SIRGAS 2000 / UTM 22S.
"""

from __future__ import annotations

import argparse
import struct
import zipfile
from pathlib import Path

# Retângulo de ~1 km em UTM 22S (EPSG:31982), longe de qualquer imóvel real.
UTM = [(600000.0, 8300000.0), (601000.0, 8300000.0), (601000.0, 8301000.0), (600000.0, 8301000.0)]
PRJ = (
    'PROJCS["SIRGAS_2000_UTM_zone_22S",GEOGCS["GCS_SIRGAS_2000",'
    'DATUM["D_SIRGAS_2000",SPHEROID["GRS_1980",6378137.0,298.257222101]],'
    'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],'
    'PROJECTION["Transverse_Mercator"],PARAMETER["False_Easting",500000.0],'
    'PARAMETER["False_Northing",10000000.0],PARAMETER["Central_Meridian",-51.0],'
    'PARAMETER["Scale_Factor",0.9996],PARAMETER["Latitude_Of_Origin",0.0],'
    'UNIT["Meter",1.0]]'
)
RECIBO_PDF = b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [] /Count 0 >> endobj
trailer << /Root 1 0 R >>
%%EOF
"""


def _shp(pontos: list[tuple[float, float]]) -> bytes:
    registros = b"".join(
        struct.pack(">2i", 1, 2)
        + struct.pack("<i", 5)
        + struct.pack("<4d", min(p[0] for p in pontos), min(p[1] for p in pontos),
                      max(p[0] for p in pontos), max(p[1] for p in pontos))
        + struct.pack("<ii", 1, len(pontos))
        + b"".join(struct.pack("<2d", *p) for p in pontos)
        + struct.pack("<2d", *pontos[0])
        for _ in (0,)
    )
    conteudo = struct.pack("<i", 5) + b"\x00" * 32 + registros
    total_palavras = len(conteudo) // 2
    cabecalho = (
        struct.pack(">i", 9994)
        + b"\x00" * 20
        + struct.pack(">i", total_palavras)
        + struct.pack("<ii", 1000, 5)
        + struct.pack("<4d", min(p[0] for p in pontos), min(p[1] for p in pontos),
                      max(p[0] for p in pontos), max(p[1] for p in pontos))
        + struct.pack("<4d", 0, 0, 0, 0)
    )
    return cabecalho + b"\x00" * (100 - len(cabecalho)) + conteudo


def _shx(shp: bytes) -> bytes:
    conteudo = struct.pack(">i", 50) + struct.pack(">i", (len(shp) - 100) // 2)
    cabecalho = (
        struct.pack(">i", 9994)
        + b"\x00" * 20
        + struct.pack(">i", len(conteudo) // 2)
        + struct.pack("<ii", 1000, 5)
        + struct.pack("<4d", *([0.0] * 4))
        + struct.pack("<4d", *([0.0] * 4))
    )
    return cabecalho + b"\x00" * (100 - len(cabecalho)) + conteudo


def _dbf(nome: str = "ATP") -> bytes:
    campos = [(b"NOME", b"C", 60, 0)]
    registro = b" " + b"Imovel Ficticio".ljust(60)[:60]
    cabecalho = (
        bytes([3, 126, 1, 1])
        + struct.pack("<IHH", 1, len(campos) * 32 + 33, len(registro))
        + b"\x00" * 20
    )
    descritores = b"".join(
        n.ljust(11, b"\x00") + t + b"\x00" * 4 + bytes([tam]) + b"\x00" * 14 for n, t, tam, _ in campos
    )
    return cabecalho + descritores + b"\x0d" + registro + b"\x1a"


def montar_pasta(destino: Path) -> dict[str, bytes]:
    arquivos = {
        "CAR/ATP.shp": _shp(UTM),
        "CAR/ATP.shx": _shx(_shp(UTM)),
        "CAR/ATP.dbf": _dbf(),
        "CAR/ATP.prj": PRJ.encode("utf-8"),
        "CAR/ATP.cpg": b"ISO-8859-1",
        "CAR - Recibo.pdf": RECIBO_PDF,
        "LEIA-ME.txt": (
            "Pacote sintético gerado por gerar_zip_sintetico.py.\n"
            "Nenhum dado de cliente: geometria inventada, recibo vazio.\n"
        ).encode("utf-8"),
    }
    for nome, dados in arquivos.items():
        caminho = destino / nome
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_bytes(dados)
    return arquivos


def gerar(destino: Path) -> Path:
    destino = Path(destino)
    if destino.suffix.lower() != ".zip":
        destino = destino / "imovel_ficticio.zip"
    destino.parent.mkdir(parents=True, exist_ok=True)
    pasta = destino.parent / "_ficticio"
    arquivos = montar_pasta(pasta)
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as zf:
        for nome in arquivos:
            zf.write(pasta / nome, arcname=nome)
    return destino


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gerar_zip_sintetico")
    parser.add_argument("--destino", default="imovel_ficticio.zip")
    args = parser.parse_args(argv)
    caminho = gerar(Path(args.destino))
    print(caminho)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
