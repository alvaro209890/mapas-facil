"""Fase 3 (paridade Harmonia) — raster de basemap via WMTS Planet.

Baixa tiles do endpoint WMTS oficial (`api.planet.com/.../wmts`), monta um
mosaico local e georeferencia no **CRS do data frame** (UTM SIRGAS) — sem
reprojeção on-the-fly no ArcMap (que era o que travava o export).

A chave nunca é escrita em disco versionado.
"""

from __future__ import annotations

import io
import json
import math
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from mapasfacil_nucleo.config import raiz_repositorio

_ORIGEM_MERC = 20037508.34278925
_TILE_PX = 256

# Endpoint WMTS estável (GetCapabilities / GetTile) — chave só em query.
WMTS_BASE = "https://api.planet.com/basemaps/v1/mosaics/wmts"

_WKT_31982 = (
    'PROJCS["SIRGAS_2000_UTM_Zone_22S",'
    'GEOGCS["GCS_SIRGAS_2000",DATUM["D_SIRGAS_2000",'
    'SPHEROID["GRS_1980",6378137.0,298.257222101]],'
    'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],'
    'PROJECTION["Transverse_Mercator"],'
    'PARAMETER["False_Easting",500000.0],'
    'PARAMETER["False_Northing",10000000.0],'
    'PARAMETER["Central_Meridian",-51.0],'
    'PARAMETER["Scale_Factor",0.9996],'
    'PARAMETER["Latitude_Of_Origin",0.0],'
    'UNIT["Meter",1.0]]'
)


def ler_chave_planet(*, override: str | None = None) -> str | None:
    """Ordem: argumento → cofre do SO → `secrets.local.json` (dev)."""
    if override is not None:
        return override.strip() or None

    try:
        from mapasfacil_nucleo import cofre

        do_cofre = cofre.usar("planet_api_key")
        if do_cofre:
            return do_cofre
    except Exception:
        pass

    caminho = raiz_repositorio() / "secrets.local.json"
    if not caminho.is_file():
        return None
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    chave = str(dados.get("planet_api_key") or "").strip()
    return chave or None


def url_wmts_capabilities(api_key: str) -> str:
    return f"{WMTS_BASE}?{urllib.parse.urlencode({'api_key': api_key})}"


def _url_wmts_tile(*, mosaico: str, z: int, tx: int, ty: int, api_key: str) -> str:
    """Tile do ResourceURL Planet (XYZ = matrix GoogleMapsCompatible do WMTS).

    O endpoint `.../mosaics/wmts?REQUEST=GetTile` devolve Capabilities XML —
    os pixels vêm de `tiles.planet.com` (ResourceURL do GetCapabilities).
    """
    return (
        f"https://tiles.planet.com/basemaps/v1/planet-tiles/{mosaico}"
        f"/gmap/{z}/{tx}/{ty}.png?{urllib.parse.urlencode({'api_key': api_key})}"
    )


def _lonlat_para_tile(lon: float, lat: float, z: int) -> tuple[float, float]:
    lat_rad = math.radians(lat)
    n = 2**z
    x = (lon + 180.0) / 360.0 * n
    y = (1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi) / 2.0 * n
    return x, y


def _tile_para_merc(xt: float, yt: float, z: int) -> tuple[float, float]:
    n = 2**z
    x_m = xt / n * 2 * _ORIGEM_MERC - _ORIGEM_MERC
    y_m = _ORIGEM_MERC - yt / n * 2 * _ORIGEM_MERC
    return x_m, y_m


def _escrever_georef_utm(
    destino_png: Path,
    *,
    x_min_m: float,
    y_max_m: float,
    x_max_m: float,
    y_min_m: float,
    width_px: int,
    height_px: int,
    epsg: int,
) -> None:
    """Worldfile no CRS do data frame — evita warp 3857→UTM no ArcMap (travava)."""
    from pyproj import CRS, Transformer

    transformer = Transformer.from_crs("EPSG:3857", f"EPSG:{epsg}", always_xy=True)
    ul_x, ul_y = transformer.transform(x_min_m, y_max_m)
    ur_x, ur_y = transformer.transform(x_max_m, y_max_m)
    ll_x, ll_y = transformer.transform(x_min_m, y_min_m)

    # Affine (worldfile): A D / B E / C F
    a = (ur_x - ul_x) / width_px
    d = (ur_y - ul_y) / width_px
    b = (ll_x - ul_x) / height_px
    e = (ll_y - ul_y) / height_px
    c, f = ul_x, ul_y

    destino_png.with_suffix(".pgw").write_text(
        f"{a}\n{d}\n{b}\n{e}\n{c}\n{f}\n",
        encoding="ascii",
    )
    try:
        wkt = CRS.from_epsg(epsg).to_wkt()
    except Exception:
        wkt = _WKT_31982 if epsg == 31982 else _WKT_31982
    destino_png.with_suffix(".prj").write_text(wkt, encoding="utf-8")


