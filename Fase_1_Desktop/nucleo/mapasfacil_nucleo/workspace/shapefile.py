from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import shapefile  # pyshp
from pyproj import CRS
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from mapasfacil_nucleo.geo.area import area_hectares
from mapasfacil_nucleo.geo.crs import epsg_utm_sirgas

ENCODINGS_DBF = ("latin-1", "utf-8", "cp1252")


@dataclass(slots=True)
class AvisoShapefile:
    codigo: str
    mensagem: str


@dataclass(slots=True)
class MetadadosShapefile:
    caminho: str
    tipo_geometria: str
    feicoes: int
    campos: list[str]
    bbox: dict[str, float]
    crs: dict[str, Any]
    area_ha: float | None
    geometrias_corrigidas: int
    encoding_dbf: str | None
    vazia: bool = False
    avisos: list[AvisoShapefile] = field(default_factory=list)
    valido: bool = True


def _ler_prj(caminho_shp: Path) -> tuple[int | None, str | None, list[AvisoShapefile]]:
    avisos: list[AvisoShapefile] = []
    prj = caminho_shp.with_suffix(".prj")
    if not prj.exists():
        avisos.append(
            AvisoShapefile(
                "NU-020",
                "Shapefile sem arquivo .prj; CRS será estimado pelas coordenadas.",
            )
        )
        return None, None, avisos
    texto = prj.read_text(encoding="utf-8", errors="replace")
    try:
        crs = CRS.from_wkt(texto)
        epsg = crs.to_epsg()
        return epsg, texto[:120], avisos
    except Exception:
        avisos.append(AvisoShapefile("NU-021", "Arquivo .prj presente mas não reconhecido."))
        return None, texto[:120], avisos


def _adivinhar_epsg_por_coordenadas(x: float, y: float) -> int:
    if abs(x) <= 180 and abs(y) <= 90:
        return 4674  # SIRGAS 2000 geográfico — comum no CAR MT
    return 31982


def _abrir_reader(caminho_shp: Path) -> tuple[shapefile.Reader, str]:
    ultimo_erro: Exception | None = None
    for encoding in ENCODINGS_DBF:
        try:
            return shapefile.Reader(str(caminho_shp), encoding=encoding), encoding
        except UnicodeDecodeError as exc:
            ultimo_erro = exc
    raise ultimo_erro or UnicodeDecodeError("dbf", b"", 0, 0, "encoding")


def _shapes_para_geometrias(reader: shapefile.Reader) -> list[BaseGeometry]:
    geometrias: list[BaseGeometry] = []
    for shp in reader.shapes():
        if shp.shapeType == shapefile.NULL:
            continue
        geojson = shp.__geo_interface__
        geometrias.append(shape(geojson))
    return geometrias


def _bbox_do_header(caminho_shp: Path) -> dict[str, float]:
    with caminho_shp.open("rb") as fh:
        fh.seek(36)
        xmin, ymin, xmax, ymax = struct.unpack("<4d", fh.read(32))
    return {"xmin": xmin, "ymin": ymin, "xmax": xmax, "ymax": ymax}


def ler_geometrias_e_epsg(caminho: str | Path) -> tuple[list[BaseGeometry], int | None]:
    """Geometrias + EPSG de um shapefile — usado por A13 (imóvel local para bbox/clip/distância)."""
    caminho_shp = Path(caminho)
    epsg, _, _ = _ler_prj(caminho_shp)
    reader, _ = _abrir_reader(caminho_shp)
    geometrias = _shapes_para_geometrias(reader)
    if epsg is None and geometrias:
        centro = geometrias[0].centroid
        epsg = _adivinhar_epsg_por_coordenadas(centro.x, centro.y)
    return geometrias, epsg


def inspecionar(caminho: str | Path) -> MetadadosShapefile:
    caminho_shp = Path(caminho)
    avisos: list[AvisoShapefile] = []

    for ext in (".shx", ".dbf", ".prj"):
        if not caminho_shp.with_suffix(ext).exists():
            avisos.append(
                AvisoShapefile("NU-022", f"Arquivo complementar ausente: {ext}")
            )

    epsg, crs_resumo, avisos_prj = _ler_prj(caminho_shp)
    avisos.extend(avisos_prj)

    reader, encoding = _abrir_reader(caminho_shp)
    campos = [f[0] for f in reader.fields[1:]]
    geometrias = _shapes_para_geometrias(reader)
    feicoes = len(geometrias)
    bbox_header = _bbox_do_header(caminho_shp)

    tipos = {reader.shapeTypeName}
    tipo_geom = next(iter(tipos)) if tipos else "UNKNOWN"

    vazia = feicoes == 0
    if vazia:
        avisos.append(
            AvisoShapefile(
                "NU-025",
                "Camada sem feições (export SIMCAR vazio — normal se não for obrigatória no MapSpec).",
            )
        )

    if epsg is None and geometrias:
        centro = geometrias[0].centroid
        epsg = _adivinhar_epsg_por_coordenadas(centro.x, centro.y)

    area_ha: float | None = None
    corrigidas = 0
    if geometrias and epsg is not None:
        if epsg in (4326, 4674):
            lon = float(sum(g.centroid.x for g in geometrias) / len(geometrias))
            area_ha, corrigidas = area_hectares(geometrias, epsg_origem=epsg, longitude_centroide=lon)
        elif epsg >= 31900:
            from shapely.ops import unary_union

            partes = [g if g.is_valid else g.buffer(0) for g in geometrias]
            area_ha = round(float(unary_union(partes).area) / 10_000, 4)
        else:
            avisos.append(
                AvisoShapefile("NU-024", f"CRS EPSG:{epsg} não suportado para cálculo de área.")
            )

    zona_utm = None
    if geometrias and epsg in (4326, 4674):
        lon = float(sum(g.centroid.x for g in geometrias) / len(geometrias))
        zona_utm = epsg_utm_sirgas(lon)

    estruturalmente_valido = not any(a.codigo == "NU-022" for a in avisos)

    return MetadadosShapefile(
        caminho=str(caminho_shp),
        tipo_geometria=tipo_geom,
        feicoes=feicoes,
        campos=campos,
        bbox=bbox_header,
        crs={
            "epsg": epsg,
            "resumo": crs_resumo,
            "zona_utm_sugerida": zona_utm,
            "adivinhado": crs_resumo is None and epsg is not None,
        },
        area_ha=area_ha,
        geometrias_corrigidas=corrigidas,
        encoding_dbf=encoding,
        vazia=vazia,
        avisos=avisos,
        valido=estruturalmente_valido,
    )
