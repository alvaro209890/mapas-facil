# A13 — cliente WFS GetFeature (F1-03 §camadas/wfs.py, planos/03-wfs-e-servicos-geo.md).
#
# Cobre o tipo `wms_wfs` do catálogo (33/41 camadas — SEMA, FUNAI, MapBiomas, PRODES
# WFS). Regras vindas de incidentes reais:
#   - GetFeature JSON 2.0.0 primeiro; servidor antigo (FUNAI) cai para 1.0.0.
#   - `authkey` na query, nunca em header — e nunca no log (redigir_url).
#   - Resposta HTTP 200 pode ser XML de erro do GeoServer: valida antes de `json.loads`.

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode

from mapasfacil_nucleo.camadas import http
from mapasfacil_nucleo.erros import ErroNucleo

BBox = tuple[float, float, float, float]

CONTAGEM_PADRAO = 2000
CONTAGEM_MAXIMA = 2000  # teto do Mapas Fácil (mapa) — GeoForest usa até 50k, escala diferente


def montar_url_getfeature(
    endpoint: str,
    layer: str,
    bbox: BBox,
    crs: str,
    *,
    authkey: str | None = None,
    count: int = CONTAGEM_PADRAO,
    version: str = "2.0.0",
) -> str:
    xmin, ymin, xmax, ymax = bbox
    params: dict[str, str] = {
        "service": "WFS",
        "version": version,
        "request": "GetFeature",
        "outputFormat": "application/json",
        "srsName": crs,
        "bbox": f"{xmin},{ymin},{xmax},{ymax},{crs}",
    }
    if version.startswith("2."):
        params["typeNames"] = layer
        params["count"] = str(count)
    else:
        params["typeName"] = layer
        params["maxFeatures"] = str(count)
    if authkey:
        params["authkey"] = authkey
    separador = "&" if "?" in endpoint else "?"
    return f"{endpoint}{separador}{urlencode(params)}"


def _parece_json(resposta: http.RespostaHttp) -> bool:
    if "json" in (resposta.content_type or "").lower():
        return True
    corpo = resposta.corpo.lstrip()
    return corpo.startswith(b"{") or corpo.startswith(b"[")


def _tentar_parsear(resposta: http.RespostaHttp, url: str) -> dict[str, Any]:
    if resposta.status != 200 or not _parece_json(resposta):
        raise ErroNucleo(
            "NU-110",
            f"Serviço WFS devolveu resposta inesperada (HTTP {resposta.status}, "
            f"content-type '{resposta.content_type}').",
            {"url": http.redigir_url(url)},
        )
    try:
        dados = json.loads(resposta.texto())
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ErroNucleo(
            "NU-110",
            "Resposta do WFS não é JSON válido — provável XML de erro do GeoServer.",
            {"url": http.redigir_url(url)},
        ) from exc
    if not isinstance(dados, dict) or "features" not in dados:
        raise ErroNucleo(
            "NU-110",
            "Resposta do WFS sem campo 'features'.",
            {"url": http.redigir_url(url)},
        )
    return dados


def buscar_feicoes(
    endpoint: str,
    layer: str,
    bbox: BBox,
    crs: str,
    *,
    authkey: str | None = None,
    timeout: int = http.TIMEOUT_PADRAO_S,
    limite: int = CONTAGEM_MAXIMA,
) -> dict[str, Any]:
    """GetFeature 2.0.0; cai para 1.0.0 se o servidor não falar 2.0 (FUNAI etc.).

    Devolve `{"features": [...], "parcial": bool, "total_disponivel": int|None,
    "versao_usada": str}`. NU-101 (timeout/rede) e NU-110 (resposta inesperada)
    propagam como `ErroNucleo` — quem chama decide se é fatal.
    """
    url_v2 = montar_url_getfeature(endpoint, layer, bbox, crs, authkey=authkey, count=limite)
    # Timeout/rede (NU-101) propaga direto — repetir noutra versão no mesmo
    # endpoint não resolveria um servidor fora do ar. Só resposta estruturalmente
    # ruim (NU-110: XML de erro, servidor sem suporte a 2.0.0) cai para 1.0.0.
    resposta = http.buscar(url_v2, timeout=timeout)
    try:
        dados = _tentar_parsear(resposta, url_v2)
        versao_usada = "2.0.0"
        parcial = False
    except ErroNucleo:
        url_v1 = montar_url_getfeature(
            endpoint, layer, bbox, crs, authkey=authkey, count=limite, version="1.0.0"
        )
        resposta_v1 = http.buscar(url_v1, timeout=timeout)
        dados = _tentar_parsear(resposta_v1, url_v1)
        versao_usada = "1.0.0"
        parcial = True  # fallback — sinaliza que o caminho principal falhou

    features = dados.get("features") or []
    total_disponivel = dados.get("totalFeatures") or dados.get("numberMatched")
    return {
        "features": features,
        "parcial": parcial,
        "total_disponivel": total_disponivel if isinstance(total_disponivel, int) else None,
        "versao_usada": versao_usada,
    }
