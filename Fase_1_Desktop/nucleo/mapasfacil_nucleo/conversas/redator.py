# Redator de CPF e segredos — aplicado ANTES do INSERT (F1-17 / AP-09).
# Compartilhável com log e, depois, com o montador de contexto do M7.

from __future__ import annotations

import re

_CPF = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
_API_KEY = re.compile(r"(?i)(api[_-]?key\s*=\s*)([^\s&\"']+)")
_AUTHKEY = re.compile(r"(?i)(authkey\s*=\s*)([^\s&\"']+)")
_BEARER = re.compile(r"(?i)(Bearer\s+)([A-Za-z0-9\-._~+/]+=*)")
_PLAK = re.compile(r"\bPLAK[A-Za-z0-9]{32}\b")
_DEEPSEEK_SK = re.compile(r"\bsk-[a-f0-9]{32}\b", re.IGNORECASE)
_WKT = re.compile(
    r"\b(?:MULTI)?(?:POLYGON|LINESTRING|POINT|GEOMETRYCOLLECTION)\s*\([^)]*(?:\([^)]*\)[^)]*)*\)",
    re.IGNORECASE,
)
_CAMINHO_USERS = re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+[^\s\"']+", re.IGNORECASE)


def redigir(texto: str) -> str:
    """Remove CPF, chaves, WKT e caminhos absolutos. Idempotente."""
    if not texto:
        return texto
    saida = _CPF.sub("[CPF removido]", texto)
    saida = _WKT.sub("[geometria removida]", saida)
    saida = _CAMINHO_USERS.sub("[caminho removido]", saida)
    saida = _API_KEY.sub("[segredo removido]", saida)
    saida = _AUTHKEY.sub("[segredo removido]", saida)
    saida = _BEARER.sub("[segredo removido]", saida)
    saida = _PLAK.sub("[chave planet removida]", saida)
    saida = _DEEPSEEK_SK.sub("[chave deepseek removida]", saida)
    return saida


def truncar(texto: str, limite: int) -> str:
    if limite <= 0:
        return ""
    if len(texto) <= limite:
        return texto
    if limite <= 1:
        return "…"
    return texto[: limite - 1] + "…"
