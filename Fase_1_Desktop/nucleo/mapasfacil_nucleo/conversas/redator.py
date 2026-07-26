# F1-17 §Privacidade / AP-09 — redator de CPF e de chaves de API.
#
# A redação é **na entrada**, antes do INSERT: redigir só na exibição deixaria o
# CPF dentro de `chats.sqlite`, onde um backup, um `grep -a` ou o Fase 2 opt-in o
# encontrariam depois. O anti-padrão da F1-17 é explícito sobre isso.
#
# Módulo sem estado e sem I/O de propósito: o log e o montador de contexto (F1-06)
# usam o mesmo `redigir`.

from __future__ import annotations

import re

MARCA_CPF = "[CPF removido]"
MARCA_CHAVE = "[chave removida]"

# 11 dígitos com pontuação opcional, sem colar em outro dígito: `(?<!\d)` e
# `(?!\d)` evitam picar um número comprido (código de recibo, coordenada) no meio.
_CPF = re.compile(r"(?<!\d)\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)")

# `chave=valor` das formas que aparecem em `.mxd`, URL de WMS e env var.
_CHAVE_ATRIBUIDA = re.compile(
    r"\b(api[_-]?key|authkey|apikey|access[_-]?token|token|senha|password)"
    r"(\s*[=:]\s*)"
    r"(\"[^\"]*\"|'[^']*'|[^\s&\"'<>]+)",
    re.IGNORECASE,
)
_BEARER = re.compile(r"\bBearer\s+[A-Za-z0-9._\-]+", re.IGNORECASE)
# `PLAK…` é a chave da Planet nos `.mxd` do acervo (incidente 2026-07-25);
# `sk-…` é o formato da chave da DeepSeek usada pelo agente.
_CHAVE_SOLTA = re.compile(r"\b(PLAK[A-Za-z0-9]{8,}|sk-[A-Za-z0-9_\-]{16,})\b")


def _substituir(texto: str) -> tuple[str, list[str]]:
    marcas: list[str] = []

    def _cpf(_casa: re.Match[str]) -> str:
        marcas.append("cpf")
        return MARCA_CPF

    def _atribuida(casa: re.Match[str]) -> str:
        marcas.append(casa.group(1).lower())
        return f"{casa.group(1)}{casa.group(2)}{MARCA_CHAVE}"

    def _solta(_casa: re.Match[str]) -> str:
        marcas.append("chave")
        return MARCA_CHAVE

    def _bearer(_casa: re.Match[str]) -> str:
        marcas.append("bearer")
        return f"Bearer {MARCA_CHAVE}"

    saida = _CPF.sub(_cpf, texto)
    saida = _CHAVE_ATRIBUIDA.sub(_atribuida, saida)
    saida = _BEARER.sub(_bearer, saida)
    saida = _CHAVE_SOLTA.sub(_solta, saida)
    return saida, marcas


def redigir(texto: str | None) -> str | None:
    """Devolve o texto sem CPF e sem chave. `None` entra, `None` sai."""
    if texto is None:
        return None
    return _substituir(texto)[0]


def redigir_com_marcas(texto: str | None) -> tuple[str | None, list[str]]:
    """Como `redigir`, mas também diz o que foi removido — para teste e para log."""
    if texto is None:
        return None, []
    limpo, marcas = _substituir(texto)
    # ordem estável, sem repetição: serve de asserção em teste
    vistas: list[str] = []
    for marca in marcas:
        if marca not in vistas:
            vistas.append(marca)
    return limpo, vistas


def tem_segredo(texto: str | None) -> bool:
    """`True` se o redator mudaria algo — usado para barrar gravação em ponto sensível."""
    if texto is None:
        return False
    return _substituir(texto)[0] != texto
