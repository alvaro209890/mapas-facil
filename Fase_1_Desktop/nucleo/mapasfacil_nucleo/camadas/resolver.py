# A13 — `camada.resolver`: catálogo → cache → cliente do tipo → clip → arquivo local
# (F1-01 §Métodos, F1-03 §camadas/, planos/03-wfs-e-servicos-geo.md).
#
# Contrato interno (mesmo usado pelas tools do agente — `agente/tools.py`
# `consultar_sema`/`distancia_ate`, R21): resolve uma camada do catálogo num
# bbox/crs e materializa o resultado **dentro do workspace** (fsguard). Falha
# de rede não crasha o processo — vira `ErroNucleo` tipado (NU-1xx) que quem
# chamou decide como tratar; camada vazia após o recorte é aviso, não erro.
#
# Os 4 tipos do catálogo têm cliente:
#   · `wms_wfs`     → `wfs.py`          (SEMA, FUNAI, MapBiomas, PRODES vetor)
#   · `arcgis_rest` → `rest_arcgis.py`  (IBAMA PAMGIA)
#   · `wfs_gml`     → `gml_incra.py`    (INCRA SIGEF/SNCI — GML, EPSG:4326 nativo)
#   · `wms_raster`  → `wms.py`          (mosaicos/SISCOM — **imagem**, sem feição)
# Os três primeiros compartilham o pipeline vetorial (clip + shapefile); o
# raster tem caminho próprio e `tipo_saida="raster"`, porque WMS não devolve
# feição nenhuma para contar ou medir.

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import shapefile  # pyshp
from pyproj import CRS
from shapely.geometry import mapping, shape
from shapely.geometry.base import BaseGeometry
from shapely.geometry.polygon import orient as shapely_orient

from mapasfacil_nucleo import cofre
from mapasfacil_nucleo.camadas import cache as cache_mod
from mapasfacil_nucleo.camadas import catalogo
from mapasfacil_nucleo.camadas import clip as clip_mod
from mapasfacil_nucleo.camadas import gml_incra
from mapasfacil_nucleo.camadas import rest_arcgis
from mapasfacil_nucleo.camadas import wfs
from mapasfacil_nucleo.camadas import wms
from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.fsguard import WorkspaceGuard
from mapasfacil_nucleo.geo.area import reprojetar

BBox = tuple[float, float, float, float]

PASTA_DESTINO_PADRAO = "SHP/_camadas"
# Raster não é shapefile — vai para a pasta de saída de imagem, não para SHP/.
PASTA_DESTINO_RASTER = "Mapas/_camadas"


@dataclass(slots=True)
class ResultadoResolucao:
    camada_id: str
    layer: str
    tema: str | None
    arquivo_rel: str
    epsg: int
    feicoes: int
    vazia: bool
    parcial: bool
    origem_cache: str  # "hit" | "expirado" | "miss"
    avisos: list[dict[str, str]]
    # "vetor" → `arquivo_rel` é shapefile e `feicoes` conta de verdade;
    # "raster" → `arquivo_rel` é PNG/JPG de fundo e `feicoes` é sempre 0
    # (WMS não devolve feição — não dá para contar nem medir área a partir dele).
    tipo_saida: str = "vetor"
    geometrias: list[BaseGeometry] = field(default_factory=list, repr=False)

    def para_ndjson(self) -> dict[str, Any]:
        """Nunca inclui geometria/WKT (AP-06) — só o que a UI/agente precisam."""
        return {
            "camada": self.camada_id,
            "layer": self.layer,
            "tema": self.tema,
            "arquivo": self.arquivo_rel,
            "epsg": self.epsg,
            "feicoes": self.feicoes,
            "vazia": self.vazia,
            "parcial": self.parcial,
            "cache": self.origem_cache,
            "tipo_saida": self.tipo_saida,
            "avisos": self.avisos,
        }


def _epsg_de_crs(crs: Any) -> int:
    texto = str(crs or "").strip().upper()
    if not texto.startswith("EPSG:"):
        raise ErroNucleo("NU-001", f"Parâmetro 'crs' precisa ser 'EPSG:<código>': {crs!r}")
    try:
        return int(texto.split(":", 1)[1])
    except ValueError as exc:
        raise ErroNucleo("NU-001", f"Parâmetro 'crs' inválido: {crs!r}") from exc


