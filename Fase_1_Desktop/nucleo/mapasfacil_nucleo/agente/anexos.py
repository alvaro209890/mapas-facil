"""Validação do payload de anexos recebido pelo renderer.

O provedor atual é somente texto: os bytes são persistidos localmente e nunca
entram no payload do LLM. Só nome, MIME e tamanho aparecem como metadados.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from typing import Any

from mapasfacil_nucleo.erros import ErroNucleo

LIMITE_ANEXO_BYTES = 20 * 1024 * 1024
MAX_ANEXOS_POR_TURNO = 5
_LIMITE_BASE64 = ((LIMITE_ANEXO_BYTES + 2) // 3) * 4 + 4


@dataclass(frozen=True)
class AnexoEntrada:
    nome: str
    mime: str
    bytes: int
    dados: bytes


def _erro(mensagem: str) -> ErroNucleo:
    return ErroNucleo("CH-004", mensagem)


def validar_anexos(valor: Any) -> list[AnexoEntrada]:
    if valor is None:
        return []
    if not isinstance(valor, list):
        raise _erro("Parâmetro 'anexos' precisa ser uma lista.")
    if len(valor) > MAX_ANEXOS_POR_TURNO:
        raise _erro(f"Cada turno aceita no máximo {MAX_ANEXOS_POR_TURNO} anexos.")

    saida: list[AnexoEntrada] = []
    for indice, bruto in enumerate(valor, start=1):
        if not isinstance(bruto, dict):
            raise _erro(f"Anexo {indice} precisa ser um objeto.")
        nome_bruto = bruto.get("nome")
        mime_bruto = bruto.get("mime")
        bytes_bruto = bruto.get("bytes")
        base64_bruto = bruto.get("base64")
        if not isinstance(nome_bruto, str) or not nome_bruto.strip():
            raise _erro(f"Anexo {indice} está sem nome.")
        # O renderer não controla o nome original: descartar qualquer prefixo
        # de diretório evita registrar caminhos locais por acidente.
        nome = nome_bruto.replace("\\", "/").rsplit("/", 1)[-1].strip()
        if not nome or len(nome) > 255:
            raise _erro(f"Nome do anexo {indice} é inválido.")
        if not isinstance(mime_bruto, str) or not mime_bruto or len(mime_bruto) > 120:
            raise _erro(f"MIME do anexo {indice} é inválido.")
        if (
            not isinstance(bytes_bruto, int)
            or isinstance(bytes_bruto, bool)
            or bytes_bruto < 0
            or bytes_bruto > LIMITE_ANEXO_BYTES
        ):
            raise _erro(f"Anexo {nome} excede o limite de 20 MB ou tem tamanho inválido.")
        if not isinstance(base64_bruto, str) or len(base64_bruto) > _LIMITE_BASE64:
            raise _erro(f"Conteúdo do anexo {nome} é inválido.")
        try:
            dados = base64.b64decode(base64_bruto, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise _erro(f"Conteúdo base64 do anexo {nome} é inválido.") from exc
        if len(dados) != bytes_bruto:
            raise _erro(f"Tamanho declarado do anexo {nome} não confere.")
        saida.append(AnexoEntrada(nome=nome, mime=mime_bruto, bytes=bytes_bruto, dados=dados))
    return saida


__all__ = (
    "AnexoEntrada",
    "LIMITE_ANEXO_BYTES",
    "MAX_ANEXOS_POR_TURNO",
    "validar_anexos",
)
