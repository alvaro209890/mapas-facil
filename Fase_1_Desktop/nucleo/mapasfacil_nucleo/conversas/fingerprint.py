# Fingerprint estável de workspace para filtrar chats (F1-17 / D13).

from __future__ import annotations

import hashlib
from pathlib import Path


def fingerprint_workspace(caminho: str | Path) -> str:
    """sha256 do realpath normalizado em minúsculas.

    O caminho absoluto NUNCA vai para o LLM; só este hash e o nome da pasta.
    """
    caminho_p = Path(caminho).expanduser()
    try:
        resolvido = caminho_p.resolve(strict=False)
    except OSError:
        resolvido = caminho_p.absolute()
    # as_posix + lower: mesmo fingerprint se o usuário misturar barras no Windows
    normalizado = resolvido.as_posix().casefold()
    return hashlib.sha256(normalizado.encode("utf-8")).hexdigest()


def nome_workspace(caminho: str | Path | None) -> str | None:
    if caminho is None:
        return None
    nome = Path(caminho).expanduser().name
    return nome or None