def gerar_basemap_planet(
    *,
    bbox_wgs84: tuple[float, float, float, float],
    mosaico: str,
    destino_png: Path,
    api_key: str | None = None,
    zoom: int = 13,
    buffer_graus: float = 0.02,
    timeout_s: int = 12,
    epsg_destino: int = 31982,
) -> dict[str, Any] | None:
    """Baixa tiles WMTS e georeferencia no `epsg_destino` (default UTM 22S).

    `bbox_wgs84` = (xmin, ymin, xmax, ymax). Grava `destino_png` + `.pgw` + `.prj`.
    Devolve `None` se a chave não estiver configurada (chamador cai para "sem
    basemap" — nunca falha o job por causa disso).
    """
    from PIL import Image

    chave = api_key or ler_chave_planet()
    if not chave:
        return None

    xmin, ymin, xmax, ymax = bbox_wgs84
    xmin -= buffer_graus
    xmax += buffer_graus
    ymin -= buffer_graus
    ymax += buffer_graus

    x0, y0 = _lonlat_para_tile(xmin, ymax, zoom)
    x1, y1 = _lonlat_para_tile(xmax, ymin, zoom)
    tx0, ty0 = int(math.floor(x0)), int(math.floor(y0))
    tx1, ty1 = int(math.floor(x1)), int(math.floor(y1))
    n_cols = tx1 - tx0 + 1
    n_rows = ty1 - ty0 + 1

    if n_cols * n_rows > 400:
        raise ValueError(
            f"basemap Planet: {n_cols}x{n_rows} tiles excede o limite de segurança (400)."
        )

    def _url_tile(tx: int, ty: int) -> str:
        return _url_wmts_tile(mosaico=mosaico, z=zoom, tx=tx, ty=ty, api_key=chave)

    try:
        with urllib.request.urlopen(_url_tile(tx0, ty0), timeout=8) as resp:
            resp.read()
    except Exception:
        return None

    mosaico_img = Image.new("RGB", (n_cols * _TILE_PX, n_rows * _TILE_PX))
    faltando = 0
    for linha, ty in enumerate(range(ty0, ty1 + 1)):
        for col, tx in enumerate(range(tx0, tx1 + 1)):
            try:
                with urllib.request.urlopen(_url_tile(tx, ty), timeout=timeout_s) as resp:
                    dados = resp.read()
                tile_img = Image.open(io.BytesIO(dados)).convert("RGB")
            except Exception:
                faltando += 1
                tile_img = Image.new("RGB", (_TILE_PX, _TILE_PX), (255, 255, 255))
            mosaico_img.paste(tile_img, (col * _TILE_PX, linha * _TILE_PX))

    destino_png.parent.mkdir(parents=True, exist_ok=True)
    mosaico_img.save(destino_png, optimize=True)

    x_min_m, y_max_m = _tile_para_merc(tx0, ty0, zoom)
    x_max_m, y_min_m = _tile_para_merc(tx1 + 1, ty1 + 1, zoom)
    _escrever_georef_utm(
        destino_png,
        x_min_m=x_min_m,
        y_max_m=y_max_m,
        x_max_m=x_max_m,
        y_min_m=y_min_m,
        width_px=n_cols * _TILE_PX,
        height_px=n_rows * _TILE_PX,
        epsg=epsg_destino,
    )

    return {
        "png": str(destino_png),
        "tiles": n_cols * n_rows,
        "tiles_faltando": faltando,
        "zoom": zoom,
        "mosaico": mosaico,
        "epsg": epsg_destino,
        "fonte": "wmts",
    }
