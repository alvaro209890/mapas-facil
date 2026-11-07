"""Fixture sintética reutilizável com dois imóveis (dois CARs).

Gera um arquivo ZIP com dois imóveis independentes (cada um com seu shapefile ATP
e recibo CAR em PDF), sem usar dados de clientes, para testes de integração e E2E.
"""

from __future__ import annotations

import argparse
import tempfile
import zipfile
from pathlib import Path

import shapefile
import pymupdf as fitz

PRJ_SIRGAS_2000 = (
    'PROJCS["SIRGAS_2000_UTM_zone_22S",GEOGCS["GCS_SIRGAS_2000",'
    'DATUM["D_SIRGAS_2000",SPHEROID["GRS_1980",6378137.0,298.257222101]],'
    'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],'
    'PROJECTION["Transverse_Mercator"],PARAMETER["False_Easting",500000.0],'
    'PARAMETER["False_Northing",10000000.0],PARAMETER["Central_Meridian",-51.0],'
    'PARAMETER["Scale_Factor",0.9996],PARAMETER["Latitude_Of_Origin",0.0],'
    'UNIT["Meter",1.0]]'
)


def _criar_recibo_pdf(
    caminho: Path,
    nome_imovel: str,
    car_num: str,
    area_ha: float,
    municipio: str = "Querência",
    uf: str = "MT",
) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    pagina = doc.new_page(width=595, height=842)
    linhas = [
        "Cadastro Ambiental Rural",
        "Recibo de Inscrição",
        "Nome do Imóvel:",
        nome_imovel,
        "Município:",
        municipio,
        "UF:",
        uf,
        "Nº do Registro no CAR:",
        car_num,
        "Recibo:",
        "A1B2C3D4-E5F6-7890-ABCD-EF1234567890",
        "Situação:",
        "Ativo",
        "Área do Imóvel:",
        f"{area_ha:.4f}".replace(".", ","),
        "Dados das Áreas dos Imóveis Rurais",
    ]
    y = 50
    for linha in linhas:
        pagina.insert_text((50, y), linha, fontsize=11)
        y += 22
    doc.save(str(caminho))
    doc.close()
    return caminho


def _criar_shapefile(
    destino_pasta: Path,
    nome: str,
    pontos: list[tuple[float, float]],
    nome_imovel: str,
    area_ha: float,
) -> list[str]:
    destino_pasta.mkdir(parents=True, exist_ok=True)
    escritor = shapefile.Writer(str(destino_pasta / nome))
    escritor.field("NOME", "C", size=60)
    escritor.field("classe", "C", size=40)
    escritor.field("area_ha", "N", decimal=4)
    # Anel externo sempre clockwise
    escritor.poly([list(pontos) + [pontos[0]]])
    escritor.record(nome_imovel, "ATP", area_ha)
    escritor.close()

    (destino_pasta / f"{nome}.prj").write_text(PRJ_SIRGAS_2000, encoding="utf-8")
    (destino_pasta / f"{nome}.cpg").write_text("ISO-8859-1", encoding="utf-8")
    return [f"{nome}{ext}" for ext in (".shp", ".shx", ".dbf", ".prj", ".cpg")]


def gerar_zip_dois_imoveis(destino: Path | str) -> Path:
    """Gera um pacote ZIP sintético com 2 imóveis em subpastas com recibos e shapefiles."""
    destino_path = Path(destino)
    destino_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp_str:
        tmp_dir = Path(tmp_str)

        pasta_alfa = tmp_dir / "CAR_Alfa"
        pasta_beta = tmp_dir / "CAR_Beta"

        # Imóvel 1: Fazenda Alfa (~100 ha)
        pontos_alfa = [
            (600000.0, 8300000.0),
            (600000.0, 8301000.0),
            (601000.0, 8301000.0),
            (601000.0, 8300000.0),
        ]
        _criar_shapefile(pasta_alfa, "ATP", pontos_alfa, "Fazenda Alfa", 100.0)
        _criar_recibo_pdf(
            pasta_alfa / "Recibo_Alfa.pdf",
            nome_imovel="Fazenda Alfa",
            car_num="MT1000001/2026",
            area_ha=100.0,
            municipio="Querência",
            uf="MT",
        )

        # Imóvel 2: Fazenda Beta (~64 ha)
        pontos_beta = [
            (602000.0, 8300000.0),
            (602000.0, 8300800.0),
            (602800.0, 8300800.0),
            (602800.0, 8300000.0),
        ]
        _criar_shapefile(pasta_beta, "ATP", pontos_beta, "Fazenda Beta", 64.0)
        _criar_recibo_pdf(
            pasta_beta / "Recibo_Beta.pdf",
            nome_imovel="Fazenda Beta",
            car_num="MT1000002/2026",
            area_ha=64.0,
            municipio="Querência",
            uf="MT",
        )

        with zipfile.ZipFile(destino_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for arq in sorted(pasta_alfa.glob("*.*")):
                zf.write(arq, f"CAR_Alfa/{arq.name}")
            for arq in sorted(pasta_beta.glob("*.*")):
                zf.write(arq, f"CAR_Beta/{arq.name}")

    return destino_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gera ZIP sintético com 2 imóveis.")
    parser.add_argument("--destino", required=True, help="Caminho do arquivo ZIP a gerar.")
    args = parser.parse_args()
    zip_gerado = gerar_zip_dois_imoveis(args.destino)
    print(f"ZIP de dois imóveis gerado com sucesso em: {zip_gerado}")
