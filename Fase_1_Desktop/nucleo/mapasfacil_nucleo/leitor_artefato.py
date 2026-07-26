"""`artefato.ler` — o renderer lê arquivo da pasta **pelo núcleo** (F1-01, fronteira 1).

O `painel-preview` (A5 fase 2) precisa dos bytes das rasterizações que
`job.artefato_parcial` anuncia. Em vez de dar acesso a disco ao renderer, o
núcleo devolve o conteúdo em base64, com três limites:

* caminho passa pelo `fsguard` — fora do workspace não existe;
* só formato de imagem previsto no contrato (`.png`, `.jpg`);
* teto de tamanho: preview é imagem leve; arquivo grande é sintoma de erro.
"""

from __future__ import annotations

import base64
from typing import Any, Final

from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.workspace import servico as workspace_servico

MIME_POR_SUFIXO: Final[dict[str, str]] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}

TAMANHO_MAX_BYTES: Final = 8 * 1024 * 1024


def ler(params: dict[str, Any]) -> dict[str, Any]:
    caminho = params.get("caminho")
    if not isinstance(caminho, str) or not caminho:
        raise ErroNucleo("NU-001", "Parâmetro 'caminho' é obrigatório.")
    estado = workspace_servico.estado_atual()
    if estado is None:
        raise ErroNucleo("NU-040", "Nenhuma pasta conectada. Use workspace.abrir primeiro.")

    alvo = estado.guard.resolver(caminho)
    sufixo = alvo.suffix.lower()
    mime = MIME_POR_SUFIXO.get(sufixo)
    if mime is None:
        raise ErroNucleo(
            "NU-043",
            f"Formato não permitido em artefato.ler: {sufixo or '(sem extensão)'}. "
            f"Permitidos: {', '.join(sorted(MIME_POR_SUFIXO))}.",
        )
    if not alvo.is_file():
        raise ErroNucleo("NU-041", f"Artefato não encontrado: {caminho}")

    tamanho = alvo.stat().st_size
    if tamanho > TAMANHO_MAX_BYTES:
        raise ErroNucleo(
            "NU-044",
            f"Artefato grande demais para o preview ({tamanho} bytes; "
            f"teto {TAMANHO_MAX_BYTES}).",
        )

    dados = base64.b64encode(alvo.read_bytes()).decode("ascii")
    return {
        "caminho": str(alvo.relative_to(estado.guard.raiz)).replace("\\", "/"),
        "mime": mime,
        "tamanho": tamanho,
        "base64": dados,
    }
