"""Preparação das camadas da análise e as derivadas, sem tocar na rede."""

from __future__ import annotations

import shapefile  # pyshp
from pyproj import CRS
from shapely.geometry import Polygon

from mapasfacil_nucleo.analise import preparar as prep
from mapasfacil_nucleo.camadas import cache as cache_mod
from mapasfacil_nucleo.camadas.resolver import escrever_shapefile
from mapasfacil_nucleo.fsguard import WorkspaceGuard

EPSG = 31982


def _shp(guard: WorkspaceGuard, papel: str, poligonos: list[Polygon]) -> str:
    destino = guard.resolver(f"SHP/{papel}", escrita=True)
    escrever_shapefile(destino, list(poligonos), EPSG)
    return str(destino.with_suffix(".shp").relative_to(guard.raiz))


def _quadrado(x0: float, y0: float, lado: float) -> Polygon:
    return Polygon([(x0, y0), (x0 + lado, y0), (x0 + lado, y0 + lado), (x0, y0 + lado)])


def test_area_que_precisa_dla_e_auas_menos_dla(tmp_path) -> None:
    """A camada não existe em serviço nenhum: é conta sobre as que existem."""
    guard = WorkspaceGuard(tmp_path)
    resultado = prep.ResultadoPreparacao()
    resultado.fontes_idx["AUAS"] = _shp(guard, "AUAS", [_quadrado(0, 0, 100)])
    resultado.fontes_idx["DLA"] = _shp(guard, "DLA", [_quadrado(0, 0, 50)])

    prep._derivar(resultado, guard=guard, epsg=EPSG, pasta="SHP")

    assert resultado.feicoes["AREA_PRECISA_DLA"] >= 1
    reader = shapefile.Reader(str(guard.resolver(resultado.fontes_idx["AREA_PRECISA_DLA"])))
    area = sum(abs(_area(s)) for s in reader.shapes())
    assert 7000 < area < 7900, "100×100 menos 50×50 = 7.500 m²"


def _area(shape) -> float:
    pontos = shape.points
    total = 0.0
    for i in range(len(pontos) - 1):
        total += pontos[i][0] * pontos[i + 1][1] - pontos[i + 1][0] * pontos[i][1]
    return total / 2


def test_amortecimento_e_anel_e_nao_disco(tmp_path) -> None:
    """Zona de amortecimento não pode cobrir a própria TI — é o anel de fora."""
    guard = WorkspaceGuard(tmp_path)
    resultado = prep.ResultadoPreparacao()
    resultado.fontes_idx["TERRAS_INDIGENAS"] = _shp(guard, "TERRAS_INDIGENAS", [_quadrado(0, 0, 1000)])

    prep._derivar(resultado, guard=guard, epsg=EPSG, pasta="SHP")

    assert resultado.feicoes.get("TI_AMORTECIMENTO", 0) >= 1
    reader = shapefile.Reader(str(guard.resolver(resultado.fontes_idx["TI_AMORTECIMENTO"])))
    anel = reader.shapes()[0]
    # O anel envolve o quadrado original: seu bbox é ~10 km maior de cada lado.
    assert anel.bbox[0] < -9000 and anel.bbox[2] > 10000


def test_derivada_sem_origem_nao_cria_camada(tmp_path) -> None:
    guard = WorkspaceGuard(tmp_path)
    resultado = prep.ResultadoPreparacao()
    prep._derivar(resultado, guard=guard, epsg=EPSG, pasta="SHP")
    assert "AREA_PRECISA_DLA" not in resultado.fontes_idx


def test_resposta_vazia_nao_entra_no_cache(tmp_path, monkeypatch) -> None:
    """Vazio de soluço do serviço não pode virar mapa em branco pelo TTL inteiro."""
    from mapasfacil_nucleo.camadas import resolver as resolver_mod

    salvos: list[str] = []
    monkeypatch.setattr(
        cache_mod, "obter", lambda *a, **k: None
    )
    monkeypatch.setattr(
        cache_mod,
        "salvar",
        lambda fonte, *a, **k: salvos.append(fonte),
    )

    camada = {"id": "qualquer", "tema": "embargos"}
    vazio, origem = resolver_mod._com_cache(
        camada, (0, 0, 1, 1), "EPSG:31982", lambda: {"features": []}, cache_base=tmp_path
    )
    assert vazio == {"features": []} and origem == "miss"
    assert salvos == [], "resposta vazia não pode ser cacheada"

    resolver_mod._com_cache(
        camada,
        (0, 0, 1, 1),
        "EPSG:31982",
        lambda: {"features": [{"geometry": None}]},
        cache_base=tmp_path,
    )
    assert salvos == ["qualquer"], "resposta com feição continua sendo cacheada"


def test_prj_do_shapefile_derivado_declara_o_crs(tmp_path) -> None:
    guard = WorkspaceGuard(tmp_path)
    rel = _shp(guard, "TESTE", [_quadrado(0, 0, 10)])
    prj = guard.resolver(rel).with_suffix(".prj").read_text(encoding="utf-8")
    assert CRS.from_wkt(prj).to_epsg() == EPSG
