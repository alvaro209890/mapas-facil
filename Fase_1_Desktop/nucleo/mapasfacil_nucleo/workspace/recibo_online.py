"""Recibo do CAR buscado na SEMA-MT quando o pacote do usuário não traz o PDF.

Dois passos, nenhum deles com login (não toca na conta do escritório nem derruba a sessão
única do SIMCAR):

1. **Qual é o CAR?** Se o número não veio do usuário, pergunta ao GeoServer da SEMA qual
   requerimento contém um ponto interno do perímetro (ATP). Camadas `SIMCAR:SIMCAR_SIMCAR_
   ANALISADO` e `..._EM_ANALISE` (campos `NUMERO`, `CODIGO_CAR`, `AREA_HA`) — exigem a
   `sema_authkey` do cofre. Havendo mais de um, fica o de área mais parecida com a do ATP.
2. **Recibo:** consulta pública do SIMCAR — `Publico/ListarRequerimento` com o filtro
   `NUMERO` dá o `Id`; `Publico/DownloadReciboCar/<Id>` devolve o PDF.

Armadilhas medidas em 04/11/2026 (mesmas do CLI `imap` do escritório):
  * o WFS com `srsName=EPSG:4674` + CQL aceita o ponto em **lon lat**;
  * a consulta pública **derruba a conexão** com chave de filtro desconhecida — só `NUMERO`;
  * `DownloadReciboCar` sem corpo responde 411: manda `{}`;
  * CAR "em cadastramento" não tem recibo: devolve `None`, não é erro.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

from mapasfacil_nucleo.erros import ErroNucleo

GEOSERVER_OWS = "https://geo.sema.mt.gov.br/geoserver/ows"
SIMCAR_API = "https://monitoramento.sema.mt.gov.br/simcar/tecnico.api/api"
CAMADAS_CAR = ("SIMCAR:SIMCAR_SIMCAR_ANALISADO", "SIMCAR:SIMCAR_SIMCAR_EM_ANALISE")
_USER_AGENT = "MapasFacil/recibo-car"
_RE_CAR = re.compile(r"^\s*MT\s*[-]?\s*(\d{1,9})\s*[/-]\s*(\d{4})\s*$", re.I)

#: Transporte trocável nos testes: (url, corpo|None, cabeçalhos, timeout) -> bytes.
Transporte = Callable[[str, bytes | None, dict[str, str], float], bytes]


def _http(url: str, corpo: bytes | None, cabecalhos: dict[str, str], timeout: float) -> bytes:
    req = urllib.request.Request(url, data=corpo, headers={"User-Agent": _USER_AGENT, **cabecalhos})
    with urllib.request.urlopen(req, timeout=timeout) as resposta:  # noqa: S310 - URLs fixas
        return resposta.read()


_transporte: Transporte = _http


def configurar_transporte(transporte: Transporte | None) -> None:
    """Testes injetam um transporte falso; `None` volta ao HTTP real."""
    global _transporte
    _transporte = transporte or _http


def normalizar_car(numero: str) -> str | None:
    """`mt 96184-2020` → `MT96184/2020`; `None` se não parece número de CAR estadual."""
    achado = _RE_CAR.match(str(numero or ""))
    if not achado:
        return None
    return f"MT{int(achado.group(1))}/{achado.group(2)}"


def identificar_car(
    lon: float,
    lat: float,
    *,
    authkey: str,
    area_ha: float | None = None,
) -> dict[str, Any] | None:
    """CAR que contém o ponto (graus SIRGAS 2000). `None` se a SEMA não tem nada ali."""
    candidatos: list[dict[str, Any]] = []
    falhas: list[str] = []
    for camada in CAMADAS_CAR:
        parametros = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": camada,
            "outputFormat": "application/json",
            "srsName": "EPSG:4674",
            "count": "5",
            "propertyName": "NUMERO,CODIGO_CAR,AREA_HA",
            "CQL_FILTER": f"INTERSECTS(GEOMETRY,POINT({lon:.7f} {lat:.7f}))",
            "authkey": authkey,
        }
        url = f"{GEOSERVER_OWS}?{urllib.parse.urlencode(parametros)}"
        try:
            dados = json.loads(_transporte(url, None, {"Accept": "application/json"}, 90.0) or b"{}")
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            falhas.append(f"{camada}: {exc}")
            continue
        for feicao in dados.get("features") or []:
            props = feicao.get("properties") or {}
            numero = normalizar_car(str(props.get("NUMERO") or ""))
            if numero:
                candidatos.append(
                    {
                        "car": numero,
                        "codigo_car": props.get("CODIGO_CAR"),
                        "area_ha": props.get("AREA_HA"),
                        "camada": camada,
                    }
                )
        if candidatos:
            break  # o analisado manda; o "em análise" só entra se não houver nada
    if not candidatos:
        if falhas and len(falhas) == len(CAMADAS_CAR):
            raise ErroNucleo(
                "NU-101",
                "O GeoServer da SEMA não respondeu à consulta do CAR.",
                {"falhas": falhas[:2]},
            )
        return None
    if area_ha:
        candidatos.sort(key=lambda c: abs(float(c.get("area_ha") or 0.0) - float(area_ha)))
    escolhido = dict(candidatos[0])
    escolhido["candidatos"] = len(candidatos)
    return escolhido


def baixar_recibo(numero: str) -> bytes | None:
    """PDF do Recibo de Inscrição pela consulta pública do SIMCAR (sem login)."""
    car = normalizar_car(numero)
    if car is None:
        raise ErroNucleo("NU-001", f"Número de CAR inválido: {numero!r} (esperado MT00000/0000).")
    corpo = json.dumps(
        {
            "ItensPorPagina": 10,
            "Pagina": 1,
            "IsOrdenarCrescente": False,
            "ColunaOrdenar": "Id",
            "Colunas": [],
            "Filtros": {"NUMERO": car},
        }
    ).encode()
    try:
        bruto = _transporte(
            f"{SIMCAR_API}/Publico/ListarRequerimento",
            corpo,
            {"Content-Type": "application/json", "Accept": "application/json"},
            90.0,
        )
        itens = json.loads(bruto or b"{}").get("Itens") or []
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        raise ErroNucleo("NU-101", "A consulta pública do SIMCAR não respondeu.", {"erro": str(exc)}) from exc
    requerimento = next((i for i in itens if normalizar_car(i.get("NumeroCompleto", "")) == car), None)
    requerimento = requerimento or (itens[0] if itens else None)
    if not requerimento or not requerimento.get("Id"):
        return None
    url = f"{SIMCAR_API}/Publico/DownloadReciboCar/{int(requerimento['Id'])}"
    for corpo_pdf, cabecalhos in (
        (b"{}", {"Content-Type": "application/json", "Accept": "application/pdf,*/*"}),
        (b"", {"Accept": "application/pdf,*/*"}),
    ):
        try:
            dados = _transporte(url, corpo_pdf, cabecalhos, 180.0)
        except (urllib.error.URLError, TimeoutError, OSError):
            continue
        if dados[:5] == b"%PDF-":
            return dados
    return None
