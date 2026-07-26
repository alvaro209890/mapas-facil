# Cliente WMS GetMap (`tipo: wms_raster` do catálogo — mosaicos SEMA, SISCOM,
# PRODES raster).
#
# Contrato diferente dos clientes vetoriais: devolve **imagem**, não feição. Não
# dá para calcular área nem contar feições a partir daqui — é pano de fundo. O
# `resolver` materializa PNG em vez de shapefile e marca `tipo_saida="raster"`.
#
# Gotcha 4 de planos/03-wfs-e-servicos-geo.md: HTTP 200 mente. GeoServer devolve
# XML de erro com status 200 e `Content-Type` às vezes até `image/png`. Só os
# magic bytes decidem.

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from mapasfacil_nucleo.camadas import http
from mapasfacil_nucleo.erros import ErroNucleo

BBox = tuple[float, float, float, float]

LARGURA_PADRAO = 1200
ALTURA_MAXIMA = 4000
ALTURA_MINIMA = 64

MAGIC_PNG = b"\x89PNG\r\n\x1a\n"
MAGIC_JPEG = b"\xff\xd8\xff"


def altura_proporcional(bbox: BBox, largura: int = LARGURA_PADRAO) -> int:
    """Altura que mantém a proporção do bbox — evita mosaico esticado no layout."""
    xmin, ymin, xmax, ymax = bbox
    largura_geo = xmax - xmin
    altura_geo = ymax - ymin
    if largura_geo <= 0 or altura_geo <= 0:
        return largura
    bruta = int(round(largura * (altura_geo / largura_geo)))
    return max(ALTURA_MINIMA, min(ALTURA_MAXIMA, bruta))


def montar_url_getmap(
    endpoint: str,
    layer: str,
    bbox: BBox,
    crs: str,
    *,
    authkey: str | None = None,
    largura: int = LARGURA_PADRAO,
    altura: int | None = None,
    formato: str = "image/png",
) -> str:
    xmin, ymin, xmax, ymax = bbox
    params: dict[str, str] = {
        "service": "WMS",
        "version": "1.1.1",
        "request": "GetMap",
        "layers": layer,
        "styles": "",
        "bbox": f"{xmin},{ymin},{xmax},{ymax}",
        "srs": crs,  # 1.1.1 usa `srs`; 1.3.0 usaria `crs` com eixos trocados
        "width": str(largura),
        "height": str(altura if altura is not None else altura_proporcional(bbox, largura)),
        "format": formato,
        "transparent": "true",
    }
    if authkey:
        params["authkey"] = authkey
    separador = "&" if "?" in endpoint else "?"
    return f"{endpoint}{separador}{urlencode(params)}"


def eh_imagem(corpo: bytes) -> bool:
    return corpo.startswith(MAGIC_PNG) or corpo.startswith(MAGIC_JPEG)


def extensao_da_imagem(corpo: bytes) -> str:
    return ".png" if corpo.startswith(MAGIC_PNG) else ".jpg"


def buscar_mapa(
    endpoint: str,
    layer: str,
    bbox: BBox,
    crs: str,
    *,
    authkey: str | None = None,
    timeout: int = http.TIMEOUT_PADRAO_S,
    largura: int = LARGURA_PADRAO,
) -> dict[str, Any]:
    """GetMap validado por magic bytes. `NU-110` quando o corpo não é imagem."""
    altura = altura_proporcional(bbox, largura)
    url = montar_url_getmap(
        endpoint, layer, bbox, crs, authkey=authkey, largura=largura, altura=altura
    )
    resposta = http.buscar(url, timeout=timeout)
    if resposta.status != 200:
        raise ErroNucleo(
            "NU-110",
            f"Serviço WMS devolveu HTTP {resposta.status}.",
            {"url": http.redigir_url(url)},
        )
    if not eh_imagem(resposta.corpo):
        # Quase sempre é ServiceExceptionReport em XML com status 200.
        trecho = resposta.texto()[:200].replace("\n", " ")
        raise ErroNucleo(
            "NU-110",
            f"WMS devolveu conteúdo que não é imagem (provável XML de erro): {trecho}",
            {"url": http.redigir_url(url), "content_type": resposta.content_type},
        )
    return {
        "imagem": resposta.corpo,
        "extensao": extensao_da_imagem(resposta.corpo),
        "largura_px": largura,
        "altura_px": altura,
        "bbox": list(bbox),
        "crs": crs,
    }
