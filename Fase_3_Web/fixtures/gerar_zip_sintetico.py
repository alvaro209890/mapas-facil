"""Gera o `imovel_ficticio.zip` sintético para testes e para o piloto (W4-08).

Nunca usa dado de cliente: geometria inventada, recibo de mentira. O ZIP tem a mesma
**forma** de um pacote do SIMCAR (`CAR/` com shapefile, recibo em PDF na raiz) para
exercitar extração, indexação e o fluxo do chat.

    python Fase_3_Web/fixtures/gerar_zip_sintetico.py --destino /tmp/imovel_ficticio.zip

Os shapefiles saem do `pyshp`, que já é dependência do núcleo. A primeira versão escrevia
`.shp`/`.shx`/`.dbf` à mão com `struct` e tinha dois defeitos silenciosos: o descritor do
`.dbf` ficava com 31 bytes em vez de 32 (o `0x0D` caía no offset 64 e o leitor recusava com
"dbf header lacks expected terminator") e o cabeçalho do `.shx` declarava 50 palavras a
menos. Fixture que o leitor real recusa não prova caminho nenhum — ele mascarava o servidor
inteiro (medido em 03/11/2026: a importação morria em `NU-000`).
"""

from __future__ import annotations

import argparse
import tempfile
import zipfile
from pathlib import Path

# Retângulo de ~1 km em UTM 22S (EPSG:31982), longe de qualquer imóvel real.
# Sentido HORÁRIO: anel externo de shapefile é clockwise; anti-horário vira buraco e o
# leitor avisa "polygon contains at least one exterior ring" (medido em 03/11/2026).
UTM = [
    (600000.0, 8300000.0),
    (600000.0, 8301000.0),
    (601000.0, 8301000.0),
    (601000.0, 8300000.0),
]
PRJ = (
    'PROJCS["SIRGAS_2000_UTM_zone_22S",GEOGCS["GCS_SIRGAS_2000",'
    'DATUM["D_SIRGAS_2000",SPHEROID["GRS_1980",6378137.0,298.257222101]],'
    'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],'
    'PROJECTION["Transverse_Mercator"],PARAMETER["False_Easting",500000.0],'
    'PARAMETER["False_Northing",10000000.0],PARAMETER["Central_Meridian",-51.0],'
    'PARAMETER["Scale_Factor",0.9996],PARAMETER["Latitude_Of_Origin",0.0],'
    'UNIT["Meter",1.0]]'
)

# Recibo de mentira: PDF de uma página, com texto legível (o extrator lê de verdade).
RECIBO_PDF = b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R
/Resources << /Font << /F1 5 0 R >> >> >> endobj
4 0 obj << /Length 520 >>
stream
BT /F1 11 Tf 56 780 Td (DOCUMENTO FICTICIO - SEM DADO DE CLIENTE) Tj
0 -24 Td (CADASTRO AMBIENTAL RURAL - RECIBO DE INSCRICAO) Tj
0 -20 Td (No do registro no CAR: MT-0000000-FICTICIO0001) Tj
0 -20 Td (Imovel: Imovel Ficticio) Tj
0 -20 Td (Municipio: Querencia / UF: MT) Tj
0 -20 Td (DADOS DAS AREAS DOS IMOVEIS RURAIS) Tj
0 -20 Td (Area do imovel: 100,0000 ha) Tj
0 -20 Td (Reserva Legal proposta: 100,0000 ha) Tj
0 -20 Td (Area consolidada: 0,0000 ha) Tj
0 -20 Td (Coordenadas em SIRGAS 2000 / UTM 22S) Tj
ET
endstream
endobj
5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj
trailer << /Root 1 0 R >>
%%EOF
"""

LEIA_ME = (
    "Pacote sintético do Mapas Fácil.\n"
    "Geometria inventada (retângulo de 1 km em UTM 22S), recibo fictício.\n"
    "Nenhum dado de cliente. Gerado por Fase_3_Web/fixtures/gerar_zip_sintetico.py.\n"
)


def _shapefile_em(destino: Path, nome: str, pontos: list[tuple[float, float]]) -> list[str]:
    """Escreve `<nome>.{shp,shx,dbf,prj,cpg}` com o pyshp e devolve os arquivos criados."""
    import shapefile

    destino.mkdir(parents=True, exist_ok=True)
    escritor = shapefile.Writer(str(destino / nome))
    escritor.field("NOME", "C", size=60)
    escritor.field("classe", "C", size=40)
    escritor.field("area_ha", "N", decimal=4)
    escritor.poly([list(pontos) + [pontos[0]]])
    escritor.record("Imovel Ficticio", "ARL", 100.0)
    escritor.close()

    (destino / f"{nome}.prj").write_text(PRJ, encoding="utf-8")
    (destino / f"{nome}.cpg").write_text("ISO-8859-1", encoding="utf-8")
    return [f"{nome}{ext}" for ext in (".shp", ".shx", ".dbf", ".prj", ".cpg")]


def montar_pasta(destino: Path) -> dict[str, bytes]:
    """Monta o conteúdo do pacote numa pasta e devolve nome → bytes."""
    arquivos_do_shp = _shapefile_em(destino / "CAR", "ATP", UTM)
    (destino / "CAR - Recibo.pdf").write_bytes(RECIBO_PDF)
    (destino / "LEIA-ME.txt").write_text(LEIA_ME, encoding="utf-8")

    nomes = [f"CAR/{nome}" for nome in arquivos_do_shp] + ["CAR - Recibo.pdf", "LEIA-ME.txt"]
    return {nome: (destino / nome).read_bytes() for nome in nomes}


def gerar(destino: Path) -> Path:
    destino = Path(destino)
    if destino.suffix.lower() != ".zip":
        destino = destino / "imovel_ficticio.zip"
    destino.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        arquivos = montar_pasta(Path(tmp))
        with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as zf:
            for nome, dados in arquivos.items():
                zf.writestr(nome, dados)
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