def validar_bbox(bbox: Any) -> BBox:
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        raise ErroNucleo(
            "NU-001", "Parâmetro 'bbox' precisa ter 4 números: [xmin, ymin, xmax, ymax]."
        )
    try:
        xmin, ymin, xmax, ymax = (float(v) for v in bbox)
    except (TypeError, ValueError) as exc:
        raise ErroNucleo("NU-001", "Parâmetro 'bbox' precisa conter números.") from exc
    if xmin >= xmax or ymin >= ymax:
        raise ErroNucleo(
            "NU-001",
            "Parâmetro 'bbox' inválido: xmin/ymin precisam ser menores que xmax/ymax.",
        )
    return (xmin, ymin, xmax, ymax)


def _geometrias_do_geojson(features: list[dict[str, Any]]) -> list[BaseGeometry]:
    geometrias: list[BaseGeometry] = []
    for feat in features:
        geom = feat.get("geometry") if isinstance(feat, dict) else None
        if not geom:
            continue
        try:
            geometrias.append(shape(geom))
        except (ValueError, AttributeError):
            continue
    return geometrias


def _shape_type_para(geometrias: list[BaseGeometry]) -> int:
    if not geometrias:
        return shapefile.POLYGON
    tipo = geometrias[0].geom_type
    if tipo in ("Point", "MultiPoint"):
        return shapefile.POINT
    if tipo in ("LineString", "MultiLineString"):
        return shapefile.POLYLINE
    return shapefile.POLYGON


def _aneis_poligono(geom: BaseGeometry) -> list[list[tuple[float, float]]]:
    # Shapefile exige anel externo em sentido horário (oposto do GeoJSON/shapely,
    # que é anti-horário) — sem isso o pyshp grava um polígono "só de buracos" e
    # a releitura vira um anel externo trocado (aviso do pyshp ao reabrir).
    orientado = shapely_orient(geom, sign=-1.0)
    gj = mapping(orientado)
    if gj["type"] == "Polygon":
        return [list(anel) for anel in gj["coordinates"]]
    if gj["type"] == "MultiPolygon":
        aneis: list[list[tuple[float, float]]] = []
        for poligono in gj["coordinates"]:
            aneis.extend(list(anel) for anel in poligono)
        return aneis
    return []


def _escrever_geometria(w: "shapefile.Writer", tipo: int, geom: BaseGeometry) -> bool:
    if geom.is_empty:
        return False
    if tipo == shapefile.POINT:
        if geom.geom_type == "Point":
            w.point(geom.x, geom.y)
            return True
        if geom.geom_type == "MultiPoint":
            primeiro = next(iter(geom.geoms))
            w.point(primeiro.x, primeiro.y)
            return True
        return False
    if tipo == shapefile.POLYLINE:
        gj = mapping(geom)
        if gj["type"] == "LineString":
            w.line([list(gj["coordinates"])])
            return True
        if gj["type"] == "MultiLineString":
            w.line([list(parte) for parte in gj["coordinates"]])
            return True
        return False
    aneis = _aneis_poligono(geom)
    if not aneis:
        return False
    w.poly(aneis)
    return True


def escrever_shapefile(
    destino_stem: Path, geometrias: list[BaseGeometry], epsg: int
) -> int:
    """Grava `.shp/.shx/.dbf/.prj` — vazio (0 feições) é um shapefile válido."""
    destino_stem.parent.mkdir(parents=True, exist_ok=True)
    tipo = _shape_type_para(geometrias)
    escritas = 0
    w = shapefile.Writer(str(destino_stem), shapeType=tipo)
    w.field("ID", "N", 10)
    for indice, geom in enumerate(geometrias, start=1):
        if _escrever_geometria(w, tipo, geom):
            w.record(indice)
            escritas += 1
    w.close()
    destino_stem.with_suffix(".prj").write_text(
        CRS.from_epsg(epsg).to_wkt(), encoding="utf-8"
    )
    return escritas


def _obter_authkey(camada: dict[str, Any]) -> str | None:
    nome_segredo = camada.get("auth")
    if not nome_segredo:
        return None
    valor = cofre.usar(nome_segredo)
    if not valor:
        raise ErroNucleo(
            "NU-102",
            f"A camada '{camada['id']}' exige a chave '{nome_segredo}', que não está "
            "configurada. Configure em Preferências (cofre) e tente de novo.",
            {"chave": nome_segredo},
        )
    return valor


