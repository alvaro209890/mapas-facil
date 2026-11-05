"""O que o .mxd gerado precisa ao lado dele, na pasta do projeto (04/11/2026).

Os templates preparados por `ferramentas/preparar_template_projeto_arcpy.py` apontam as
camadas para `..\\SHP\\...` com os **nomes de arquivo do modelo** (`AIR.shp`,
`limites/lml_municipio_a.shp`, `imagens/<raster>.tif`): o `.slots.json` lista esses
arquivos com o papel de cada um (`arquivos`), e este módulo grava as cópias.

Também calcula as extensões dos data frames na proporção do quadro — o ArcMap respeita a
extensão gravada e deriva a escala dela (conferido no ArcMap 10.8).
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from mapasfacil_nucleo.fsguard import WorkspaceGuard

SUFIXOS_SHAPE = (".shp", ".shx", ".dbf", ".prj", ".cpg")

# papel → nome canônico materializado em SHP/ (camadas/materializar.py)
ORIGEM_LOCAL = {"perimetro": "ATP", "avn": "AVN", "ac": "AREA_CONSOLIDADA", "auas": "AUAS"}


def ajustar_envelope(
    bbox: tuple[float, float, float, float], quadro_cm: list[float] | tuple[float, float] | None
) -> tuple[float, float, float, float]:
    """Expande o bbox até a proporção do data frame, mantendo o centro."""
    x0, y0, x1, y1 = (float(v) for v in bbox)
    if not quadro_cm or quadro_cm[0] <= 0 or quadro_cm[1] <= 0:
        return x0, y0, x1, y1
    razao = float(quadro_cm[0]) / float(quadro_cm[1])
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    largura, altura = max(x1 - x0, 1e-9), max(y1 - y0, 1e-9)
    if largura / altura > razao:
        altura = largura / razao
    else:
        largura = altura * razao
    return cx - largura / 2, cy - altura / 2, cx + largura / 2, cy + altura / 2


METROS_POR_GRAU_ARCMAP = 111194.87222222222
"""Como o ArcMap mede escala em data frame geográfico: grau = 2π·6.371.000/360 m (medido no
ArcMap 10.8: 3° em 4,2594 cm → 1:7.831.728)."""


def escala_do_envelope(
    envelope: tuple[float, float, float, float], quadro_cm: list[float], epsg: int = 31982
) -> float:
    """Denominador da escala de um envelope no quadro dado, como o ArcMap calcula."""
    largura = envelope[2] - envelope[0]
    if int(epsg) in (4326, 4674, 4618, 4291):
        largura *= METROS_POR_GRAU_ARCMAP
    return largura / (float(quadro_cm[0]) / 100.0)


def _transformar_bbox(bbox: tuple[float, float, float, float], de: int, para: int) -> tuple[float, ...]:
    if de == para:
        return bbox
    from pyproj import Transformer

    t = Transformer.from_crs(f"EPSG:{de}", f"EPSG:{para}", always_xy=True)
    xs, ys = t.transform([bbox[0], bbox[0], bbox[2], bbox[2]], [bbox[1], bbox[3], bbox[1], bbox[3]])
    return min(xs), min(ys), max(xs), max(ys)


def extensao_minimapa(
    municipio: str | None, epsg: int, quadro_cm: list[float] | None
) -> tuple[float, float, float, float] | None:
    """Município inteiro (com folga) no CRS do minimapa, na proporção do quadro."""
    if not municipio:
        return None
    from mapasfacil_nucleo.camadas import ibge

    try:
        bbox = ibge.extent_municipio(nome=municipio, padding=1.15)
    except Exception:  # noqa: BLE001 — base ausente: o minimapa fica no lugar da sentinela
        return None
    if not bbox:
        return None
    return ajustar_envelope(_transformar_bbox(bbox, 4674, int(epsg)), quadro_cm)


def _wkt_esri(epsg: int) -> str:
    from pyproj import CRS

    return CRS.from_epsg(int(epsg)).to_wkt("WKT1_ESRI")


REGISTRO = "SHP/.mapasfacil_gerados.json"
"""Arquivos que o núcleo gravou para o .mxd. Um arquivo que já existe e **não** está aqui é
do usuário (pasta do desktop com SHP/AIR.shp original): nunca é sobrescrito."""


def _ler_registro(guard: WorkspaceGuard) -> set[str]:
    import json

    try:
        return set(json.loads(guard.resolver(REGISTRO).read_text(encoding="utf-8")))
    except Exception:  # noqa: BLE001
        return set()


def _salvar_registro(guard: WorkspaceGuard, nomes: set[str]) -> None:
    import json

    try:
        guard.resolver(REGISTRO, escrita=True).write_text(json.dumps(sorted(nomes), indent=1), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def _copiar_shape(origem: Path, destino: Path) -> bool:
    if not origem.with_suffix(".shp").is_file():
        return False
    if origem.with_suffix(".shp").resolve() == destino.with_suffix(".shp").resolve():
        return True
    destino.parent.mkdir(parents=True, exist_ok=True)
    for sufixo in SUFIXOS_SHAPE:
        src = origem.with_suffix(sufixo)
        if src.is_file():
            shutil.copy2(src, destino.with_suffix(sufixo))
    return True


def _gravar_localizador(destino: Path, centro_lonlat: tuple[float, float], meio_lado: float) -> None:
    import shapefile as pyshp

    destino.parent.mkdir(parents=True, exist_ok=True)
    lon, lat = centro_lonlat
    x0, x1, y0, y1 = lon - meio_lado, lon + meio_lado, lat - meio_lado, lat + meio_lado
    with pyshp.Writer(str(destino.with_suffix("")), shapeType=pyshp.POLYGON) as w:
        w.field("ID", "N")
        w.poly([[(x0, y1), (x1, y1), (x1, y0), (x0, y0), (x0, y1)]])
        w.record(1)
    destino.with_suffix(".prj").write_text(_wkt_esri(4674), encoding="ascii")


def _gravar_raster(destino: Path, imagem: Path, extent: tuple[float, ...], epsg: int) -> None:
    """GeoTIFF simples: TIFF RGB + world file (.tfw) + .prj — o ArcMap lê sem GDAL."""
    from PIL import Image

    destino.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(imagem) as im:
        rgb = im.convert("RGB")
        largura, altura = rgb.size
        rgb.save(destino, format="TIFF", compression="tiff_lzw")
    px = (extent[2] - extent[0]) / largura
    py = (extent[3] - extent[1]) / altura
    destino.with_suffix(".tfw").write_text(
        f"{px!r}\n0.0\n0.0\n{-py!r}\n{extent[0] + px / 2!r}\n{extent[3] - py / 2!r}\n", encoding="ascii"
    )
    destino.with_suffix(".prj").write_text(_wkt_esri(epsg), encoding="ascii")
    for velho in (destino.with_name(destino.name + ".aux.xml"), destino.with_suffix(".ovr")):
        if velho.exists():
            velho.unlink()


def gravar_arquivos(
    arquivos: list[dict[str, str]],
    *,
    guard: WorkspaceGuard,
    centro_lonlat: tuple[float, float] | None = None,
    meio_lado_localizador: float = 0.02,
    basemap: dict[str, Any] | None = None,
) -> list[str]:
    """Grava cada arquivo que o template espera. Devolve avisos (nunca levanta)."""
    from mapasfacil_nucleo.camadas import ibge

    avisos: list[str] = []
    base_ibge = ibge.pasta_shapefile_repo()
    feitos: set[str] = set()
    nossos = _ler_registro(guard)
    for item in arquivos:
        rel, papel = item.get("arquivo", ""), item.get("papel", "")
        if not rel or rel in feitos:
            continue
        feitos.add(rel)
        try:
            destino = guard.resolver(rel, escrita=True)
            if destino.exists() and rel not in nossos:
                continue  # arquivo do usuário com o mesmo nome: fica como está
            nossos.add(rel)
            if papel in ORIGEM_LOCAL:
                origem = guard.resolver(f"SHP/{ORIGEM_LOCAL[papel]}.shp")
                if not _copiar_shape(origem, destino):
                    avisos.append(f"[MX-060] {rel}: sem {ORIGEM_LOCAL[papel]}.shp no projeto — a camada abre vazia.")
            elif papel == "municipios":
                mt = base_ibge / "lml_municipio_mt.shp"
                _copiar_shape(mt if mt.is_file() else base_ibge / "lml_municipio_a.shp", destino)
            elif papel == "uf":
                _copiar_shape(base_ibge / "lml_uf_a.shp", destino)
            elif papel == "localizador":
                if centro_lonlat is not None:
                    _gravar_localizador(destino, centro_lonlat, meio_lado_localizador)
            elif papel == "basemap":
                if basemap and Path(basemap["caminho"]).is_file():
                    _gravar_raster(destino, Path(basemap["caminho"]), tuple(basemap["extent"]), int(basemap["epsg"]))
                elif basemap is not None:
                    avisos.append(f"[MX-061] {rel}: sem imagem de fundo baixada — o .mxd abre sem a imagem.")
        except Exception as exc:  # noqa: BLE001 — um arquivo a menos não derruba o .mxd
            avisos.append(f"[MX-062] {rel}: {exc}")
    _salvar_registro(guard, nossos)
    return avisos


def centro_lonlat(bbox: tuple[float, float, float, float], epsg: int) -> tuple[float, float]:
    x0, y0, x1, y1 = _transformar_bbox(bbox, int(epsg), 4674)
    return (x0 + x1) / 2, (y0 + y1) / 2


def meio_lado_localizador(minimapa: tuple[float, ...] | None, epsg: int) -> float:
    """Quadradinho com ~5% da largura do minimapa (em graus), mínimo de 0,01°."""
    if not minimapa:
        return 0.02
    x0, _, x1, _ = _transformar_bbox(tuple(minimapa), int(epsg), 4674)
    return max(0.01, abs(x1 - x0) * 0.025)


__all__ = [
    "ajustar_envelope",
    "centro_lonlat",
    "escala_do_envelope",
    "extensao_minimapa",
    "gravar_arquivos",
    "meio_lado_localizador",
]
