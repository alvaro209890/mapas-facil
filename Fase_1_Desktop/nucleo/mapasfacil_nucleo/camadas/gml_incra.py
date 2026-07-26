# Cliente WFS 1.0 + parser GML (`tipo: wfs_gml` do catálogo — acervo INCRA).
#
# O i3geo do INCRA não fala GeoJSON: só GML. Parser próprio, deliberadamente
# pequeno — cobre o que o acervo devolve (`featureMember`/`member` com
# `coordinates` ou `posList`), não o GML inteiro. O que não casar vira feição
# ignorada com aviso, nunca geometria inventada.
#
# Coordenadas do INCRA vêm em **EPSG:4326 lon/lat** (campo `epsg` do catálogo);
# quem reprojeta é o resolver, que sabe o CRS pedido.

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlencode
from xml.etree import ElementTree

from mapasfacil_nucleo.camadas import http
from mapasfacil_nucleo.erros import ErroNucleo

BBox = tuple[float, float, float, float]

CONTAGEM_PADRAO = 500
TIMEOUT_INCRA_S = http.TIMEOUT_INCRA_S  # 120 s — o acervo é notoriamente lento

_TAG_MEMBRO = re.compile(r"\}(featureMember|member)$")
_TAG_POLIGONO = re.compile(r"\}(Polygon|MultiPolygon|Surface|MultiSurface)$")
_TAG_ANEL_EXTERNO = re.compile(r"\}(outerBoundaryIs|exterior)$")
_TAG_COORDS = re.compile(r"\}(coordinates|posList)$")


def montar_url_getfeature(
    endpoint: str,
    layer: str,
    bbox: BBox,
    *,
    limite: int = CONTAGEM_PADRAO,
) -> str:
    xmin, ymin, xmax, ymax = bbox
    params = {
        "service": "WFS",
        "version": "1.0.0",
        "request": "GetFeature",
        "typeName": layer,
        "bbox": f"{xmin},{ymin},{xmax},{ymax}",
        "maxFeatures": str(limite),
    }
    separador = "&" if "?" in endpoint else "?"
    return f"{endpoint}{separador}{urlencode(params)}"


def _pares_de_coordenadas(texto: str, *, e_poslist: bool) -> list[tuple[float, float]]:
    """`coordinates` = `x,y x,y`; `posList` = `x y x y` (par a par)."""
    bruto = texto.strip()
    if not bruto:
        return []
    if e_poslist:
        numeros = [float(n) for n in bruto.split()]
        return [(numeros[i], numeros[i + 1]) for i in range(0, len(numeros) - 1, 2)]
    pares: list[tuple[float, float]] = []
    for token in bruto.replace("\n", " ").split():
        partes = token.split(",")
        if len(partes) >= 2:
            pares.append((float(partes[0]), float(partes[1])))
    return pares


def _fechar_anel(pontos: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Anel GeoJSON tem de fechar — gotcha 11 de planos/03."""
    if len(pontos) >= 3 and pontos[0] != pontos[-1]:
        return [*pontos, pontos[0]]
    return pontos


def _aneis_do_poligono(elemento: ElementTree.Element) -> list[list[tuple[float, float]]]:
    aneis: list[list[tuple[float, float]]] = []
    externos: list[list[tuple[float, float]]] = []
    for filho in elemento.iter():
        if not _TAG_COORDS.search(filho.tag):
            continue
        e_poslist = filho.tag.endswith("posList")
        try:
            pontos = _fechar_anel(_pares_de_coordenadas(filho.text or "", e_poslist=e_poslist))
        except ValueError:
            continue  # coordenada não numérica — feição ignorada, não inventada
        if len(pontos) < 4:
            continue
        aneis.append(pontos)
    # O primeiro anel encontrado dentro de outerBoundaryIs/exterior é o externo;
    # sem essa marcação, assume o primeiro (comportamento do acervo INCRA).
    for filho in elemento.iter():
        if _TAG_ANEL_EXTERNO.search(filho.tag):
            for neto in filho.iter():
                if _TAG_COORDS.search(neto.tag):
                    e_poslist = neto.tag.endswith("posList")
                    try:
                        pontos = _fechar_anel(
                            _pares_de_coordenadas(neto.text or "", e_poslist=e_poslist)
                        )
                    except ValueError:
                        continue
                    if len(pontos) >= 4:
                        externos.append(pontos)
                    break
            break
    if externos:
        resto = [a for a in aneis if a != externos[0]]
        return [externos[0], *resto]
    return aneis


def parsear_gml(xml: str) -> tuple[list[dict[str, Any]], list[str]]:
    """GML → features GeoJSON-like. Devolve `(features, avisos)`."""
    try:
        raiz = ElementTree.fromstring(xml)
    except ElementTree.ParseError as exc:
        raise ErroNucleo("NU-110", f"GML inválido do serviço: {exc}") from exc

    # ServiceExceptionReport: erro do servidor disfarçado de 200.
    if "ServiceException" in raiz.tag or raiz.find(".//{*}ServiceException") is not None:
        texto = "".join(raiz.itertext()).strip()[:200]
        raise ErroNucleo("NU-110", f"Serviço GML recusou a consulta: {texto}")

    features: list[dict[str, Any]] = []
    avisos: list[str] = []
    for membro in raiz.iter():
        if not _TAG_MEMBRO.search(membro.tag):
            continue
        poligonos: list[list[list[tuple[float, float]]]] = []
        for elemento in membro.iter():
            if _TAG_POLIGONO.search(elemento.tag):
                aneis = _aneis_do_poligono(elemento)
                if aneis:
                    poligonos.append(aneis)
        if not poligonos:
            avisos.append("feição GML sem polígono reconhecível — ignorada")
            continue
        propriedades: dict[str, Any] = {}
        for elemento in membro.iter():
            if elemento.text and elemento.text.strip() and len(list(elemento)) == 0:
                nome = elemento.tag.split("}")[-1]
                if not _TAG_COORDS.search(elemento.tag):
                    propriedades[nome] = elemento.text.strip()[:120]
        if len(poligonos) == 1:
            geometria = {
                "type": "Polygon",
                "coordinates": [[list(p) for p in anel] for anel in poligonos[0]],
            }
        else:
            geometria = {
                "type": "MultiPolygon",
                "coordinates": [
                    [[list(p) for p in anel] for anel in aneis] for aneis in poligonos
                ],
            }
        features.append({"type": "Feature", "geometry": geometria, "properties": propriedades})
    return features, avisos


def buscar_feicoes(
    endpoint: str,
    layer: str,
    bbox: BBox,
    *,
    timeout: int = TIMEOUT_INCRA_S,
    limite: int = CONTAGEM_PADRAO,
) -> dict[str, Any]:
    """GetFeature GML 1.0. Mesmo contrato de retorno de `wfs.buscar_feicoes`."""
    url = montar_url_getfeature(endpoint, layer, bbox, limite=limite)
    resposta = http.buscar(url, timeout=timeout)
    if resposta.status != 200:
        raise ErroNucleo(
            "NU-110",
            f"Serviço GML devolveu HTTP {resposta.status}.",
            {"url": http.redigir_url(url)},
        )
    features, avisos = parsear_gml(resposta.texto())
    return {
        "features": features,
        "parcial": len(features) >= limite,  # bateu no teto: pode haver mais
        "total_disponivel": len(features),
        "versao_usada": "wfs_gml_1.0.0",
        "avisos_parser": avisos[:5],
    }