def _epsg_nativo(camada: dict[str, Any], epsg_pedido: int) -> int:
    """CRS em que o serviço devolve. INCRA declara `epsg: 4326` no catálogo."""
    declarado = camada.get("epsg")
    if isinstance(declarado, int) and declarado > 0:
        return declarado
    return epsg_pedido


def _buscar_vetor(
    camada: dict[str, Any],
    bbox: BBox,
    epsg_nativo: int,
    *,
    timeout: int,
    limite: int,
) -> dict[str, Any]:
    """Despacha para o cliente do `tipo` — todos devolvem o mesmo envelope."""
    tipo = camada["tipo"]
    authkey = _obter_authkey(camada)
    if tipo == "wms_wfs":
        return wfs.buscar_feicoes(
            camada["endpoint"],
            camada["layer"],
            bbox,
            f"EPSG:{epsg_nativo}",
            authkey=authkey,
            timeout=timeout,
            limite=limite,
        )
    if tipo == "arcgis_rest":
        return rest_arcgis.buscar_feicoes(
            camada["endpoint"], bbox, epsg_nativo, timeout=timeout, limite=limite
        )
    if tipo == "wfs_gml":
        return gml_incra.buscar_feicoes(
            camada["endpoint"],
            camada["layer"],
            bbox,
            timeout=max(timeout, gml_incra.TIMEOUT_INCRA_S),
            limite=limite,
        )
    raise ErroNucleo(  # pragma: no cover — `resolver_camada` já filtrou o tipo
        "NU-140", f"Tipo vetorial sem despacho: {tipo}", {"tipo": tipo}
    )


def _com_cache(
    camada: dict[str, Any],
    bbox: BBox,
    chave_crs: str,
    buscar,
    *,
    cache_base: Path | None,
) -> tuple[dict[str, Any], str]:
    """Cache TTL por tema + degrade offline com cache expirado (F1-03 §Modo offline)."""
    tema = camada.get("tema")
    entrada = cache_mod.obter(camada["id"], bbox, chave_crs, tema=tema, base=cache_base)
    if entrada is not None and not entrada.expirada:
        return entrada.dados, "hit"
    try:
        dados = buscar()
    except ErroNucleo:
        # Sem rede, cache expirado ainda serve, com aviso de idade. Sem cache
        # nenhum, a falha propaga — nunca devolvemos geometria inventada.
        if entrada is not None:
            return entrada.dados, "expirado"
        raise
    cache_mod.salvar(camada["id"], bbox, chave_crs, dados, base=cache_base)
    return dados, "miss"


def _resolver_vetor(
    camada: dict[str, Any],
    bbox_expandido: BBox,
    epsg: int,
    *,
    guard: WorkspaceGuard,
    pasta_destino: str,
    timeout: int,
    limite: int,
    usar_cache: bool,
    cache_base: Path | None,
) -> ResultadoResolucao:
    epsg_nativo = _epsg_nativo(camada, epsg)
    chave_crs = f"EPSG:{epsg_nativo}"

    def _buscar() -> dict[str, Any]:
        return _buscar_vetor(
            camada, bbox_expandido, epsg_nativo, timeout=timeout, limite=limite
        )

    if usar_cache:
        dados, origem_cache = _com_cache(
            camada, bbox_expandido, chave_crs, _buscar, cache_base=cache_base
        )
    else:
        dados, origem_cache = _buscar(), "miss"

    geometrias_brutas = _geometrias_do_geojson(dados.get("features") or [])
    # Serviço com CRS nativo diferente do pedido (INCRA em 4326): reprojeta antes
    # do clip, senão o recorte compara graus com metros e some com tudo.
    if epsg_nativo != epsg:
        geometrias_brutas = [
            reprojetar(g, epsg_nativo, epsg) for g in geometrias_brutas if not g.is_empty
        ]
    geometrias = clip_mod.clip_bbox(geometrias_brutas, bbox_expandido)

    avisos: list[dict[str, str]] = []
    if origem_cache == "expirado":
        avisos.append(
            {"codigo": "NU-103", "mensagem": "Sem rede — usando cache expirado desta camada."}
        )
    if dados.get("parcial"):
        avisos.append(
            {
                "codigo": "NU-104",
                "mensagem": (
                    "Resposta parcial do serviço "
                    f"({dados.get('versao_usada') or 'fallback'}) — pode haver mais feições."
                ),
            }
        )
    for aviso_parser in dados.get("avisos_parser") or []:
        avisos.append({"codigo": "NU-111", "mensagem": str(aviso_parser)})
    vazia = len(geometrias) == 0
    if vazia:
        avisos.append(
            {
                "codigo": "NU-120",
                "mensagem": f"Camada '{camada['id']}' sem feições após o recorte no bbox.",
            }
        )

    destino_stem = guard.resolver(f"{pasta_destino}/{camada['id']}", escrita=True)
    escrever_shapefile(destino_stem, geometrias, epsg)
    arquivo_rel = str(destino_stem.with_suffix(".shp").relative_to(guard.raiz))

    return ResultadoResolucao(
        camada_id=camada["id"],
        layer=camada["layer"],
        tema=camada.get("tema"),
        arquivo_rel=arquivo_rel,
        epsg=epsg,
        feicoes=len(geometrias),
        vazia=vazia,
        parcial=bool(dados.get("parcial")),
        origem_cache=origem_cache,
        avisos=avisos,
        tipo_saida="vetor",
        geometrias=geometrias,
    )


