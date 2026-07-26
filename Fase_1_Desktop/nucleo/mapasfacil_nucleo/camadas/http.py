# A13 — cliente HTTP para camadas externas (F1-03 §Cliente HTTP,
# planos/03-wfs-e-servicos-geo.md §Cliente HTTP).
#
# Regras vindas de incidentes reais do GeoForest: User-Agent de navegador (WAF
# governamental bloqueia "bot"), timeout generoso, retry com backoff, e —
# crítico — nenhum valor de segredo (`authkey`, `api_key`, `token`) sobrevive a
# um log ou mensagem de erro (AP-03). `redigir_url` roda antes de qualquer
# `ErroNucleo`/log tocar a URL.

from __future__ import annotations

import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from mapasfacil_nucleo.erros import ErroNucleo

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) MapasFacil/1.0"
)

TIMEOUT_PADRAO_S = 60
TIMEOUT_INCRA_S = 120

_PARAMS_SEGREDO = frozenset({"authkey", "api_key", "apikey", "token", "access_token"})


@dataclass(frozen=True, slots=True)
class RespostaHttp:
    status: int
    corpo: bytes
    content_type: str

    def texto(self, *, errors: str = "replace") -> str:
        return self.corpo.decode("utf-8", errors=errors)


Transporte = Callable[[str, int], RespostaHttp]

_transporte: Transporte | None = None


def configurar_transporte(fn: Transporte | None) -> None:
    """Injeta transporte fake (testes). `None` volta ao `urllib` real."""
    global _transporte
    _transporte = fn


def redigir_url(url: str) -> str:
    """Mascara `authkey`/`api_key`/`token` da query string — nunca loga o valor."""
    try:
        partes = urlsplit(url)
    except ValueError:
        return "***url-invalida***"
    pares = parse_qsl(partes.query, keep_blank_values=True)
    mascarados = [
        (chave, "***" if chave.lower() in _PARAMS_SEGREDO else valor) for chave, valor in pares
    ]
    return urlunsplit(partes._replace(query=urlencode(mascarados)))


def _transporte_padrao(url: str, timeout: int) -> RespostaHttp:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json, text/xml, */*"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — endpoints do catálogo
            corpo = resp.read()
            return RespostaHttp(
                status=resp.status,
                corpo=corpo,
                content_type=resp.headers.get("Content-Type", ""),
            )
    except urllib.error.HTTPError as exc:
        corpo = exc.read() if exc.fp else b""
        content_type = exc.headers.get("Content-Type", "") if exc.headers else ""
        return RespostaHttp(status=exc.code, corpo=corpo, content_type=content_type)
    except (socket.timeout, TimeoutError) as exc:
        raise ErroNucleo(
            "NU-101",
            f"Timeout ao consultar {redigir_url(url)}.",
        ) from exc
    except urllib.error.URLError as exc:
        motivo = exc.reason
        if isinstance(motivo, (socket.timeout, TimeoutError)):
            raise ErroNucleo("NU-101", f"Timeout ao consultar {redigir_url(url)}.") from exc
        raise ErroNucleo(
            "NU-101",
            f"Falha de rede ao consultar {redigir_url(url)}: {motivo}",
        ) from exc


def _transporte_ativo() -> Transporte:
    return _transporte or _transporte_padrao


def buscar(
    url: str,
    *,
    timeout: int = TIMEOUT_PADRAO_S,
    tentativas: int = 2,
    dormir: Callable[[float], None] = time.sleep,
) -> RespostaHttp:
    """GET com retry (2× por padrão) e backoff curto. NU-101 em timeout/rede."""
    ultimo: ErroNucleo | None = None
    for indice in range(tentativas + 1):
        try:
            return _transporte_ativo()(url, timeout)
        except ErroNucleo as exc:
            ultimo = exc
            if indice < tentativas:
                dormir(0.05 * (indice + 1))
                continue
    assert ultimo is not None  # loop sempre roda ao menos uma vez
    raise ultimo
