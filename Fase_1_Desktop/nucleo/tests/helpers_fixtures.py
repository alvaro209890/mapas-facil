from __future__ import annotations

import json
from pathlib import Path

import fitz
import shapefile
from pyproj import CRS


def escrever_shapefile_quadrado_utm(
    destino: Path,
    *,
    xmin: float = 500_000.0,
    ymin: float = 8_000_000.0,
    lado_m: float = 1_000.0,
    nome: str = "quadra",
) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    shp = destino if destino.suffix == ".shp" else destino.with_suffix(".shp")
    w = shapefile.Writer(str(shp), shapeType=shapefile.POLYGON)
    w.field("NOME", "C", 80)
    xs = [xmin, xmin + lado_m, xmin + lado_m, xmin, xmin]
    ys = [ymin, ymin, ymin + lado_m, ymin + lado_m, ymin]
    w.poly([[[x, y] for x, y in zip(xs, ys)]])
    w.record(nome)
    w.close()

    prj = shp.with_suffix(".prj")
    prj.write_text(CRS.from_epsg(31982).to_wkt(), encoding="utf-8")
    return shp


def escrever_shapefile_geografico(
    destino: Path,
    *,
    lon: float,
    lat: float,
    delta: float = 0.01,
) -> Path:
    shp = destino if destino.suffix == ".shp" else destino.with_suffix(".shp")
    w = shapefile.Writer(str(shp), shapeType=shapefile.POLYGON)
    w.field("ID", "N", 10)
    xs = [lon, lon + delta, lon + delta, lon, lon]
    ys = [lat, lat, lat + delta, lat + delta, lat]
    w.poly([[[x, y] for x, y in zip(xs, ys)]])
    w.record(1)
    w.close()
    shp.with_suffix(".prj").write_text(CRS.from_epsg(4674).to_wkt(), encoding="utf-8")
    return shp


def escrever_recibo_car_pdf(caminho: Path) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    linhas = [
        "Cadastro Ambiental Rural",
        "Recibo de Inscrição",
        "Nome do Imóvel:",
        "Fazenda Harmonia",
        "Município:",
        "Vila Rica",
        "UF:",
        "MT",
        "Nº do Registro no CAR:",
        "MT102042/2017",
        "Recibo:",
        "A1B2C3D4-E5F6-7890-ABCD-EF1234567890",
        "Situação:",
        "Ativo",
        "CPF do Proprietário:",
        "123.456.789-00",
        "Área do Imóvel:",
        "3.823,9033",
        "Área de Vegetação Nativa:",
        "2.833,7541",
        "Área Consolidada:",
        "483,8562",
        "Dados das Áreas dos Imóveis Rurais",
        "Documento",
        "Tipo",
        "Área (ha)",
        "Matrícula 12.345",
        "Matrícula",
        "3.823,9033",
        "Tipologia da Vegetação",
        "Floresta",
        "2.584,8600",
        "Cerrado",
        "1.224,0200",
    ]
    doc = fitz.open()
    pagina = doc.new_page()
    y = 40
    for linha in linhas:
        pagina.insert_text((40, y), linha, fontsize=10)
        y += 14
    doc.save(caminho)
    doc.close()
    return caminho


def escrever_pdf_cor_solido(caminho: Path, *, rgb: tuple[int, int, int]) -> None:
    """PDF de uma página com retângulo preenchido (testes B9)."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    cor = tuple(c / 255.0 for c in rgb)
    doc = fitz.open()
    pagina = doc.new_page(width=200, height=200)
    pagina.draw_rect(fitz.Rect(0, 0, 200, 200), color=cor, fill=cor)
    doc.save(caminho)
    doc.close()


def montar_workspace_minimo(raiz: Path) -> dict[str, Path]:
    dados = raiz / "dados"
    mapas = raiz / "Mapas"
    mapas.mkdir(parents=True)
    escrever_shapefile_quadrado_utm(dados / "ATP.shp", lado_m=1000)
    escrever_shapefile_quadrado_utm(dados / "AVN.shp", xmin=500_100, ymin=8_000_100, lado_m=800)
    escrever_shapefile_quadrado_utm(dados / "AUAS.shp", xmin=500_200, ymin=8_000_200, lado_m=400)
    pdf = escrever_recibo_car_pdf(raiz / "CAR - Emitido.pdf")
    return {"raiz": raiz, "pdf": pdf}