def _resolver_raster(
    camada: dict[str, Any],
    bbox_expandido: BBox,
    epsg: int,
    *,
    guard: WorkspaceGuard,
    pasta_destino: str,
    timeout: int,
) -> ResultadoResolucao:
    """WMS GetMap → imagem em `Mapas/_camadas/`. Sem feição, sem área (contrato distinto)."""
    authkey = _obter_authkey(camada)
    dados = wms.buscar_mapa(
        camada["endpoint"],
        camada["layer"],
        bbox_expandido,
        f"EPSG:{epsg}",
        authkey=authkey,
        timeout=timeout,
    )
    destino = guard.resolver(
        f"{pasta_destino}/{camada['id']}{dados['extensao']}", escrita=True
    )
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(dados["imagem"])

    return ResultadoResolucao(
        camada_id=camada["id"],
        layer=camada["layer"],
        tema=camada.get("tema"),
        arquivo_rel=str(destino.relative_to(guard.raiz)),
        epsg=epsg,
        feicoes=0,
        vazia=False,
        parcial=False,
        # GetMap é imagem: sempre buscado na hora, sem cache de feição pra reusar.
        origem_cache="miss",
        avisos=[
            {
                "codigo": "NU-112",
                "mensagem": (
                    f"'{camada['id']}' é camada raster (WMS): serve de fundo, "
                    "não produz contagem de feições nem área."
                ),
            }
        ],
        tipo_saida="raster",
    )


def resolver_camada(
    fonte: str,
    bbox: Any,
    crs: Any,
    *,
    guard: WorkspaceGuard,
    pasta_destino: str = PASTA_DESTINO_PADRAO,
    pasta_destino_raster: str = PASTA_DESTINO_RASTER,
    timeout: int = wfs.http.TIMEOUT_PADRAO_S,
    limite: int = wfs.CONTAGEM_MAXIMA,
    usar_cache: bool = True,
    cache_base: Path | None = None,
) -> ResultadoResolucao:
    camada = catalogo.buscar(fonte)
    tipo = camada["tipo"]
    if tipo not in catalogo.TIPOS_SUPORTADOS:
        raise ErroNucleo(
            "NU-140",
            f"Tipo de serviço sem cliente: '{tipo}' (camada '{camada['id']}'). "
            f"Suportados: {sorted(catalogo.TIPOS_SUPORTADOS)}.",
            {"tipo": tipo, "camada": camada["id"]},
        )
    bbox_val = validar_bbox(bbox)
    epsg = _epsg_de_crs(crs)
    bbox_expandido = clip_mod.expandir_bbox(bbox_val)

    if tipo in catalogo.TIPOS_RASTER:
        return _resolver_raster(
            camada,
            bbox_expandido,
            epsg,
            guard=guard,
            pasta_destino=pasta_destino_raster,
            timeout=timeout,
        )
    return _resolver_vetor(
        camada,
        bbox_expandido,
        epsg,
        guard=guard,
        pasta_destino=pasta_destino,
        timeout=timeout,
        limite=limite,
        usar_cache=usar_cache,
        cache_base=cache_base,
    )
