"""Palco da web — os arquivos que o navegador desenha (W7-07 / W7-08).

O palco **não** baixa o shapefile do projeto: recebe, por camada, um GeoJSON em EPSG:4326 já
simplificado, e, para o mosaico, um PNG recortado com o `bbox_4326` para encaixar. Isso protege
três coisas de uma vez: o dado bruto do cliente não sai do servidor, o volume no navegador fica
abaixo de 2 MB por camada, e o desenho do palco é o **mesmo** material que foi para o PDF.

Regras (testadas em `tests/test_palco.py`):

* tudo é gravado sob `Mapas/.preview/<job_id>/` — pasta que a rota do servidor conhece;
* coordenadas com 6 casas (≈ 10 cm) e `properties` só com o que o palco usa;
* teto de **2 MB** por arquivo e **20.000** vértices; passou, dobra a tolerância de simplificação
  até caber e marca `"simplificado": true` na coleção;
* a área (`area_ha`) é sempre calculada no CRS **projetado** de origem, nunca em graus — em graus
  a conta não significa nada.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

from shapely.geometry import mapping, shape
from shapely.ops import transform as shapely_transform

from mapasfacil_nucleo.erros import ErroNucleo

PASTA_PREVIEW: Final = "Mapas/.preview"
SUBP_GEOMETRIAS: Final = "camadas"
SUBP_LAYOUT: Final = "layout"
SUBP_RASTER: Final = "raster"

LIMITE_BYTES: Final = 2 * 1024 * 1024
LIMITE_VERTICES: Final = 20_000
CASAS: Final = 6
TENTATIVAS_SIMPLIFICACAO: Final = 6

# PNG de palco: maior lado, em pixels. 1600 dá 4x o quadro de um A4 a 96 dpi — nitidez sem
# estourar a memória de uma aba com 10 jobs abertos.
LADO_RASTER: Final = 1600


def pasta_do_job(guard: Any, job_id: str, sub: str | None = None) -> Path:
    """`Mapas/.preview/<job_id>[/<sub>]`, criada e autorizada pelo fsguard."""
    rel = f"{PASTA_PREVIEW}/{job_id}"
    if sub:
        rel = f"{rel}/{sub}"
    caminho = guard.resolver(rel, escrita=True)
    caminho.mkdir(parents=True, exist_ok=True)
    return caminho


def relativo(caminho: Path, guard: Any) -> str:
    """Caminho relativo à pasta do projeto, com `/` — é o que vai no evento."""
    return str(Path(caminho).resolve().relative_to(Path(guard.raiz).resolve())).replace("\\", "/")


def _contar_vertices(geom: Any) -> int:
    if geom.is_empty:
        return 0
    if geom.geom_type in ("Polygon", "LineString", "Point"):
        return _contar_vertices_um(geom)
    return sum(_contar_vertices_um(g) for g in getattr(geom, "geoms", []))


def _contar_vertices_um(geom: Any) -> int:
    if geom.geom_type == "Polygon":
        return len(geom.exterior.coords) + sum(len(i.coords) for i in geom.interiors)
    if geom.geom_type == "LineString":
        return len(geom.coords)
    if geom.geom_type == "Point":
        return 1
    return 0


def _arredondar(geom: Any) -> Any:
    return shapely_transform(lambda x, y, z=None: (round(x, CASAS), round(y, CASAS)), geom)


def _geometria_do_arquivo(shp: Path) -> list[Any]:
    """Geometrias do shapefile, com a projeção de origem (`.prj`)."""
    import shapefile  # pyshp

    reader = shapefile.Reader(str(shp))
    geoms = []
    for sr in reader.iterShapeRecords():
        try:
            geom = shape(sr.shape.__geo_interface__)
        except Exception:  # noqa: BLE001 - feição corrompida não derruba a camada
            continue
        if not geom.is_empty:
            geoms.append(geom)
    return geoms


def _epsg_do_prj(shp: Path) -> int | None:
    prj = shp.with_suffix(".prj")
    if not prj.is_file():
        return None
    from pyproj import CRS

    try:
        return int(CRS.from_wkt(prj.read_text(encoding="utf-8", errors="replace")).to_epsg() or 0) or None
    except Exception:  # noqa: BLE001
        return None


def _para_4326(geom: Any, epsg: int) -> Any:
    if epsg in (4326, 0):
        return geom
    from pyproj import Transformer

    transformer = Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4326", always_xy=True)
    return shapely_transform(transformer.transform, geom)


def gravar_geojson(
    shp: Path,
    destino: Path,
    *,
    epsg_origem: int | None = None,
    bbox_imovel_4326: tuple[float, float, float, float] | None = None,
    propriedades: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Grava o GeoJSON de palco de uma camada e devolve o que o evento precisa.

    Devolve `{caminho, bbox_4326, geometria, n_feicoes, area_ha, vertices, simplificado}`.
    """
    shp = Path(shp)
    if not shp.is_file():
        raise ErroNucleo("NU-410", f"Shapefile da camada não existe: {shp.name}")

    epsg = epsg_origem or _epsg_do_prj(shp) or 31982
    geoms = _geometria_do_arquivo(shp)
    if not geoms:
        raise ErroNucleo("NU-411", f"Camada sem feição: {shp.name}")

    tipos = {g.geom_type for g in geoms}
    if tipos <= {"Polygon", "MultiPolygon"}:
        geometria = "poligono"
    elif tipos <= {"LineString", "MultiLineString"}:
        geometria = "linha"
    else:
        geometria = "ponto"

    # Área no CRS projetado de origem — em graus a conta não significa nada.
    area_ha: float | None = None
    if geometria == "poligono":
        from shapely.ops import unary_union

        uniao = unary_union(geoms)
        area_m2 = abs(uniao.area)
        if area_m2 > 0:
            area_ha = round(area_m2 / 10_000.0, 4)

    if bbox_imovel_4326 is None:
        em_graus = [_para_4326(g, epsg) for g in geoms]
        from shapely.ops import unary_union as _uniao

        minx, miny, maxx, maxy = _uniao(em_graus).bounds
        bbox_imovel_4326 = (minx, miny, maxx, maxy)

    diagonal = max(1e-9, ((bbox_imovel_4326[2] - bbox_imovel_4326[0]) ** 2 + (
        bbox_imovel_4326[3] - bbox_imovel_4326[1]
    ) ** 2) ** 0.5)
    tol = diagonal / 4000.0

    props = dict(propriedades or {})
    colecao: dict[str, Any] = {}
    vertices = 0
    simplificado = False
    for tentativa in range(TENTATIVAS_SIMPLIFICACAO):
        em_graus = [_arredondar(_para_4326(g, epsg).simplify(tol * (2**tentativa), preserve_topology=True)) for g in geoms]
        vertices = sum(_contar_vertices(g) for g in em_graus)
        colecao = {
            "type": "FeatureCollection",
            "name": props.get("nome") or shp.stem,
            "features": [
                {"type": "Feature", "properties": dict(props, area_ha=area_ha), "geometry": mapping(g)}
                for g in em_graus
                if not g.is_empty
            ],
        }
        texto = json.dumps(colecao, ensure_ascii=False, separators=(",", ":"))
        simplificado = tentativa > 0
        if len(texto.encode("utf-8")) <= LIMITE_BYTES and vertices <= LIMITE_VERTICES:
            break
    else:
        raise ErroNucleo(
            "NU-412",
            f"Camada {shp.stem} não coube em {LIMITE_BYTES // 1024 // 1024} MB mesmo simplificada.",
            {"vertices": vertices},
        )

    if simplificado:
        colecao["simplificado"] = True
        colecao["tolerancia"] = round(tol * (2 ** (TENTATIVAS_SIMPLIFICACAO - 1)), 9)

    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(colecao, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    geoms_4326 = [_para_4326(g, epsg) for g in geoms]
    from shapely.ops import unary_union as _uniao2

    minx, miny, maxx, maxy = _uniao2(geoms_4326).bounds
    return {
        "caminho": destino,
        "bbox_4326": [round(minx, 6), round(miny, 6), round(maxx, 6), round(maxy, 6)],
        "geometria": geometria,
        "n_feicoes": len(geoms),
        "area_ha": area_ha,
        "vertices": vertices,
        "simplificado": simplificado,
        "bytes": destino.stat().st_size,
    }


def gravar_raster(
    origem: Path,
    destino: Path,
    *,
    bbox_4326: tuple[float, float, float, float] | list[float],
) -> dict[str, Any]:
    """Prepara o PNG do mosaico para o palco: encaixa em `LADO_RASTER` e devolve o bbox."""
    from PIL import Image

    origem = Path(origem)
    if not origem.is_file():
        raise ErroNucleo("NU-413", f"Raster do basemap não existe: {origem.name}")
    with Image.open(origem) as img:
        img = img.convert("RGB")
        maior = max(img.size)
        if maior > LADO_RASTER:
            fator = LADO_RASTER / float(maior)
            novo = (max(1, int(img.width * fator)), max(1, int(img.height * fator)))
            img = img.resize(novo, Image.LANCZOS)
        destino = Path(destino)
        destino.parent.mkdir(parents=True, exist_ok=True)
        img.save(destino, "PNG", optimize=True)
        tamanho = img.size
    return {
        "caminho": destino,
        "bbox_4326": [round(float(v), 6) for v in bbox_4326],
        "largura_px": tamanho[0],
        "altura_px": tamanho[1],
        "bytes": destino.stat().st_size,
    }


def gravar_recorte_elemento(
    pagina_png: Path,
    destino: Path,
    *,
    caixa_mm: dict[str, float],
    largura_mm: float,
    altura_mm: float,
    dpi: int = 150,
) -> dict[str, Any]:
    """Recorta um elemento da página renderizada (W7-06): o palco mostra o bloco **real**.

    A página é desenhada inteira pelo motor nativo; aqui só se corta a caixa do elemento na
    mesma escala usada no PDF (mm → px pelo `dpi`). Sem a página, não há recorte: quem chama
    trata como ausente.
    """
    from PIL import Image

    pagina_png = Path(pagina_png)
    if not pagina_png.is_file():
        raise ErroNucleo("NU-414", f"Página renderizada não existe: {pagina_png.name}")
    with Image.open(pagina_png) as img:
        px_por_mm_x = img.width / float(largura_mm)
        px_por_mm_y = img.height / float(altura_mm)
        esquerda = int(round(caixa_mm["x0"] * px_por_mm_x))
        topo = int(round(caixa_mm["y0"] * px_por_mm_y))
        direita = int(round(caixa_mm["x1"] * px_por_mm_x))
        baixo = int(round(caixa_mm["y1"] * px_por_mm_y))
        esquerda = max(0, min(esquerda, img.width - 1))
        topo = max(0, min(topo, img.height - 1))
        direita = max(esquerda + 1, min(direita, img.width))
        baixo = max(topo + 1, min(baixo, img.height))
        recorte = img.crop((esquerda, topo, direita, baixo))
        if recorte.width > 1200:
            fator = 1200 / float(recorte.width)
            recorte = recorte.resize(
                (1200, max(1, int(recorte.height * fator))), Image.LANCZOS
            )
        destino = Path(destino)
        destino.parent.mkdir(parents=True, exist_ok=True)
        recorte.save(destino, "PNG", optimize=True)
        tamanho = recorte.size
    return {
        "caminho": destino,
        "largura_px": tamanho[0],
        "altura_px": tamanho[1],
        "bytes": destino.stat().st_size,
    }
