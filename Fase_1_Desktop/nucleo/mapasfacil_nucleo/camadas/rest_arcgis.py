# Cliente ArcGIS REST (`tipo: arcgis_rest` do catálogo — IBAMA PAMGIA).
#
# Receita de planos/03-wfs-e-servicos-geo.md §ArcGIS REST. Duas armadilhas que
# não existem no WFS:
#   1. erro vem como HTTP 200 com `{"error": {...}}` no corpo — checar sempre;
#   2. `exceededTransferLimit: true` significa resposta truncada pelo servidor,
#      não "acabou" — vira `parcial`, igual ao fallback 1.0.0 do WFS.

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode

from mapasfacil_nucleo.camadas import http
from mapasfacil_nucleo.erros import ErroNucleo

BBox = tuple[float, float, float, float]

CONTAGEM_PADRAO = 500


def montar_url_query(
    endpoint: str,
    bbox: BBox,
    epsg: int,
    *,
    limite: int = CONTAGEM_PADRAO,
) -> str:
    xmin, ymin, xmax, ymax = bbox
    geometria = {
        "xmin": xmin,
        "ymin": ymin,
        "xmax": xmax,
        "ymax": ymax,
        "spatialReference": {"wkid": epsg},
    }
    params = {
        "f": "geojson",
        "where": "1=1",
        "outFields": "*",
        "returnGeometry": "true",
        "geometry": json.dumps(geometria, separators=(",", ":")),
        "geometryType": "esriGeometryEnvelope",
        "inSR": str(epsg),
        "outSR": str(epsg),
        "spatialRel": "esriSpatialRelIntersects",
        "resultRecordCount": str(limite),
    }
    separador = "&" if "?" in endpoint else "?"
    return f"{endpoint}{separador}{urlencode(params)}"


def _parsear(resposta: http.RespostaHttp, url: str) -> dict[str, Any]:
    if resposta.status != 200:
        raise ErroNucleo(
            "NU-110",
            f"Serviço ArcGIS REST devolveu HTTP {resposta.status}.",
            {"url": http.redigir_url(url)},
        )
    try:
        dados = json.loads(resposta.texto())
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ErroNucleo(
            "NU-110",
            "Resposta do ArcGIS REST não é JSON válido.",
            {"url": http.redigir_url(url)},
        ) from exc
    if not isinstance(dados, dict):
        raise ErroNucleo(
            "NU-110",
            "Resposta do ArcGIS REST em formato inesperado.",
            {"url": http.redigir_url(url)},
        )
    # HTTP 200 com erro no corpo — o caso que mais engana quem só olha o status.
    erro = dados.get("error")
    if isinstance(erro, dict):
        mensagem = str(erro.get("message") or "erro sem mensagem")
        raise ErroNucleo(
            "NU-110",
            f"ArcGIS REST recusou a consulta: {mensagem}",
            {"url": http.redigir_url(url), "codigo_servico": erro.get("code")},
        )
    if "features" not in dados:
        raise ErroNucleo(
            "NU-110",
            "Resposta do ArcGIS REST sem campo 'features'.",
            {"url": http.redigir_url(url)},
        )
    return dados


def buscar_feicoes(
    endpoint: str,
    bbox: BBox,
    epsg: int,
    *,
    timeout: int = http.TIMEOUT_PADRAO_S,
    limite: int = CONTAGEM_PADRAO,
) -> dict[str, Any]:
    """Query GeoJSON por envelope. Mesmo contrato de retorno de `wfs.buscar_feicoes`."""
    url = montar_url_query(endpoint, bbox, epsg, limite=limite)
    resposta = http.buscar(url, timeout=timeout)
    dados = _parsear(resposta, url)
    features = dados.get("features") or []
    return {
        "features": features,
        # `exceededTransferLimit` = o servidor cortou; não é o fim natural da lista.
        "parcial": bool(dados.get("exceededTransferLimit")),
        "total_disponivel": len(features),
        "versao_usada": "arcgis_rest",
    }
