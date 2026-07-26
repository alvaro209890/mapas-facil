# Clientes que fecharam os 4 tipos do catálogo (depois do A13, que só tinha
# `wms_wfs`): `arcgis_rest` (IBAMA PAMGIA), `wfs_gml` (INCRA) e `wms_raster`
# (mosaicos/SISCOM). Todos com HTTP fake — nenhuma rede no CI.

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mapasfacil_nucleo.camadas import gml_incra, http, rest_arcgis, wms
from mapasfacil_nucleo.erros import ErroNucleo

BBOX = (-58.02, -11.02, -57.98, -10.98)


@pytest.fixture(autouse=True)
def _sem_transporte_real():
    yield
    http.configurar_transporte(None)


def _resposta(corpo: bytes, *, status: int = 200, content_type: str = "application/json"):
    return lambda url, timeout: http.RespostaHttp(
        status=status, corpo=corpo, content_type=content_type
    )


# --------------------------------------------------------------------------- arcgis_rest

GEOJSON_ARCGIS = json.dumps(
    {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [-58.01, -11.01],
                            [-57.99, -11.01],
                            [-57.99, -10.99],
                            [-58.01, -10.99],
                            [-58.01, -11.01],
                        ]
                    ],
                },
                "properties": {"num_tad": "IBAMA-123"},
            }
        ],
    }
).encode()


def test_arcgis_monta_query_com_envelope_e_srs() -> None:
    url = rest_arcgis.montar_url_query("https://x.example/MapServer/0/query", BBOX, 4674)
    assert "f=geojson" in url
    assert "esriGeometryEnvelope" in url
    assert "inSR=4674" in url and "outSR=4674" in url
    assert "esriSpatialRelIntersects" in url


def test_arcgis_parseia_geojson() -> None:
    http.configurar_transporte(_resposta(GEOJSON_ARCGIS))
    r = rest_arcgis.buscar_feicoes("https://x.example/query", BBOX, 4674)
    assert len(r["features"]) == 1
    assert r["parcial"] is False


def test_arcgis_exceeded_transfer_limit_marca_parcial() -> None:
    corpo = json.loads(GEOJSON_ARCGIS)
    corpo["exceededTransferLimit"] = True
    http.configurar_transporte(_resposta(json.dumps(corpo).encode()))
    r = rest_arcgis.buscar_feicoes("https://x.example/query", BBOX, 4674)
    assert r["parcial"] is True  # servidor cortou; não é o fim natural da lista


def test_arcgis_erro_no_corpo_com_http_200_e_nu110() -> None:
    """A armadilha do ArcGIS REST: erro chega com status 200."""
    corpo = json.dumps({"error": {"code": 400, "message": "Invalid geometry"}}).encode()
    http.configurar_transporte(_resposta(corpo))
    with pytest.raises(ErroNucleo) as exc:
        rest_arcgis.buscar_feicoes("https://x.example/query", BBOX, 4674)
    assert exc.value.codigo == "NU-110"
    assert "Invalid geometry" in exc.value.mensagem


def test_arcgis_corpo_nao_json_e_nu110() -> None:
    http.configurar_transporte(_resposta(b"<html>gateway</html>", content_type="text/html"))
    with pytest.raises(ErroNucleo) as exc:
        rest_arcgis.buscar_feicoes("https://x.example/query", BBOX, 4674)
    assert exc.value.codigo == "NU-110"


# --------------------------------------------------------------------------- wfs_gml

GML_INCRA = """<?xml version="1.0" encoding="UTF-8"?>
<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs"
                       xmlns:gml="http://www.opengis.net/gml"
                       xmlns:ms="http://mapserver.gis.umn.edu/mapserver">
  <gml:featureMember>
    <ms:certificada_sigef_particular_mt>
      <ms:parcela_codigo>ABC-123</ms:parcela_codigo>
      <ms:geometry>
        <gml:Polygon srsName="EPSG:4326">
          <gml:outerBoundaryIs>
            <gml:LinearRing>
              <gml:coordinates>-58.01,-11.01 -57.99,-11.01 -57.99,-10.99 -58.01,-10.99</gml:coordinates>
            </gml:LinearRing>
          </gml:outerBoundaryIs>
        </gml:Polygon>
      </ms:geometry>
    </ms:certificada_sigef_particular_mt>
  </gml:featureMember>
</wfs:FeatureCollection>
"""

GML_POSLIST = """<?xml version="1.0" encoding="UTF-8"?>
<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs"
                       xmlns:gml="http://www.opengis.net/gml">
  <gml:member>
    <feicao>
      <gml:Surface>
        <gml:exterior>
          <gml:LinearRing>
            <gml:posList>-58.01 -11.01 -57.99 -11.01 -57.99 -10.99 -58.01 -10.99</gml:posList>
          </gml:LinearRing>
        </gml:exterior>
      </gml:Surface>
    </feicao>
  </gml:member>
</wfs:FeatureCollection>
"""


def test_gml_monta_url_wfs_1_0_preservando_query_do_endpoint() -> None:
    """O endpoint do INCRA já vem com `?tema=` — os params têm de entrar com `&`."""
    url = gml_incra.montar_url_getfeature(
        "https://acervofundiario.incra.gov.br/i3geo/ogc.php?tema=x", "x", BBOX
    )
    assert "tema=x&" in url
    assert "version=1.0.0" in url
    assert "typeName=x" in url
    assert "maxFeatures=" in url


