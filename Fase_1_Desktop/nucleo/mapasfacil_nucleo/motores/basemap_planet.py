"""Fase 3 (paridade Harmonia) — raster de basemap via mosaico WMTS Planet.

Baixa tiles XYZ/Web Mercator do mosaico informado, monta um mosaico local e
georeferencia com worldfile (.pgw) + .prj — sem depender de GDAL/rasterio.
O raster fica fora do repositório (pasta do job do usuário); a chave nunca é
escrita em disco versionado.
"""

from __future__ import annotations

import io
import json
import math
import urllib.request
from pathlib import Path
from typing import Any

from mapasfacil_nucleo.config import raiz_repositorio

_ORIGEM_MERC = 20037508.34278925  # metros — meia-circunferência Web Mercator
_TILE_PX = 256
_WKT_3857 = (
    'PROJCS["WGS_1984_Web_Mercator_Auxiliary_Sphere",'
    'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",'
    'SPHEROID["WGS_1984",6378137.0,298.257223563]],'
    'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],'
    'PROJECTION["Mercator_Auxiliary_Sphere"],'
    'PARAMETER["False_Easting",0.0],PARAMETER["False_Northing",0.0],'
    'PARAMETER["Central_Meridian",0.0],PARAMETER["Standard_Parallel_1",0.0],'
    'PARAMETER["Auxiliary_Sphere_Type",0.0],UNIT["Meter",1.0]]'
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


def gerar_basemap_planet(
    *,
    bbox_wgs84: tuple[float, float, float, float],
    mosaico: str,
    destino_png: Path,
    api_key: str | None = None,
    zoom: int = 15,
    buffer_graus: float = 0.02,
    timeout_s: int = 20,
) -> dict[str, Any] | None:
    """Baixa e georeferencia o mosaico Planet cobrindo `bbox_wgs84` (+ buffer).

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
        return (
            f"https://tiles.planet.com/basemaps/v1/planet-tiles/{mosaico}"
            f"/gmap/{zoom}/{tx}/{ty}.png?api_key={chave}"
        )

    # Sonda rapida: se o mosaico nao existir/rede indisponivel, falha em
    # segundos em vez de tentar (e esperar timeout de) ate centenas de tiles.
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
    mosaico_img.save(destino_png)

    x_min_m, y_max_m = _tile_para_merc(tx0, ty0, zoom)
    x_max_m, y_min_m = _tile_para_merc(tx1 + 1, ty1 + 1, zoom)
    px_x = (x_max_m - x_min_m) / (n_cols * _TILE_PX)
    px_y = (y_max_m - y_min_m) / (n_rows * _TILE_PX)

    pgw = destino_png.with_suffix(".pgw")
    pgw.write_text(f"{px_x}\n0.0\n0.0\n{-px_y}\n{x_min_m}\n{y_max_m}\n", encoding="ascii")
    destino_png.with_suffix(".prj").write_text(_WKT_3857, encoding="ascii")

    return {
        "png": str(destino_png),
        "tiles": n_cols * n_rows,
        "tiles_faltando": faltando,
        "zoom": zoom,
        "mosaico": mosaico,
    }
