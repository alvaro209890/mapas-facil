# F1-17 §Esquema — `workspace_fingerprint`: sha256 do realpath normalizado minúsculo.
#
# É o que amarra a conversa à pasta sem guardar o caminho no que vai para a UI de
# outras pastas, e o que faz `DELETE ... WHERE workspace_fingerprint = ?` apagar o
# histórico de um projeto inteiro. Minúsculo porque no Windows `C:\Obra` e
# `c:\obra` são a mesma pasta e o usuário digita das duas formas.

from __future__ import annotations

import hashlib
from pathlib import Path

SEM_WORKSPACE = "sem-workspace"


def normalizar(caminho: str | Path) -> str:
    """Realpath (quando o caminho existe) normalizado, sem barra final, minúsculo."""
    bruto = Path(caminho).expanduser()
    try:
        resolvido = bruto.resolve()
    except OSError:
        resolvido = bruto
    return str(resolvido).replace("\\", "/").rstrip("/").lower()


def calcular(caminho: str | Path | None) -> str:
    """Fingerprint da pasta. Sem pasta, devolve `sem-workspace` — não um hash de vazio."""
    if caminho is None or str(caminho).strip() == "":
        return SEM_WORKSPACE
    return hashlib.sha256(normalizar(caminho).encode("utf-8")).hexdigest()


def nome_da_pasta(caminho: str | Path | None) -> str | None:
    """Só o nome da pasta, que é o único pedaço do caminho que a sidebar mostra."""
    if caminho is None or str(caminho).strip() == "":
        return None
    return Path(caminho).expanduser().name or None