def test_gml_parseia_coordinates_e_fecha_anel() -> None:
    features, avisos = gml_incra.parsear_gml(GML_INCRA)
    assert len(features) == 1
    anel = features[0]["geometry"]["coordinates"][0]
    assert anel[0] == anel[-1], "anel GeoJSON precisa fechar (gotcha 11)"
    assert features[0]["properties"]["parcela_codigo"] == "ABC-123"
    assert avisos == []


def test_gml_parseia_poslist() -> None:
    features, _ = gml_incra.parsear_gml(GML_POSLIST)
    assert len(features) == 1
    assert features[0]["geometry"]["type"] == "Polygon"


def test_gml_service_exception_e_nu110() -> None:
    xml = (
        '<?xml version="1.0"?><ServiceExceptionReport>'
        "<ServiceException>tema inexistente</ServiceException></ServiceExceptionReport>"
    )
    with pytest.raises(ErroNucleo) as exc:
        gml_incra.parsear_gml(xml)
    assert exc.value.codigo == "NU-110"


def test_gml_xml_quebrado_e_nu110() -> None:
    with pytest.raises(ErroNucleo) as exc:
        gml_incra.parsear_gml("<nao fecha")
    assert exc.value.codigo == "NU-110"


def test_gml_feicao_sem_poligono_vira_aviso_nao_geometria_inventada() -> None:
    xml = (
        '<?xml version="1.0"?><wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs" '
        'xmlns:gml="http://www.opengis.net/gml">'
        "<gml:featureMember><feicao><ms:nome>sem geometria</ms:nome></feicao></gml:featureMember>"
        "</wfs:FeatureCollection>"
    ).replace("ms:", "")
    features, avisos = gml_incra.parsear_gml(xml)
    assert features == []
    assert avisos


def test_gml_buscar_feicoes_marca_parcial_ao_bater_no_teto() -> None:
    http.configurar_transporte(_resposta(GML_INCRA.encode(), content_type="text/xml"))
    r = gml_incra.buscar_feicoes("https://x.example/ogc.php?tema=t", "t", BBOX, limite=1)
    assert len(r["features"]) == 1
    assert r["parcial"] is True  # veio exatamente o teto: pode haver mais


# --------------------------------------------------------------------------- wms_raster

PNG_MINIMO = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
)


def test_wms_monta_getmap_1_1_1_com_srs_e_authkey() -> None:
    url = wms.montar_url_getmap(
        "https://geo.sema.mt.gov.br/geoserver/ows",
        "Mosaicos:MOSAICO_SPOT_SEPLAN",
        BBOX,
        "EPSG:4674",
        authkey="segredo",
    )
    assert "request=GetMap" in url
    assert "version=1.1.1" in url
    assert "srs=EPSG%3A4674" in url  # 1.1.1 usa `srs`, não `crs`
    assert "authkey=segredo" in url


def test_wms_altura_proporcional_ao_bbox() -> None:
    quadrado = wms.altura_proporcional((0, 0, 1, 1), largura=1000)
    assert quadrado == 1000
    achatado = wms.altura_proporcional((0, 0, 2, 1), largura=1000)
    assert achatado == 500


def test_wms_altura_de_bbox_degenerado_nao_explode() -> None:
    assert wms.altura_proporcional((0, 0, 0, 0), largura=800) == 800


def test_wms_aceita_png_por_magic_bytes() -> None:
    http.configurar_transporte(_resposta(PNG_MINIMO, content_type="image/png"))
    r = wms.buscar_mapa("https://x.example/ows", "layer", BBOX, "EPSG:4674")
    assert r["imagem"] == PNG_MINIMO
    assert r["extensao"] == ".png"
    assert r["altura_px"] > 0


def test_wms_xml_de_erro_com_http_200_e_content_type_de_imagem_e_nu110() -> None:
    """Gotcha 4: HTTP 200 + `Content-Type: image/png` e o corpo é XML de erro."""
    xml = b'<?xml version="1.0"?><ServiceExceptionReport><ServiceException>fora do range</ServiceException></ServiceExceptionReport>'
    http.configurar_transporte(_resposta(xml, content_type="image/png"))
    with pytest.raises(ErroNucleo) as exc:
        wms.buscar_mapa("https://x.example/ows", "layer", BBOX, "EPSG:4674")
    assert exc.value.codigo == "NU-110"
    assert "não é imagem" in exc.value.mensagem


def test_wms_http_500_e_nu110() -> None:
    http.configurar_transporte(_resposta(b"erro", status=500, content_type="text/plain"))
    with pytest.raises(ErroNucleo) as exc:
        wms.buscar_mapa("https://x.example/ows", "layer", BBOX, "EPSG:4674")
    assert exc.value.codigo == "NU-110"


def test_wms_url_com_authkey_e_redigida_no_erro() -> None:
    http.configurar_transporte(_resposta(b"nao imagem", content_type="text/xml"))
    with pytest.raises(ErroNucleo) as exc:
        wms.buscar_mapa(
            "https://x.example/ows", "layer", BBOX, "EPSG:4674", authkey="segredo-real-aqui"
        )
    assert "segredo-real-aqui" not in json.dumps(exc.value.para_dict())
