"""Redação de dados sensíveis em log (W3-24).

Vale para qualquer log do servidor: stderr de worker, uvicorn, esteira de importação.
CPF, chave de API e `authkey` nunca chegam ao arquivo.
"""

from __future__ import annotations

import logging
import re

_RE_CPF = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
_RE_CHAVE = re.compile(r"\b(sk|csk|pl)-[A-Za-z0-9_\-]{8,}")
_RE_AUTHKEY = re.compile(r"(authkey=)[^&\s\"']+")
_RE_BEARER = re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]{8,}")
_RE_EMAIL = re.compile(r"\b([A-Za-z0-9._%+\-])[A-Za-z0-9._%+\-]*(@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})\b")


def redigir(texto: str, *, email: bool = False) -> str:
    """Mascara CPF e chaves. `email=True` mascara também o miolo do endereço."""
    texto = _RE_CPF.sub("***.***.***-**", texto)
    texto = _RE_CHAVE.sub(lambda m: f"{m.group(1)}-***", texto)
    texto = _RE_AUTHKEY.sub(r"\1***", texto)
    texto = _RE_BEARER.sub(r"\1***", texto)
    if email:
        texto = _RE_EMAIL.sub(lambda m: f"{m.group(1)}***{m.group(2)}", texto)
    return texto


class FiltroRedacao(logging.Filter):
    """Filtro de logging: aplica `redigir` na mensagem final."""

    def __init__(self, *, email: bool = False) -> None:
        super().__init__()
        self._email = email

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            original = record.getMessage()
        except Exception:  # pragma: no cover - formatação quebrada não derruba log
            return True
        limpo = redigir(original, email=self._email)
        if limpo != original:
            record.msg = limpo
            record.args = ()
        return True


def configurar(nivel: int = logging.INFO) -> None:
    """Liga a redação no logger raiz (chamado no boot do servidor)."""
    raiz = logging.getLogger()
    if not any(isinstance(f, FiltroRedacao) for f in raiz.filters):
        raiz.addFilter(FiltroRedacao())
    raiz.setLevel(nivel)
